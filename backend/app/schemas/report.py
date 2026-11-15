"""Fixed report contract shared by the agents, the database and the frontend.

Any change here is a breaking change for the UI: bump REPORT_VERSION and regenerate
frontend types (`npm run gen:types`).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

REPORT_VERSION = "1.0"

Source = Literal[
    "pubmed", "europepmc", "openalex", "crossref", "orcid", "clinicaltrials", "open_payments", "web"
]
Confidence = Literal["low", "medium", "high"]
CompanyType = Literal["pharma", "device", "biotech", "other"]
RelationshipKind = Literal[
    "employee",
    "consultant",
    "speaker",
    "advisory_board",
    "research_grant",
    "stock",
    "payments",
    "patent",
    "other",
]
FundingType = Literal["industry", "public", "nonprofit", "unknown"]
RiskLevel = Literal["low", "moderate", "high"]


class Evidence(BaseModel):
    source: Source
    url: str = Field(description="Exact URL returned by a tool. Never invent URLs.")
    snippet: str = Field(
        description="Short verbatim excerpt supporting the claim (max ~300 chars)."
    )
    retrieved_at: datetime | None = None


class Relationship(BaseModel):
    company: str
    company_type: CompanyType = "other"
    kind: RelationshipKind
    period: str | None = Field(None, description="e.g. '2019-2022' if known")
    amount_usd: float | None = None
    declared_in_paper: bool = Field(
        description="True only if the paper's own COI/funding statement mentions this company."
    )
    confidence: Confidence
    evidence: list[Evidence] = Field(min_length=1)


class AuthorFinding(BaseModel):
    name: str
    orcid: str | None = None
    affiliations: list[str] = []
    relationships: list[Relationship] = []


class FundingSource(BaseModel):
    name: str
    type: FundingType
    declared_in_paper: bool
    evidence: list[Evidence] = []


class PaperMeta(BaseModel):
    title: str | None = None
    doi: str | None = None
    pmid: str | None = None
    journal: str | None = None
    year: int | None = None
    interventions: list[str] = Field(default_factory=list, description="Drugs/devices studied")
    conditions: list[str] = Field(default_factory=list)
    trial_ids: list[str] = Field(default_factory=list, description="e.g. NCT identifiers")


class RiskFactor(BaseModel):
    label: str
    points: int


class BiasReport(BaseModel):
    report_version: Literal["1.0"] = REPORT_VERSION
    paper: PaperMeta
    declared_coi_statement: str | None = None
    declared_funding_statement: str | None = None
    funding: list[FundingSource] = []
    authors: list[AuthorFinding] = []
    undisclosed_count: int = 0
    risk_level: RiskLevel = "low"
    risk_score: int = Field(0, ge=0, le=100)
    risk_breakdown: list[RiskFactor] = []
    summary: str = ""
    limitations: list[str] = []
    generated_at: datetime | None = None


class ProgressEntry(BaseModel):
    ts: datetime
    msg: str


AnalysisStatus = Literal["queued", "running", "done", "failed"]


class AnalysisOut(BaseModel):
    sha256: str
    status: AnalysisStatus
    progress: list[ProgressEntry] = []
    report: BiasReport | None = None
    error: str | None = None
