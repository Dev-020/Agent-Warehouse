---
id: protocol/working-memory
version: 0.2.0
status: draft
summary: "Using markdown notes as agent external working memory to manage context limits and prevent hallucinations."
applies-to: [vault, codebase]
settings:
  memory_folder:
    description: "Folder for agent notes, plans, and working context"
    default: "AI"
  active_context_folder:
    description: "Folder inside memory_folder that holds the active-context router note and one file per work item"
    default: "ACTIVE_CONTEXT"
requires: [template/active-context@0.1]
replaces: null
---

# External Working Memory

A structured workflow for executing complex tasks — deep research, multi-file code modifications, architectural refactors, and multi-session projects — without exhausting context window limits or inducing hallucinations under memory pressure.

Related protocols:
- Operating constraints and working posture: [[agent-protocol]]
- Session logs and cross-session handoffs: [[session-log]]
- Verification discipline and citations: [[research-discipline]]

---

## Core Principle

**Disk is memory. The context window is RAM.**

For non-trivial tasks, never attempt to hold raw source files, dependency graphs, bug traces, and execution plans simultaneously in model memory. Instead, follow this pipeline:

> **Read & Research → Write notes to disk (`{{memory_folder}}/`) → Clear RAM → Synthesize plan from notes → Execute & Verify**

Offloading intermediate findings to markdown notes on disk prevents hallucinations caused by context saturation and generates persistent, auditable artifacts that survive across agent turns and multi-agent handoffs.

---

## When to trigger this workflow

Use this workflow whenever a task meets **two or more** of the following conditions:

- **Large source material:** Spans multiple files, extensive documentation, large datasets, or unfamiliar third-party libraries.
- **Multi-phase execution:** Requires distinct stages (research → architecture plan → code modification → test verification).
- **High accuracy requirement:** Involves production code, delicate algorithms (e.g. geometric projections, financial math, state machines), or architectural invariants.
- **Multi-session continuity:** Expected to span multiple turns, conversation restarts, or handoffs between different agents.

Skip this procedure for trivial, single-step operations (e.g. fixing a typo, updating a single comment, formatting a table).

---

## The 5-Phase Workflow

```
[Phase 1: Scoping] ──> [Phase 2: Chunked Research] ──> [Phase 3: Synthesis Plan]
                                                                  │
[Phase 5: Verification & Archival] <── [Phase 4: Surgical Execution] ┘
```

### Phase 1 — Scoping

Before modifying any code or creating final deliverables, establish task boundaries:
1. Define the explicit deliverables and acceptance criteria.
2. Identify which source documents, modules, or APIs must be inspected.
3. Establish active state tracking: a work-item file in `{{memory_folder}}/{{active_context_folder}}/` and its row in the router (see [The active context](#the-active-context)), or `{{memory_folder}}/00_INDEX.md` mapping what will be investigated.

### Phase 2 — Chunked Research & Investigation

Inspect source material in small, focused chunks. Immediately after reading each chunk, **write a structured notes file to `{{memory_folder}}/`** before inspecting the next chunk.

Each notes file should be:
- **Focused:** Covers a single topic, subsystem, or interface.
- **Self-contained:** Comprehensible on its own without re-reading the raw source.
- **Linked:** Cites the exact source file and line numbers.

#### Sourcing discipline: Excerpts vs References

Choose the citation depth based on the source medium:

- **Embed verbatim excerpts** when the source is human-authored prose, specifications, policy, or academic text where specific wording and phrasing are load-bearing:
  > *"The completeness axiom guarantees that every non-empty set of real numbers bounded above has a least upper bound."* `*(analysis_spec.md:L42)*`
- **Use locator references only** when the source is code, structured data, or execution logs:
  `*(see TokenValidator in auth/tokens.py:L85-L110)*`
  `*(see retry loop defect in client.py:L214)*`
  Do not embed large blocks of raw code into working notes; the value lies in the analysis and interface contract written around the reference.

### Phase 3 — Synthesis → Master Plan

Once research notes are written to disk, read **only from the notes files in `{{memory_folder}}/`** (not the raw source materials) to synthesize the master plan or design document (such as `{{memory_folder}}/IMPLEMENTATION_PLAN.md`). The active context points to the plan; it does not hold it.

The master plan:
- Orders steps logically with explicit dependencies.
- References the underlying research notes for rationale and trade-offs.
- Omits raw excerpts — it serves as the clean, synthesized execution blueprint.

### Phase 4 — Surgical Execution

Execute against the synthesized plan:
- Make minimal, targeted modifications.
- Preserve unrelated code, existing docstrings, and established style conventions.
- If unexpected bugs or ambiguities arise mid-execution, **write a new note to `{{memory_folder}}/`** rather than attempting to juggle debugging context in model RAM.

### Phase 5 — Verification & Archival

Verify results against the scoping criteria:
- Run automated test suites and linters.
- Verify runtime behavior or user interfaces where applicable.
- Decide what to retain:
  - Move durable insights, discovered gotchas, and architectural decisions into permanent project documentation.
  - Archive or remove ephemeral, session-specific scratchpad notes.
  - Empty the work item's active-context file per [Keeping it small](#keeping-it-small), and delete it when the item closes.

---

## Standard memory file types

| File | Purpose | Example path |
|---|---|---|
| Index / Map | Maps active files, scope, and purpose | `{{memory_folder}}/00_INDEX.md` |
| Active Context | The router note: what is in progress, who owns it, which file to read | `{{memory_folder}}/{{active_context_folder}}/{{active_context_folder}}.md` |
| Work-item context | One work item's current state: now, next, open questions | `{{memory_folder}}/{{active_context_folder}}/<id>-<slug>.md` |
| Section / Module Notes | Summarizes a single investigated subsystem or source chunk | `{{memory_folder}}/notes/01_auth_flow.md` |
| Concept Notes | Defines a core domain concept or data structure | `{{memory_folder}}/notes/concept_state_machine.md` |
| Gotcha Notes | Captures non-obvious traps, bugs, and API quirks | `{{memory_folder}}/gotchas/async_lock_quirk.md` |
| Dependency Map | Documents package dependencies and version pins | `{{memory_folder}}/notes/dependency_map.md` |
| Decision Log | Records chosen approach and rejected alternatives | `{{memory_folder}}/notes/decisions.md` |
| Implementation Plan | The master plan for executing the task | `{{memory_folder}}/IMPLEMENTATION_PLAN.md` |

---

## The active context

The active context is what a session reads first to pick up where the last one stopped. It is a
folder, `{{memory_folder}}/{{active_context_folder}}/`, laid out by [[active-context]]
(`template/active-context`):

- **A router note**, `{{active_context_folder}}.md`, read by every session. At most 6,000 characters (`wc -m`): one row per
  work item (owner, status, link) and where standing rules, decisions, history and open issues live.
- **One file per work item**, holding only that item's current state. Keyed by the work item, not by
  the session: sessions end, the work goes on, and the next session takes over the file.

### Why it is not in `AGENTS.md` or `CLAUDE.md`

Those files load into every agent and subagent, they hold rules rather than state, and they change
rarely. The active context changes every phase, and only the session that owns an item needs that
item's state. Keeping them apart means a subagent never pays for, or acts on, the owner's to-do list.

### Read tiers

The router says who reads what. Don't leave it to an agent to decide whether it has read enough:
right after a compaction is exactly when it reads too little.

| Reader | Reads |
|---|---|
| Every session | The router, to the end |
| The session that owns an item | That item's file, all of it, at the start and after every compaction |
| Anyone, when the item's file points there | The plan, notes, older session logs |

### Keeping it small

The active context exists to save tokens. It only does that while it stays small, and it grows when
nothing ever leaves it. At every hand-over (the end of a phase, before a compaction, or when an item
changes owner) the owner sends each line of the item's file to its home:

| The line is… | It goes to |
|---|---|
| Done | The session log ([[session-log]]) |
| A decision | The plan, or the brief for a one-phase decision |
| An unresolved issue or finding | Handled per [[issue-triage]] |
| A rule that will outlast the item | The project's instruction file (e.g. `AGENTS.md`) |
| Still current | Stays |

When the item closes, its file is deleted and its row leaves the router. Git keeps the old text.

---

## The Key Rule

> **Never synthesize before all research notes are written to disk. Never execute before the master plan exists.**

Skipping intermediate notes files and jumping straight to implementation is the primary cause of hallucinations, dropped requirements, and forgotten edge cases during complex tasks.

---

## Changelog

### [Unreleased]

### [0.2.0] - 2026-10-12
#### Changed
- **BREAKING:** the active context is now a folder: a router note every session reads (6,000
  characters at most) plus one file per work item, laid out by `template/active-context`. The setting
  `active_context_file` (default `ACTIVE_CONTEXT.md`) is replaced by `active_context_folder` (default
  `ACTIVE_CONTEXT`).
  **Migration:**
  1. Create `{{memory_folder}}/{{active_context_folder}}/` and its router `{{active_context_folder}}.md` from the template.
  2. For each item in progress in the old file, create its work-item file holding only its current
     state, and add its row to the router.
  3. Send the rest of the old file to its homes per "Keeping it small". Anything with no home goes into a
     session log dated the day of the migration, so nothing is lost.
  4. Delete the old `ACTIVE_CONTEXT.md` (git keeps it) and point any reference to it at the router.
  5. If `.warehouse.yml` sets `active_context_file`, replace it with `active_context_folder` (a folder
     name, without `.md`).
- Phase 3 no longer suggests the active context as a place for the master plan; it points to the plan.
#### Added
- "The active context" section: why it is kept out of `AGENTS.md`/`CLAUDE.md`, read tiers, and the
  hand-over eviction table.
- Phase 5 empties the work item's active-context file and deletes it when the item closes.
- Requires `template/active-context@0.1`.

### [0.1.0] - 2026-09-15
#### Added
- Initial draft of the external working memory protocol.
