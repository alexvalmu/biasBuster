"""Worker endpoint, invoked by Cloud Tasks (or directly by the api in local dev)."""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import update

from app.agents.runner import run_analysis
from app.core.config import get_settings
from app.db import repo
from app.db.models import Paper
from app.db.session import SessionLocal
from app.services.tasks import TASK_PATH

log = logging.getLogger(__name__)
router = APIRouter(tags=["tasks"])


class RunAnalysis(BaseModel):
    analysis_id: uuid.UUID


def verify_oidc(request: Request) -> None:
    settings = get_settings()
    if not settings.tasks_verify_oidc:
        return
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        claims = id_token.verify_oauth2_token(
            auth.removeprefix("Bearer "), google_requests.Request(), audience=settings.worker_url
        )
    except ValueError as exc:
        raise HTTPException(401, "Invalid token") from exc
    if settings.tasks_service_account and claims.get("email") != settings.tasks_service_account:
        raise HTTPException(403, "Unexpected caller")


@router.post(TASK_PATH)
async def run_analysis_task(body: RunAnalysis, request: Request) -> dict:
    """Idempotent: a duplicate delivery of a done/running analysis is acknowledged and ignored.
    Returns 5xx on a retryable failure so Cloud Tasks redelivers it."""
    verify_oidc(request)
    settings = get_settings()

    analysis = await repo.claim(body.analysis_id)
    if analysis is None:
        return {"status": "skipped"}

    try:
        report, models_used, cost = await run_analysis(analysis.id, analysis.input_text or "")
    except Exception as exc:
        log.exception("analysis %s failed (attempt %s)", analysis.id, analysis.attempts)
        final = analysis.attempts >= settings.max_attempts
        await repo.add_progress(
            analysis.id,
            "$ error: analysis failed" + ("" if final else ", retrying…"),
        )
        await repo.fail(analysis.id, f"{type(exc).__name__}: {exc}", final=final)
        if final:
            return {"status": "failed"}
        raise HTTPException(500, "Analysis failed, will retry") from exc

    await repo.complete(analysis.id, report.model_dump(mode="json"), models_used, cost)
    async with SessionLocal() as session:
        await session.execute(
            update(Paper)
            .where(Paper.sha256 == analysis.paper_sha256)
            .values(
                doi=report.paper.doi,
                pmid=report.paper.pmid,
                title=report.paper.title,
                metadata_=report.paper.model_dump(mode="json"),
            )
        )
        await session.commit()
    return {"status": "done"}
