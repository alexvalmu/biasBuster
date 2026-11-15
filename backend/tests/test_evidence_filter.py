from app.agents.nodes.synthesizer import filter_evidence
from app.agents.progress import urls_in
from app.schemas.report import AuthorFinding, Evidence, FundingSource, Relationship


def test_hallucinated_urls_are_dropped_with_their_relationships():
    real = Evidence(
        source="orcid", url="https://orcid.org/0000-0001-2345-6789/", snippet="Employee"
    )
    fake = Evidence(source="web", url="https://made-up.example/claim", snippet="Consultant")
    authors = [
        AuthorFinding(
            name="A",
            relationships=[
                Relationship(
                    company="X",
                    kind="employee",
                    declared_in_paper=False,
                    confidence="high",
                    evidence=[real],
                ),
                Relationship(
                    company="Y",
                    kind="consultant",
                    declared_in_paper=False,
                    confidence="high",
                    evidence=[fake],
                ),
            ],
        )
    ]
    funding = [FundingSource(name="Y", type="industry", declared_in_paper=True, evidence=[fake])]

    clean_authors, clean_funding, dropped = filter_evidence(
        authors, funding, {"https://ORCID.org/0000-0001-2345-6789"}
    )
    assert [r.company for r in clean_authors[0].relationships] == ["X"]
    assert clean_authors[0].relationships[0].evidence[0].retrieved_at is not None
    # funders survive without evidence (they may come from the paper text), but lose fake links
    assert clean_funding[0].evidence == []
    assert dropped == 2


def test_urls_are_extracted_from_tool_output():
    text = '{"url": "https://pubmed.ncbi.nlm.nih.gov/123/", "x": "see https://a.org/b."}'
    assert urls_in(text) == ["https://pubmed.ncbi.nlm.nih.gov/123/", "https://a.org/b"]
