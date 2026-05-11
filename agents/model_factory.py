from langchain_anthropic import ChatAnthropic

from core.config import get_anthropic_api_key

WORKER_MODEL = "claude-sonnet-4-20250514"


def worker_llm():
    return ChatAnthropic(
        model=WORKER_MODEL,
        api_key=get_anthropic_api_key(),
        temperature=0.2,
        max_tokens=4096,
    )
