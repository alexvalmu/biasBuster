"""
extract ─▶ enrich ─┬─▶ funding_investigator ───────────┐
                   └─▶ author_investigator × N (Send) ──┴─▶ synthesize (+ score) ─▶ END
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.nodes.author_investigator import investigate_author
from app.agents.nodes.enricher import enrich
from app.agents.nodes.extractor import extract
from app.agents.nodes.funding_investigator import investigate_funding
from app.agents.nodes.synthesizer import synthesize
from app.agents.state import GraphState


def fan_out(state: GraphState) -> list[Send]:
    enrichment = state.get("enrichment", {})
    funding_names = sorted(
        {f["name"] for f in enrichment.get("crossref_funders", []) if f.get("name")}
        | set(enrichment.get("openalex_funders", []))
        | {
            t["lead_sponsor"]["name"]
            for t in enrichment.get("trials", [])
            if t["lead_sponsor"].get("name")
        }
    )
    sends = [Send("funding_investigator", state)]
    sends += [
        Send(
            "author_investigator",
            {"author": a, "extracted": state["extracted"], "funding_names": funding_names},
        )
        for a in state.get("authors", [])
    ]
    return sends


@lru_cache
def build_graph():
    g = StateGraph(GraphState)
    g.add_node("extract", extract)
    g.add_node("enrich", enrich)
    g.add_node("funding_investigator", investigate_funding)
    g.add_node("author_investigator", investigate_author)
    g.add_node("synthesize", synthesize)

    g.add_edge(START, "extract")
    g.add_edge("extract", "enrich")
    g.add_conditional_edges("enrich", fan_out, ["funding_investigator", "author_investigator"])
    # All Sends run in the same superstep, so synthesize runs once after every branch finishes.
    # (A list-join edge would hang when a paper yields zero authors.)
    g.add_edge("funding_investigator", "synthesize")
    g.add_edge("author_investigator", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()
