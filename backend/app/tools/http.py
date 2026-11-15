"""Shared HTTP client for external data sources, with a Postgres-backed response cache."""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.db.models import HttpCache
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


class SourceError(RuntimeError):
    pass


def _cache_key(url: str, params: dict | None) -> str:
    raw = url + "?" + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {"User-Agent": f"biasBuster/0.1 (mailto:{settings.contact_email})"}


async def _cache_get(key: str) -> Any | None:
    try:
        async with SessionLocal() as session:
            row = await session.get(HttpCache, key)
            if row and row.expires_at > datetime.now():
                return row.response.get("body")
    except Exception as exc:  # cache must never break a lookup
        log.debug("http cache read failed: %s", exc)
    return None


async def _cache_put(key: str, url: str, body: Any, ttl_hours: int) -> None:
    try:
        async with SessionLocal() as session:
            expires = datetime.now() + timedelta(hours=ttl_hours)
            stmt = insert(HttpCache).values(
                key=key, url=url, response={"body": body}, expires_at=expires
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["key"],
                set_={"response": stmt.excluded.response, "expires_at": expires},
            )
            await session.execute(stmt)
            await session.commit()
    except Exception as exc:
        log.debug("http cache write failed: %s", exc)


async def fetch(
    url: str,
    params: dict | None = None,
    *,
    as_json: bool = True,
    headers: dict[str, str] | None = None,
    cache: bool = True,
) -> Any:
    """GET a URL and return parsed JSON (or text). Raises SourceError on failure."""
    settings = get_settings()
    key = _cache_key(url, params)
    if cache:
        cached = await _cache_get(key)
        if cached is not None:
            return cached

    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_s, headers=_headers(), follow_redirects=True
        ) as client:
            resp = await client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        raise SourceError(f"{url}: {exc}") from exc

    if resp.status_code == 404:
        body: Any = None
    elif not resp.is_success:
        raise SourceError(f"{url}: HTTP {resp.status_code}")
    else:
        body = resp.json() if as_json else resp.text

    if cache and body is not None:
        await _cache_put(key, url, body, settings.http_cache_ttl_hours)
    return body
