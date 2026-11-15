import json

from langchain_core.tools import tool

from app.tools.http import SourceError, fetch

BASE = "https://pub.orcid.org/v3.0"
ACCEPT_JSON = {"Accept": "application/json"}


def _date(d: dict | None) -> str | None:
    if not d or not d.get("year"):
        return None
    return d["year"].get("value")


def _period(summary: dict) -> str | None:
    start, end = _date(summary.get("start-date")), _date(summary.get("end-date"))
    if not start and not end:
        return None
    return f"{start or '?'}-{end or 'present'}"


async def employments(orcid: str) -> list[dict]:
    data = await fetch(f"{BASE}/{orcid}/employments", headers=ACCEPT_JSON)
    out = []
    for group in (data or {}).get("affiliation-group", []):
        for s in group.get("summaries", []):
            e = s.get("employment-summary", {})
            out.append(
                {
                    "organization": e.get("organization", {}).get("name"),
                    "role": e.get("role-title"),
                    "period": _period(e),
                }
            )
    return out


async def fundings(orcid: str) -> list[dict]:
    data = await fetch(f"{BASE}/{orcid}/fundings", headers=ACCEPT_JSON)
    out = []
    for group in (data or {}).get("group", []):
        for f in group.get("funding-summary", []):
            out.append(
                {
                    "title": (f.get("title") or {}).get("title", {}).get("value"),
                    "funder": f.get("organization", {}).get("name"),
                    "period": _period(f),
                }
            )
    return out


@tool
async def orcid_record(orcid: str) -> str:
    """Get employments and funding records an author declared on their public ORCID profile.
    Pass the bare ORCID iD, e.g. "0000-0002-1825-0097". Returns JSON with the profile URL."""
    try:
        return json.dumps(
            {
                "source": "orcid",
                "url": f"https://orcid.org/{orcid}",
                "employments": await employments(orcid),
                "fundings": (await fundings(orcid))[:30],
            },
            ensure_ascii=False,
        )
    except SourceError as exc:
        return json.dumps({"error": str(exc)})
