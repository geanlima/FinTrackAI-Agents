from langchain_core.tools import tool

from tools.memory_tools import buscar_fatos_agente, salvar_fato_agente


def criar_ferramentas_memoria(usuario_id: str):
    @tool
    def salvar_fato_memoria(chave: str, valor: str) -> str:
        """Salva um fato sobre preferências ou contexto do usuário na memória persistente."""
        return salvar_fato_agente(usuario_id, chave, valor)

    @tool
    def buscar_fatos_memoria() -> str:
        """Recupera fatos salvos anteriormente para este usuário."""
        return buscar_fatos_agente(usuario_id)

    return [salvar_fato_memoria, buscar_fatos_memoria]
