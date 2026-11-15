"""API + worker endpoint against the real Postgres from docker compose (skipped if unavailable)."""

import uuid

import httpx
import pymupdf
import pytest
from sqlalchemy import delete, text

from app.api import tasks as tasks_api
from app.db.models import Paper
from app.db.session import SessionLocal, engine
from app.main import app
from app.schemas.report import BiasReport, PaperMeta
from app.services import tasks as tasks_service


async def db_available() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1 FROM analyses LIMIT 1"))
        return True
    except Exception:
        return False


def make_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    # unique content so each test run gets a fresh hash
    body = f"Run {uuid.uuid4()}. Efficacy of drug X in condition Y. " * 30
    page.insert_textbox(pymupdf.Rect(40, 40, 560, 800), body, fontsize=8)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
async def client(monkeypatch):
    if not await db_available():
        pytest.skip("Postgres not available (run inside docker compose)")
    enqueued: list[uuid.UUID] = []

    async def fake_enqueue(analysis_id):
        enqueued.append(analysis_id)

    monkeypatch.setattr(tasks_service, "enqueue", fake_enqueue)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.enqueued = enqueued
        yield c
    await engine.dispose()


async def test_upload_dedupes_and_worker_is_idempotent(client, monkeypatch):
    runs = 0

    async def fake_run(analysis_id, text_):
        nonlocal runs
        runs += 1
        return BiasReport(paper=PaperMeta(title="Drug X")), {"agent": "fake"}, 0.01

    monkeypatch.setattr(tasks_api, "run_analysis", fake_run)
    pdf = make_pdf()

    r1 = await client.post("/api/analyses", files={"file": ("p.pdf", pdf, "application/pdf")})
    assert r1.status_code == 202, r1.text
    sha = r1.json()["sha256"]
    assert r1.json()["status"] == "queued"

    r2 = await client.post("/api/analyses", files={"file": ("p.pdf", pdf, "application/pdf")})
    assert r2.status_code == 200 and r2.json()["sha256"] == sha
    assert len(client.enqueued) == 1

    analysis_id = str(client.enqueued[0])
    for _ in range(2):  # duplicate Cloud Tasks delivery
        r = await client.post("/tasks/run-analysis", json={"analysis_id": analysis_id})
        assert r.status_code == 200
    assert runs == 1

    done = await client.get(f"/api/analyses/{sha}")
    assert done.json()["status"] == "done"
    assert done.json()["report"]["paper"]["title"] == "Drug X"
    assert "max-age" in done.headers["cache-control"]

    async with SessionLocal() as s:
        await s.execute(delete(Paper).where(Paper.sha256 == sha))
        await s.commit()


async def test_rejects_non_pdf(client):
    r = await client.post(
        "/api/analyses", files={"file": ("x.pdf", b"not a pdf" * 100, "application/pdf")}
    )
    assert r.status_code == 422


async def test_unknown_report_is_404(client):
    r = await client.get("/api/analyses/" + "0" * 64)
    assert r.status_code == 404
