import json
from contextvars import ContextVar

from langchain_core.tools import tool
from tavily import AsyncTavilyClient

from app.core.config import get_settings

MAX_SEARCHES_PER_ANALYSIS = 15
# Remaining Tavily budget for the analysis running in the current context.
search_budget: ContextVar[list[int] | None] = ContextVar("search_budget", default=None)


def reset_budget() -> None:
    search_budget.set([MAX_SEARCHES_PER_ANALYSIS])


@tool
async def web_search(query: str) -> str:
    """Search the web (Tavily). Use it only when the structured databases are not enough,
    e.g. '"Jane Smith" advisory board Pfizer' or '<company> sponsored <drug> trial'.
    Returns JSON with result URLs and content excerpts."""
    settings = get_settings()
    if not settings.tavily_api_key:
        return json.dumps({"error": "web search is not configured"})
    budget = search_budget.get()
    if budget is not None:
        if budget[0] <= 0:
            return json.dumps({"error": "web search budget for this analysis is exhausted"})
        budget[0] -= 1

    client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    try:
        resp = await client.search(query, max_results=5, search_depth="basic")
    except Exception as exc:
        return json.dumps({"error": f"web search failed: {exc}"})
    return json.dumps(
        {
            "source": "web",
            "results": [
                {
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "content": (r.get("content") or "")[:600],
                }
                for r in resp.get("results", [])
            ],
        },
        ensure_ascii=False,
    )
