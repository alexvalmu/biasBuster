import operator
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field

from app.schemas.report import AuthorFinding, BiasReport, FundingSource, PaperMeta


class ExtractedAuthor(BaseModel):
    name: str
    affiliations: list[str] = []
    is_corresponding: bool = False


class ExtractedPaper(BaseModel):
    """What the extractor reads from the PDF text itself."""

    paper: PaperMeta
    authors: list[ExtractedAuthor] = []
    funding_statement: str | None = Field(None, description="Verbatim Funding section, if any")
    coi_statement: str | None = Field(
        None,
        description="Verbatim Conflicts of interest / Competing interests / Disclosures section",
    )
    acknowledgements: str | None = None


class EnrichedAuthor(BaseModel):
    name: str
    affiliations: list[str] = []
    orcid: str | None = None
    openalex_id: str | None = None
    is_corresponding: bool = False


class FundingCandidates(BaseModel):
    funding: list[FundingSource] = []
    notes: list[str] = Field(default_factory=list, description="Caveats or unresolved questions")


class AuthorInvestigation(BaseModel):
    author: AuthorFinding
    notes: list[str] = Field(default_factory=list, description="Homonym doubts, missing data, etc.")


class GraphState(TypedDict, total=False):
    analysis_id: str
    text: str
    extracted: ExtractedPaper
    authors: list[EnrichedAuthor]
    enrichment: dict[str, Any]
    funding_candidates: FundingCandidates
    author_findings: Annotated[list[AuthorInvestigation], operator.add]
    # Every URL actually returned by a tool or source; evidence outside this set is dropped.
    known_urls: Annotated[list[str], operator.add]
    limitations: Annotated[list[str], operator.add]
    report: BiasReport


class AuthorTask(TypedDict):
    """Payload sent to each parallel author_investigator."""

    author: EnrichedAuthor
    extracted: ExtractedPaper
    funding_names: list[str]
