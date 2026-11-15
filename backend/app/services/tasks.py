"""Dispatch analysis jobs to the worker: Cloud Tasks in prod, direct HTTP in local dev."""

import asyncio
import json
import logging
import uuid

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

TASK_PATH = "/tasks/run-analysis"
# Keep strong references so local background tasks are not garbage collected mid-flight.
_background: set[asyncio.Task] = set()


async def enqueue(analysis_id: uuid.UUID) -> None:
    settings = get_settings()
    if settings.tasks_backend == "cloudtasks":
        await _enqueue_cloud_tasks(analysis_id)
    else:
        task = asyncio.create_task(_call_worker_locally(analysis_id))
        _background.add(task)
        task.add_done_callback(_background.discard)


async def _call_worker_locally(analysis_id: uuid.UUID) -> None:
    settings = get_settings()
    url = settings.worker_url.rstrip("/") + TASK_PATH
    # Mimic Cloud Tasks: retry on non-2xx up to max_attempts.
    for attempt in range(1, settings.max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=1800) as client:
                resp = await client.post(url, json={"analysis_id": str(analysis_id)})
            if resp.is_success:
                return
            log.warning("worker returned %s (attempt %s)", resp.status_code, attempt)
        except httpx.HTTPError as exc:
            log.warning("worker call failed (attempt %s): %s", attempt, exc)
        await asyncio.sleep(2**attempt)


async def _enqueue_cloud_tasks(analysis_id: uuid.UUID) -> None:
    from google.cloud import tasks_v2

    settings = get_settings()
    client = tasks_v2.CloudTasksAsyncClient()
    parent = client.queue_path(
        settings.gcp_project, settings.gcp_location, settings.gcp_tasks_queue
    )
    url = settings.worker_url.rstrip("/") + TASK_PATH
    http_request: dict = {
        "http_method": tasks_v2.HttpMethod.POST,
        "url": url,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"analysis_id": str(analysis_id)}).encode(),
    }
    if settings.tasks_service_account:
        http_request["oidc_token"] = {
            "service_account_email": settings.tasks_service_account,
            "audience": settings.worker_url,
        }
    await client.create_task(
        parent=parent,
        task={"http_request": http_request, "dispatch_deadline": {"seconds": 1800}},
    )
