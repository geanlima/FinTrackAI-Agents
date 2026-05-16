import json
from calendar import monthrange
from datetime import datetime

from core.database import get_conn


def periodo_timestamps(mes: int, ano: int) -> tuple[str, str]:
    """Limites do mês como TIMESTAMP (mesma regra do app / Swagger)."""
    _, ultimo_dia = monthrange(ano, mes)
    inicio = f"{ano}-{mes:02d}-01 00:00:00"
    fim = f"{ano}-{mes:02d}-{ultimo_dia:02d} 23:59:59"
    return inicio, fim


def periodo_mes(mes: int, ano: int) -> tuple[int, int]:
    """Retorna (inicio_ms, fim_ms) via EXTRACT(EPOCH) no PostgreSQL."""
    inicio_ts, fim_ts = periodo_timestamps(mes, ano)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              (EXTRACT(EPOCH FROM TIMESTAMP %s) * 1000)::bigint,
              (EXTRACT(EPOCH FROM TIMESTAMP %s) * 1000)::bigint
            """,
            (inicio_ts, fim_ts),
        )
        row = cur.fetchone()
        return int(row[0]), int(row[1])


_SQL_FILTRO_PERIODO = """
  AND data_hora >= (EXTRACT(EPOCH FROM TIMESTAMP %s) * 1000)::bigint
  AND data_hora <= (EXTRACT(EPOCH FROM TIMESTAMP %s) * 1000)::bigint
"""

_SQL_FILTRO_PERIODO_L = """
  AND l.data_hora >= (EXTRACT(EPOCH FROM TIMESTAMP %s) * 1000)::bigint
  AND l.data_hora <= (EXTRACT(EPOCH FROM TIMESTAMP %s) * 1000)::bigint
"""


def ts_para_data(ts_ms: int) -> str:
    if not ts_ms:
        return ""
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%d/%m/%Y")


def buscar_total_gasto_mes(mes: int, ano: int) -> float:
    """Total de despesas do mês (mesma query do app)."""
    inicio_ts, fim_ts = periodo_timestamps(mes, ano)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT COALESCE(SUM(valor), 0) AS total_gasto_mes
            FROM lancamentos
            WHERE tipo_movimento = 1
              AND pago = 1
              AND COALESCE(pagamento_fatura, 0) = 0
            {_SQL_FILTRO_PERIODO}
            """,
            (inicio_ts, fim_ts),
        )
        return float(cur.fetchone()[0])


def buscar_resumo_mensal(mes: int, ano: int) -> str:
    """Total de receitas, despesas e saldo do período."""
    inicio_ts, fim_ts = periodo_timestamps(mes, ano)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                COALESCE(SUM(valor) FILTER (WHERE tipo_movimento = 2), 0) AS receitas,
                COALESCE(
                    SUM(valor) FILTER (
                        WHERE tipo_movimento = 1
                          AND COALESCE(pagamento_fatura, 0) = 0
                    ),
                    0
                ) AS despesas,
                COUNT(*) FILTER (
                    WHERE tipo_movimento = 1
                      AND COALESCE(pagamento_fatura, 0) = 0
                ) AS total_lancamentos_gasto
            FROM lancamentos
            WHERE pago = 1
            {_SQL_FILTRO_PERIODO}
            """,
            (inicio_ts, fim_ts),
        )
        row = cur.fetchone()
        receitas = float(row[0])
        despesas = float(row[1])
        return json.dumps(
            {
                "mes": mes,
                "ano": ano,
                "receitas": receitas,
                "despesas": despesas,
                "total_gasto_mes": despesas,
                "saldo": receitas - despesas,
                "total_lancamentos": row[2],
            },
            ensure_ascii=False,
        )


def buscar_gastos_por_categoria(mes: int, ano: int) -> str:
    """
    Gastos agrupados por categoria COM subcategorias detalhadas.
    """
    inicio_ts, fim_ts = periodo_timestamps(mes, ano)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                COALESCE(c.nome, 'Sem categoria')  AS categoria,
                COALESCE(s.nome, 'Sem subcategoria') AS subcategoria,
                SUM(l.valor)                        AS total
            FROM lancamentos l
            LEFT JOIN categorias_personalizadas c
                ON l.id_categoria_personalizada = c.id
                AND l.id_categoria_personalizada > 0
            LEFT JOIN subcategorias_personalizadas s
                ON l.id_subcategoria_personalizada = s.id
                AND l.id_subcategoria_personalizada > 0
            WHERE l.tipo_movimento = 1
              AND l.pago = 1
              AND COALESCE(l.pagamento_fatura, 0) = 0
            {_SQL_FILTRO_PERIODO_L}
            GROUP BY c.nome, s.nome
            ORDER BY SUM(l.valor) DESC
            """,
            (inicio_ts, fim_ts),
        )
        rows = cur.fetchall()

    categorias: dict = {}
    for categoria, subcategoria, total in rows:
        if categoria not in categorias:
            categorias[categoria] = {
                "categoria": categoria,
                "total": 0.0,
                "subcategorias": [],
            }
        categorias[categoria]["total"] += float(total)
        if subcategoria and subcategoria != "Sem subcategoria":
            categorias[categoria]["subcategorias"].append(
                {"nome": subcategoria, "total": float(total)}
            )

    resultado = sorted(categorias.values(), key=lambda x: x["total"], reverse=True)
    for cat in resultado:
        cat["subcategorias"].sort(key=lambda x: x["total"], reverse=True)

    return json.dumps(resultado, ensure_ascii=False)


def buscar_lancamentos_recentes(mes: int, ano: int, limite: int = 10) -> str:
    """Últimos lançamentos do período com categoria e subcategoria."""
    inicio_ts, fim_ts = periodo_timestamps(mes, ano)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                l.descricao,
                l.valor,
                l.data_hora,
                l.tipo_movimento,
                COALESCE(c.nome, 'Sem categoria')    AS categoria,
                COALESCE(s.nome, 'Sem subcategoria') AS subcategoria
            FROM lancamentos l
            LEFT JOIN categorias_personalizadas c
                ON l.id_categoria_personalizada = c.id
                AND l.id_categoria_personalizada > 0
            LEFT JOIN subcategorias_personalizadas s
                ON l.id_subcategoria_personalizada = s.id
                AND l.id_subcategoria_personalizada > 0
            WHERE l.pago = 1
            {_SQL_FILTRO_PERIODO_L}
            ORDER BY l.data_hora DESC
            LIMIT %s
            """,
            (inicio_ts, fim_ts, limite),
        )
        rows = cur.fetchall()

    resultado = [
        {
            "descricao": r[0],
            "valor": float(r[1]),
            "data": ts_para_data(r[2]),
            "tipo": "receita" if r[3] == 2 else "despesa",
            "categoria": r[4],
            "subcategoria": r[5],
        }
        for r in rows
    ]
    return json.dumps(resultado, ensure_ascii=False)


def buscar_contas_pendentes() -> str:
    """Contas a pagar não pagas com dias até vencimento."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT descricao, valor, data_vencimento
            FROM conta_pagar
            WHERE pago = 0
            ORDER BY data_vencimento ASC
            """
        )
        rows = cur.fetchall()

    hoje_ms = int(datetime.now().timestamp() * 1000)
    resultado = []
    for r in rows:
        venc_ms = r[2] or 0
        dias = int((venc_ms - hoje_ms) / (1000 * 60 * 60 * 24))
        status = (
            "vencida"
            if dias < 0
            else "vence hoje" if dias == 0 else f"vence em {dias} dias"
        )
        resultado.append(
            {
                "descricao": r[0],
                "valor": float(r[1]),
                "vencimento": ts_para_data(venc_ms),
                "dias_ate_vencimento": dias,
                "status": status,
            }
        )
    return json.dumps(resultado, ensure_ascii=False)


def buscar_historico_meses(quantidade: int = 6) -> str:
    """Evolução financeira dos últimos N meses."""
    hoje = datetime.now()
    resultado = []
    for k in range(quantidade - 1, -1, -1):
        total_meses_idx = hoje.year * 12 + hoje.month - 1 - k
        ano_offset = total_meses_idx // 12
        mes_offset = total_meses_idx % 12 + 1
        dados = json.loads(buscar_resumo_mensal(mes_offset, ano_offset))
        resultado.append(dados)
    return json.dumps(resultado, ensure_ascii=False)


def buscar_top_gastos(mes: int, ano: int, limite: int = 5) -> str:
    """Top N maiores gastos do período com categoria e subcategoria."""
    inicio_ts, fim_ts = periodo_timestamps(mes, ano)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                l.descricao,
                l.valor,
                COALESCE(c.nome, 'Sem categoria')    AS categoria,
                COALESCE(s.nome, 'Sem subcategoria') AS subcategoria,
                l.data_hora
            FROM lancamentos l
            LEFT JOIN categorias_personalizadas c
                ON l.id_categoria_personalizada = c.id
                AND l.id_categoria_personalizada > 0
            LEFT JOIN subcategorias_personalizadas s
                ON l.id_subcategoria_personalizada = s.id
                AND l.id_subcategoria_personalizada > 0
            WHERE l.tipo_movimento = 1
              AND l.pago = 1
              AND COALESCE(l.pagamento_fatura, 0) = 0
            {_SQL_FILTRO_PERIODO_L}
            ORDER BY l.valor DESC
            LIMIT %s
            """,
            (inicio_ts, fim_ts, limite),
        )
        rows = cur.fetchall()

    resultado = [
        {
            "descricao": r[0],
            "valor": float(r[1]),
            "categoria": r[2],
            "subcategoria": r[3],
            "data": ts_para_data(r[4]),
        }
        for r in rows
    ]
    return json.dumps(resultado, ensure_ascii=False)


def buscar_investimentos() -> str:
    """Carteiras de investimento com saldo calculado."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                w.nome,
                COALESCE(SUM(
                    CASE WHEN m.tipo = 1 THEN m.valor ELSE -m.valor END
                ), 0) AS saldo,
                COUNT(m.id) AS num_movimentos
            FROM investimento_carteiras w
            LEFT JOIN investimento_cdi_movimentos m ON m.id_carteira = w.id
            GROUP BY w.id, w.nome
            ORDER BY saldo DESC
            """
        )
        rows = cur.fetchall()

    resultado = [
        {
            "carteira": r[0],
            "saldo": float(r[1]),
            "num_movimentos": r[2],
        }
        for r in rows
    ]
    return json.dumps(resultado, ensure_ascii=False)
