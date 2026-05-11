from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.memory_tool_factory import criar_ferramentas_memoria
from core.config import ANTHROPIC_API_KEY, MODEL_AGENTS
from tools.db_tools import buscar_investimentos
from tools.search_tools import buscar_noticias_investimento

INVEST_SYSTEM = """Você é o agente de investimentos do FinTrack AI.

Período de referência: mês {mes}, ano {ano}.

Regras:
- Use buscar_investimentos para dados reais das carteiras no banco.
- Use buscar_noticias_investimento para contexto de mercado (notícias recentes).
- Padrão Corrective RAG: se os dados do banco forem vazios ou estranhos, diga claramente.
- Sempre inclua no final: "Isso não é recomendação financeira profissional."
- Responda em português do Brasil. Formate valores como R$ X.XXX,XX.
"""


def build_investimentos_agent(mes: int, ano: int, usuario_id: str):
    @tool
    def buscar_investimentos_tool() -> str:
        """Carteiras cadastradas com saldo agregado e número de movimentos."""
        return buscar_investimentos()

    @tool
    async def buscar_noticias_investimento_tool(tipo: str) -> str:
        """Busca notícias recentes. Parâmetro tipo: ex. 'CDB', 'ações', 'Tesouro', 'fundos imobiliários'."""
        return await buscar_noticias_investimento(tipo)

    tools = [
        buscar_investimentos_tool,
        buscar_noticias_investimento_tool,
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
        state_modifier=INVEST_SYSTEM.format(mes=mes, ano=ano),
    )
