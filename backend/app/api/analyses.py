import logging

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, UploadFile
from slowapi import Limiter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Analysis, Paper
from app.db.session import get_session
from app.schemas.report import AnalysisOut
from app.services import tasks
from app.services.pdf import InvalidPdfError, extract_text, sha256_of

log = logging.getLogger(__name__)
settings = get_settings()


def client_ip(request: Request) -> str:
    # Behind Firebase Hosting / Cloud Run the real client is the first X-Forwarded-For hop.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# In-memory per instance: a soft limit, the global daily cap below is the hard guard.
limiter = Limiter(key_func=client_ip)
router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def to_out(analysis: Analysis) -> AnalysisOut:
    return AnalysisOut(
        sha256=analysis.paper_sha256,
        status=analysis.status,
        progress=analysis.progress or [],
        report=analysis.report if analysis.status == "done" else None,
        error="The analysis could not be completed." if analysis.status == "failed" else None,
    )


async def verify_captcha(token: str | None, ip: str) -> None:
    if not settings.recaptcha_secret:
        return
    if not token:
        raise HTTPException(400, "Missing captcha token")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": settings.recaptcha_secret, "response": token, "remoteip": ip},
        )
    data = resp.json()
    if not data.get("success") or data.get("score", 1.0) < settings.recaptcha_min_score:
        raise HTTPException(403, "Captcha verification failed")


async def enforce_daily_cap(session: AsyncSession) -> None:
    count = await session.scalar(
        select(func.count(Analysis.id)).where(
            Analysis.created_at >= func.date_trunc("day", func.now())
        )
    )
    if (count or 0) >= settings.max_daily_analyses:
        raise HTTPException(429, "Daily analysis capacity reached, please try again tomorrow")


@router.post("", response_model=AnalysisOut, status_code=202)
@limiter.limit(settings.rate_limit_new_analyses)
async def create_analysis(
    request: Request,
    response: Response,
    file: UploadFile,
    captcha_token: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> AnalysisOut:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"File larger than {settings.max_upload_mb} MB")

    sha = sha256_of(data)
    existing = await session.scalar(select(Analysis).where(Analysis.paper_sha256 == sha))
    if existing and existing.status != "failed":
        # Same PDF already analysed (or in progress): reuse it, costs nothing.
        response.status_code = 200
        return to_out(existing)

    await verify_captcha(captcha_token, client_ip(request))
    await enforce_daily_cap(session)
    try:
        text = extract_text(data, settings.max_text_chars)
    except InvalidPdfError as exc:
        raise HTTPException(422, str(exc)) from exc

    if existing:
        # A previous run failed for good: uploading the PDF again starts a fresh attempt.
        analysis = existing
        analysis.status, analysis.attempts, analysis.error = "queued", 0, None
        analysis.input_text, analysis.progress = text, []
        await session.commit()
    else:
        analysis = Analysis(paper_sha256=sha, input_text=text)
        try:
            # Flush the paper first: without an ORM relationship the insert order is not guaranteed.
            session.add(Paper(sha256=sha))
            await session.flush()
            session.add(analysis)
            await session.commit()
        except IntegrityError:
            # Someone uploaded the same PDF concurrently; return their analysis.
            await session.rollback()
            existing = await session.scalar(select(Analysis).where(Analysis.paper_sha256 == sha))
            response.status_code = 200
            return to_out(existing)
    await session.refresh(analysis)

    await tasks.enqueue(analysis.id)
    return to_out(analysis)


@router.get("/{sha256}", response_model=AnalysisOut)
async def get_analysis(
    sha256: str, response: Response, session: AsyncSession = Depends(get_session)
) -> AnalysisOut:
    analysis = await session.scalar(select(Analysis).where(Analysis.paper_sha256 == sha256.lower()))
    if not analysis:
        raise HTTPException(404, "Report not found")
    if analysis.status == "done":
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-store"
    return to_out(analysis)
