---
id: protocol/working-memory
version: 0.1.0
status: draft
summary: "Using markdown notes as agent external working memory to manage context limits and prevent hallucinations."
applies-to: [vault, codebase]
settings:
  memory_folder:
    description: "Folder for agent notes, plans, and working context"
    default: "AI"
  active_context_file:
    description: "File used for tracking active task context across turns"
    default: "ACTIVE_CONTEXT.md"
requires: []
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
3. Establish active state tracking in `{{memory_folder}}/{{active_context_file}}` or `{{memory_folder}}/00_INDEX.md` mapping what will be investigated.

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

Once research notes are written to disk, read **only from the notes files in `{{memory_folder}}/`** (not the raw source materials) to synthesize the master plan or design document (such as `{{memory_folder}}/IMPLEMENTATION_PLAN.md` or `{{memory_folder}}/{{active_context_file}}`).

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

---

## Standard memory file types

| File | Purpose | Example path |
|---|---|---|
| Index / Map | Maps active files, scope, and purpose | `{{memory_folder}}/00_INDEX.md` |
| Active Context | Tracks current task state across turns | `{{memory_folder}}/{{active_context_file}}` |
| Section / Module Notes | Summarizes a single investigated subsystem or source chunk | `{{memory_folder}}/notes/01_auth_flow.md` |
| Concept Notes | Defines a core domain concept or data structure | `{{memory_folder}}/notes/concept_state_machine.md` |
| Gotcha Notes | Captures non-obvious traps, bugs, and API quirks | `{{memory_folder}}/gotchas/async_lock_quirk.md` |
| Dependency Map | Documents package dependencies and version pins | `{{memory_folder}}/notes/dependency_map.md` |
| Decision Log | Records chosen approach and rejected alternatives | `{{memory_folder}}/notes/decisions.md` |
| Implementation Plan | The master plan for executing the task | `{{memory_folder}}/IMPLEMENTATION_PLAN.md` |

---

## The Key Rule

> **Never synthesize before all research notes are written to disk. Never execute before the master plan exists.**

Skipping intermediate notes files and jumping straight to implementation is the primary cause of hallucinations, dropped requirements, and forgotten edge cases during complex tasks.

---

## Changelog

### [Unreleased]

#### Added
- Initial draft of the external working memory protocol.
