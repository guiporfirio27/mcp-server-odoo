"""
Proxy MCP server com OAuth 2.0 completo para Claude.ai
Suporte a streaming (SSE/chunked)
"""
import os
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
import uvicorn

app = FastAPI()

BEARER_TOKEN = os.getenv("MCP_BEARER_TOKEN", "gp-consultoria-2026")
CLIENT_ID = os.getenv("MCP_CLIENT_ID", "gp-odoo-client")
CLIENT_SECRET = os.getenv("MCP_CLIENT_SECRET", "gp-odoo-secret-2026")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://mcp-server-odoo-rrab.onrender.com")

@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    return JSONResponse({
        "issuer": BASE_URL,
        "authorization_endpoint": f"{BASE_URL}/oauth/authorize",
        "token_endpoint": f"{BASE_URL}/oauth/token",
        "registration_endpoint": f"{BASE_URL}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "client_credentials"],
        "code_challenge_methods_supported": ["S256", "plain"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic", "none"]
    })

@app.post("/oauth/register")
async def oauth_register(request: Request):
    body = await request.json()
    return JSONResponse({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "client_name": body.get("client_name", "Claude.ai"),
        "redirect_uris": body.get("redirect_uris", []),
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none"
    }, status_code=201)

@app.get("/oauth/authorize")
async def oauth_authorize(request: Request):
    params = dict(request.query_params)
    redirect_uri = params.get("redirect_uri", "")
    state = params.get("state", "")
    code = "gp-auth-code-2026"
    return RedirectResponse(url=f"{redirect_uri}?code={code}&state={state}", status_code=302)

@app.post("/oauth/token")
async def oauth_token(request: Request):
    return JSONResponse({
        "access_token": BEARER_TOKEN,
        "token_type": "bearer",
        "expires_in": 86400,
        "scope": "read write"
    })

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.api_route("/mcp", methods=["GET", "POST", "DELETE", "PUT"])
@app.api_route("/mcp/{path:path}", methods=["GET", "POST", "DELETE", "PUT"])
async def proxy_mcp(request: Request, path: str = ""):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    internal_url = "http://localhost:8001/mcp"
    if path:
        internal_url = f"http://localhost:8001/mcp/{path}"

    body = await request.body()
    headers = {k: v for k, v in request.headers.items() 
               if k.lower() not in ["host", "authorization", "content-length"]}

    # Usar streaming para suportar SSE e chunked responses
    async def stream_response():
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                method=request.method,
                url=internal_url,
                headers=headers,
                content=body,
                params=dict(request.query_params)
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

    # Fazer primeira requisição para pegar headers de resposta
    async with httpx.AsyncClient(timeout=30) as client:
        async with client.stream(
            method=request.method,
            url=internal_url,
            headers=headers,
            content=body,
            params=dict(request.query_params)
        ) as resp:
            response_headers = dict(resp.headers)
            response_headers.pop("content-length", None)
            status_code = resp.status_code

            return StreamingResponse(
                resp.aiter_bytes(),
                status_code=status_code,
                headers=response_headers,
                media_type=response_headers.get("content-type", "application/json")
            )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
