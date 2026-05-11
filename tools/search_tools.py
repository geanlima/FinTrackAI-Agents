import json
import os

import httpx

SERPER_KEY = os.environ.get("SERPER_API_KEY")


async def buscar_precos(produto: str) -> str:
    """Busca preços em lojas brasileiras via Serper Shopping."""
    if not SERPER_KEY:
        return json.dumps({"erro": "SERPER_API_KEY não configurada"}, ensure_ascii=False)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://google.serper.dev/shopping",
            headers={"X-API-KEY": SERPER_KEY},
            json={"q": produto, "gl": "br", "hl": "pt-br", "num": 8},
        )
        r.raise_for_status()
        itens = r.json().get("shopping", [])[:5]
    resultado = [
        {
            "nome": i.get("title", ""),
            "preco": i.get("price", ""),
            "loja": i.get("source", ""),
            "link": i.get("link", ""),
        }
        for i in itens
    ]
    return json.dumps(resultado, ensure_ascii=False)


async def buscar_noticias_investimento(tipo: str) -> str:
    """Busca notícias financeiras atuais via Serper."""
    if not SERPER_KEY:
        return json.dumps({"erro": "SERPER_API_KEY não configurada"}, ensure_ascii=False)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": SERPER_KEY},
            json={
                "q": f"{tipo} investimento brasil 2026",
                "gl": "br",
                "hl": "pt-br",
                "num": 5,
            },
        )
        r.raise_for_status()
        noticias = r.json().get("news", [])[:4]
    resultado = [
        {
            "titulo": n.get("title", ""),
            "fonte": n.get("source", ""),
            "data": n.get("date", ""),
            "resumo": n.get("snippet", ""),
        }
        for n in noticias
    ]
    return json.dumps(resultado, ensure_ascii=False)
