import json

from langchain_core.tools import tool

from app.tools.http import SourceError, fetch

BASE = "https://clinicaltrials.gov/api/v2/studies"


def _summarize(study: dict) -> dict:
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    sponsors = proto.get("sponsorCollaboratorsModule", {})
    nct = ident.get("nctId")
    lead = sponsors.get("leadSponsor", {})
    return {
        "nct_id": nct,
        "url": f"https://clinicaltrials.gov/study/{nct}" if nct else None,
        "title": ident.get("briefTitle"),
        # class INDUSTRY marks commercial sponsors
        "lead_sponsor": {"name": lead.get("name"), "class": lead.get("class")},
        "collaborators": [
            {"name": c.get("name"), "class": c.get("class")}
            for c in sponsors.get("collaborators", [])
        ],
        "interventions": [
            i.get("name") for i in proto.get("armsInterventionsModule", {}).get("interventions", [])
        ],
    }


async def study(nct_id: str) -> dict | None:
    data = await fetch(f"{BASE}/{nct_id}")
    return _summarize(data) if data else None


async def search(query: str, limit: int = 5) -> list[dict]:
    data = await fetch(BASE, {"query.term": query, "pageSize": limit, "format": "json"})
    return [_summarize(s) for s in (data or {}).get("studies", [])]


@tool
async def clinicaltrials_lookup(nct_id: str = "", query: str = "") -> str:
    """Look up a trial on ClinicalTrials.gov to find its lead sponsor and collaborators
    (class INDUSTRY = company). Pass an NCT id (e.g. "NCT01234567") or a free-text query
    such as "<drug> <condition>". Returns JSON with trial URLs."""
    try:
        if nct_id:
            return json.dumps({"source": "clinicaltrials", "study": await study(nct_id)})
        if query:
            return json.dumps({"source": "clinicaltrials", "studies": await search(query)})
        return json.dumps({"error": "pass nct_id or query"})
    except SourceError as exc:
        return json.dumps({"error": str(exc)})
