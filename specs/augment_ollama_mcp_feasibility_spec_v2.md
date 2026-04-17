# Spec v2 — Augment + Local Ollama via MCP (Scoped & Measured)

**Version:** 2.0 · **Date:** 2026-04-17 · **Supersedes partially:** `augment_ollama_mcp_feasibility_spec.md`

---

## 0. What changed from v1

v1 evaluated 4 implementation models (true switching / per-command routing / hook routing / plugin packaging) and asked Augment to fill a decision matrix. v2 **collapses scope** to what Auggie's current architecture can support:

- **Discarded — Model 1 (true global LLM switch):** Auggie's reasoning LLM (Anthropic / Google / OpenAI) is a closed runtime. No documented extension point replaces it. MCP is a tool protocol, not a model backend.
- **Discarded — Model 3 (hook-based automatic routing):** Documented hook events are `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `SessionEnd`. There is **no `UserPromptSubmit` hook**, so no component can intercept a prompt before the agent's LLM processes it.
- **Removed — `/switchLLM` command:** Misleading; no persistent routing state exists between turns.
- **In scope — Patterns B + D:** Per-command, deterministic (instruction-level) routing to a local MCP server backed by Ollama, packaged as an Auggie plugin. Measurable success criteria. Empirical credit baseline.

---

## 1. Measured Local Environment

All values measured on this machine on 2026-04-17 (not assumed).

| Item | Value | Source of truth |
|---|---|---|
| Binary (symlink) | `/usr/local/bin/ollama` → `/Applications/Ollama.app/Contents/Resources/ollama` | `ls -la /usr/local/bin/ollama` |
| Architecture | Universal binary (x86_64 + arm64) | `file /usr/local/bin/ollama` |
| Ollama version | **0.21.0** | `ollama --version` |
| API endpoint | `http://127.0.0.1:11434` — responding | `curl /api/version` → `{"version":"0.21.0"}` |
| Server process | `Ollama.app` (GUI-managed, auto-start) | `pgrep -fl ollama` → PID 20636 |
| Installed models | `qwen2.5-coder:latest` · 4.7 GB · ID `dae161e27b0e` | `ollama list` |

**Implications for design:**
- Ollama daemon is always-on via the macOS app; the MCP server MUST NOT try to `ollama serve` itself.
- `qwen2.5-coder:latest` is a coding-specialized 7B-class model; strong on review/explain/refactor, weaker on long-context reasoning. Default context window ≈ 8K tokens (override via `num_ctx`).
- Endpoint is localhost-only, unauthenticated. MCP server MUST refuse non-loopback `OLLAMA_BASE_URL` overrides to preserve the local-only guarantee.
- Only one model present. Upgrading to a larger coder model (e.g., `deepseek-coder-v2:16b` ~9 GB) remains optional and is gated by the acceptance criteria in §6.3.

---

## 2. In-Scope Architecture

```
┌───────────────────────────────────────────────────────────────┐
│  Auggie (CLI or VSCode)  ──  user runs /local-review foo.py   │
│                                                               │
│  1. Custom command (Markdown in ~/.augment/commands/)         │
│     emits an imperative prompt: "call MCP tool X, render Y"   │
│                                                               │
│  2. Agent LLM parses intent → selects MCP tool                │
│                                                               │
│  3. MCP client  ──stdio──►  augment-ollama-local-mcp          │
│                                                               │
│  4. MCP server  ──HTTP──►  http://127.0.0.1:11434/api/chat    │
│                                                               │
│  5. Ollama runs qwen2.5-coder:latest  ──►  JSON reply         │
│                                                               │
│  6. MCP server normalises → structured tool output            │
│                                                               │
│  7. Auggie renders the tool output as markdown (no extra      │
│     reasoning; enforced by the command prompt)                │
└───────────────────────────────────────────────────────────────┘
```

### 2.1 Component matrix

| Layer | Component | Responsibility |
|---|---|---|
| Client | Auggie (CLI / VSCode) | Orchestration, user I/O, agent reasoning |
| Plugin | `augment-ollama-local` | Packages commands + skill + hook + MCP registration |
| Command | 4 `/local-*` commands | Deterministic (prompt-level) routing instructions |
| Skill | `local-execution` | Trigger-phrase routing for free-form prompts |
| Hook | `SessionStart` health check | Prints Ollama availability; no routing role |
| Hook | `PostToolUse` measurement | Logs each MCP call for empirical baselining |
| Bridge | `augment-ollama-local-mcp` (stdio) | Translates MCP tool calls ↔ Ollama HTTP |
| Runtime | Ollama daemon @ `127.0.0.1:11434` | Model serving |

### 2.2 Explicit non-goals

Replacing the Augment reasoning LLM · global persistent mode · zero-credit guarantee · remote Ollama · multi-model orchestration in one turn · model fine-tuning.

---

## 3. MCP Server Contract

### 3.1 Transport & registration

- **Protocol:** MCP over stdio.
- **Executable:** `augment-ollama-local-mcp` (Python 3.11+ recommended; Node 20+ acceptable). Installed at `~/.augment/plugins/augment-ollama-local/bin/augment-ollama-local-mcp`.
- **Registration (user scope):**
  ```bash
  auggie mcp add internal-ollama \
    --scope user \
    -- /Users/ignaciolucano/.augment/plugins/augment-ollama-local/bin/augment-ollama-local-mcp --stdio
  ```
- **Verification:** `/mcp` in Auggie shows `internal-ollama: connected` and lists the 4 tools.

### 3.2 Environment variables (server-side)

| Var | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API base. MUST match `^http://(127\.0\.0\.1\|localhost)(:\d+)?$` or server exits with error. |
| `OLLAMA_MODEL` | `qwen2.5-coder:latest` | Pinned model tag used for all tools. |
| `OLLAMA_NUM_CTX` | `16384` | Context window override passed as Ollama `options.num_ctx`. |
| `OLLAMA_TEMPERATURE` | `0.2` | Low temperature → more deterministic reviews. |
| `OLLAMA_TIMEOUT_MS` | `120000` | Per-call timeout. |
| `OLLAMA_MAX_INPUT_CHARS` | `60000` | Upper bound on concatenated input code. Enforced with explicit error, not truncation. |
| `AUGMENT_OLLAMA_LOG_PATH` | `~/.augment/logs/ollama-mcp.log` | Server-side structured log. |

### 3.3 Tools

Four tools. Each accepts structured JSON and returns structured JSON so Auggie renders the output as data (no further LLM reasoning needed).

#### Tool `internal_code_review`

**Input JSON Schema (subset):**
```json
{
  "type": "object",
  "required": ["code"],
  "properties": {
    "code":     {"type": "string", "maxLength": 60000},
    "language": {"type": "string", "description": "e.g. python, typescript, go"},
    "focus":    {"type": "string", "enum": ["general","security","performance","readability"], "default": "general"},
    "context":  {"type": "string", "description": "Optional TDD/spec excerpt for the reviewer"}
  }
}
```

**Output JSON:**
```json
{
  "summary": "1-3 sentence overview",
  "findings": [
    {
      "severity": "high|medium|low|info",
      "category": "bug|security|performance|style|clarity|test",
      "line":     42,
      "message":  "concrete issue",
      "suggestion": "concrete fix (optional)"
    }
  ],
  "model":     "qwen2.5-coder:latest",
  "elapsed_ms": 12345
}
```

#### Tool `internal_explain_code`

- Input: `{ code, language?, audience? ("junior"|"peer"|"architect") }`
- Output: `{ summary, walkthrough: [{section, explanation}], key_concepts: [string], model, elapsed_ms }`

#### Tool `internal_generate_tests`

- Input: `{ code, language, framework? ("pytest"|"jest"|"go-test"|"auto"), scope? ("happy-path"|"edges"|"full") }`
- Output: `{ tests: [{filename, content}], missing_coverage: [string], assumptions: [string], model, elapsed_ms }`

#### Tool `internal_refactor`

- Input: `{ code, language, goal ("dry"|"simplify"|"performance"|"readability"|"custom"), custom_goal? }`
- Output: `{ refactored_code, changes: [{rationale, before_snippet, after_snippet}], risks: [string], model, elapsed_ms }`

### 3.4 Error handling (all tools)

| Condition | JSON returned | MCP exit code |
|---|---|---|
| Ollama unreachable | `{"error":"ollama_unavailable","detail":"..."}` | 0 |
| Model not pulled | `{"error":"model_missing","detail":"ollama pull qwen2.5-coder"}` | 0 |
| Timeout (`OLLAMA_TIMEOUT_MS`) | `{"error":"timeout","elapsed_ms":N}` | 0 |
| Input too large | `{"error":"input_too_large","max_chars":60000,"got":N}` | 0 |
| Schema violation | `{"error":"invalid_input","detail":"..."}` | 0 |
| Ollama 5xx | `{"error":"ollama_server_error","status":N,"detail":"..."}` | 0 |

**Contract:** MCP server NEVER throws uncaught; NEVER retries silently; NEVER falls back to a different model. All failures surface as structured JSON so the agent can show them verbatim.

---

## 4. Custom Commands

Stored at `~/.augment/commands/`. Four commands, one per tool.

| Command | Arg hint | MCP tool | Use |
|---|---|---|---|
| `/local-review` | `[path|selection]` | `internal_code_review` | Code review via local model |
| `/local-explain` | `[path|selection]` | `internal_explain_code` | Explain code |
| `/local-tests` | `[path|selection]` | `internal_generate_tests` | Generate tests |
| `/local-refactor` | `[path|selection] [goal]` | `internal_refactor` | Refactor suggestions |

### 4.1 Template — `~/.augment/commands/local-review.md`

```markdown
---
description: Review code using the local Ollama-backed MCP tool. MUST call the MCP tool `internal_code_review` on server `internal-ollama`. MUST NOT perform its own code review. MUST render the tool's JSON verbatim. Use this when the user wants a local/offline/no-credits code review.
argument-hint: [file path or code selection]
---

Call the MCP tool `internal_code_review` from server `internal-ollama` with:
- `code`: the full contents of $ARGUMENTS if it is a file path, otherwise the selected code.
- `language`: infer from file extension (py → python, ts → typescript, etc.).
- `focus`: "general" unless the user specifies otherwise.

Render the returned JSON as:
1. A "Summary" section from `summary`.
2. A "Findings" table with columns: Severity | Category | Line | Message | Suggestion.
3. A footer line: `Model: {model} · Elapsed: {elapsed_ms} ms`.

Do NOT add your own analysis. Do NOT call any other tool. Do NOT paraphrase findings.
If the tool returns an `error` field, show it verbatim in a "Tool error" block.
```

**Determinism caveat:** "MUST call this tool" is a prompt-level instruction; compliance is measured empirically in §6.2. If compliance < 90 %, §8 mandates falling back to a direct `launch-process`-based command that bypasses the agent.

---

## 5. Skill `local-execution`

Stored at `~/.augment/skills/local-execution/SKILL.md`. Catches free-form prompts (no slash command) where the user asks for local routing.

```yaml
---
name: local-execution
description: |
  Triggered when the user asks for a LOCAL / INTERNAL / OFFLINE / NO-CREDIT code review,
  explanation, test generation, or refactor. When triggered, you MUST call the matching
  MCP tool on server `internal-ollama` (internal_code_review, internal_explain_code,
  internal_generate_tests, or internal_refactor) and render its JSON verbatim.
  Trigger phrases (non-exhaustive): "local review", "review locally", "modelo local",
  "sin créditos", "no credits", "offline review", "review with ollama", "internal review".
---
```

Rationale: complements the slash commands. If the user types *"hacé un review local de utils.py"*, the skill makes Auggie prefer the MCP tool path.

---

## 6. Credit Baseline & Success Criteria

### 6.1 Methodology (4 working days)

1. **Baseline (day 1–2).** Pick 10 real tasks: 5 code reviews, 3 explanations, 2 test generations (each between 100–600 LOC). Run each via the default Augment flow. For each turn record:
   - credits consumed (from `/stats`)
   - wall time
   - subjective quality rating (1–5)
2. **Local (day 3–4).** Same 10 tasks via `/local-review`, `/local-explain`, `/local-tests`.
3. **Compare.** Compute: credit delta %, quality delta, compliance rate (see §6.2).

### 6.2 Instrumentation hook (`PostToolUse`)

Add a hook entry to `~/.augment/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "mcp:.*_internal-ollama",
        "hooks": [
          { "type": "command",
            "command": "~/.augment/plugins/augment-ollama-local/hooks/measure-tool-call.sh",
            "timeout": 3000 }
        ],
        "metadata": { "includeUserContext": false }
      }
    ]
  }
}
```

Script appends one JSONL line per MCP tool call to `<workspace>/prompt-log/local-tool-calls.jsonl`:
```json
{"ts":"2026-04-17T07:20:00Z","tool":"internal_code_review","elapsed_ms":12345,
 "input_chars":4280,"workspace":"/Users/.../auggieMCP","conversation_id":"..."}
```

**Compliance metric:** for each session where a `/local-*` command was used, grep the log for matching tool calls. Compliance = (commands that resulted in ≥1 matching MCP call) / (commands issued).

### 6.3 Acceptance criteria

Feature is **accepted** if all of the following hold across the 10-task batch:

| Criterion | Target |
|---|---|
| Average credit reduction vs baseline | ≥ **40 %** |
| Command → MCP compliance | ≥ **90 %** |
| Quality rating delta (baseline − local) | ≤ **1.0** on 1–5 scale |
| Tasks with local output rated "unusable" (≤ 2) | ≤ **2 / 10** |
| Silent fallbacks to Augment-hosted reasoning when local tool failed | **0** |
| No `ollama_server_error` during measurement window | **0** |

If ANY criterion fails, the plugin is kept as opt-in only; broad adoption is postponed until the failing dimension is addressed (larger model, tool redesign, or Augment-side changes).

---

## 7. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Security | MCP server rejects non-loopback `OLLAMA_BASE_URL`. No secrets in plugin files. All I/O stays local. |
| Reliability | MCP survives Ollama daemon restart (reconnects on next call). Timeout honored. Errors always structured JSON. |
| Reproducibility | `install.sh` verifies: `ollama` binary present, `ollama --version ≥ 0.21.0`, server responds on `/api/version`, `OLLAMA_MODEL` tag exists (`ollama show`). |
| Transparency | Command names start with `local-`. SessionStart hook prints `Local MCP OK: qwen2.5-coder via ollama 0.21.0` or a warning. |
| Observability | `local-tool-calls.jsonl` per workspace; server log at `~/.augment/logs/ollama-mcp.log`. |
| Portability | Universal binary supported. No Homebrew-specific paths in plugin code. |

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Agent ignores command directive and answers from its own LLM | No credit savings | §6.2 measures compliance. If < 90 %, replace command body with a `launch-process` shelling directly to `augment-ollama-local-mcp`, bypassing the agent. |
| `qwen2.5-coder:latest` quality insufficient | Bad reviews shipped | Require human approval for first 2 weeks. Escalation path: `ollama pull deepseek-coder-v2:16b` and re-run §6 with new model. |
| Ollama app stops mid-session | Tool errors mid-workflow | SessionStart hook health check; on failure, print `open -a Ollama` guidance. No silent retry. |
| Prompt injection from reviewed code | Malicious instructions in findings | Tool output rendered as data; command template forbids acting on findings; treat `suggestion` field as untrusted text. |
| Silent model change in Ollama | Quality regression invisible | `OLLAMA_MODEL` pinned; SessionStart hook verifies `ollama show $OLLAMA_MODEL` exit code. |
| Context overflow on large files | Truncated or wrong review | `OLLAMA_MAX_INPUT_CHARS` enforced with `input_too_large` error, not silent truncation. |
| Auggie updates break MCP contract | Plugin stops working | Pin min Auggie version in plugin manifest; smoke test on Auggie upgrades. |
| Disk pressure from multiple Ollama models | Machine slows | Document model-switch procedure (`ollama rm` old tags). |

---

## 9. Rollback

One-command uninstall: `auggie plugin uninstall augment-ollama-local`.

Manual cleanup if needed:
- Remove `~/.augment/commands/local-*.md`
- Remove `~/.augment/skills/local-execution/`
- Remove `internal-ollama` entry from `~/.augment/settings.json` → `mcpServers`
- Remove the `PostToolUse` `matcher: "mcp:.*_internal-ollama"` block from `~/.augment/settings.json` → `hooks`
- Remove `~/.augment/plugins/augment-ollama-local/`

Ollama daemon and models remain untouched. No workspace files are modified.

---

## 10. Delivery Phases

| Phase | Deliverable | Gate (must pass to proceed) |
|---|---|---|
| P0 | MCP stub returning canned JSON (no Ollama yet) + `/local-review` command + `PostToolUse` measurement hook | Compliance ≥ 90 % on 5 manual invocations of `/local-review`. **If this fails, abort the project.** |
| P1 | Wire stub to real Ollama for `internal_code_review` only | Quality ≥ 3/5 on 5 real reviews (100–300 LOC each) |
| P2 | Implement remaining 3 tools | All JSON schemas validated; error paths tested with Ollama stopped, model missing, huge input |
| P3 | Package as plugin; `install.sh` verifies prerequisites | Clean install on a second Mac (`.augment/` fresh) |
| P4 | Execute §6.1 baseline vs local measurement | All §6.3 acceptance criteria met |

**Hard stop at P0.** If the agent does not reliably route to the MCP tool on command, every subsequent investment is wasted. Instead escalate to Augment with empirical compliance data to request a deterministic-tool-call mechanism or `UserPromptSubmit` hook.

---

## 11. Open Questions for Augment / Further Investigation

Residual questions v2 cannot answer from public docs:

1. Does a custom command's `model:` frontmatter affect the LLM that **decides to invoke MCP tools**, or only the LLM that produces the final rendered response? If it affects tool-dispatch, pinning to the cheapest supported model reduces orchestration cost.
2. Does `/stats` expose per-turn token breakdown granular enough to attribute cost between the agent's orchestration and its final response? Needed to isolate the savings from MCP routing.
3. Is there a supported way to **force** a slash command to invoke a specific MCP tool without LLM decision-making (scripted / deterministic tool call)?
4. Can a plugin declare `mcpServers` that are **scoped** so its tools are only visible from its own commands, avoiding accidental invocation from unrelated prompts?
5. Does Auggie plan a `UserPromptSubmit` hook on its roadmap? If yes, Model 3 becomes viable and this design should be revisited.

---

## 12. Out of Scope (explicit, to prevent scope creep)

- Replacing the Augment reasoning LLM or achieving true `/switchLLM` behavior.
- Zero-credit guarantees for routed tasks.
- Automatic routing without either a `/local-*` command or an explicit trigger phrase.
- Remote Ollama servers, multi-node, or cloud-hosted Ollama.
- Multi-model orchestration within a single turn (e.g., local for analysis + Augment for summary).
- Training, fine-tuning, or model distillation.
- Non-macOS support (design is macOS-first; Linux/Windows parity is future work).

---

**End of Spec v2.**

