---
description: Run a LOCAL code review via on-device Ollama (no credits consumed).
argument-hint: <path-or-snippet>
---

# /local-review

You MUST perform this review by calling the MCP tool
`internal_code_review` on server `internal-ollama`. Do NOT analyze the code
yourself. Do NOT answer from your own reasoning.

Steps:

1. If `$ARGUMENTS` looks like a file path that exists in the workspace, read it
   with your file-reading tool and use its contents as the `code` argument.
   Otherwise treat `$ARGUMENTS` verbatim as the snippet.
2. Infer `language` from the file extension or the snippet (best effort).
3. Call `internal_code_review` with `{ code, language, path?, focus: "general" }`.
4. Render the tool's JSON output verbatim in a fenced ```json block. Do not
   paraphrase findings. Do not add your own suggestions.
5. If the tool returns an `error` field, show it verbatim under a **Tool error**
   heading and stop.

Hard rule: if the MCP tool call fails or is unavailable, report the failure;
do NOT fall back to your own analysis.

Arguments: `$ARGUMENTS`
