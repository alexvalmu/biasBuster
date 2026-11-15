import re
from collections.abc import Awaitable, Callable

from langchain_core.runnables import RunnableConfig

ProgressFn = Callable[[str], Awaitable[None]]

_URL = re.compile(r"https?://[^\s\"'<>\\)\]]+")


async def report_progress(config: RunnableConfig, msg: str) -> None:
    fn: ProgressFn | None = (config.get("configurable") or {}).get("progress")
    if fn:
        await fn(msg)


def urls_in(text: str) -> list[str]:
    return [u.rstrip(".,;") for u in _URL.findall(text)]
