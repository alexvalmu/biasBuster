import json

from langchain_core.tools import tool

from app.core.config import get_settings
from app.tools.http import SourceError, fetch

BASE = "https://api.openalex.org"


def _params(**extra) -> dict:
    return {"mailto": get_settings().contact_email, **extra}


def _short_id(openalex_id: str) -> str:
    return openalex_id.rstrip("/").rsplit("/", 1)[-1]


async def work_by_doi(doi: str) -> dict | None:
    data = await fetch(f"{BASE}/works/doi:{doi}", _params())
    if not data:
        return None
    funders = [g.get("funder_display_name") for g in data.get("grants", []) or []]
    funders += [f.get("display_name") for f in data.get("funders", []) or []]
    return {
        "url": data.get("id"),
        "title": data.get("title"),
        "year": data.get("publication_year"),
        "funders": sorted({f for f in funders if f}),
        "authors": [
            {
                "name": a.get("author", {}).get("display_name"),
                "openalex_id": _short_id(a["author"]["id"])
                if a.get("author", {}).get("id")
                else None,
                "orcid": (a.get("author", {}).get("orcid") or "").rsplit("/", 1)[-1] or None,
                "affiliations": [i.get("display_name") for i in a.get("institutions", [])]
                or a.get("raw_affiliation_strings", []),
                "is_corresponding": a.get("is_corresponding", False),
            }
            for a in data.get("authorships", [])
        ],
    }


async def author_profile(openalex_id: str) -> dict | None:
    data = await fetch(f"{BASE}/authors/{_short_id(openalex_id)}", _params())
    if not data:
        return None
    affiliations = []
    for aff in data.get("affiliations", []) or []:
        inst = aff.get("institution", {})
        affiliations.append(
            {
                "institution": inst.get("display_name"),
                # type "company" is the key signal of an industry affiliation
                "type": inst.get("type"),
                "years": sorted(aff.get("years", []))[-6:],
            }
        )
    return {
        "url": data.get("id"),
        "name": data.get("display_name"),
        "orcid": (data.get("orcid") or "").rsplit("/", 1)[-1] or None,
        "works_count": data.get("works_count"),
        "affiliations": affiliations,
    }


async def search_author(name: str) -> list[dict]:
    data = await fetch(f"{BASE}/authors", _params(search=name, per_page=5))
    return [
        {
            "openalex_id": _short_id(a["id"]),
            "name": a.get("display_name"),
            "orcid": (a.get("orcid") or "").rsplit("/", 1)[-1] or None,
            "works_count": a.get("works_count"),
            "last_institutions": [
                i.get("display_name") for i in a.get("last_known_institutions", []) or []
            ],
        }
        for a in (data or {}).get("results", [])
    ]


@tool
async def openalex_author_affiliations(openalex_id: str = "", author_name: str = "") -> str:
    """Get an author's affiliation history from OpenAlex, including institutions of type
    "company" (industry employers). Prefer openalex_id (e.g. "A5023888391"); if unknown,
    pass author_name to list candidate profiles first. Returns JSON with profile URLs."""
    try:
        if openalex_id:
            profile = await author_profile(openalex_id)
            return json.dumps({"source": "openalex", "profile": profile}, ensure_ascii=False)
        if author_name:
            return json.dumps(
                {"source": "openalex", "candidates": await search_author(author_name)},
                ensure_ascii=False,
            )
        return json.dumps({"error": "pass openalex_id or author_name"})
    except SourceError as exc:
        return json.dumps({"error": str(exc)})
