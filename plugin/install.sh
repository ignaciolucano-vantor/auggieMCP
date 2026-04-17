#!/usr/bin/env bash
# Installer for the augment-ollama-local plugin.
# - Verifies Ollama prerequisites
# - Symlinks the /local-review command into ~/.augment/commands/
# - Patches ~/.augment/settings.json to register the MCP server and the
#   PostToolUse measurement hook (idempotent, preserves existing keys).

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BIN="$HERE/bin/augment-ollama-local-mcp"
HOOK="$HERE/hooks/measure-tool-call.sh"
CMD_SRC="$HERE/commands/local-review.md"

AUG_DIR="${HOME}/.augment"
CMD_DST_DIR="$AUG_DIR/commands"
SETTINGS="$AUG_DIR/settings.json"

red()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
ylw()  { printf '\033[33m%s\033[0m\n' "$*"; }

# 1. Prerequisites
command -v jq >/dev/null 2>&1 || { red "jq is required (brew install jq)"; exit 1; }
command -v /usr/bin/python3 >/dev/null 2>&1 || { red "python3 missing"; exit 1; }

OLLAMA_BIN="$(command -v ollama || true)"
[ -z "$OLLAMA_BIN" ] && { red "ollama binary not found"; exit 1; }
OLLAMA_VER="$("$OLLAMA_BIN" --version 2>/dev/null | awk '{print $NF}' | head -1)"
grn "ollama $OLLAMA_VER at $OLLAMA_BIN"

if ! curl -fsS -m 3 http://127.0.0.1:11434/api/version >/dev/null; then
  red "Ollama daemon is not responding on 127.0.0.1:11434"
  red "Start the Ollama app: open -a Ollama"
  exit 1
fi
grn "ollama daemon reachable"

MODEL="${OLLAMA_MODEL:-qwen2.5-coder:latest}"
if ! "$OLLAMA_BIN" show "$MODEL" >/dev/null 2>&1; then
  red "Model '$MODEL' is not installed. Run: ollama pull $MODEL"
  exit 1
fi
grn "model $MODEL present"

# 2. Make scripts executable
chmod +x "$BIN" "$HOOK"

# 3. Symlink command file
mkdir -p "$CMD_DST_DIR"
ln -sfn "$CMD_SRC" "$CMD_DST_DIR/local-review.md"
grn "command symlinked: $CMD_DST_DIR/local-review.md"

# 4. Patch settings.json (idempotent)
mkdir -p "$AUG_DIR"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"

TMP="$(mktemp)"
jq \
  --arg bin "$BIN" \
  --arg hook "$HOOK" \
  --arg model "$MODEL" \
  '
    .mcpServers = ((.mcpServers // {}) + {
      "internal-ollama": {
        "command": $bin,
        "args": [],
        "env": {
          "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
          "OLLAMA_MODEL": $model,
          "OLLAMA_TIMEOUT_MS": "120000",
          "OLLAMA_MAX_INPUT_CHARS": "32000",
          "OLLAMA_MCP_PHASE": "1"
        }
      }
    })
    | .hooks = (.hooks // {})
    | .hooks.PostToolUse = (
        ((.hooks.PostToolUse // []) | map(select(.matcher != "mcp:.*_internal-ollama")))
        + [{
            "matcher": "mcp:.*_internal-ollama",
            "hooks": [{"type": "command", "command": $hook, "timeout": 3000}]
          }]
      )
  ' "$SETTINGS" > "$TMP"
mv "$TMP" "$SETTINGS"
grn "settings.json patched (mcpServers.internal-ollama + PostToolUse matcher)"

ylw "Restart your Auggie session for the MCP server and hook to load."
