"""Insert a finished demo analysis so the report UI can be developed without spending on LLMs.

    docker compose exec api python -m app.devtools.seed   →  /report/<DEMO_SHA>
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from app.db.models import Analysis, Paper
from app.db.session import SessionLocal, engine
from app.schemas.report import BiasReport

DEMO_SHA = "d" * 64
FIXTURE = Path(__file__).parents[2] / "tests" / "fixtures" / "sample_report.json"


async def main() -> None:
    report = BiasReport.model_validate(json.loads(FIXTURE.read_text()))
    data = report.model_dump(mode="json")
    async with SessionLocal() as session:
        await session.execute(
            insert(Paper)
            .values(sha256=DEMO_SHA, doi=report.paper.doi, title=report.paper.title)
            .on_conflict_do_nothing()
        )
        await session.execute(
            insert(Analysis)
            .values(
                paper_sha256=DEMO_SHA,
                status="done",
                report=data,
                report_version=report.report_version,
                progress=[{"ts": "2026-11-14T12:00:00", "msg": "$ seeded demo report"}],
            )
            .on_conflict_do_update(index_elements=["paper_sha256"], set_={"report": data})
        )
        await session.commit()
    await engine.dispose()
    print(f"demo report ready: /report/{DEMO_SHA}")


if __name__ == "__main__":
    asyncio.run(main())
