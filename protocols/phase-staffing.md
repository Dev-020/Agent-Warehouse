---
id: protocol/phase-staffing
version: 0.1.0
status: draft
summary: Before a phase or task is built, decide staffing from three things in order (size, coupling, model), show the user the table, and verify every agent's report against its raw evidence.
applies-to: [codebase]
settings:
  memory_folder:
    description: "Folder for agent notes, plans and briefs"
    default: "AI"
requires: []
replaces: null
---

# Phase Staffing Protocol

How a coordinating agent (such as the Orchestrator in [[phased-implementation]], or a lead session in paired/swarm pipelines) decides **who builds a phase or task**: how many agents, whether they run sequentially (one continued agent vs. fresh agents per step) or side by side, and on which model tier. It is evaluated fresh for every phase, derived directly from the task's properties, and presented to the user before implementation begins.

When used with [[phased-implementation]], it refines:
- The legacy "one fresh agent per step" rule into three distinct staffing shapes chosen by size and coupling.
- The legacy "use the strongest model available" advice into deliberate per-phase model tiers.

## Why it exists

Staffing setups that work for one task or milestone are often blindly carried into the next out of habit. In the case this protocol originated from, an Orchestrator proposed five fresh agents on the strongest model for a phase whose five steps were tiny and built directly on each other. Starting five fresh agents would have paid the cold-start context penalty five times over for no benefit. One agent continued across the steps on a mid-tier model was sufficient, cutting token usage by half or more.

Token usage, rate limits, and wall-clock time are scarce resources. The staffing shape decides all three.

## The three questions, in order

### 1. Size: how long and how heavy is each step?
Estimate, for each step or phase:
- The new code and tests, in lines of code.
- The expected wall-clock time to build it.
- The number of agent runs needed (implementers, reviewer, fix rounds).

Base estimates on how earlier phases of the same project progressed. State plainly that they are estimates, and refine them when drafting the brief.

### 2. Coupling: how do the steps connect?
List the files each step modifies and what each step requires from the others. Then choose the staffing shape:

| Coupling | What it looks like | Staffing shape |
|---|---|---|
| **Tight** | Each step builds on the last; steps share files; later steps depend on code written in earlier steps | **One implementer, continued across steps.** One commit per step. The coordinator checks each commit, then instructs the same agent to continue. |
| **Loose** | Steps touch disjoint files and share no runtime state | **Separate agents.** Run side by side when no files overlap; run sequentially otherwise. |
| **Large and loosely related** | Each step is large enough to saturate an agent's working context alone | **A fresh agent per step.** |

Rules for the tight shape:
- The implementer must stop after each commit and wait. It never runs ahead unverified.
- Replace the implementer with a fresh agent at a step boundary if it drifts: repeating mistakes, forgetting rules in the brief, or returning vague reports.
- The entire phase must fit within one context window. If it will not, split the phase into subphases or switch to fresh agents per step.

Rules for building side by side:
- **Check file overlap first,** file by file, from the briefs. Even one shared file makes steps sequential.
- Each brief must list the other phase's files under "files you must not touch".
- Each phase operates in its own worktree and branch, per [[worktree-claims]].
- **Merges, the full test suite run, and live verification checks stay strictly serial.**
- Running two agents simultaneously burns rate limits and context twice as fast. Inform the user before launching parallel agents.
- A large phase can be split so an independent sub-component runs side by side with another phase (e.g., a pure tool service built beside a UI phase).

### 3. Model: does it need the strongest one?

| Use a mid-tier model (e.g. Sonnet / Flash) when: | Use the strongest model (e.g. Opus / Pro) when: |
|---|---|
| The brief is prescriptive: names, types, formats, and test cases are explicitly given | A mistake **fails open**: authentication, tokens, security boundaries, sandboxes, permission rules |
| The work consists of new, isolated modules | The work manages a lifecycle across threads/processes, or a complex state machine |
| The work is storage, queries, or standard CRUD operations | The work is performance-sensitive rendering or a tight hot path |
| The work is adding or updating unit tests | The change touches shared legacy code with unwritten invariants |

- **The reviewer is always on the strongest model.** A mid-tier implementer paired with a top-tier reviewer is dramatically cheaper than a top-tier implementer, while ensuring critical defect detection.
- A wrong "mid-tier" call costs extra review findings and a larger fix round. Acknowledge this tradeoff when proposing it.
- Prefer a tighter, more prescriptive brief over a stronger model. If a task needs a frontier model only because the brief leaves choices open, close those choices in the brief first.

## The staffing table

Plans should present a staffing table across phases, and every brief should open with its assigned row:

| Phase | Size (new code; build time) | Needs | Can be built beside | Implementer |
|---|---|---|---|---|
| P1 | 1,000–1,300 lines; 2–3 h | nothing | **P2** | one, mid-tier |
| P2 | 500–700 lines; 1.5–2.5 h | nothing | **P1** | one, mid-tier |
| P3 | 700–1,000 lines; 2.5–3.5 h | P1, P2 | nothing | one, strongest: shared UI code |

When requesting user approval, state the three answers and rationale concisely. The user makes the final determination and may route specific phases to different models or agent harnesses.

## Reports are checked against their raw evidence

Delegating work across multiple agents or external tools is only reliable if reports are objectively verifiable:

1. **Every number, measurement, and quote in a report must name the raw file it originates from.** Require this in the brief. If something was not measured, the report must explicitly state "not tested".
2. **The coordinator must verify raw data before merging or building on a result.**
   - For code commits: verify the commit hash, clean tree, files touched, and passing changed tests.
   - For probes and benchmarks: recompute a sample of numbers directly from the raw output files, and inspect the raw execution stream where assertions about tool behavior are made.

A report may quote what a model claimed happened rather than what the execution stream actually recorded. Independent raw-file inspection prevents building subsequent phases on false premises.

## Fallbacks

| Situation | Action |
|---|---|
| Continued implementer drifts or degrades | Replace with a fresh agent at the next step boundary; provide the brief and completed commits so far. |
| Side-by-side tasks conflict on a shared file | Stop that agent, report the collision, and serialize the remaining work. |
| Mid-tier implementer triggers design-level review blockers | Escalate the fix round (or remaining steps) to the strongest model. |
| Sizing estimate was significantly inaccurate | Record actual numbers in the session log; calibrate subsequent phase estimates accordingly. |
| Report numbers contradict raw output files | Refuse merge. Issue a corrections list citing the contradictory files and enforce raw-file citations. |

## Open points

- Model selection heuristics reflect empirical trials across software and desktop automation tasks; they should be adjusted based on project domain.
- "Fits one context" varies by model; typical single-implementer phases range from 1,500 to 3,000 lines (including tests) before context degradation becomes measurable.

---

## Changelog

### [Unreleased]

### [0.1.0] - 2026-10-02
#### Added
- Initial draft of the phase staffing protocol, distilled from Shadow Cursor #063.
- Three-question staffing decision framework (size, coupling, model) supporting single continued agents, fresh agents, and side-by-side pairings.
- Raw-evidence verification rule for agent and subagent reports.
