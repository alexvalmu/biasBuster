import json
import xml.etree.ElementTree as ET

from langchain_core.tools import tool

from app.core.config import get_settings
from app.tools.http import SourceError, fetch

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _params(**extra) -> dict:
    settings = get_settings()
    params = {"db": "pubmed", "tool": "biasbuster", "email": settings.contact_email, **extra}
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    return params


def article_url(pmid: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


async def esearch(term: str, retmax: int = 20) -> list[str]:
    data = await fetch(f"{EUTILS}/esearch.fcgi", _params(term=term, retmode="json", retmax=retmax))
    return (data or {}).get("esearchresult", {}).get("idlist", [])


async def find_pmid_by_doi(doi: str) -> str | None:
    ids = await esearch(f"{doi}[doi]", retmax=1)
    return ids[0] if ids else None


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    value = "".join(el.itertext()).strip()
    return value or None


def parse_articles(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    articles = []
    for node in root.findall(".//PubmedArticle"):
        pmid = _text(node.find(".//MedlineCitation/PMID"))
        authors = []
        for au in node.findall(".//AuthorList/Author"):
            last, fore = _text(au.find("LastName")), _text(au.find("ForeName"))
            if not last:
                continue
            authors.append(
                {
                    "name": f"{fore} {last}" if fore else last,
                    "affiliations": [
                        a
                        for a in (_text(x) for x in au.findall(".//AffiliationInfo/Affiliation"))
                        if a
                    ],
                }
            )
        articles.append(
            {
                "pmid": pmid,
                "url": article_url(pmid) if pmid else None,
                "title": _text(node.find(".//ArticleTitle")),
                "journal": _text(node.find(".//Journal/Title")),
                "year": _text(node.find(".//JournalIssue/PubDate/Year")),
                "coi_statement": _text(node.find(".//CoiStatement")),
                "grants": [
                    {"agency": _text(g.find("Agency")), "grant_id": _text(g.find("GrantID"))}
                    for g in node.findall(".//GrantList/Grant")
                ],
                "authors": authors,
            }
        )
    return articles


async def fetch_articles(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    xml_text = await fetch(
        f"{EUTILS}/efetch.fcgi", _params(id=",".join(pmids), retmode="xml"), as_json=False
    )
    return parse_articles(xml_text) if xml_text else []


async def author_disclosures(author_name: str, affiliation_keyword: str = "") -> list[dict]:
    term = f'"{author_name}"[au]'
    if affiliation_keyword:
        term += f' AND "{affiliation_keyword}"[ad]'
    pmids = await esearch(term, retmax=25)
    articles = await fetch_articles(pmids)
    return [
        {k: a[k] for k in ("pmid", "url", "title", "year", "coi_statement")}
        for a in articles
        if a.get("coi_statement")
    ]


@tool
async def pubmed_author_disclosures(author_name: str, affiliation_keyword: str = "") -> str:
    """Search PubMed for other papers by an author and return their conflict-of-interest
    statements. Use the full author name, e.g. "Jane Smith". Optionally pass one affiliation
    keyword (e.g. "Harvard") to reduce homonyms. Returns JSON with article URLs."""
    try:
        results = await author_disclosures(author_name, affiliation_keyword)
    except SourceError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"source": "pubmed", "results": results[:15]}, ensure_ascii=False)
