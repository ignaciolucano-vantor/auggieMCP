#!/usr/bin/env python3
"""Internal-ollama MCP server (stdio, JSON-RPC 2.0).

Implements the minimum subset of the Model Context Protocol required by
Auggie to list and call tools:

  - initialize
  - notifications/initialized  (notification, no response)
  - tools/list
  - tools/call

Stdlib-only. Each line on stdin is one JSON-RPC message; each response is
written as a single line on stdout. Diagnostics go to stderr.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any

# Allow imports when launched via absolute path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schemas import TOOLS  # noqa: E402
from tools import dispatch  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "internal-ollama"
SERVER_VERSION = "0.1.0"

LOG_PATH = os.environ.get(
    "OLLAMA_MCP_LOG",
    os.path.expanduser("~/.augment/logs/ollama-mcp.log"),
)


def _log(msg: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as fh:
            fh.write(msg.rstrip() + "\n")
    except Exception:
        pass
    print(msg, file=sys.stderr, flush=True)


def _result(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle_initialize(_params: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


def _handle_tools_list(_params: dict[str, Any]) -> dict[str, Any]:
    return {"tools": TOOLS}


def _handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(name, str):
        return {"isError": True, "content": [{"type": "text", "text": "Missing tool name."}]}
    _log(f"tools/call name={name} args_keys={list(arguments.keys())}")
    payload = dispatch(name, arguments)
    is_error = "error" in payload
    return {
        "isError": is_error,
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
    }


def _handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        return _result(req_id, _handle_initialize(params))
    if method == "notifications/initialized":
        return None  # notification; no response
    if method == "tools/list":
        return _result(req_id, _handle_tools_list(params))
    if method == "tools/call":
        return _result(req_id, _handle_tools_call(params))
    if method == "ping":
        return _result(req_id, {})
    if req_id is None:
        # Unknown notification: ignore.
        return None
    return _error(req_id, -32601, f"Method not found: {method}")


def main() -> int:
    _log(f"server start pid={os.getpid()} phase={os.environ.get('OLLAMA_MCP_PHASE', '1')}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            _log(f"bad json: {e}")
            continue
        try:
            response = _handle(msg)
        except Exception:
            _log("handler crash:\n" + traceback.format_exc())
            response = _error(msg.get("id"), -32603, "Internal error")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    _log("server stop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
