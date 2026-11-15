"""OpenRouter-backed chat models plus a structured-output helper that tolerates open models."""

import json
import logging
import re
from typing import Any, Literal

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

log = logging.getLogger(__name__)


def get_llm(kind: Literal["fast", "agent"]) -> ChatOpenAI:
    settings = get_settings()
    model = settings.llm_model_fast if kind == "fast" else settings.llm_model_agent
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0,
        timeout=settings.llm_timeout_s,
        max_retries=2,
        default_headers={"HTTP-Referer": "https://biasbuster.app", "X-Title": "biasBuster"},
        # Ask OpenRouter to include the cost of each call in the usage block.
        extra_body={"usage": {"include": True}},
    )


class UsageTracker(AsyncCallbackHandler):
    """Accumulates token usage and OpenRouter cost across every LLM call of an analysis."""

    def __init__(self) -> None:
        self.cost_usd = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        usage = (response.llm_output or {}).get("token_usage") or {}
        if not usage:
            for gens in response.generations:
                for gen in gens:
                    msg = getattr(gen, "message", None)
                    meta = getattr(msg, "response_metadata", {}) or {}
                    usage = meta.get("token_usage") or usage
        self.prompt_tokens += usage.get("prompt_tokens") or 0
        self.completion_tokens += usage.get("completion_tokens") or 0
        self.cost_usd += float(usage.get("cost") or 0)


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


async def structured[T: BaseModel](
    kind: Literal["fast", "agent"],
    schema: type[T],
    system: str,
    user: str,
    config: RunnableConfig | None = None,
) -> T:
    """Return `schema` from the model. Tries native JSON-schema output, then falls back to
    plain JSON prompting with validation feedback (many open models are flaky at the former)."""
    llm = get_llm(kind)
    messages: list[BaseMessage] = [SystemMessage(system), HumanMessage(user)]
    try:
        result = await llm.with_structured_output(schema, method="json_schema").ainvoke(
            messages, config=config
        )
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)
    except Exception as exc:
        log.info("json_schema output failed (%s), falling back to prompted JSON", exc)

    schema_json = json.dumps(schema.model_json_schema())
    prompt = [
        SystemMessage(
            f"{system}\n\nRespond ONLY with a JSON object that validates against this JSON "
            f"schema, with no prose and no markdown fences:\n{schema_json}"
        ),
        HumanMessage(user),
    ]
    last_error: Exception | None = None
    for _ in range(2):
        reply = await llm.ainvoke(prompt, config=config)
        content = reply.content if isinstance(reply.content, str) else str(reply.content)
        match = _JSON_BLOCK.search(content)
        try:
            return schema.model_validate_json(match.group(0) if match else content)
        except (ValidationError, ValueError) as exc:
            last_error = exc
            prompt += [
                reply,
                HumanMessage(f"That JSON was invalid: {exc}. Return corrected JSON only."),
            ]
    raise RuntimeError(f"Model did not return valid {schema.__name__}: {last_error}")
