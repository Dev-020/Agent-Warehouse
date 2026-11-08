---
id: template/implementation-brief
version: 0.2.0
status: draft
summary: Copyable brief for one phase of a phased implementation — rules, staffing row, settled Orchestrator decisions, interfaces, checkpoint steps, tests and the report format, plus an optional section for work another engine does.
applies-to: [codebase]
settings: {}
requires: []
replaces: null
---

<!-- Used by [[phased-implementation]] (Stage 2, step 2) and [[phase-staffing]]. Save it as `BRIEF_<id>_<phase>.md`, fill every [bracketed] placeholder, delete these comments. A brief is a task given to an agent; a hand-over is state passed between sessions (the session log and the active context). Keep "How this round runs" only when another engine does part of the phase; otherwise delete it. -->

# Brief — [Item ID] [Phase]: [Phase title]

> **From:** the Orchestrator ([engine], [model]) | **To:** [one model implementer subagent per step / one continued model implementer across steps] | **Written:** [YYYY-MM-DD]
> **Plan:** [path to the plan] (approved): [§ that specifies this phase] is the spec; [§ with the rules or invariants] are the rules; [§ with the tests] lists the tests that must exist.
> **Branch / worktree:** `[branch]` at `[worktree path]`, from `[integration branch]` ([what is already merged]; suite [N passed, M skipped]).
> **Read first:** this brief; [plan sections]; the previous hand-over [path to the last session log] ("What [previous phase] delivered" is the interface you build on); then the code you touch.

## How this round runs (only when another engine does part of the phase)
<!-- Per [[phase-staffing]], "Handing work to another engine". Name engines only in the filled copy, never in this template. If this brief was already handed out before the split was chosen, put this section in its own file, `BRIEF_<id>_<phase>_<engine>.md`, and point it at this brief as the spec. -->

**Why another engine:** [the reason, e.g. this side's usage limit, or the user's choice for this phase]. The user agreed on [YYYY-MM-DD], including the model change.

| Agent | Engine (side) | Does | Never does |
|---|---|---|---|
| Orchestrator | [engine] | [checks each stop against the commits and the raw test output; starts the reviewer; triages; merges] | Writes product code |
| Implementer | [engine, model] | The steps below, one commit per step, targeted tests, a report at each stop | Runs the full suite before step [last step]; reviews its own work; edits tracking files; merges |
| Reviewer | [engine, model: the strongest available] | Reviews the phase's commits against this brief, one failing probe per finding | Edits the code |
| [Second orchestrator, if the other side runs a complete pipeline] | [engine] | [gives the implementer one step at a time, checks each commit, starts its own reviewer] | Writes product code |

- **The channel:** [there is no direct channel between the sides. Files in the repository carry the work: this brief going out, the report coming back at `[report path]`. The user relays the start prompt below and a one-line prompt each way.]
- **Stops:** [after which steps the other side stops and reports, and what it waits for before going on].

### What the sending engine used for this task
[engine] ([model]) on [YYYY-MM-DD], when it prepared this work. Only what this work needs, as it was actually done:

| Capability | How it was done |
|---|---|
| Read files | [tool, path style] |
| Write and edit files | [tools; encoding and line endings] |
| Run commands | [shell, path style] |
| Run tests | `[targeted test command]` |
| Use git | [how; whether commits run the repository's hooks] |
| [Other, e.g. images, screenshots, network] | [what was used and what it returned] |

**Environment:** [OS]; [shell]; [interpreter, test runner and CLI versions the steps call]; [repository quirks, e.g. a git folder outside the tree, a commit-message hook].

### Step 0 for the receiver: capability check
Before writing any code, check each row above against your own engine and report one of **same**, **different (and how)** or **missing** for each. Also run these from the worktree and report their output verbatim:

```
[git -C <worktree> status --short --branch]
[interpreter --version]
[test runner --version]
```

If [something essential, e.g. writing files in the worktree, running the interpreter, running git] is missing, **stop and report** instead of building.

### Where this round differs from the rest of this brief
- [Who does the checkpoint after each step, and who checks it again afterwards.]
- Commits end with a `Co-Authored-By:` line naming the model that actually wrote them.
- [Anything the other side must not run: e.g. the project's own CLIs, the live app, the network.]

### What comes back, and how it is checked
Each report (through the user, at `[report path]`) carries: the capability check (first report only); the items in "Report" below; the reviewer's findings with each probe's result before and after the fix, verbatim, if the other side reviews; and **the model each agent ran on**. Every number names the command or file it came from. The Orchestrator then checks the report against the commits and re-runs the targeted tests [and the probes] before building on it.

### Start prompt
The user pastes this into a new [engine] session started in the worktree folder:

```text
You are the [role] for [step or phase] of a phased build. Another engine ([engine]) is the
orchestrator; the user carries your report back to it.

Working folder: [worktree path] (branch [branch]). Work only inside this folder.

Read, in this order:
1. [this brief's path] - the spec, your capability check and your report.
2. [plan sections]
3. [AGENTS.md or the project's instruction file]

Then do Step 0, the capability check; if anything essential is missing, stop and report.
Build [step] only. Run only the targeted tests the brief names. Commit as the brief says.
Stop, and reply with the report in this brief's format.
If the brief, the plan and the code disagree, stop and report instead of guessing.
```

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

- **Testing:** while working, run ONLY targeted tests (the files you add or change, with `-k` where it helps). Full suite: as stated under Tests below. Earlier steps end with their targeted files green.
- **Speed:** [what to test with fakes and what with real dependencies]. Target: this phase's new tests add **under [N] s** to the suite.
- One commit per step. [Commit convention], ending `[attribution line]`.
- Only this phase's worktree. Never the primary tree or the coordinator's files ([list the tracking files]). [Anything else off limits: live services, the running app.]
- [Dependency and import constraints.]
- [Behaviour that must stay exactly as it is, and whose tests must stay green unchanged.]
- Keep coverage. List every assertion removed or weakened, and why. **Stop and report instead of guessing** if the plan and the code disagree.
- **Evidence rule:** Every number, measurement, and quote in your report must name the raw file it comes from (per [[phase-staffing]]).

### Tests
<!-- Per [[testing]] and [[test-planning]]. -->
- **Targeted test files:** `[list the test files to run while working]`.
- **Full suite:** `[whether the implementer runs <full test command> once at the end of step <last step>, or does not run it per the project's test plan]`.
- **Time budget:** `[under [N] s for this phase's new tests; default suite budget [M] min]`.
- **Convention rules ([[testing]]):** `[the rules this step must follow, e.g. fakes vs real dependencies (§6), temp dirs only, fixed seeds, no real clock, no sleeps (§7), and agent-test rules §10 (a)–(e)]`.

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
Commit hash; files changed; tests added and their targeted results ([last step]: the full-suite line); anything in this brief you couldn't do as written, and why; assertions removed or weakened; raw-file citations for any measured metrics; open questions for the next step; the model you ran on.

## Out of scope (later phases)
- [Item] ([phase that owns it]).

## Changelog

### [Unreleased]
#### Added
- A "Tests" subsection under "Rules (all steps)" covering targeted test files, whether the full suite may be run, the time budget, and the [[testing]] rules the step must follow.

### [0.2.0] - 2026-10-17
#### Added
- An optional "How this round runs" section for a phase another engine does part of, complete or mixed:
  the reason and the user's agreement, the agents per side, the channel, what the sending engine used
  for this task (with engine, model and date), an environment line, the receiver's Step 0 capability
  check (same, different or missing), where the round differs, what comes back and how it is checked,
  and a start prompt. Generalised from Shadow Cursor #063 MM5b–MM13 and #081 A2a, and the warehouse's
  WH-1 Phase 1 Antigravity brief.
- The report names the model the implementer ran on.

#### Changed
- The template is a *brief*, not a "Task Handoff": its title is "Brief — …", and it is saved as
  `BRIEF_<id>_<phase>.md`. A *hand-over* is state passed between sessions. Briefs already saved under
  the old name need no change.
- The header names the Orchestrator's engine and model.

### [0.1.0] - 2026-10-02
#### Added
- Initial template, generalised from Shadow Cursor #038 briefs and refined with #063 phase staffing.
