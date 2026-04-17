#!/usr/bin/env bash
# Smoke test: drive the MCP server over stdin/stdout.
# Usage: ./plugin/tests/smoke_stdio.sh [p0|p1]
# p0 = force canned stubs (OLLAMA_MCP_PHASE=0); p1 = real Ollama call (default).

set -euo pipefail
PHASE="${1:-p1}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SERVER="$HERE/../bin/augment-ollama-local-mcp"

if [ "$PHASE" = "p0" ]; then
  export OLLAMA_MCP_PHASE=0
else
  export OLLAMA_MCP_PHASE=1
fi

REQS=$(cat <<'JSON'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"internal_code_review","arguments":{"code":"def add(a,b):\n  return a + b\n","language":"python","path":"demo.py","focus":"general"}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"internal_refactor","arguments":{"code":"x=1","goal":"readability","language":"python"}}}
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"internal_code_review","arguments":{"language":"python"}}}
JSON
)

printf '%s\n' "$REQS" | "$SERVER"
