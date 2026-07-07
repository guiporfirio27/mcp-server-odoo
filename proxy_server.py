"""
Proxy MCP server com OAuth simples para Claude.ai
Faz bridge para o mcp-server-odoo via HTTP interno
"""
import os
import json
import asyncio
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

app = FastAPI()

BEARER_TOKEN = os.getenv("MCP_BEARER_TOKEN", "gp-consultoria-2026")
ODOO_URL = os.getenv("ODOO_URL", "")
ODOO_USER = os.getenv("ODOO_USER", "")
ODOO_API_KEY = os.getenv("ODOO_API_KEY", "")
ODOO_DB = os.getenv("ODOO_DB", "")

# OAuth 2.0 metadata endpoint (exigido pelo Claude.ai)
@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    base = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
    }

# Token endpoint - retorna token fixo
@app.post("/oauth/token")
async def oauth_token(request: Request):
    return {
        "access_token": BEARER_TOKEN,
        "token_type": "bearer",
        "expires_in": 86400
    }

# Authorization endpoint - auto-aprova
@app.get("/oauth/authorize")
async def oauth_authorize(request: Request):
    params = dict(request.query_params)
    redirect_uri = params.get("redirect_uri", "")
    state = params.get("state", "")
    code = "gp-auth-code-2026"
    return Response(
        status_code=302,
        headers={"Location": f"{redirect_uri}?code={code}&state={state}"}
    )

# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "GP Consultoria Ambiental - Odoo MCP"}

# Proxy MCP requests para o servidor interno
@app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
@app.api_route("/mcp/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy_mcp(request: Request, path: str = ""):
    # Verificar autenticação
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = auth.replace("Bearer ", "")
    if token != BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Forward para o servidor MCP interno na porta 8001
    internal_url = f"http://localhost:8001/mcp"
    if path:
        internal_url = f"http://localhost:8001/mcp/{path}"
    
    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)
    
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.request(
            method=request.method,
            url=internal_url,
            headers=headers,
            content=body,
            params=dict(request.query_params)
        )
    
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers)
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
