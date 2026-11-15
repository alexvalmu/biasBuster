"""End-to-end graph wiring with the LLM and external sources stubbed out."""

from app.agents import graph as graph_module
from app.agents.nodes import (
    author_investigator,
    enricher,
    extractor,
    funding_investigator,
    synthesizer,
)
from app.agents.state import AuthorInvestigation, ExtractedAuthor, ExtractedPaper, FundingCandidates
from app.schemas.report import AuthorFinding, Evidence, FundingSource, PaperMeta, Relationship

ORCID_URL = "https://orcid.org/0000-0001-2345-6789"


async def test_graph_runs_fan_out_and_produces_scored_report(monkeypatch):
    async def fake_structured(kind, schema, system, user, config=None):
        if schema is ExtractedPaper:
            return ExtractedPaper(
                paper=PaperMeta(title="Drug X for Y", interventions=["Drug X"]),
                authors=[ExtractedAuthor(name="Jane Smith"), ExtractedAuthor(name="John Doe")],
                coi_statement="None declared.",
                funding_statement="Funded by Acme Pharma.",
            )
        raise RuntimeError("force synthesis fallback to raw findings")

    investigated: list[str] = []

    async def fake_run_agent(*, schema, label, **_):
        if schema is FundingCandidates:
            return FundingCandidates(
                funding=[FundingSource(name="Acme Pharma", type="industry", declared_in_paper=True)]
            ), []
        investigated.append(label)
        rels = []
        if label == "Jane Smith":
            rels = [
                Relationship(
                    company="Acme Pharma",
                    kind="employee",
                    declared_in_paper=False,
                    confidence="high",
                    evidence=[
                        Evidence(source="orcid", url=ORCID_URL, snippet="Acme Pharma, Scientist")
                    ],
                ),
                Relationship(
                    company="Other Co",
                    kind="consultant",
                    declared_in_paper=False,
                    confidence="high",
                    evidence=[Evidence(source="web", url="https://invented.example", snippet="?")],
                ),
            ]
        return AuthorInvestigation(author=AuthorFinding(name=label, relationships=rels)), [
            ORCID_URL
        ]

    async def no_source(*_a, **_k):
        return None

    monkeypatch.setattr(extractor, "structured", fake_structured)
    monkeypatch.setattr(synthesizer, "structured", fake_structured)
    monkeypatch.setattr(funding_investigator, "run_agent", fake_run_agent)
    monkeypatch.setattr(author_investigator, "run_agent", fake_run_agent)
    for mod, fn in (
        (enricher.crossref, "by_doi"),
        (enricher.europepmc, "by_doi"),
        (enricher.openalex, "work_by_doi"),
        (enricher.pubmed, "find_pmid_by_doi"),
    ):
        monkeypatch.setattr(mod, fn, no_source)

    progress: list[str] = []

    async def on_progress(msg):
        progress.append(msg)

    graph_module.build_graph.cache_clear()
    text = "Drug X for Y. doi: 10.1000/xyz123 " + "body " * 200
    final = await graph_module.build_graph().ainvoke(
        {"analysis_id": "t", "text": text},
        config={"configurable": {"progress": on_progress}},
    )
    report = final["report"]

    assert sorted(investigated) == ["Jane Smith", "John Doe"]
    assert report.paper.doi == "10.1000/xyz123"
    # the relationship backed by an invented URL is removed
    assert [r.company for r in report.authors[0].relationships] == ["Acme Pharma"]
    assert report.undisclosed_count == 1
    # 30 industry + 15 undisclosed + 10 employee
    assert report.risk_score == 55 and report.risk_level == "moderate"
    assert any(p.startswith("$ done") for p in progress)
