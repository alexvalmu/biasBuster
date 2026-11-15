import json

from langchain_core.runnables import RunnableConfig

from app.agents.progress import report_progress
from app.agents.react import run_agent
from app.agents.state import AuthorInvestigation, AuthorTask, GraphState
from app.schemas.report import AuthorFinding
from app.tools.open_payments import open_payments_lookup
from app.tools.openalex import openalex_author_affiliations
from app.tools.orcid import orcid_record
from app.tools.pubmed import pubmed_author_disclosures
from app.tools.web_search import web_search

SYSTEM = """You investigate ONE author of a biomedical paper to find relationships with companies
(pharma, medical devices, biotech) that could bias the study: employment, consulting, speaker fees,
advisory boards, research grants, stock, payments, patents.
Procedure:
1. Confirm identity first. Use the ORCID / OpenAlex id if given; otherwise match by affiliation.
   If you cannot tell the author apart from homonyms, set confidence=low and say so in notes.
2. Check OpenAlex affiliations (institution type "company"), ORCID employments/fundings and the
   author's COI statements in other PubMed papers. Use Open Payments only for US-based physicians.
3. Use web_search sparingly (max 3 queries) for companies related to the drugs/conditions studied
   or to the study's funders.
Rules:
- Only report relationships supported by tool results. Each relationship needs >=1 evidence item
  whose url is copied exactly from a tool result, with a short verbatim snippet.
- declared_in_paper = true only if the paper's COI statement mentions that company for this author.
- confidence: high = identity confirmed and explicit source; medium = likely; low = uncertain.
- Prefer relationships from the last ~5 years and with companies relevant to the study topic.
- Be factual and neutral; do not speculate. If nothing is found, return no relationships."""


async def investigate_author(task: AuthorTask, config: RunnableConfig) -> GraphState:
    author = task["author"]
    extracted = task["extracted"]
    await report_progress(config, f'$ investigating author "{author.name}"')
    payload = json.dumps(
        {
            "author": author.model_dump(),
            "paper": {
                "title": extracted.paper.title,
                "year": extracted.paper.year,
                "interventions": extracted.paper.interventions,
                "conditions": extracted.paper.conditions,
            },
            "paper_coi_statement": extracted.coi_statement,
            "study_funders": task["funding_names"],
        },
        ensure_ascii=False,
    )
    result, urls = await run_agent(
        tools=[
            openalex_author_affiliations,
            orcid_record,
            pubmed_author_disclosures,
            open_payments_lookup,
            web_search,
        ],
        system=SYSTEM,
        task=payload,
        schema=AuthorInvestigation,
        config=config,
        label=author.name,
    )
    if result is None:
        result = AuthorInvestigation(
            author=AuthorFinding(
                name=author.name, orcid=author.orcid, affiliations=author.affiliations
            ),
            notes=[f"Investigation of {author.name} did not complete."],
        )
    # Keep the canonical identity from the paper rather than whatever the model echoed back.
    result.author.name = author.name
    result.author.orcid = result.author.orcid or author.orcid
    result.author.affiliations = result.author.affiliations or author.affiliations
    n = len(result.author.relationships)
    await report_progress(config, f'$ "{author.name}": {n} potential relationship(s)')
    return {"author_findings": [result], "known_urls": urls, "limitations": result.notes}
