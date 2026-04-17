"""Input/output JSON schemas for the four internal-ollama MCP tools.

Kept minimal and stdlib-only: no jsonschema dependency; validation is done
inline in tools.py against these dicts.
"""

TOOLS = [
    {
        "name": "internal_code_review",
        "description": (
            "Runs a LOCAL code review via the on-device Ollama model. "
            "Returns structured findings (severity, line, category, suggestion). "
            "Use this tool whenever the user asks for a local / offline / "
            "no-credit / internal code review."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["code"],
            "properties": {
                "code": {"type": "string", "description": "Source code to review."},
                "language": {"type": "string", "description": "Language hint (e.g. python, ts)."},
                "path": {"type": "string", "description": "Optional file path for context."},
                "focus": {
                    "type": "string",
                    "enum": ["general", "security", "performance", "style"],
                    "default": "general",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "internal_explain_code",
        "description": (
            "Explains a code snippet in plain language using the LOCAL Ollama model. "
            "No credits consumed. Use for local/offline/internal explanations."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["code"],
            "properties": {
                "code": {"type": "string"},
                "language": {"type": "string"},
                "audience": {
                    "type": "string",
                    "enum": ["junior", "senior", "non-technical"],
                    "default": "senior",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "internal_generate_tests",
        "description": (
            "Generates unit tests for a snippet using the LOCAL Ollama model. "
            "Use for local/offline/internal test generation."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["code"],
            "properties": {
                "code": {"type": "string"},
                "language": {"type": "string"},
                "framework": {"type": "string", "description": "e.g. pytest, jest, junit"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "internal_refactor",
        "description": (
            "Proposes a refactor of the given snippet using the LOCAL Ollama model. "
            "Returns before/after plus rationale. Local/offline/no-credit."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["code", "goal"],
            "properties": {
                "code": {"type": "string"},
                "goal": {"type": "string", "description": "What to optimize for."},
                "language": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
]


ERROR_CODES = {
    "invalid_input": "Input failed schema validation.",
    "ollama_unreachable": "Ollama daemon not reachable on OLLAMA_BASE_URL.",
    "ollama_model_missing": "Configured OLLAMA_MODEL is not installed.",
    "ollama_timeout": "Ollama request exceeded OLLAMA_TIMEOUT_MS.",
    "ollama_server_error": "Ollama returned a non-2xx response.",
    "input_too_large": "Input exceeds OLLAMA_MAX_INPUT_CHARS.",
    "bad_model_output": "Model output could not be parsed as the expected JSON.",
    "not_loopback": "OLLAMA_BASE_URL must resolve to 127.0.0.1/localhost.",
}
