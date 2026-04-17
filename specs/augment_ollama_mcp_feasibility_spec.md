# Functional Specification
## Augment + Local Ollama via MCP with Command-Based Switching

**Document purpose**

This document defines a target architecture, behavioral requirements, constraints, and feasibility questions for using **Augment / Auggie** with a **local MCP server backed by Ollama** so that selected code-review and code-generation workflows can be routed to an internal local model instead of consuming Augment credits.

This spec is intentionally written as a feasibility and implementation brief for Augment itself to evaluate against its current supported capabilities.

---

## 1. Objective

Enable a developer using Augment / Auggie to switch, at command level, between:

- **Augment-native execution** using Augment-supported models and normal agent behavior
- **Internal execution** using a **local MCP server** that calls **Ollama** and uses a model already installed on the machine

The desired user experience is a simple command interface such as:

- `/switchLLM internal`
- `/switchLLM augment`

or equivalent commands such as:

- `/internal-review`
- `/internal-generate`
- `/augment-review`
- `/augment-generate`

The main business goal is to reduce unnecessary Augment credit consumption for tasks that can be handled acceptably by a local model.

---

## 2. Background and documented Augment capabilities

Based on current Augment documentation, the following capabilities are documented:

### 2.1 MCP support

Auggie supports **Model Context Protocol (MCP) servers** and allows them to be configured in `~/.augment/settings.json` or via `auggie mcp add ...`. MCP servers may be configured with local command execution or HTTP/SSE transport. The documentation describes MCP as a way to connect **external tools and data sources** to Auggie. It also documents `/mcp` for inspection and CLI subcommands for add/list/remove.  
Source basis: Augment docs for Integrations and MCP.

### 2.2 Custom slash commands

Auggie supports **custom slash commands** stored as Markdown files. These commands support frontmatter such as:

- `description`
- `argument-hint`
- `model`

The documented meaning of `model` is: **specify the model to run this command with, overriding the CLI default model**.

### 2.3 Plugins

Auggie plugins can package together:

- custom commands
- subagents
- rules
- hooks
- skills
- MCP server integrations

This means a complete solution could potentially be distributed as a reusable plugin.

### 2.4 Hooks

Auggie supports hooks, including events such as:

- `SessionStart`
- `PreToolUse`
- `PostToolUse`

Session-start hooks can inject context. Tool hooks expose metadata around tool execution.

### 2.5 Skills

Auggie supports skills loaded from user or workspace directories and exposed via `/skills`. Skills provide domain- or workflow-specific guidance and instructions to the agent.

### 2.6 Model selection

Current Augment model documentation lists supported models from Anthropic, Google, and OpenAI. The current models page does **not** document Ollama or a generic “bring your own model” backend for the core Augment model runtime.

---

## 3. Core feasibility question

### Primary question

**Can Augment / Auggie switch its primary LLM execution path between Augment-supported hosted models and a local Ollama-backed MCP server by means of a slash command or equivalent user command?**

### More precise sub-questions

1. Can a slash command such as `/switchLLM internal` change the **actual agent model provider/runtime** for subsequent interactions?
2. Can a custom command or plugin redirect an entire prompt or agent task to a local MCP tool while avoiding normal Augment model execution for the task?
3. Can hooks intercept user intent early enough to reroute prompt handling to an MCP-backed local model instead of the built-in Augment agent model?
4. Is there any supported mechanism for “bring your own model” as the underlying reasoning engine, as opposed to using MCP only for tools?
5. If full switching is not supported, what is the **closest supported pattern** to achieve near-equivalent behavior with minimal Augment credit usage?

---

## 4. Desired functional behavior

### 4.1 User-facing behavior

The system should support a clear workflow toggle between two modes:

#### Mode A: Augment mode
Use Augment normally:

- Augment-native model selection
- standard Auggie orchestration
- standard credit consumption rules
- standard agent behavior, tool usage, and context handling

#### Mode B: Internal mode
Use internal local compute through Ollama:

- route selected code-related tasks to a local MCP server
- use a locally installed Ollama model
- minimize Augment credit usage as much as Augment architecture allows
- keep the workflow simple and repeatable from within Auggie

### 4.2 Command ergonomics

Preferred command interface:

```text
/switchLLM internal
/switchLLM augment
```

Acceptable alternatives if global switching is unsupported:

```text
/internal-review
/internal-generate
/internal-refactor
/augment-review
/augment-generate
```

### 4.3 Scope of tasks for internal mode

Internal mode should ideally support at least:

- code review
- code explanation
- code generation
- refactoring suggestions
- test generation
- documentation generation for code

### 4.4 Scope boundaries

This spec does **not** require replacing every Augment feature. If only a subset can be routed to Ollama, that is acceptable provided the behavior is explicit and reliable.

---

## 5. Proposed target architecture

### 5.1 Components

1. **Auggie / Augment**
2. **Local MCP server**
3. **Ollama runtime**
4. **Installed local model**
5. Optional packaging as an **Augment plugin**
6. Optional command wrappers as **custom slash commands**
7. Optional behavior assistance via **hooks** and/or **skills**

### 5.2 Conceptual flow for internal mode

```text
User invokes internal command in Auggie
-> Auggie resolves custom command / plugin behavior
-> Auggie calls MCP tool exposed by local MCP server
-> MCP server sends request to local Ollama instance
-> Ollama runs installed local model
-> MCP server returns structured result to Auggie
-> Auggie displays or uses the result
```

### 5.3 Candidate MCP tools

The local MCP server may expose tools such as:

- `internal_code_review`
- `internal_codegen`
- `internal_refactor`
- `internal_explain_code`
- `internal_generate_tests`

### 5.4 Candidate local server behavior

The MCP server should:

- accept prompt + code context
- support file snippets or selected file paths
- call Ollama locally
- return structured markdown or JSON
- enforce prompt templates per task type
- handle timeouts and model unavailability gracefully

---

## 6. Feasibility models to evaluate

Augment should assess the following implementation models in order.

### Model 1: True global LLM switching

**Goal:** `/switchLLM internal` changes the active runtime so that subsequent requests are handled by local Ollama instead of Augment-hosted models.

**Questions:**

- Is this supported today?
- Can custom commands change persistent model-routing state?
- Can plugin state persist this choice across commands or session scope?
- Can hooks alter core model dispatch?

**Success criterion:**
Auggie uses local Ollama as the effective primary model runtime for subsequent tasks.

### Model 2: Per-command task routing to MCP

**Goal:** dedicated commands route only specific tasks to local MCP/Ollama.

Examples:

- `/internal-review`
- `/internal-generate`
- `/internal-refactor`

**Questions:**

- Can a custom command force execution through an MCP tool path?
- Can the command pass selected files, current buffer, or prompt text to the MCP tool reliably?
- How much Augment model usage still occurs in the orchestration layer?

**Success criterion:**
Selected workflows are mostly handled by local Ollama via MCP, even if Augment still performs lightweight orchestration.

### Model 3: Hook-assisted automatic routing

**Goal:** hooks inspect intent or tool usage and automatically steer certain tasks toward MCP/Ollama.

**Questions:**

- Can hooks rewrite, block, or redirect a prompt before standard model handling?
- Can hooks call external scripts that influence downstream execution path?
- Is this reliable and supported, or only advisory?

**Success criterion:**
Tasks matching a rule set are routed with minimal user friction and predictable behavior.

### Model 4: Plugin-packaged hybrid workflow

**Goal:** package MCP + commands + hooks + skills into a reusable plugin that provides an internal/local workflow profile.

**Questions:**

- Can a plugin provide an ergonomic command suite that feels like LLM switching?
- Can the plugin package and auto-register MCP server definitions?
- Can plugin installation make the workflow team-friendly and reproducible?

**Success criterion:**
Even if true model replacement is unsupported, a plugin provides a clean operational substitute.

---

## 7. Required technical capabilities to validate

Augment should explicitly validate whether each capability is:

- **Supported**
- **Partially supported**
- **Unsupported**
- **Possible only with workaround**

### 7.1 MCP execution

- Register a local MCP server in `~/.augment/settings.json`
- Register via `auggie mcp add`
- Invoke MCP tools from Auggie in a controlled way
- View and debug MCP registration with `/mcp`

### 7.2 Command-driven orchestration

- Define custom slash commands in Markdown
- Use frontmatter metadata
- Pass user input arguments to command logic
- Select a documented Augment model with `model:` frontmatter
- Invoke tool-based workflows from a slash command

### 7.3 Context passing

- Pass selected code
- Pass current file contents
- Pass diff/patch context
- Pass repository context
- Pass instructions and style requirements
- Pass large code context without breaking the workflow

### 7.4 Session or mode state

- Store a current mode such as `internal` or `augment`
- Make later commands aware of the selected mode
- Persist the mode for current session or workspace
- Surface the active mode clearly to the user

### 7.5 Hook intervention

- Detect a mode at `SessionStart`
- Inject context about preferred routing
- Inspect `PreToolUse` or related events
- Influence downstream behavior without unsupported hacks

### 7.6 Credit optimization

- Minimize hosted-model usage during internal workflows
- Understand whether command parsing and orchestration still consume credits
- Determine whether full zero-credit routing is achievable or not

---

## 8. Non-functional requirements

### 8.1 Security

- All Ollama traffic should remain local unless explicitly configured otherwise
- No secrets should be hardcoded into plugin or config files
- The local MCP server must be from a trusted source and auditable

### 8.2 Reliability

- Graceful failure when Ollama is not running
- Graceful failure when target model is missing
- Clear fallback behavior
- No silent switching failures

### 8.3 Developer ergonomics

- Switching must be simple
- Internal and Augment workflows must be easy to distinguish
- Setup must be reproducible across machines
- Ideally packageable via plugin

### 8.4 Transparency

The user should always know:

- which mode is active
- whether a request is being handled by Augment or local Ollama
- whether credits are expected to be consumed

---

## 9. Candidate implementation patterns

These patterns are listed from most desirable to most likely.

### Pattern A: Real model backend switching

#### Description
Auggie changes the underlying model runtime between Augment-hosted models and local Ollama.

#### Pros
- closest to requested UX
- simple mental model
- likely best for credit avoidance

#### Cons
- may not be supported by current architecture
- not documented in current model support pages

#### Question for Augment
Is there any official or unofficial supported extension point for replacing the core model runtime with a local provider such as Ollama?

### Pattern B: MCP as a task execution backend

#### Description
Auggie stays in control, but specific commands route heavy tasks to MCP tools backed by Ollama.

#### Pros
- aligned with documented MCP usage
- likely implementable
- good partial credit savings

#### Cons
- not a true provider switch
- Augment may still consume some credits in orchestration

#### Question for Augment
Can custom commands be designed so that the agent deterministically invokes a specific MCP tool and performs minimal additional reasoning?

### Pattern C: Command aliases that simulate switching

#### Description
Instead of a persistent switch, provide explicit task commands for internal vs Augment workflows.

#### Pros
- easy to explain
- avoids fragile hidden state
- likely simplest supported design

#### Cons
- less elegant than a global switch
- user must choose per task

#### Question for Augment
What is the best-practice supported way to implement this pattern today?

### Pattern D: Plugin-wrapped hybrid workflow

#### Description
Package MCP servers, commands, hooks, and skills into a plugin that standardizes the internal workflow.

#### Pros
- reusable
- maintainable
- team installable

#### Cons
- may still not solve true backend replacement
- can add complexity

#### Question for Augment
What plugin structure would Augment recommend for this use case?

---

## 10. Example desired artifacts

### 10.1 Example Auggie settings entry for local MCP

```json
{
  "mcpServers": {
    "internal-ollama": {
      "command": "/usr/local/bin/internal-ollama-mcp",
      "args": ["--stdio"],
      "env": {
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "my-local-model"
      }
    }
  }
}
```

This is illustrative only. The question is whether Augment can use this merely as a tool provider or as a true model-execution backend.

### 10.2 Example custom command for explicit internal review

```md
---
description: Review code using the internal Ollama-backed MCP workflow
argument-hint: [review target or instructions]
---

Use the internal MCP-based review workflow for this request.
Prefer the internal-ollama MCP tools for analysis and review.
Be explicit that this is an internal/local execution path.
Request: $ARGUMENTS
```

### 10.3 Example conceptual switch command

```md
---
description: Switch active LLM mode between augment and internal
argument-hint: <augment|internal>
---

Set the active execution mode to "$ARGUMENTS".
For internal mode, prefer local MCP/Ollama workflows.
For augment mode, use normal Augment-native execution.
Confirm the active mode after switching.
```

Important feasibility question: can this command truly change later behavior in a persistent and supported way, or is it only a prompt instruction with no hard routing guarantees?

---

## 11. Expected limitations to assess honestly

Augment should explicitly confirm whether the following limitations apply:

1. MCP is only for tools and external systems, not a replacement for the core model runtime.
2. Custom commands can select only Augment-supported models through `model:` frontmatter.
3. Hooks can inject context or react to tool events but cannot replace core LLM dispatch.
4. A plugin can improve ergonomics but cannot bypass unsupported model-routing architecture.
5. Some Augment credit usage may still occur even when an MCP tool does most of the work.

---

## 12. Decision matrix requested from Augment

Please answer the following with **Yes / No / Partial**, plus implementation notes.

| Question | Yes / No / Partial | Notes |
|---|---|---|
| Can Auggie use a local Ollama backend as the primary model runtime? |  |  |
| Can MCP be used as a true LLM replacement rather than only a tool layer? |  |  |
| Can a slash command persistently switch model-routing mode for later prompts? |  |  |
| Can hooks redirect a user request before hosted model reasoning occurs? |  |  |
| Can a custom command force deterministic invocation of a specific MCP tool? |  |  |
| Can a plugin package this workflow cleanly for reuse? |  |  |
| Can the internal path reduce credit usage materially? |  |  |
| Can the internal path reduce credit usage to zero for routed tasks? |  |  |
| What is the closest fully supported architecture to the requested outcome? |  |  |

---

## 13. Recommended fallback outcome if full switching is unsupported

If full provider switching is not supported, the recommended fallback should be:

### Supported fallback target

A **hybrid internal workflow** where:

- Auggie remains the orchestrator
- a local MCP server backed by Ollama performs selected heavy tasks
- custom slash commands explicitly select internal workflows
- optional hooks and skills improve consistency
- optional plugin packaging makes the setup reusable

### Minimum acceptable UX

```text
/internal-review
/internal-generate
/internal-refactor
/augment-review
/augment-generate
```

### Desired answer from Augment

If this fallback is the only supported design, please provide:

1. the recommended architecture
2. the exact command/plugin structure
3. the limits on routing guarantees
4. the expected impact on credit usage
5. the cleanest way to package and maintain it

---

## 14. Final request to Augment

Please evaluate this specification against **current documented and supported Augment capabilities** and answer with:

1. **What is fully supported**
2. **What is partially supported**
3. **What is not supported**
4. **What workaround architecture you recommend**
5. **Whether true switching between Augment-hosted models and local Ollama is possible**
6. **If not, what is the best achievable equivalent**

Please be explicit about the boundary between:

- core model selection
- custom command behavior
- MCP tool invocation
- plugin packaging
- hook-based influence
- actual credit consumption

---

## 15. Documentation basis used for this spec

This spec is based on the current Augment documentation areas covering:

- Integrations and MCP
- Plugins
- Hooks
- Skills
- Custom Commands
- Available Models

Key documented themes reflected in this spec:

- MCP is described as an integration path for external tools and systems
- MCP servers can be added via config or CLI
- custom commands support frontmatter including `model`
- plugins can package MCP servers, commands, hooks, and skills
- hooks expose session and tool lifecycle events
- available model documentation lists Augment-supported hosted models, without documenting Ollama as a core runtime option

