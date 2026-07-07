#!/bin/bash
# Inicia o MCP server interno na porta 8001
export ODOO_MCP_PORT=8001
export ODOO_MCP_HOST=0.0.0.0
export ODOO_MCP_TRANSPORT=streamable-http
mcp-server-odoo --transport streamable-http --host 0.0.0.0 --port 8001 &

# Aguarda o servidor interno iniciar
sleep 5

# Inicia o proxy OAuth na porta principal
python proxy_server.py
