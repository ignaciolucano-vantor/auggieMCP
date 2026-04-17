"""Tool dispatch for the internal-ollama MCP server.

P0: all four tools return canned structured JSON (no Ollama call).
P1: internal_code_review switches to a real Ollama call; the others stay canned
until P2.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ollama_client import OllamaError, chat
from schemas import TOOLS

MAX_INPUT_CHARS = int(os.environ.get("OLLAMA_MAX_INPUT_CHARS", "32000"))


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _validate(tool_name: str, args: dict[str, Any]) -> str | None:
    spec = next((t for t in TOOLS if t["name"] == tool_name), None)
    if spec is None:
        return f"Unknown tool: {tool_name}"
    schema = spec["inputSchema"]
    for req in schema.get("required", []):
        if req not in args:
            return f"Missing required field: {req}"
    for k, v in args.items():
        prop = schema["properties"].get(k)
        if prop is None:
            return f"Unknown field: {k}"
        if prop.get("type") == "string" and not isinstance(v, str):
            return f"Field {k} must be string"
        if "enum" in prop and v not in prop["enum"]:
            return f"Field {k} must be one of {prop['enum']}"
    code = args.get("code", "")
    if isinstance(code, str) and len(code) > MAX_INPUT_CHARS:
        return f"input_too_large: code has {len(code)} chars, max {MAX_INPUT_CHARS}"
    return None


# ---------- P1 real Ollama implementation for code review ----------

_REVIEW_SYSTEM = (
    "You are a senior code reviewer. Return ONLY valid JSON matching this shape: "
    '{"summary": str, "findings": [{"severity":"info|warn|error","line":int|null,'
    '"category":str,"suggestion":str}]}. '
    "Be concise. Do not include prose outside the JSON. "
    "Do not include a 'model' field — the caller adds it."
)


def _review_real(args: dict[str, Any]) -> dict[str, Any]:
    language = args.get("language", "unknown")
    focus = args.get("focus", "general")
    path = args.get("path", "")
    user = (
        f"Language: {language}\nFocus: {focus}\nPath: {path}\n\n"
        f"Code:\n```\n{args['code']}\n```\n"
    )
    try:
        raw = chat(_REVIEW_SYSTEM, user, json_mode=True)
    except OllamaError as e:
        return _err(e.code, e.message)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return _err("bad_model_output", f"Non-JSON output: {e}; raw={raw[:300]}")
    parsed["model"] = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:latest")
    parsed["source"] = "ollama-local"
    return parsed


# ---------- P0 canned responses ----------

def _canned_review(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "canned-stub-p0",
        "model": "none",
        "summary": f"[stub] Review of {args.get('path', '<inline>')} ({len(args['code'])} chars).",
        "findings": [
            {"severity": "info", "line": 1, "category": "stub",
             "suggestion": "P0 stub: no real analysis performed. Enable P1 to invoke Ollama."},
        ],
    }


def _canned_explain(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "canned-stub-p0",
        "summary": "[stub] Explanation placeholder.",
        "audience": args.get("audience", "senior"),
        "explanation": f"({len(args['code'])} chars of code received)",
    }


def _canned_tests(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "canned-stub-p0",
        "framework": args.get("framework", "unknown"),
        "tests": "# stub: no tests generated in P0\n",
    }


def _canned_refactor(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "canned-stub-p0",
        "goal": args["goal"],
        "before": args["code"],
        "after": args["code"],
        "rationale": "[stub] No refactor performed in P0.",
    }


# P1 flag: set OLLAMA_MCP_PHASE=1 to enable real Ollama for internal_code_review.
# Default is "1" because we ship P0+P1 together; set to "0" to force stubs.
def _phase() -> int:
    return int(os.environ.get("OLLAMA_MCP_PHASE", "1"))


def dispatch(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    err = _validate(tool_name, args)
    if err is not None:
        code = "input_too_large" if err.startswith("input_too_large") else "invalid_input"
        return _err(code, err)

    if tool_name == "internal_code_review":
        if _phase() >= 1:
            return _review_real(args)
        return _canned_review(args)
    if tool_name == "internal_explain_code":
        return _canned_explain(args)
    if tool_name == "internal_generate_tests":
        return _canned_tests(args)
    if tool_name == "internal_refactor":
        return _canned_refactor(args)
    return _err("invalid_input", f"Unknown tool: {tool_name}")
