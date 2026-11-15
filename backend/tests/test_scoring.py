from app.agents.nodes.scoring import score_report
from app.schemas.report import (
    AuthorFinding,
    BiasReport,
    Evidence,
    FundingSource,
    PaperMeta,
    Relationship,
)


def ev(source="web"):
    return Evidence(source=source, url="https://example.org/x", snippet="...")


def rel(declared, confidence="high", kind="consultant", source="web"):
    return Relationship(
        company="Acme Pharma",
        kind=kind,
        declared_in_paper=declared,
        confidence=confidence,
        evidence=[ev(source)],
    )


def test_clean_paper_scores_low():
    report = score_report(BiasReport(paper=PaperMeta(title="t")))
    assert report.risk_score == 0
    assert report.risk_level == "low"
    assert report.risk_breakdown == []


def test_industry_funding_and_undisclosed_relationships_score_high():
    report = BiasReport(
        paper=PaperMeta(),
        funding=[FundingSource(name="Acme Pharma", type="industry", declared_in_paper=True)],
        authors=[
            AuthorFinding(name="A", relationships=[rel(False), rel(False, kind="employee")]),
            AuthorFinding(name="B", relationships=[rel(True), rel(False, confidence="low")]),
        ],
    )
    scored = score_report(report)
    # 30 industry + (15+15+2) undisclosed + 4 disclosed + 10 employee
    assert scored.risk_score == 76
    assert scored.risk_level == "high"
    # low-confidence findings do not count as undisclosed conflicts
    assert scored.undisclosed_count == 2


def test_score_is_capped_and_open_payments_counted():
    rels = [rel(False, source="open_payments") for _ in range(10)]
    scored = score_report(
        BiasReport(paper=PaperMeta(), authors=[AuthorFinding(name="A", relationships=rels)])
    )
    assert scored.risk_score == 100
    assert any("Open Payments" in f.label for f in scored.risk_breakdown)


def test_demo_fixture_is_valid_and_its_score_matches_the_scorer():
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).parent / "fixtures" / "sample_report.json").read_text())
    report = BiasReport.model_validate(data)
    rescored = score_report(report)
    assert rescored.risk_score == report.risk_score
    assert rescored.undisclosed_count == report.undisclosed_count
