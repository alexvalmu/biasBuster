"""Thin wrapper around a tool-calling agent that returns a typed result plus the URLs it saw."""

import logging

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from app.agents.llm import get_llm
from app.agents.progress import report_progress, urls_in
from app.core.config import get_settings

log = logging.getLogger(__name__)


async def run_agent[T: BaseModel](
    *,
    tools: list[BaseTool],
    system: str,
    task: str,
    schema: type[T],
    config: RunnableConfig,
    label: str,
) -> tuple[T | None, list[str]]:
    agent = create_agent(
        get_llm("agent"),
        tools=tools,
        system_prompt=system,
        response_format=ToolStrategy(schema),
    )
    agent_config: RunnableConfig = {
        **config,
        "recursion_limit": get_settings().agent_recursion_limit * 2 + 1,
    }
    try:
        result = await agent.ainvoke({"messages": [("user", task)]}, config=agent_config)
    except Exception as exc:
        log.warning("agent %s failed: %s", label, exc)
        await report_progress(config, f"$ {label}: agent stopped early ({type(exc).__name__})")
        return None, []

    urls: list[str] = []
    for msg in result.get("messages", []):
        if isinstance(msg, ToolMessage):
            urls += urls_in(str(msg.content))
    return result.get("structured_response"), urls
