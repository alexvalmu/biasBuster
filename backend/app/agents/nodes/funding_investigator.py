import json

from langchain_core.runnables import RunnableConfig

from app.agents.progress import report_progress
from app.agents.react import run_agent
from app.agents.state import FundingCandidates, GraphState
from app.tools.clinicaltrials import clinicaltrials_lookup
from app.tools.web_search import web_search

SYSTEM = """You investigate who funded a biomedical study and whether the funders have a
commercial interest in the result.
- Start from the declared funding statement, the database records and trial registries provided.
- Use clinicaltrials_lookup for trial sponsors; use web_search only to resolve gaps, e.g. who
  manufactures the drug under study or whether a funder is a company.
- type = industry for companies (pharma, device, biotech, CROs paid by them), public for
  governments/universities, nonprofit for foundations and charities.
- declared_in_paper = true only if the paper's own funding/COI text names that funder.
- Every evidence item MUST use a URL that appears in the data or tool results. Never invent URLs.
  For funders found only in the paper text, leave evidence empty.
- Be factual and neutral. Add notes for anything uncertain."""


async def investigate_funding(state: GraphState, config: RunnableConfig) -> GraphState:
    await report_progress(config, "$ investigating funding sources and trial sponsors")
    extracted = state["extracted"]
    task = json.dumps(
        {
            "paper": extracted.paper.model_dump(),
            "declared_funding_statement": extracted.funding_statement,
            "declared_coi_statement": extracted.coi_statement,
            "acknowledgements": extracted.acknowledgements,
            "database_records": state.get("enrichment", {}),
        },
        ensure_ascii=False,
        default=str,
    )
    result, urls = await run_agent(
        tools=[clinicaltrials_lookup, web_search],
        system=SYSTEM,
        task=task,
        schema=FundingCandidates,
        config=config,
        label="funding",
    )
    if result is None:
        return {
            "funding_candidates": FundingCandidates(),
            "limitations": [
                "Funding investigation did not complete; funding list may be incomplete."
            ],
        }
    await report_progress(config, f"$ funding: {len(result.funding)} source(s) identified")
    return {"funding_candidates": result, "known_urls": urls, "limitations": result.notes}
