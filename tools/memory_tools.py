import json

from core.database import get_conn


def salvar_fato_agente(usuario_id: str, chave: str, valor: str) -> str:
    """Persiste um fato na memória de longo prazo do usuário (somente tabelas agente_*)."""
    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agente_fatos (usuario_id, chave, valor)
                VALUES (%s, %s, %s)
                ON CONFLICT (usuario_id, chave)
                DO UPDATE SET valor = EXCLUDED.valor, atualizado_em = NOW()
                """,
                (usuario_id, chave, valor),
            )
    return json.dumps({"ok": True, "chave": chave}, ensure_ascii=False)


def buscar_fatos_agente(usuario_id: str) -> str:
    """Lista fatos memorizados para o usuário."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chave, valor, atualizado_em
                FROM agente_fatos
                WHERE usuario_id = %s
                ORDER BY atualizado_em DESC
                LIMIT 50
                """,
                (usuario_id,),
            )
            rows = cur.fetchall()
    resultado = [
        {"chave": r[0], "valor": r[1], "atualizado_em": r[2].isoformat() if r[2] else ""}
        for r in rows
    ]
    return json.dumps(resultado, ensure_ascii=False)


def salvar_resumo_sessao(usuario_id: str, resumo: str) -> str:
    """Armazena resumo da sessão (checkpoint leve)."""
    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agente_sessoes (usuario_id, resumo)
                VALUES (%s, %s)
                """,
                (usuario_id, resumo),
            )
    return json.dumps({"ok": True}, ensure_ascii=False)
