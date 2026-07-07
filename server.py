"""
Servidor MCP unificado com OAuth para Claude.ai
Conecta direto ao Odoo via XML-RPC sem depender do mcp-server-odoo
"""
import os, json, xmlrpc.client, logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
import uvicorn

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Config
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://mcp-server-odoo-rrab.onrender.com")
CLIENT_ID = os.getenv("MCP_CLIENT_ID", "gp-odoo-client")
CLIENT_SECRET = os.getenv("MCP_CLIENT_SECRET", "gp-odoo-secret-2026")
TOKEN = os.getenv("MCP_BEARER_TOKEN", "gp-consultoria-2026")
ODOO_URL = os.getenv("ODOO_URL", "")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USER = os.getenv("ODOO_USER", "")
ODOO_KEY = os.getenv("ODOO_API_KEY", "")

def odoo_call(model, method, args=[], kwargs={}):
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_KEY, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return models.execute_kw(ODOO_DB, uid, ODOO_KEY, model, method, args, kwargs)

# OAuth endpoints
@app.get("/.well-known/oauth-authorization-server")
async def oauth_meta():
    return JSONResponse({
        "issuer": BASE_URL,
        "authorization_endpoint": f"{BASE_URL}/oauth/authorize",
        "token_endpoint": f"{BASE_URL}/oauth/token",
        "registration_endpoint": f"{BASE_URL}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"]
    })

@app.post("/oauth/register")
async def oauth_register(request: Request):
    body = await request.json()
    return JSONResponse({"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "redirect_uris": body.get("redirect_uris", []),
        "grant_types": ["authorization_code"], "response_types": ["code"],
        "token_endpoint_auth_method": "none"}, status_code=201)

@app.get("/oauth/authorize")
async def oauth_auth(request: Request):
    p = dict(request.query_params)
    return RedirectResponse(f"{p.get('redirect_uri')}?code=gp2026&state={p.get('state','')}", 302)

@app.post("/oauth/token")
async def oauth_token():
    return JSONResponse({"access_token": TOKEN, "token_type": "bearer", "expires_in": 86400})

@app.get("/health")
async def health():
    return {"status": "ok"}

# MCP endpoint - implementação manual do protocolo
@app.post("/mcp")
async def mcp_handler(request: Request):
    auth = request.headers.get("Authorization", "")
    logger.debug(f"MCP POST auth={auth[:30]}")
    
    body = await request.json()
    logger.debug(f"MCP body={json.dumps(body)[:300]}")
    
    method = body.get("method", "")
    req_id = body.get("id")
    
    # Initialize
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "odoo-gp-consultoria", "version": "1.0.0"}
            }
        })
    
    # List tools
    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0", "id": req_id,
            "result": {"tools": [
                {"name": "buscar_registros", "description": "Busca registros no Odoo",
                 "inputSchema": {"type": "object", "properties": {
                     "modelo": {"type": "string"}, "filtro": {"type": "array"}, "campos": {"type": "array"}
                 }, "required": ["modelo"]}},
                {"name": "criar_registro", "description": "Cria um registro no Odoo",
                 "inputSchema": {"type": "object", "properties": {
                     "modelo": {"type": "string"}, "dados": {"type": "object"}
                 }, "required": ["modelo", "dados"]}},
                {"name": "atualizar_registro", "description": "Atualiza registro no Odoo",
                 "inputSchema": {"type": "object", "properties": {
                     "modelo": {"type": "string"}, "id": {"type": "integer"}, "dados": {"type": "object"}
                 }, "required": ["modelo", "id", "dados"]}},
            ]}
        })
    
    # Call tool
    if method == "tools/call":
        tool = body.get("params", {}).get("name")
        args = body.get("params", {}).get("arguments", {})
        
        try:
            if tool == "buscar_registros":
                result = odoo_call(args["modelo"], "search_read",
                    [args.get("filtro", [])],
                    {"fields": args.get("campos", []), "limit": 20})
                return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}})
            
            elif tool == "criar_registro":
                result = odoo_call(args["modelo"], "create", [args["dados"]])
                return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"Criado com ID: {result}"}]}})
            
            elif tool == "atualizar_registro":
                result = odoo_call(args["modelo"], "write", [[args["id"]], args["dados"]])
                return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"Atualizado: {result}"}]}})
        except Exception as e:
            logger.error(f"Tool error: {e}")
            return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": f"Erro: {str(e)}"}]}})
    
    # notifications/initialized - sem resposta necessária
    if method == "notifications/initialized":
        return JSONResponse({"jsonrpc": "2.0"})

    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}})

@app.get("/mcp")
async def mcp_get(request: Request):
    logger.debug(f"MCP GET headers={dict(request.headers)}")
    return JSONResponse({"status": "MCP server running"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)), log_level="debug")
