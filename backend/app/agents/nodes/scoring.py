"""Deterministic risk scoring. The LLM never decides the score, so it is reproducible."""

from app.schemas.report import BiasReport, RiskFactor, RiskLevel

INDUSTRY_FUNDING = 30
UNDISCLOSED = {"high": 15, "medium": 8, "low": 2}
DISCLOSED = {"high": 4, "medium": 2, "low": 0}
EMPLOYEE_BONUS = 10
PAYMENTS_BONUS = 5
DISCLOSED_CAP = 20


def risk_level(score: int) -> RiskLevel:
    if score < 25:
        return "low"
    if score < 60:
        return "moderate"
    return "high"


def score_report(report: BiasReport) -> BiasReport:
    factors: list[RiskFactor] = []

    industry = [f for f in report.funding if f.type == "industry"]
    if industry:
        names = ", ".join(sorted({f.name for f in industry}))
        factors.append(RiskFactor(label=f"Industry funding: {names}", points=INDUSTRY_FUNDING))

    undisclosed = disclosed = employees = payments = 0
    undisclosed_count = 0
    for author in report.authors:
        for rel in author.relationships:
            if rel.declared_in_paper:
                disclosed += DISCLOSED[rel.confidence]
            else:
                undisclosed += UNDISCLOSED[rel.confidence]
                if rel.confidence != "low":
                    undisclosed_count += 1
            if rel.kind == "employee" and rel.confidence != "low":
                employees += EMPLOYEE_BONUS
            if any(e.source == "open_payments" for e in rel.evidence):
                payments += PAYMENTS_BONUS

    if undisclosed:
        factors.append(
            RiskFactor(label="Relationships not declared in the paper", points=undisclosed)
        )
    if disclosed:
        factors.append(
            RiskFactor(
                label="Declared industry relationships", points=min(disclosed, DISCLOSED_CAP)
            )
        )
    if employees:
        factors.append(RiskFactor(label="Authors employed by industry", points=employees))
    if payments:
        factors.append(RiskFactor(label="Payments recorded in CMS Open Payments", points=payments))

    score = min(100, sum(f.points for f in factors))
    return report.model_copy(
        update={
            "risk_score": score,
            "risk_level": risk_level(score),
            "risk_breakdown": factors,
            "undisclosed_count": undisclosed_count,
        }
    )
