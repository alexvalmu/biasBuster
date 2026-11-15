"""CMS Open Payments: industry payments to US physicians.

CMS publishes one dataset per program year; set OPEN_PAYMENTS_DATASET_ID to the
"General Payment Data" dataset id of the year to query (see infra/README.md).
"""

import json
from collections import defaultdict

from langchain_core.tools import tool

from app.core.config import get_settings
from app.tools.http import SourceError, fetch

BASE = "https://openpaymentsdata.cms.gov/api/1/datastore/query"


async def payments(first_name: str, last_name: str) -> dict | None:
    dataset = get_settings().open_payments_dataset_id
    if not dataset:
        return None
    url = f"{BASE}/{dataset}/0"
    params = {
        "conditions[0][property]": "covered_recipient_last_name",
        "conditions[0][value]": last_name.upper(),
        "conditions[0][operator]": "=",
        "conditions[1][property]": "covered_recipient_first_name",
        "conditions[1][value]": first_name.upper(),
        "conditions[1][operator]": "=",
        "limit": 200,
    }
    data = await fetch(url, params)
    rows = (data or {}).get("results", [])

    by_company: dict[tuple, dict] = defaultdict(
        lambda: {"total_usd": 0.0, "count": 0, "natures": set()}
    )
    for r in rows:
        key = (
            r.get("applicable_manufacturer_or_applicable_gpo_making_payment_name"),
            r.get("recipient_city"),
            r.get("recipient_state"),
        )
        agg = by_company[key]
        agg["total_usd"] += float(r.get("total_amount_of_payment_usdollars") or 0)
        agg["count"] += 1
        if r.get("nature_of_payment_or_transfer_of_value"):
            agg["natures"].add(r["nature_of_payment_or_transfer_of_value"])

    query_url = (
        f"{url}?conditions[0][property]=covered_recipient_last_name&conditions[0][value]="
        f"{last_name.upper()}&conditions[1][property]=covered_recipient_first_name"
        f"&conditions[1][value]={first_name.upper()}"
    )
    return {
        "url": query_url,
        "payments_by_company": [
            {
                "company": company,
                "recipient_location": f"{city}, {state}",
                "total_usd": round(agg["total_usd"], 2),
                "payments": agg["count"],
                "natures": sorted(agg["natures"]),
            }
            for (company, city, state), agg in sorted(
                by_company.items(), key=lambda kv: -kv[1]["total_usd"]
            )
        ][:20],
    }


@tool
async def open_payments_lookup(first_name: str, last_name: str) -> str:
    """Search CMS Open Payments for industry payments to a US physician. Only relevant for
    authors practicing in the United States. Check recipient_location matches the author's
    affiliation before trusting a match (homonyms are common). Returns JSON with the query URL."""
    try:
        result = await payments(first_name, last_name)
    except SourceError as exc:
        return json.dumps({"error": str(exc)})
    if result is None:
        return json.dumps({"error": "Open Payments is not configured"})
    return json.dumps({"source": "open_payments", **result}, ensure_ascii=False)
