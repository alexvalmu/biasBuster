import json
import uuid
from decimal import Decimal

from sqlalchemy import or_, text, update

from app.db.models import Analysis
from app.db.session import SessionLocal


async def add_progress(analysis_id: uuid.UUID, msg: str) -> None:
    """Append one log line; uses its own short transaction so the UI sees it immediately."""
    async with SessionLocal() as session:
        await session.execute(
            text(
                "UPDATE analyses SET progress = progress || "
                "jsonb_build_array(jsonb_build_object('ts', now(), 'msg', CAST(:msg AS text))), "
                "updated_at = now() WHERE id = :id"
            ),
            {"id": analysis_id, "msg": msg[:500]},
        )
        await session.commit()


# Longer than the Cloud Tasks dispatch deadline (30 min).
STALE_RUNNING = text("now() - interval '35 minutes'")


async def claim(analysis_id: uuid.UUID) -> Analysis | None:
    """Atomically move a queued analysis to running. Returns None if not claimable.

    A 'running' row whose worker died (no progress for STALE_RUNNING) can be reclaimed,
    so a crashed instance does not leave the analysis stuck forever.
    """
    async with SessionLocal() as session:
        row = await session.execute(
            update(Analysis)
            .where(
                Analysis.id == analysis_id,
                or_(
                    Analysis.status == "queued",
                    (Analysis.status == "running") & (Analysis.updated_at < STALE_RUNNING),
                ),
            )
            .values(status="running", attempts=Analysis.attempts + 1, error=None)
            .returning(Analysis)
        )
        analysis = row.scalar_one_or_none()
        await session.commit()
        return analysis


async def complete(
    analysis_id: uuid.UUID, report: dict, models_used: dict, cost_usd: float | None
) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(Analysis)
            .where(Analysis.id == analysis_id)
            .values(
                status="done",
                report=json.loads(json.dumps(report, default=str)),
                report_version=report.get("report_version"),
                models_used=models_used,
                cost_usd=Decimal(str(round(cost_usd, 5))) if cost_usd is not None else None,
                input_text=None,
                error=None,
            )
        )
        await session.commit()


async def fail(analysis_id: uuid.UUID, error: str, final: bool) -> None:
    """final=False puts it back to queued so the next Cloud Tasks retry can claim it."""
    async with SessionLocal() as session:
        values: dict = {"status": "failed" if final else "queued", "error": error[:2000]}
        if final:
            values["input_text"] = None
        await session.execute(update(Analysis).where(Analysis.id == analysis_id).values(**values))
        await session.commit()
