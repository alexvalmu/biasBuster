from urllib.parse import quote

from app.tools.http import fetch

BASE = "https://api.crossref.org/works"


async def by_doi(doi: str) -> dict | None:
    data = await fetch(f"{BASE}/{quote(doi, safe='/')}")
    msg = (data or {}).get("message")
    if not msg:
        return None
    issued = (msg.get("issued", {}).get("date-parts") or [[None]])[0]
    return {
        "url": f"https://doi.org/{doi}",
        "title": (msg.get("title") or [None])[0],
        "journal": (msg.get("container-title") or [None])[0],
        "year": issued[0] if issued else None,
        "funders": [
            {"name": f.get("name"), "funder_doi": f.get("DOI"), "awards": f.get("award", [])}
            for f in msg.get("funder", [])
        ],
        "authors": [
            {
                "name": " ".join(p for p in (a.get("given"), a.get("family")) if p),
                "orcid": (a.get("ORCID") or "").rsplit("/", 1)[-1] or None,
                "affiliations": [x.get("name") for x in a.get("affiliation", []) if x.get("name")],
            }
            for a in msg.get("author", [])
        ],
    }
