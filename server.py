"""MDS Precios — MCP server HTTP (para Railway).

Expone un endpoint HTTP/Streamable-HTTP que Cowork puede conectar como
MCP remoto. La herramienta `buscar_precio_partida` busca en DuckDuckGo
los precios de mercado de una partida de construcción española y
devuelve media, mínimo, máximo y fuentes.
"""

import os
import re
from urllib.parse import quote_plus, parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mds-precios")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36")

PRICE_PATTERNS_M2 = [
    re.compile(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*/?\s*m[²2]', re.IGNORECASE),
    re.compile(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*euros?\s*/?\s*m[²2]', re.IGNORECASE),
    re.compile(r'€\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*/?\s*m[²2]', re.IGNORECASE),
]
PRICE_PATTERNS_UD = [
    re.compile(r'(\d{1,4}(?:[.,]\d{1,2})?)\s*€\s*/?\s*(?:ud|unidad|uds)\b', re.IGNORECASE),
]
PRICE_PATTERNS_ML = [
    re.compile(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*/?\s*(?:ml|m\.?l\.?|metro\s+lineal)', re.IGNORECASE),
]


def extract_prices(text: str, unit: str) -> list:
    patterns = {
        "m2": PRICE_PATTERNS_M2,
        "ud": PRICE_PATTERNS_UD,
        "ml": PRICE_PATTERNS_ML,
    }.get(unit, PRICE_PATTERNS_M2)
    lo, hi = {"m2": (5, 500), "ud": (10, 5000), "ml": (3, 300)}.get(unit, (5, 500))

    out = []
    for pat in patterns:
        for m in pat.finditer(text):
            try:
                p = float(m.group(1).replace(",", "."))
                if lo <= p <= hi:
                    out.append(p)
            except ValueError:
                continue
    return out


async def ddg_search(query: str, num: int = 8) -> list:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        r = await c.post("https://html.duckduckgo.com/html/",
                         data={"q": query}, headers={"User-Agent": UA})
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.select("a.result__a")[:num]:
        href = a.get("href", "")
        parsed = urlparse(href)
        if "duckduckgo.com" in parsed.netloc and "/l/" in parsed.path:
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                href = qs["uddg"][0]
        elif href.startswith("//"):
            href = "https:" + href
        if href.startswith("http"):
            out.append({"title": a.get_text(strip=True), "url": href})
    return out


async def fetch_prices(url: str, unit: str) -> list:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": UA})
        if r.status_code != 200:
            return []
        text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
        return extract_prices(text, unit)
    except Exception:
        return []


@mcp.tool()
async def buscar_precio_partida(partida: str, unidad: str = "m2") -> dict:
    """Busca precios de mercado en España para una partida de construcción.

    Args:
        partida: Descripción breve de la partida (ej: "tabique pladur 15+70+15").
        unidad: "m2", "ud" o "ml". Por defecto "m2".
    """
    query = f"precio {partida} {unidad} España 2026"
    results = await ddg_search(query, num=8)

    all_prices = []
    sources = []
    for r in results:
        prices = await fetch_prices(r["url"], unidad)
        if prices:
            all_prices.extend(prices)
            sources.append({
                "titulo": r["title"],
                "url": r["url"],
                "precios": sorted(set(prices))[:15],
            })

    if not all_prices:
        return {"partida": partida, "unidad": unidad,
                "error": "Sin precios encontrados",
                "urls": [r["url"] for r in results]}

    s = sorted(all_prices)
    n = len(s)
    mediana = s[n // 2] if n % 2 else round((s[n//2-1] + s[n//2]) / 2, 2)
    return {
        "partida": partida,
        "unidad": unidad,
        "num_fuentes": len(sources),
        "total_precios": len(all_prices),
        "minimo": round(min(all_prices), 2),
        "maximo": round(max(all_prices), 2),
        "media": round(sum(all_prices) / len(all_prices), 2),
        "mediana": round(mediana, 2),
        "todos_los_precios": s,
        "fuentes": sources,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Streamable-HTTP es el transporte moderno para MCP remoto
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    mcp.run(transport="streamable-http")
