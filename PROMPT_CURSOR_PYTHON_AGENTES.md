# PROMPT CURSOR — Microsserviço Python — Agentes FinTrack AI

## CONTEXTO

O FinTrack AI já tem uma API .NET Web API funcionando com Clean Architecture.
Preciso de um **microsserviço Python** pequeno que roda na porta 8001
e expõe apenas um endpoint: `POST /agentes/chat`

O .NET chama esse endpoint internamente. O Angular não sabe que existe.

---

## RESPONSABILIDADE DESTE SERVIÇO

Apenas processar mensagens via agentes LangGraph especializados.
Sem autenticação, sem CRUD, sem banco próprio além de memória do agente.

---

## STACK

- Python 3.12
- FastAPI + Uvicorn (porta 8001)
- LangGraph + LangChain Anthropic
- psycopg2 para ler PostgreSQL existente (porta 5434)
- httpx para Serper API
- python-dotenv

---

## BANCO DE DADOS — PostgreSQL existente (porta 5434)

O banco `fintrack` já existe com dados reais migrados do Vox Finance.
**Nunca escrever nas tabelas de dados — somente leitura.**
Criar tabelas próprias de memória do agente no mesmo banco.

### Tabelas de dados (somente leitura):
```sql
lancamentos (id, descricao, valor, data_hora, tipo_movimento,
             pago, id_categoria_personalizada,
             id_subcategoria_personalizada)

categorias_personalizadas (id, nome, tipo_movimento)

subcategorias_personalizadas (id, id_categoria_personalizada, nome)

conta_pagar (id, descricao, valor, data_vencimento, pago)

investimento_carteiras (id, nome)

investimento_cdi_movimentos (id, id_carteira, tipo, valor, data)
```

### Tabelas de memória (criar se não existir):
```sql
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
```

---

## ESTRUTURA DO PROJETO

```
vox-finance-ia-agentes/
├── main.py
├── .env
├── requirements.txt
├── agents/
│   ├── supervisor.py
│   ├── gastos_agent.py
│   ├── investimentos_agent.py
│   ├── precos_agent.py
│   └── compra_agent.py
├── tools/
│   ├── db_tools.py        ← consultas PostgreSQL somente leitura
│   ├── search_tools.py    ← Serper API
│   └── memory_tools.py    ← memória do agente
└── core/
    ├── config.py
    └── database.py
```

---

## .env

```
ANTHROPIC_API_KEY=sua_chave
SERPER_API_KEY=sua_chave_serper
POSTGRES_URL=postgresql://postgres:postgres@localhost:5434/fintrack
```

---

## ÚNICO ENDPOINT

### POST /agentes/chat

```python
# Request:
{
  "mensagem": "quanto gastei esse mês?",
  "historico": [
    {"role": "user", "content": "oi"},
    {"role": "assistant", "content": "Olá!"}
  ],
  "usuario_id": "usuario_1",
  "mes": 5,
  "ano": 2026
}

# Response: Server-Sent Events (SSE)
# data: {"tipo": "token", "conteudo": "Seus gastos..."}
# data: {"tipo": "agente", "conteudo": "gastos"}
# data: {"tipo": "fim", "conteudo": ""}
# data: [DONE]
```

---

## FERRAMENTAS DO BANCO (db_tools.py)

```python
import psycopg2
import json
from datetime import datetime
import os

POSTGRES_URL = os.environ.get("POSTGRES_URL")

def get_conn():
    return psycopg2.connect(POSTGRES_URL)

def buscar_resumo_mensal(mes: int, ano: int) -> str:
    """Total receitas, despesas e saldo do período."""
    with get_conn() as conn:
        cur = conn.cursor()
        # data_hora é timestamp em milissegundos
        inicio = int(datetime(ano, mes, 1).timestamp() * 1000)
        from calendar import monthrange
        _, ultimo = monthrange(ano, mes)
        fim = int(datetime(ano, mes, ultimo, 23, 59, 59).timestamp() * 1000)

        cur.execute("""
            SELECT
                SUM(CASE WHEN tipo_movimento = 2 THEN valor ELSE 0 END) as receitas,
                SUM(CASE WHEN tipo_movimento = 1 THEN valor ELSE 0 END) as despesas
            FROM lancamentos
            WHERE data_hora BETWEEN %s AND %s AND pago = 1
        """, (inicio, fim))
        row = cur.fetchone()
        receitas = float(row[0] or 0)
        despesas = float(row[1] or 0)
        return json.dumps({
            "mes": mes, "ano": ano,
            "receitas": receitas,
            "despesas": despesas,
            "saldo": receitas - despesas
        })

def buscar_gastos_por_categoria(mes: int, ano: int) -> str:
    """Gastos por categoria e subcategoria."""
    with get_conn() as conn:
        cur = conn.cursor()
        inicio = int(datetime(ano, mes, 1).timestamp() * 1000)
        from calendar import monthrange
        _, ultimo = monthrange(ano, mes)
        fim = int(datetime(ano, mes, ultimo, 23, 59, 59).timestamp() * 1000)

        cur.execute("""
            SELECT
                c.nome as categoria,
                s.nome as subcategoria,
                SUM(l.valor) as total
            FROM lancamentos l
            LEFT JOIN categorias_personalizadas c
                ON l.id_categoria_personalizada = c.id
            LEFT JOIN subcategorias_personalizadas s
                ON l.id_subcategoria_personalizada = s.id
            WHERE l.data_hora BETWEEN %s AND %s
              AND l.tipo_movimento = 1
              AND l.pago = 1
            GROUP BY c.nome, s.nome
            ORDER BY total DESC
        """, (inicio, fim))
        rows = cur.fetchall()
        resultado = [
            {"categoria": r[0] or "Sem categoria",
             "subcategoria": r[1] or "",
             "total": float(r[2])}
            for r in rows
        ]
        return json.dumps(resultado, ensure_ascii=False)

def buscar_contas_pendentes() -> str:
    """Contas a pagar não pagas."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT descricao, valor, data_vencimento
            FROM conta_pagar
            WHERE pago = 0
            ORDER BY data_vencimento ASC
        """)
        rows = cur.fetchall()
        resultado = []
        for r in rows:
            venc = datetime.fromtimestamp(r[2] / 1000).strftime("%d/%m/%Y") if r[2] else ""
            resultado.append({
                "descricao": r[0],
                "valor": float(r[1]),
                "vencimento": venc
            })
        return json.dumps(resultado, ensure_ascii=False)

def buscar_historico_meses(quantidade: int = 6) -> str:
    """Evolução financeira dos últimos N meses."""
    from datetime import date
    resultado = []
    hoje = date.today()
    for i in range(quantidade - 1, -1, -1):
        mes = (hoje.month - i - 1) % 12 + 1
        ano = hoje.year - ((i - hoje.month + 1) // 12 + 1
                           if i >= hoje.month else 0)
        dados = json.loads(buscar_resumo_mensal(mes, ano))
        resultado.append(dados)
    return json.dumps(resultado)

def buscar_investimentos() -> str:
    """Carteiras e movimentos de investimento."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT w.nome,
                   SUM(CASE WHEN m.tipo = 1 THEN m.valor ELSE -m.valor END) as saldo
            FROM investimento_carteiras w
            LEFT JOIN investimento_cdi_movimentos m ON m.id_carteira = w.id
            GROUP BY w.nome
        """)
        rows = cur.fetchall()
        resultado = [{"carteira": r[0], "saldo": float(r[1] or 0)} for r in rows]
        return json.dumps(resultado, ensure_ascii=False)
```

---

## FERRAMENTAS DE BUSCA (search_tools.py)

```python
import httpx, json, os

SERPER_KEY = os.environ.get("SERPER_API_KEY")

async def buscar_precos(produto: str) -> str:
    """Busca preços em lojas brasileiras via Serper Shopping."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://google.serper.dev/shopping",
            headers={"X-API-KEY": SERPER_KEY},
            json={"q": produto, "gl": "br", "hl": "pt-br", "num": 8}
        )
    dados = r.json()
    itens = dados.get("shopping", [])[:5]
    resultado = [
        {
            "nome":  i.get("title", ""),
            "preco": i.get("price", ""),
            "loja":  i.get("source", ""),
            "link":  i.get("link", "")
        }
        for i in itens
    ]
    return json.dumps(resultado, ensure_ascii=False)

async def buscar_noticias_investimento(tipo: str) -> str:
    """Busca notícias financeiras atuais via Serper."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": SERPER_KEY},
            json={"q": f"{tipo} investimento brasil 2026",
                  "gl": "br", "hl": "pt-br", "num": 5}
        )
    dados = r.json()
    noticias = dados.get("news", [])[:4]
    resultado = [
        {
            "titulo": n.get("title", ""),
            "fonte":  n.get("source", ""),
            "data":   n.get("date", ""),
            "resumo": n.get("snippet", "")
        }
        for n in noticias
    ]
    return json.dumps(resultado, ensure_ascii=False)
```

---

## AGENTES LANGGRAPH

### Estado compartilhado:
```python
class EstadoAgente(TypedDict):
    messages:   Annotated[list, add_messages]
    pergunta:   str
    usuario_id: str
    mes:        int
    ano:        int
    destino:    str   # agente escolhido pelo supervisor
    dados:      str   # resultado das ferramentas
    resposta:   str
```

### Supervisor:
- Usa `claude-haiku-4-5-20251001` para classificar (barato)
- Categorias: `gastos | investimentos | precos | compra | geral`
- Retorna só o nome da categoria

### Agente Gastos:
- Ferramentas: `buscar_resumo_mensal`, `buscar_gastos_por_categoria`,
  `buscar_contas_pendentes`, `buscar_historico_meses`
- Padrão: Self-RAG — decide quais ferramentas usar
- Formata valores como R$ X.XXX,XX

### Agente Investimentos:
- Ferramentas: `buscar_investimentos`, `buscar_noticias_investimento`
- Padrão: Corrective RAG
- Sempre inclui: "Isso não é recomendação financeira profissional"

### Agente Preços:
- Ferramentas: `buscar_precos`, `buscar_resumo_mensal`
- Extrai nome do produto da pergunta
- Lista top 5 com preço, loja e link
- Se pergunta incluir "posso comprar", verifica saldo

### Agente Compra:
- Ferramentas: `buscar_resumo_mensal`, `buscar_contas_pendentes`,
  `buscar_precos`
- Padrão: Plan-and-Execute
- Resposta sempre inclui: saldo, pendentes e recomendação clara

---

## MAIN.PY

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json

app = FastAPI(title="Vox Finance IA — Agentes")

app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5000", "http://localhost:4200"],
    allow_methods=["POST"],
    allow_headers=["*"])

@app.post("/agentes/chat")
async def chat(body: ChatRequest):
    async def gerar():
        # Executa o grafo LangGraph
        # Emite tokens via SSE conforme gera
        # Formato: f"data: {json.dumps(evento)}\n\n"
        # Termina com: "data: [DONE]\n\n"
        pass

    return StreamingResponse(gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache",
                 "X-Accel-Buffering": "no"})

@app.get("/health")
async def health():
    # Verifica conexão com PostgreSQL
    # Retorna status
    pass
```

---

## RESULTADO ESPERADO

Após `python -m uvicorn main:app --reload --port 8001`:

- `http://localhost:8001/health` → `{"status": "ok"}`
- `POST http://localhost:8001/agentes/chat` → SSE com tokens
- O .NET vai chamar este endpoint internamente
