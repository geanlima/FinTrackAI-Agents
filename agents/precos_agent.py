from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.memory_tool_factory import criar_ferramentas_memoria
from core.config import ANTHROPIC_API_KEY, MODEL_AGENTS
from tools.db_tools import buscar_resumo_mensal
from tools.search_tools import buscar_precos

PRECOS_SYSTEM = """Você é o agente de preços do FinTrack AI.

Período financeiro de referência: mês {mes}, ano {ano}.

Regras:
- Extraia o nome do produto da pergunta e use buscar_precos.
- Opcionalmente use buscar_resumo_mensal para ver se o orçamento do mês comporta o gasto.
- Liste até 5 ofertas com nome, preço, loja e link quando disponíveis.
- Responda em português do Brasil.
"""


def build_precos_agent(mes: int, ano: int, usuario_id: str):
    @tool
    async def buscar_precos_tool(produto: str) -> str:
        """Busca preços em lojas brasileiras (Serper Shopping)."""
        return await buscar_precos(produto)

    @tool
    def buscar_resumo_mensal_tool() -> str:
        """Resumo financeiro do período de referência (receitas, despesas, saldo)."""
        return buscar_resumo_mensal(mes, ano)

    tools = [
        buscar_precos_tool,
        buscar_resumo_mensal_tool,
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
        state_modifier=PRECOS_SYSTEM.format(mes=mes, ano=ano),
    )
