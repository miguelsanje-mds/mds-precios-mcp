"""MDS Precios — MCP server HTTP con OAuth minimal (Railway)."""

import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from urllib.parse import quote_plus, parse_qs, urlparse, urlencode

import httpx
from bs4 import BeautifulSoup

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Mount, Route

from mcp.server.fastmcp import FastMCP


# ========================================================================
# MCP server
# ========================================================================
mcp = FastMCP("mds-precios")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36")

PRICE_M2 = [
    re.compile(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*/?\s*m[²2]', re.IGNORECASE),
    re.compile(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*euros?\s*/?\s*m[²2]', re.IGNORECASE),
    re.compile(r'€\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*/?\s*m[²2]', re.IGNORECASE),
]
PRICE_UD = [re.compile(r'(\d{1,4}(?:[.,]\d{1,2})?)\s*€\s*/?\s*(?:ud|unidad|uds)\b', re.IGNORECASE)]
PRICE_ML = [re.compile(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*/?\s*(?:ml|m\.?l\.?|metro\s+lineal)', re.IGNORECASE)]


def _extract_prices(text: str, unidad: str) -> list:
    pats = {"m2": PRICE_M2, "ud": PRICE_UD, "ml": PRICE_ML}.get(unidad, PRICE_M2)
    lo, hi = {"m2": (5, 500), "ud": (10, 5000), "ml": (3, 300)}.get(unidad, (5, 500))
    out = []
    for p in pats:
        for m in p.finditer(text):
            try:
                v = float(m.group(1).replace(",", "."))
                if lo <= v <= hi:
                    out.append(v)
            except ValueError:
                continue
    return out


async def _ddg(query: str, num: int = 8) -> list:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        r = await c.post("https://html.duckduckgo.com/html/",
                         data={"q": query}, headers={"User-Agent": UA})
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.select("a.result__a")[:num]:
        href = a.get("href", "")
        p = urlparse(href)
        if "duckduckgo.com" in p.netloc and "/l/" in p.path:
            qs = parse_qs(p.query)
            if "uddg" in qs:
                href = qs["uddg"][0]
        elif href.startswith("//"):
            href = "https:" + href
        if href.startswith("http"):
            out.append({"title": a.get_text(strip=True), "url": href})
    return out


async def _fetch(url: str, unidad: str) -> list:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": UA})
        if r.status_code != 200:
            return []
        text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
        return _extract_prices(text, unidad)
    except Exception:
        return []


@mcp.tool()
async def buscar_precio_partida(partida: str, unidad: str = "m2") -> dict:
    """Busca precios de mercado en España para una partida de construcción.

    Consulta portales públicos (CYPE, Cronoshare, Habitissimo, Reiteman, etc.)
    vía DuckDuckGo. Devuelve lista de precios encontrados + media + fuentes.

    Args:
        partida: Descripción breve (ej: "tabique pladur 15+70+15 100mm").
        unidad: "m2" (default), "ud" o "ml".
    """
    query = f"precio {partida} {unidad} España 2026"
    results = await _ddg(query, 8)
    all_prices, sources = [], []
    for r in results:
        prices = await _fetch(r["url"], unidad)
        if prices:
            all_prices.extend(prices)
            sources.append({"titulo": r["title"], "url": r["url"],
                            "precios": sorted(set(prices))[:15]})
    if not all_prices:
        return {"partida": partida, "unidad": unidad,
                "error": "Sin precios encontrados",
                "urls": [r["url"] for r in results]}
    s = sorted(all_prices)
    n = len(s)
    med = s[n // 2] if n % 2 else round((s[n // 2 - 1] + s[n // 2]) / 2, 2)
    return {
        "partida": partida, "unidad": unidad,
        "num_fuentes": len(sources), "total_precios": len(all_prices),
        "minimo": round(min(all_prices), 2),
        "maximo": round(max(all_prices), 2),
        "media": round(sum(all_prices) / len(all_prices), 2),
        "mediana": round(med, 2),
        "todos_los_precios": s, "fuentes": sources,
    }


# ========================================================================
# OAuth 2.1 minimal
# ========================================================================
BASE_URL = os.environ.get("BASE_URL", "https://web-production-303d2.up.railway.app")

_auth_codes: dict[str, dict] = {}
_tokens: dict[str, float] = {}


def _now() -> float:
    return time.time()


async def oauth_protected_resource(request):
    return JSONResponse({
        "resource": f"{BASE_URL}/mcp",
        "authorization_servers": [BASE_URL],
        "scopes_supported": ["mcp"],
        "bearer_methods_supported": ["header"],
    })


async def oauth_authorization_server(request):
    return JSONResponse({
        "issuer": BASE_URL,
        "authorization_endpoint": f"{BASE_URL}/authorize",
        "token_endpoint": f"{BASE_URL}/token",
        "registration_endpoint": f"{BASE_URL}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["mcp"],
        "code_challenge_methods_supported": ["S256", "plain"],
    })


async def register_client(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    client_id = f"client_{secrets.token_urlsafe(12)}"
    return JSONResponse({
        "client_id": client_id,
        "client_id_issued_at": int(_now()),
        "client_name": data.get("client_name", "MCP Client"),
        "redirect_uris": data.get("redirect_uris", []),
        "grant_types": data.get("grant_types", ["authorization_code", "refresh_token"]),
        "response_types": data.get("response_types", ["code"]),
        "token_endpoint_auth_method": "none",
        "scope": "mcp",
    })


async def authorize(request):
    q = dict(request.query_params)
    code = f"code_{secrets.token_urlsafe(24)}"
    _auth_codes[code] = {
        "client_id": q.get("client_id"),
        "redirect_uri": q.get("redirect_uri"),
        "code_challenge": q.get("code_challenge"),
        "code_challenge_method": q.get("code_challenge_method"),
        "expires_at": _now() + 600,
    }
    redirect_uri = q.get("redirect_uri")
    if not redirect_uri:
        return JSONResponse({"error": "missing_redirect_uri"}, status_code=400)
    params = {"code": code}
    if q.get("state"):
        params["state"] = q["state"]
    return RedirectResponse(f"{redirect_uri}?{urlencode(params)}")


async def token_endpoint(request):
    form = dict(await request.form())
    grant = form.get("grant_type", "")

    if grant == "authorization_code":
        code = form.get("code")
        if code in _auth_codes:
            del _auth_codes[code]
    elif grant == "refresh_token":
        pass
    else:
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    access = f"at_{secrets.token_urlsafe(32)}"
    refresh = f"rt_{secrets.token_urlsafe(32)}"
    _tokens[access] = _now() + 3600
    return JSONResponse({
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": refresh,
        "scope": "mcp",
    })


async def health(request):
    return JSONResponse({"status": "ok", "service": "mds-precios"})


# ========================================================================
# ASGI wrapper para MCP (maneja scope lifespan + http delegando a session_manager)
# ========================================================================
async def mcp_asgi_app(scope, receive, send):
    if scope["type"] == "http":
        await mcp.session_manager.handle_request(scope, receive, send)
    elif scope["type"] == "lifespan":
        while True:
            msg = await receive()
            if msg["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif msg["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


# ========================================================================
# Starlette app con lifespan que arranca session_manager.run()
# ========================================================================
@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield


routes = [
    Route("/", health),
    Route("/.well-known/oauth-protected-resource", oauth_protected_resource),
    Route("/.well-known/oauth-protected-resource/mcp", oauth_protected_resource),
    Route("/.well-known/oauth-authorization-server", oauth_authorization_server),
    Route("/.well-known/oauth-authorization-server/mcp", oauth_authorization_server),
    Route("/register", register_client, methods=["POST"]),
    Route("/authorize", authorize, methods=["GET"]),
    Route("/token", token_endpoint, methods=["POST"]),
    Mount("/mcp", app=mcp_asgi_app),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
]

app = Starlette(routes=routes, middleware=middleware, lifespan=lifespan)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
