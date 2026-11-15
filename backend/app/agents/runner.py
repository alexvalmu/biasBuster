import uuid

from app.agents.graph import build_graph
from app.agents.llm import UsageTracker
from app.core.config import get_settings
from app.db import repo
from app.schemas.report import BiasReport
from app.tools.web_search import reset_budget


async def run_analysis(analysis_id: uuid.UUID, text: str) -> tuple[BiasReport, dict, float]:
    """Run the agent graph for one paper. Returns (report, models_used, cost_usd)."""
    settings = get_settings()
    usage = UsageTracker()
    reset_budget()

    async def progress(msg: str) -> None:
        await repo.add_progress(analysis_id, msg)

    final = await build_graph().ainvoke(
        {"analysis_id": str(analysis_id), "text": text},
        config={"callbacks": [usage], "configurable": {"progress": progress}},
    )
    models_used = {
        "fast": settings.llm_model_fast,
        "agent": settings.llm_model_agent,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
    }
    return final["report"], models_used, usage.cost_usd
