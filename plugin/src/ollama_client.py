"""Thin Ollama HTTP client (stdlib only).

P0: module present but unused; tools return canned responses.
P1: internal_code_review calls chat() with a strict-JSON prompt.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5-coder:latest"
DEFAULT_TIMEOUT_MS = 120_000


def _base_url() -> str:
    url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    # Enforce loopback: refuse any non-loopback host to preserve the local-only guarantee.
    host = urllib.parse.urlparse(url).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise OllamaError("not_loopback", f"Refusing non-loopback host: {host!r}")
    return url


def _model() -> str:
    return os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)


def _timeout_s() -> float:
    return int(os.environ.get("OLLAMA_TIMEOUT_MS", DEFAULT_TIMEOUT_MS)) / 1000.0


class OllamaError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def health() -> dict[str, Any]:
    """GET /api/version — used by install.sh and SessionStart hook."""
    try:
        with urllib.request.urlopen(_base_url() + "/api/version", timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise OllamaError("ollama_unreachable", str(e))


def chat(system: str, user: str, *, json_mode: bool = True) -> str:
    """POST /api/chat, non-streaming. Returns the assistant message content as a string.

    When json_mode=True, uses Ollama's `format: "json"` so the model is
    constrained to emit valid JSON. Caller is responsible for json.loads().
    """
    body: dict[str, Any] = {
        "model": _model(),
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": 0.2},
    }
    if json_mode:
        body["format"] = "json"

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        _base_url() + "/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_timeout_s()) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        if e.code == 404 and "model" in body_text.lower():
            raise OllamaError("ollama_model_missing", f"{_model()} not installed: {body_text}")
        raise OllamaError("ollama_server_error", f"HTTP {e.code}: {body_text}")
    except urllib.error.URLError as e:
        # TimeoutError arrives wrapped in URLError.reason on Py3.9
        reason = getattr(e, "reason", e)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            raise OllamaError("ollama_timeout", str(reason))
        raise OllamaError("ollama_unreachable", str(reason))

    msg = (payload.get("message") or {}).get("content")
    if not isinstance(msg, str):
        raise OllamaError("bad_model_output", f"Missing message.content in: {payload!r}")
    return msg
