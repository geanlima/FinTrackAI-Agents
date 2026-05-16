from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.memory_tool_factory import criar_ferramentas_memoria
from core.config import ANTHROPIC_API_KEY, MODEL_AGENTS
from tools.db_tools import (
    buscar_gastos_por_categoria,
    buscar_historico_meses,
    buscar_lancamentos_recentes,
    buscar_resumo_mensal,
    buscar_top_gastos,
)

GASTOS_SYSTEM = """Você é o agente de gastos do FinTrack AI.

Período de referência da conversa: mês {mes}, ano {ano}.
As ferramentas de período já consultam esse mês/ano automaticamente.

Regras:
- Use as ferramentas para obter dados reais antes de responder.
- Ao apresentar gastos por categoria, SEMPRE mostre subcategorias indentadas sob cada categoria.
- Formate valores como R$ X.XXX,XX (padrão brasileiro).
- Responda em português do Brasil.
- Padrão Self-RAG: escolha só as ferramentas necessárias para a pergunta.

Exemplo de formatação:
Alimentação: R$ 850,00
  • Supermercado: R$ 600,00
  • Restaurante: R$ 250,00
"""


def build_gastos_agent(mes: int, ano: int, usuario_id: str):
    @tool
    def buscar_resumo_mensal_tool() -> str:
        f"""Total de receitas, despesas, saldo e lançamentos de gasto em {mes}/{ano}."""
        return buscar_resumo_mensal(mes, ano)

    @tool
    def buscar_gastos_por_categoria_tool() -> str:
        f"""Gastos de {mes}/{ano} por categoria e subcategoria (JSON hierárquico)."""
        return buscar_gastos_por_categoria(mes, ano)

    @tool
    def buscar_lancamentos_recentes_tool(limite: int = 10) -> str:
        f"""Últimos lançamentos de {mes}/{ano} com categoria e subcategoria."""
        return buscar_lancamentos_recentes(mes, ano, limite)

    @tool
    def buscar_top_gastos_tool(limite: int = 5) -> str:
        f"""Maiores despesas de {mes}/{ano} com categoria e subcategoria."""
        return buscar_top_gastos(mes, ano, limite)

    @tool
    def buscar_historico_meses_tool(quantidade: int = 6) -> str:
        """Evolução de receitas/despesas/saldo dos últimos N meses."""
        return buscar_historico_meses(quantidade)

    tools = [
        buscar_resumo_mensal_tool,
        buscar_gastos_por_categoria_tool,
        buscar_lancamentos_recentes_tool,
        buscar_top_gastos_tool,
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
        state_modifier=GASTOS_SYSTEM.format(mes=mes, ano=ano),
    )
