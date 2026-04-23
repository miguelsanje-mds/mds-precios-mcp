# MDS Precios — MCP remoto

Servidor MCP (Streamable-HTTP) para búsqueda de precios de mercado
en partidas de construcción en España. Se conecta como MCP remoto
desde Cowork / Claude Desktop.

## Deploy en Railway

1. Conectar este repo en Railway.
2. Railway detecta `requirements.txt` + `Procfile` y despliega solo.
3. La URL pública será `https://<proyecto>.up.railway.app`.

## Endpoint MCP

- Transport: `streamable-http`
- URL: `https://<proyecto>.up.railway.app/mcp`

## Herramienta expuesta

`buscar_precio_partida(partida, unidad="m2")` — devuelve precios
encontrados + media + fuentes.
