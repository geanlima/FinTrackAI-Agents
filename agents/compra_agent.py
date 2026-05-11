from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.memory_tool_factory import criar_ferramentas_memoria
from core.config import ANTHROPIC_API_KEY, MODEL_AGENTS
from tools.db_tools import (
    buscar_contas_pendentes,
    buscar_gastos_por_categoria,
    buscar_resumo_mensal,
)
from tools.search_tools import buscar_precos

COMPRA_SYSTEM = """Você é o agente de decisão de compra do FinTrack AI.

Período de referência: mês {mes}, ano {ano}.

Padrão Plan-and-Execute:
1) Entenda o produto ou valor envolvido.
2) Consulte resumo do mês e contas pendentes.
3) Se útil, veja gastos por categoria para sugerir onde cortar.
4) Se o preço não for informado, use buscar_precos para estimar.

Sua resposta deve incluir:
- Saldo (receitas - despesas) do período quando relevante
- Contas pendentes críticas
- Maior categoria de gasto se for sugerir corte
- Recomendação explícita: PODE comprar / NÃO PODE comprar / CUIDADO (com justificativa)

Responda em português do Brasil. Valores em R$ X.XXX,XX.
"""


def build_compra_agent(mes: int, ano: int, usuario_id: str):
    @tool
    def buscar_resumo_mensal_tool(m: int, a: int) -> str:
        """Receitas, despesas e saldo do mês."""
        return buscar_resumo_mensal(m, a)

    @tool
    def buscar_contas_pendentes_tool() -> str:
        """Contas a pagar em aberto com vencimento."""
        return buscar_contas_pendentes()

    @tool
    def buscar_gastos_por_categoria_tool(m: int, a: int) -> str:
        """Despesas por categoria e subcategoria para identificar onde reduzir."""
        return buscar_gastos_por_categoria(m, a)

    @tool
    async def buscar_precos_tool(produto: str) -> str:
        """Preço de mercado do produto quando o valor não foi informado."""
        return await buscar_precos(produto)

    tools = [
        buscar_resumo_mensal_tool,
        buscar_contas_pendentes_tool,
        buscar_gastos_por_categoria_tool,
        buscar_precos_tool,
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
        state_modifier=COMPRA_SYSTEM.format(mes=mes, ano=ano),
    )
