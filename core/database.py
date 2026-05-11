import psycopg2

from core.config import POSTGRES_URL

MEMORY_DDL = """
CREATE TABLE IF NOT EXISTS agente_sessoes (
    id SERIAL PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    resumo TEXT NOT NULL,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agente_fatos (
    id SERIAL PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    chave TEXT NOT NULL,
    valor TEXT NOT NULL,
    atualizado_em TIMESTAMP DEFAULT NOW(),
    UNIQUE(usuario_id, chave)
);
"""


def get_conn():
    if not POSTGRES_URL:
        raise RuntimeError("POSTGRES_URL não configurado.")
    return psycopg2.connect(POSTGRES_URL)


def init_memory_tables() -> None:
    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(MEMORY_DDL)
