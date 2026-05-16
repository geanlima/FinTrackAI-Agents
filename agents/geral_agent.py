from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.memory_tool_factory import criar_ferramentas_memoria
from core.config import ANTHROPIC_API_KEY, MODEL_AGENTS
from tools.db_tools import (
    buscar_contas_pendentes,
    buscar_historico_meses,
    buscar_lancamentos_recentes,
    buscar_resumo_mensal,
)

GERAL_SYSTEM = """Você é o agente geral do FinTrack AI (resumo, saldo, contas, visão ampla).

Período de referência: mês {mes}, ano {ano}. Ferramentas de período já usam esse mês/ano.

Regras:
- Use ferramentas para dados reais.
- Responda em português do Brasil. Formate valores como R$ X.XXX,XX.
"""


def build_geral_agent(mes: int, ano: int, usuario_id: str):
    @tool
    def buscar_resumo_mensal_tool() -> str:
        f"""Resumo de receitas, despesas e saldo de {mes}/{ano}."""
        return buscar_resumo_mensal(mes, ano)

    @tool
    def buscar_contas_pendentes_tool() -> str:
        """Contas a pagar não quitadas."""
        return buscar_contas_pendentes()

    @tool
    def buscar_lancamentos_recentes_tool(limite: int = 10) -> str:
        f"""Lançamentos recentes de {mes}/{ano} com categoria e subcategoria."""
        return buscar_lancamentos_recentes(mes, ano, limite)

    @tool
    def buscar_historico_meses_tool(quantidade: int = 6) -> str:
        """Histórico dos últimos N meses."""
        return buscar_historico_meses(quantidade)

    tools = [
        buscar_resumo_mensal_tool,
        buscar_contas_pendentes_tool,
        buscar_lancamentos_recentes_tool,
        buscar_historico_meses_tool,
        *criar_ferramentas_memoria(usuario_id),
    ]
    model = ChatAnthropic(
        model=MODEL_AGENTS,
        api_key=ANTHROPIC_API_KEY,
        temperature=0.2,
    )
    return create_react_agent(
        model,
        tools,
        state_modifier=GERAL_SYSTEM.format(mes=mes, ano=ano),
    )
