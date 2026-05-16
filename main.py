import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from agents.compra_agent import build_compra_agent
from agents.gastos_agent import build_gastos_agent
from agents.geral_agent import build_geral_agent
from agents.investimentos_agent import build_investimentos_agent
from agents.precos_agent import build_precos_agent
from agents.supervisor import classificar_intencao
from core.database import get_conn, init_memory_tables
from tools.db_tools import buscar_resumo_mensal, buscar_total_gasto_mes


class MensagemHistorico(BaseModel):
    role: str = "user"
    content: str = ""


class ChatRequest(BaseModel):
    mensagem: str
    historico: list[MensagemHistorico] = Field(default_factory=list)
    usuario_id: str = "default"
    mes: int | None = None
    ano: int | None = None


def extrair_texto_chunk(chunk) -> str:
    if chunk is None:
        return ""
    c = getattr(chunk, "content", None)
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        partes: list[str] = []
        for bloco in c:
            if isinstance(bloco, dict) and bloco.get("type") == "text":
                partes.append(str(bloco.get("text", "")))
            elif hasattr(bloco, "text"):
                partes.append(str(getattr(bloco, "text", "") or ""))
        return "".join(partes)
    return str(c)


def montar_mensagens(historico: list[MensagemHistorico], mensagem: str) -> list[BaseMessage]:
    msgs: list[BaseMessage] = []
    for h in historico:
        role = (h.role or "user").lower()
        conteudo = h.content or ""
        if role == "assistant":
            msgs.append(AIMessage(content=conteudo))
        else:
            msgs.append(HumanMessage(content=conteudo))
    msgs.append(HumanMessage(content=mensagem))
    return msgs


def obter_agente(destino: str, mes: int, ano: int, usuario_id: str):
    builders = {
        "gastos": build_gastos_agent,
        "investimentos": build_investimentos_agent,
        "precos": build_precos_agent,
        "compra": build_compra_agent,
        "geral": build_geral_agent,
    }
    fn = builders.get(destino, build_geral_agent)
    return fn(mes, ano, usuario_id)


async def stream_tokens_grafo(agent, messages: list[BaseMessage]) -> AsyncIterator[str]:
    entrada = {"messages": messages}
    async for ev in agent.astream_events(entrada, version="v2"):
        if ev.get("event") != "on_chat_model_stream":
            continue
        chunk = ev.get("data", {}).get("chunk")
        texto = extrair_texto_chunk(chunk)
        if texto:
            yield texto


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_memory_tables()
    except Exception:
        pass
    yield


app = FastAPI(title="Vox Finance IA — Agentes", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.post("/agentes/chat")
async def chat(body: ChatRequest):
    mes = body.mes or datetime.now().month
    ano = body.ano or datetime.now().year

    async def gerar():
        try:
            destino = await classificar_intencao(body.mensagem)
            yield (
                "data: "
                + json.dumps({"tipo": "agente", "conteudo": destino}, ensure_ascii=False)
                + "\n\n"
            )

            agente = obter_agente(destino, mes, ano, body.usuario_id)
            mensagens = montar_mensagens(body.historico, body.mensagem)

            async for trecho in stream_tokens_grafo(agente, mensagens):
                yield (
                    "data: "
                    + json.dumps({"tipo": "token", "conteudo": trecho}, ensure_ascii=False)
                    + "\n\n"
                )
        except Exception as ex:
            yield (
                "data: "
                + json.dumps({"tipo": "erro", "conteudo": str(ex)}, ensure_ascii=False)
                + "\n\n"
            )
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/dados/resumo-mensal")
async def resumo_mensal(mes: int | None = None, ano: int | None = None):
    """Resumo do mês (mesma query do app). Útil para validar no Swagger."""
    m = mes or datetime.now().month
    a = ano or datetime.now().year
    return json.loads(buscar_resumo_mensal(m, a))


@app.get("/dados/total-gasto-mes")
async def total_gasto_mes(mes: int | None = None, ano: int | None = None):
    """Total de despesas do mês (query canônica do FinTrack)."""
    m = mes or datetime.now().month
    a = ano or datetime.now().year
    total = buscar_total_gasto_mes(m, a)
    return {"mes": m, "ano": a, "total_gasto_mes": total}


@app.get("/health")
async def health():
    postgres_ok = False
    total_lancamentos = 0
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM lancamentos")
            total_lancamentos = int(cur.fetchone()[0])
            postgres_ok = True
    except Exception:
        pass

    status = "ok" if postgres_ok else "degraded"
    return {
        "status": status,
        "postgres": postgres_ok,
        "total_lancamentos": total_lancamentos,
    }
