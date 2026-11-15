import json

import httpx
import pytest
import respx

from app.tools import clinicaltrials, crossref, http, openalex, pubmed

PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet><PubmedArticle><MedlineCitation>
  <PMID>123456</PMID>
  <Article>
    <Journal><Title>The Journal</Title><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue></Journal>
    <ArticleTitle>Drug X for Y</ArticleTitle>
    <AuthorList>
      <Author><LastName>Smith</LastName><ForeName>Jane</ForeName>
        <AffiliationInfo><Affiliation>Harvard Medical School</Affiliation></AffiliationInfo></Author>
    </AuthorList>
    <GrantList><Grant><GrantID>R01-1</GrantID><Agency>NIH</Agency></Grant></GrantList>
  </Article>
  <CoiStatement>JS has received consulting fees from Acme Pharma.</CoiStatement>
</MedlineCitation></PubmedArticle></PubmedArticleSet>"""


@pytest.fixture(autouse=True)
def no_db_cache(monkeypatch):
    async def miss(_key):
        return None

    async def noop(*_args):
        return None

    monkeypatch.setattr(http, "_cache_get", miss)
    monkeypatch.setattr(http, "_cache_put", noop)


def test_pubmed_xml_parsing():
    [article] = pubmed.parse_articles(PUBMED_XML)
    assert article["pmid"] == "123456"
    assert article["coi_statement"].startswith("JS has received")
    assert article["grants"] == [{"agency": "NIH", "grant_id": "R01-1"}]
    assert article["authors"][0] == {
        "name": "Jane Smith",
        "affiliations": ["Harvard Medical School"],
    }
    assert article["url"] == "https://pubmed.ncbi.nlm.nih.gov/123456/"


@respx.mock
async def test_pubmed_author_disclosures_tool():
    respx.get(url__startswith=f"{pubmed.EUTILS}/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["123456"]}})
    )
    respx.get(url__startswith=f"{pubmed.EUTILS}/efetch.fcgi").mock(
        return_value=httpx.Response(200, text=PUBMED_XML)
    )
    out = json.loads(await pubmed.pubmed_author_disclosures.ainvoke({"author_name": "Jane Smith"}))
    assert out["results"][0]["coi_statement"].endswith("Acme Pharma.")


@respx.mock
async def test_clinicaltrials_sponsor():
    respx.get(f"{clinicaltrials.BASE}/NCT01234567").mock(
        return_value=httpx.Response(
            200,
            json={
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT01234567", "briefTitle": "Trial"},
                    "sponsorCollaboratorsModule": {
                        "leadSponsor": {"name": "Acme Pharma", "class": "INDUSTRY"},
                        "collaborators": [{"name": "Uni", "class": "OTHER"}],
                    },
                }
            },
        )
    )
    study = await clinicaltrials.study("NCT01234567")
    assert study["lead_sponsor"] == {"name": "Acme Pharma", "class": "INDUSTRY"}
    assert study["url"] == "https://clinicaltrials.gov/study/NCT01234567"


@respx.mock
async def test_openalex_and_crossref_by_doi():
    respx.get(url__startswith=f"{openalex.BASE}/works/doi:10.1/abc").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "https://openalex.org/W1",
                "title": "T",
                "funders": [{"display_name": "NIH"}],
                "authorships": [
                    {
                        "author": {
                            "id": "https://openalex.org/A9",
                            "display_name": "Jane Smith",
                            "orcid": "https://orcid.org/0000-0001-2345-6789",
                        },
                        "institutions": [{"display_name": "Harvard"}],
                        "is_corresponding": True,
                    }
                ],
            },
        )
    )
    respx.get(f"{crossref.BASE}/10.1/abc").mock(
        return_value=httpx.Response(
            200,
            json={"message": {"funder": [{"name": "Acme Pharma", "award": ["A1"]}], "author": []}},
        )
    )
    work = await openalex.work_by_doi("10.1/abc")
    assert work["authors"][0]["openalex_id"] == "A9"
    assert work["authors"][0]["orcid"] == "0000-0001-2345-6789"
    assert work["funders"] == ["NIH"]
    cr = await crossref.by_doi("10.1/abc")
    assert cr["funders"][0]["name"] == "Acme Pharma"


@respx.mock
async def test_source_errors_are_reported_not_raised_by_tools():
    respx.get(url__startswith=f"{pubmed.EUTILS}/esearch.fcgi").mock(
        return_value=httpx.Response(503)
    )
    out = json.loads(await pubmed.pubmed_author_disclosures.ainvoke({"author_name": "X"}))
    assert "error" in out
