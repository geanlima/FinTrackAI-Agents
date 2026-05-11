from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage


def _chunk_text(chunk: AIMessageChunk) -> str:
    c = chunk.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for p in c:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and p.get("type") == "text":
                parts.append(p.get("text", ""))
        return "".join(parts)
    return ""


async def stream_agent_tokens(
    graph: Any, messages: list[BaseMessage]
) -> AsyncIterator[str]:
    """Emite texto incremental do modelo durante o ReAct."""
    async for event in graph.astream_events(
        {"messages": messages},
        version="v2",
    ):
        if event.get("event") != "on_chat_model_stream":
            continue
        chunk = event.get("data", {}).get("chunk")
        if not isinstance(chunk, AIMessageChunk):
            continue
        text = _chunk_text(chunk)
        if text:
            yield text


def build_lc_messages(
    historico: list[dict], mensagem: str, usuario_id: str, mes: int, ano: int
) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for h in historico:
        role = h.get("role")
        content = h.get("content", "")
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
    ctx = (
        f"[Contexto automático] usuario_id={usuario_id}, período financeiro: "
        f"mês {mes}, ano {ano}.\nPergunta atual:\n{mensagem}"
    )
    out.append(HumanMessage(content=ctx))
    return out
