---
id: protocol/phase-staffing
version: 0.2.0
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

## Handing work to another engine

A phase, part of a phase, or a probe can go to another engine's agents when the coordinating side is short of usage, when the user chooses it, or to build two loose phases at once.

**Choose the split, and say who reviews:**

| Split | The other engine runs | The coordinating side keeps | Fits when |
|---|---|---|---|
| **Complete pipeline** | Its own orchestrator, implementer and reviewer: it builds, reviews, fixes, and reports only when that is done | Verification and the merge | The coordinating side is short of usage for the whole phase |
| **Mixed** | Only the implementer (or another single role) | Orchestration, the review and the merge | The other engine builds well, but the review should stay on the strongest model this side has |

- **Every split has a reviewer, and it is never the implementer.** A round that comes back built but unreviewed is reviewed by the coordinating side; plan for that usage when choosing the split.
- **The brief carries a "How this round runs" section** ([[implementation-brief]]): the reason and the user's agreement, each agent's engine and what it never does, what the sending engine used for this task, the environment, the receiver's Step 0 capability check, what comes back, and a start prompt. A failing probe backs every finding, whichever side reviews.
- **The sender describes itself; the receiver compares.** The brief states what the sending engine actually used and observed for this task, with engine, model and date. It doesn't rely on a skill for the receiving engine, which may not exist and goes stale as engines update. The receiver's first step checks each capability against its own engine and stops before building if something essential is missing.
- **Name the environment.** OS, shell, and the versions of the tools the steps call. Some dependencies are invisible from inside an engine, e.g. a shell whose `PATH` lacks a command a test runs.
- **The two sides never share a file in flight.** Each brief lists the other side's files as off limits.
- **The coordinating Orchestrator still verifies** the report against the commits and re-runs the targeted tests and the probes before merging. Verifying costs far less than reviewing.
- **Files in the repository are the channel** between the two sides when there is no direct one: a brief going out, a report coming back, the user relaying the start prompt and a one-line prompt each way.
- **Ask the user about usage** before starting a round on either side, and get their agreement to each model change.

## Reports are checked against their raw evidence

Delegating work across multiple agents or external tools is only reliable if reports are objectively verifiable:

1. **Every number, measurement, and quote in a report must name the raw file it originates from.** Require this in the brief. If something was not measured, the report must explicitly state "not tested". A probe's report also marks each result CONFIRMED or INFERRED ([[probe-brief]]). Every report names the model each agent ran on.
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

### [0.2.0] - 2026-10-17
#### Changed
- "Handing a phase to a second pipeline" is now "Handing work to another engine". Besides a complete
  second pipeline it allows a mixed split, where the other engine runs only the implementer and the
  coordinating side keeps the orchestration and the review (Shadow Cursor #081 A2a). Every split has a
  reviewer that isn't the implementer.
- The brief for such a round carries the "How this round runs" section of `template/implementation-brief`:
  the sending engine describes what it used, names the environment, and the receiver checks its own
  capabilities before building.
- Reports name the model each agent ran on; probe reports mark results CONFIRMED or INFERRED
  (`template/probe-brief`).

### [0.1.1] - 2026-10-02
#### Added
- Added guidelines for handing a phase to a second pipeline (self-contained orchestrator/implementer/reviewer roles, inter-pipeline IPC via repository files, and probe verification).

### [0.1.0] - 2026-10-02
#### Added
- Initial draft of the phase staffing protocol, distilled from Shadow Cursor #063.
- Three-question staffing decision framework (size, coupling, model) supporting single continued agents, fresh agents, and side-by-side pairings.
- Raw-evidence verification rule for agent and subagent reports.
