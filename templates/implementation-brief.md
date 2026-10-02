---
id: template/implementation-brief
version: 0.1.0
status: draft
summary: Copyable brief for one phase of a phased implementation — rules, staffing row, settled Orchestrator decisions, interfaces, checkpoint steps, tests and the report format.
applies-to: [codebase]
settings: {}
requires: []
replaces: null
---

<!-- Used by [[phased-implementation]] (Stage 2, step 2) and [[phase-staffing]]. Copy it, fill every [bracketed] placeholder, delete this comment. -->

# Task Handoff — [Item ID] [Phase]: [Phase title]

> **From:** Orchestrator | **To:** [one model implementer subagent per step / one continued model implementer across steps] | **Written:** [YYYY-MM-DD]
> **Plan:** [path to the plan] (approved): [§ that specifies this phase] is the spec; [§ with the rules or invariants] are the rules; [§ with the tests] lists the tests that must exist.
> **Branch / worktree:** `[branch]` at `[worktree path]`, from `[integration branch]` ([what is already merged]; suite [N passed, M skipped]).
> **Read first:** this brief; [plan sections]; the previous hand-over [path to the last session log] ("What [previous phase] delivered" is the interface you build on); then the code you touch.

## How this phase is staffed
<!-- Per [[phase-staffing]] -->

| Phase | Size (new code; build time) | Needs | Can be built beside | Implementer |
|---|---|---|---|---|
| [Phase] | [lines of code; hours] | [dependencies / nothing] | [sibling phase / nothing] | [one continued mid-tier / fresh strongest / etc.] |

- **Coupling & Shape:** [Tight: one continued implementer / Loose: separate / Large: fresh per step].
- **Model:** [Model chosen and why].
- **Side-by-side rules (if applicable):** [Files off limits: list other phase's files].

## What [Phase] is

[Two or three short paragraphs: what this phase adds, what it deliberately doesn't do, and who calls it. State the invariants a reader must not break, for example "every status change goes through X".]

[What this phase must never do, as a short list, taken from the plan's failure indicators.]

## Rules (all steps)

- **Testing:** while working, run ONLY targeted tests (the files you add or change, with `-k` where it helps). Run `[full test command]` **once**, at the very end of **step [last step] only**. Earlier steps end with their targeted files green.
- **Speed:** [what to test with fakes and what with real dependencies]. Target: this phase's new tests add **under [N] s** to the suite.
- One commit per step. [Commit convention], ending `[attribution line]`.
- Only this phase's worktree. Never the primary tree or the coordinator's files ([list the tracking files]). [Anything else off limits: live services, the running app.]
- [Dependency and import constraints.]
- [Behaviour that must stay exactly as it is, and whose tests must stay green unchanged.]
- Keep coverage. List every assertion removed or weakened, and why. **Stop and report instead of guessing** if the plan and the code disagree.
- **Evidence rule:** Every number, measurement, and quote in your report must name the raw file it comes from (per [[phase-staffing]]).

## Orchestrator decisions for [Phase] (settled; don't reopen)

[Every choice the plan leaves open for this phase, made now. One numbered item each: the decision in bold, then the detail an implementer needs, then a line of why. Include the edge cases you already know about. Earlier phases' decisions that still hold can be referenced rather than repeated.]

1. **[Decision.]** [Detail.] [Why.]
2. **[Decision.]** [Detail.] [Why.]

## The interfaces [Phase] builds on

[The functions, types and shapes the implementers call or must produce, with signatures. Code blocks where exact shapes matter.]

## Steps

### Step [S1] — [title]
- [What to build.]
- Tests: [new test file], plus [changed files]. Targeted runs only.

### Step [S2] — [title]
- [What to build.]
- Tests: [...]

### Step [S3] — [title]
- [What to build, including the integration tests against real dependencies.]
- Then `[full test command]` **once** for the whole suite. If it fails, fix and run it once more; report both results.

## Report (each step)
Commit hash; files changed; tests added and their targeted results ([last step]: the full-suite line); anything in this brief you couldn't do as written, and why; assertions removed or weakened; raw-file citations for any measured metrics; open questions for the next step.

## Out of scope (later phases)
- [Item] ([phase that owns it]).

## Changelog

### [Unreleased]

### [0.1.0] - 2026-10-02
#### Added
- Initial template, generalised from Shadow Cursor #038 briefs and refined with #063 phase staffing.
