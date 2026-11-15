import re

from langchain_core.runnables import RunnableConfig

from app.agents.llm import structured
from app.agents.progress import report_progress
from app.agents.state import ExtractedPaper, GraphState

HEAD_CHARS = 12_000
SECTION_CHARS = 4_000
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
NCT_RE = re.compile(r"\bNCT\d{8}\b")
# Disclosure sections usually sit at the end of the paper, far from the first pages.
SECTION_RE = re.compile(
    r"(funding|financial support|role of the funding source|conflicts? of interest|"
    r"competing interests?|declaration of interests?|disclosures?|acknowledge?ments?)",
    re.IGNORECASE,
)

SYSTEM = """You extract bibliographic and disclosure data from the text of a biomedical paper.
Rules:
- Copy the Funding and Conflicts-of-interest/Competing-interests/Disclosures sections VERBATIM.
  If a section does not exist, use null. Never summarize or invent them.
- List every author in order with their affiliations as printed.
- interventions = drugs, devices or products studied; conditions = diseases studied.
- trial_ids = registry identifiers such as NCT numbers."""


def build_excerpt(text: str) -> str:
    parts = [text[:HEAD_CHARS]]
    seen_until = HEAD_CHARS
    for m in SECTION_RE.finditer(text, HEAD_CHARS):
        if m.start() < seen_until:
            continue
        parts.append(text[m.start() : m.start() + SECTION_CHARS])
        seen_until = m.start() + SECTION_CHARS
    return "\n\n[...]\n\n".join(parts)[:40_000]


def clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("doi:").rstrip(".,;)")
    return doi.lower() if DOI_RE.fullmatch(doi) else None


async def extract(state: GraphState, config: RunnableConfig) -> GraphState:
    await report_progress(config, "$ parsing paper: authors, funding and disclosures")
    text = state["text"]
    extracted = await structured("fast", ExtractedPaper, SYSTEM, build_excerpt(text), config=config)

    # Regex is more reliable than the model for identifiers; use it as ground truth when found.
    regex_doi = DOI_RE.search(text[:HEAD_CHARS])
    extracted.paper.doi = clean_doi(extracted.paper.doi) or clean_doi(
        regex_doi.group(1) if regex_doi else None
    )
    extracted.paper.trial_ids = sorted(set(extracted.paper.trial_ids) | set(NCT_RE.findall(text)))

    await report_progress(
        config,
        f"$ found {len(extracted.authors)} authors · doi={extracted.paper.doi or 'unknown'}",
    )
    return {"extracted": extracted}
