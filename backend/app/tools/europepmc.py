from app.tools.http import fetch

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


async def by_doi(doi: str) -> dict | None:
    data = await fetch(
        f"{BASE}/search",
        {"query": f'DOI:"{doi}"', "resultType": "core", "format": "json", "pageSize": 1},
    )
    results = (data or {}).get("resultList", {}).get("result", [])
    if not results:
        return None
    r = results[0]

    authors = []
    for a in r.get("authorList", {}).get("author", []):
        orcid = None
        author_id = a.get("authorId") or {}
        if author_id.get("type") == "ORCID":
            orcid = author_id.get("value")
        affiliations = [
            x.get("affiliation")
            for x in a.get("authorAffiliationDetailsList", {}).get("authorAffiliation", [])
            if x.get("affiliation")
        ]
        authors.append({"name": a.get("fullName"), "orcid": orcid, "affiliations": affiliations})

    source_id = r.get("id")
    return {
        "pmid": r.get("pmid"),
        "url": f"https://europepmc.org/article/{r.get('source', 'MED')}/{source_id}",
        "title": r.get("title"),
        "journal": r.get("journalInfo", {}).get("journal", {}).get("title"),
        "year": r.get("pubYear"),
        "grants": [
            {"agency": g.get("agency"), "grant_id": g.get("grantId")}
            for g in r.get("grantsList", {}).get("grant", [])
        ],
        "authors": authors,
    }
