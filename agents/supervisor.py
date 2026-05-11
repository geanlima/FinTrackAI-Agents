from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from core.config import ANTHROPIC_API_KEY, MODEL_SUPERVISOR

SUPERVISOR_PROMPT = """Classifique a mensagem do usuário em EXATAMENTE uma categoria:
- gastos: despesas, categorias, subcategorias, quanto gastei, alimentação, gastos por tipo
- investimentos: investir, renda fixa, CDB, onde aplicar, carteira de investimento
- precos: preço de produto, quanto custa, pesquisa de preço em lojas
- compra: posso comprar, devo comprar, cabe no orçamento, vale a pena comprar
- geral: saldo, resumo do mês, contas a pagar, visão geral, receitas e despesas

Responda APENAS com uma palavra: gastos, investimentos, precos, compra ou geral.

Mensagem: {mensagem}"""


def _normalizar(texto: str) -> str:
    t = texto.strip().lower()
    for cat in ("gastos", "investimentos", "precos", "compra", "geral"):
        if cat in t:
            return cat
    return "geral"


async def classificar_intencao(mensagem: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "geral"
    model = ChatAnthropic(
        model=MODEL_SUPERVISOR,
        max_tokens=32,
        api_key=ANTHROPIC_API_KEY,
        temperature=0,
    )
    msg = HumanMessage(content=SUPERVISOR_PROMPT.format(mensagem=mensagem))
    resp = await model.ainvoke([msg])
    raw = resp.content
    if isinstance(raw, str):
        return _normalizar(raw)
    if isinstance(raw, list):
        partes = []
        for bloco in raw:
            if isinstance(bloco, dict) and bloco.get("type") == "text":
                partes.append(bloco.get("text", ""))
        return _normalizar("".join(partes))
    return _normalizar(str(raw))
