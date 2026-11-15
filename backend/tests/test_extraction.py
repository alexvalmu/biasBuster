import pymupdf
import pytest

from app.agents.nodes.enricher import name_key, select_authors
from app.agents.nodes.extractor import HEAD_CHARS, build_excerpt, clean_doi
from app.agents.state import EnrichedAuthor
from app.services.pdf import InvalidPdfError, extract_text, is_pdf, sha256_of


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(40, 40, 560, 800), text, fontsize=8)
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_text_extraction_and_hash():
    data = make_pdf("Efficacy of drug X in condition Y. " * 40)
    assert is_pdf(data)
    assert "drug X" in extract_text(data, max_chars=100_000)
    assert sha256_of(data) == sha256_of(data) and len(sha256_of(data)) == 64


def test_non_pdf_and_empty_pdf_are_rejected():
    with pytest.raises(InvalidPdfError):
        extract_text(b"hello", 1000)
    with pytest.raises(InvalidPdfError):
        extract_text(make_pdf("tiny"), 1000)


def test_excerpt_includes_disclosure_sections_at_the_end():
    body = "x" * (HEAD_CHARS + 50_000)
    text = body + "\nConflicts of interest: Dr. A is a consultant for Acme.\n"
    excerpt = build_excerpt(text)
    assert "consultant for Acme" in excerpt
    assert len(excerpt) <= 40_000


def test_clean_doi():
    assert clean_doi("https://doi.org/10.1056/NEJMoa2034577.") == "10.1056/nejmoa2034577"
    assert clean_doi("not a doi") is None


def test_name_matching_is_accent_and_initial_tolerant():
    assert name_key("José A. García") == name_key("Jose Garcia")


def test_author_selection_keeps_first_last_and_corresponding():
    authors = [EnrichedAuthor(name=f"Author {i}") for i in range(20)]
    authors[10].is_corresponding = True
    picked = select_authors(authors, limit=8)
    names = [a.name for a in picked]
    assert names[:6] == [f"Author {i}" for i in range(6)]
    assert "Author 19" in names and "Author 10" in names
    assert len(picked) == 8
