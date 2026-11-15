"""Deterministic enrichment from bibliographic databases (no LLM involved)."""

import asyncio
import logging
import unicodedata

from langchain_core.runnables import RunnableConfig

from app.agents.progress import report_progress
from app.agents.state import EnrichedAuthor, GraphState
from app.core.config import get_settings
from app.tools import clinicaltrials, crossref, europepmc, openalex, pubmed

log = logging.getLogger(__name__)
MAX_TRIALS = 3


def name_key(name: str) -> tuple[str, str]:
    """(last name, first initial) normalized, for loose author matching across sources."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    parts = [p for p in ascii_name.replace(".", " ").replace(",", " ").split() if p]
    if not parts:
        return ("", "")
    return (parts[-1], parts[0][0])


def select_authors(authors: list[EnrichedAuthor], limit: int) -> list[EnrichedAuthor]:
    """First authors, the last (senior) author and the corresponding author, capped at `limit`."""
    if len(authors) <= limit:
        return authors
    picked = authors[: max(limit - 2, 1)] + [authors[-1]]
    picked += [a for a in authors if a.is_corresponding]
    unique: list[EnrichedAuthor] = []
    for a in picked:
        if a not in unique:
            unique.append(a)
    return unique[:limit]


async def _safe(name: str, coro):
    try:
        return await coro
    except Exception as exc:
        log.warning("enrich source %s failed: %s", name, exc)
        return exc


async def enrich(state: GraphState, config: RunnableConfig) -> GraphState:
    settings = get_settings()
    extracted = state["extracted"]
    paper = extracted.paper
    limitations: list[str] = []
    known_urls: list[str] = []
    enrichment: dict = {}

    oa_work = None
    if paper.doi:
        await report_progress(
            config, f"$ querying crossref, europepmc, openalex, pubmed for {paper.doi}"
        )
        cr, epmc, oa, pmid = await asyncio.gather(
            _safe("crossref", crossref.by_doi(paper.doi)),
            _safe("europepmc", europepmc.by_doi(paper.doi)),
            _safe("openalex", openalex.work_by_doi(paper.doi)),
            _safe("pubmed", pubmed.find_pmid_by_doi(paper.doi)),
        )
        for name, value in (
            ("Crossref", cr),
            ("Europe PMC", epmc),
            ("OpenAlex", oa),
            ("PubMed", pmid),
        ):
            if isinstance(value, Exception):
                limitations.append(f"{name} could not be queried.")

        if isinstance(cr, dict):
            enrichment["crossref_funders"] = cr["funders"]
            known_urls.append(cr["url"])
            paper.journal = paper.journal or cr.get("journal")
            paper.year = paper.year or cr.get("year")
        if isinstance(epmc, dict):
            enrichment["europepmc_grants"] = epmc["grants"]
            known_urls.append(epmc["url"])
            paper.pmid = paper.pmid or epmc.get("pmid")
        if isinstance(oa, dict):
            oa_work = oa
            enrichment["openalex_funders"] = oa["funders"]
            if oa.get("url"):
                known_urls.append(oa["url"])
        if isinstance(pmid, str):
            paper.pmid = paper.pmid or pmid
        if paper.pmid:
            articles = await _safe("pubmed", pubmed.fetch_articles([paper.pmid]))
            if isinstance(articles, list) and articles:
                art = articles[0]
                enrichment["pubmed_coi_statement"] = art.get("coi_statement")
                enrichment["pubmed_grants"] = art.get("grants")
                known_urls.append(art["url"])
    else:
        limitations.append(
            "No DOI found in the paper; bibliographic databases were not cross-checked."
        )

    trial_ids = paper.trial_ids[:MAX_TRIALS]
    if trial_ids:
        await report_progress(config, f"$ querying clinicaltrials.gov for {', '.join(trial_ids)}")
        trials = await asyncio.gather(
            *(_safe("clinicaltrials", clinicaltrials.study(t)) for t in trial_ids)
        )
        enrichment["trials"] = [t for t in trials if isinstance(t, dict)]
        known_urls += [t["url"] for t in enrichment["trials"] if t.get("url")]

    # Merge authors: the PDF order is authoritative, OpenAlex adds stable ids and ORCID.
    oa_by_key = {
        name_key(a["name"]): a for a in (oa_work or {}).get("authors", []) if a.get("name")
    }
    source_authors = extracted.authors or [
        {
            "name": a["name"],
            "affiliations": a["affiliations"],
            "is_corresponding": a["is_corresponding"],
        }
        for a in (oa_work or {}).get("authors", [])
    ]
    authors: list[EnrichedAuthor] = []
    for a in source_authors:
        a = a if isinstance(a, dict) else a.model_dump()
        oa_author = oa_by_key.get(name_key(a["name"]), {})
        authors.append(
            EnrichedAuthor(
                name=a["name"],
                affiliations=a.get("affiliations") or oa_author.get("affiliations", []),
                orcid=oa_author.get("orcid"),
                openalex_id=oa_author.get("openalex_id"),
                is_corresponding=a.get("is_corresponding")
                or oa_author.get("is_corresponding", False),
            )
        )

    selected = select_authors(authors, settings.max_authors_investigated)
    if len(selected) < len(authors):
        limitations.append(
            f"Only {len(selected)} of {len(authors)} authors were investigated "
            "(first authors, senior author and corresponding author)."
        )
    if not authors:
        limitations.append("No authors could be identified.")

    return {
        "extracted": extracted,
        "authors": selected,
        "enrichment": enrichment,
        "known_urls": known_urls,
        "limitations": limitations,
    }
