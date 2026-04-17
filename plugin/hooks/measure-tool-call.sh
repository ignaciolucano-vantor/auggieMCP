#!/usr/bin/env bash
# PostToolUse hook for MCP tools on server internal-ollama.
# Appends one JSONL line per call to <workspace>/prompt-log/local-tool-calls.jsonl.
# Never blocks: on any error, exits 0 silently.

set -u

EVENT_DATA="$(cat || true)"
[ -z "$EVENT_DATA" ] && exit 0

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

ISO_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
WORKSPACE="$(printf '%s' "$EVENT_DATA" | jq -r '.workspace_roots[0] // empty' 2>/dev/null)"
[ -z "$WORKSPACE" ] && exit 0

LOG_DIR="$WORKSPACE/prompt-log"
mkdir -p "$LOG_DIR" 2>/dev/null || exit 0
LOG_FILE="$LOG_DIR/local-tool-calls.jsonl"

printf '%s' "$EVENT_DATA" | jq -c \
  --arg ts "$ISO_TS" \
  --arg ws "$WORKSPACE" \
  '{
     ts: $ts,
     workspace: $ws,
     conversation_id: (.conversation_id // null),
     tool: (.tool_name // .tool // null),
     server: (.server_name // null),
     elapsed_ms: (.elapsed_ms // .duration_ms // null),
     input_chars: ((.tool_input // .arguments // {}) | (.code // "") | length),
     is_error: (.is_error // .isError // false)
   }' >> "$LOG_FILE" 2>/dev/null || true

exit 0
