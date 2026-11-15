import json
import logging
from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.agents.llm import structured
from app.agents.nodes.scoring import score_report
from app.agents.progress import report_progress
from app.agents.state import GraphState
from app.schemas.report import AuthorFinding, BiasReport, Evidence, FundingSource

log = logging.getLogger(__name__)
MAX_LIMITATIONS = 8

SYSTEM = """You consolidate the findings of several investigators into a final conflict-of-interest
review of a biomedical paper.
- Merge duplicate companies (e.g. "Pfizer Inc." and "Pfizer") and duplicate relationships.
- Re-check declared_in_paper for every relationship and funder against the paper's own Funding and
  COI statements: true only if that company is named there (for that author, when the statement
  is per-author).
- Do NOT add relationships, funders or evidence that are not in the input. You may drop items
  that are clearly about a different person or irrelevant to the study topic.
- summary: 3-5 neutral, factual sentences in English. Say "possible relationship" / "not declared
  in the paper", never accuse. Do not state an overall risk level (it is computed separately).
- limitations: short list of the most important caveats (homonyms, sources unavailable...)."""


class Synthesis(BaseModel):
    funding: list[FundingSource] = []
    authors: list[AuthorFinding] = []
    summary: str
    limitations: list[str] = Field(default_factory=list)


def _norm(url: str) -> str:
    return url.strip().rstrip("/").lower()


def filter_evidence(
    authors: list[AuthorFinding], funding: list[FundingSource], known_urls: set[str]
) -> tuple[list[AuthorFinding], list[FundingSource], int]:
    """Drop evidence whose URL no tool actually returned, and relationships left without evidence.
    This is the main guard against hallucinated sources."""
    now = datetime.now(UTC)
    known = {_norm(u) for u in known_urls}
    dropped = 0

    def keep(evs: list[Evidence]) -> list[Evidence]:
        nonlocal dropped
        out = []
        for e in evs:
            if _norm(e.url) in known:
                out.append(e.model_copy(update={"retrieved_at": e.retrieved_at or now}))
            else:
                dropped += 1
        return out

    clean_authors = []
    for a in authors:
        rels = []
        for r in a.relationships:
            evs = keep(r.evidence)
            if evs:
                rels.append(r.model_copy(update={"evidence": evs}))
        clean_authors.append(a.model_copy(update={"relationships": rels}))

    clean_funding = [f.model_copy(update={"evidence": keep(f.evidence)}) for f in funding]
    return clean_authors, clean_funding, dropped


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


async def synthesize(state: GraphState, config: RunnableConfig) -> GraphState:
    await report_progress(config, "$ consolidating findings")
    extracted = state["extracted"]
    candidates = state.get("funding_candidates")
    raw_funding = candidates.funding if candidates else []
    raw_authors = [f.author for f in state.get("author_findings", [])]
    limitations = list(state.get("limitations", []))

    payload = json.dumps(
        {
            "paper": extracted.paper.model_dump(),
            "declared_funding_statement": extracted.funding_statement,
            "declared_coi_statement": extracted.coi_statement,
            "funding": [f.model_dump(mode="json") for f in raw_funding],
            "authors": [a.model_dump(mode="json") for a in raw_authors],
            "investigator_notes": limitations,
        },
        ensure_ascii=False,
    )
    try:
        synthesis = await structured("agent", Synthesis, SYSTEM, payload, config=config)
        funding, authors = synthesis.funding, synthesis.authors
        summary, limitations = synthesis.summary, synthesis.limitations + limitations[:2]
    except Exception as exc:
        log.warning("synthesis failed, using raw findings: %s", exc)
        funding, authors = raw_funding, raw_authors
        summary = "Automatic summary unavailable; see the detailed findings below."

    authors, funding, dropped = filter_evidence(authors, funding, set(state.get("known_urls", [])))
    if dropped:
        log.info("dropped %s evidence items with unverifiable URLs", dropped)

    report = BiasReport(
        paper=extracted.paper,
        declared_coi_statement=extracted.coi_statement,
        declared_funding_statement=extracted.funding_statement,
        funding=funding,
        authors=authors,
        summary=summary,
        limitations=_dedupe(limitations)[:MAX_LIMITATIONS],
        generated_at=datetime.now(UTC),
    )
    report = score_report(report)
    await report_progress(config, f"$ done · risk={report.risk_level} ({report.risk_score}/100)")
    return {"report": report}
