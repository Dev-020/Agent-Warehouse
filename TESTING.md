<!-- from warehouse template template/test-plan v0.1.0 -->

# Test Plan — AI Agent Warehouse

> **Stage:** Gate active (more than one author: agents work from briefs)
> **Follows:** [[testing]] (`convention/testing`) and [[test-planning]] (`protocol/test-planning`).

## Commands and measured duration

One main suite per independently released component, each with one recorded default command; the time
budget applies per command ([[testing]] §11).

| Run | Command | Sizes included | Measured duration | Date measured |
|---|---|---|---|---|
| **`_tools`** | `python -m pytest _tools/tests -q` | Medium (all medium, unmarked) | `[Orchestrator: measured after review]` | `[Orchestrator: measured after review]` |
| **`backlog-cli`** | `python -m pytest tools/backlog-cli/tests -q` | Small and medium | `[Orchestrator: measured after review]` | `[Orchestrator: measured after review]` |

## Project testing decisions

### 1. Which tests a change needs
A behaviour change needs a test; a bug fix starts with a failing regression test.

### 2. What runs while working
Targeted tests only (the test files added or touched by the change).

### 3. When the full suite runs, and who runs it
`_tools`: by the implementer once before a `_tools` change is merged, and by the Orchestrator to confirm. `backlog-cli`: by the implementer once before a change is merged, by the Orchestrator to confirm, and `warehouse release` runs it before tagging.

### 4. What blocks a merge or release
A full run with no failures that aren't already in the [[backlog]].

### 5. Which sizes run by default
Small and medium. `backlog-cli` marks `medium`; pure unit tests are un-marked and run with `-m "not medium"`. `_tools` tests are all medium and unmarked (a known exception).

### 6. Time budget of the default run
**10 minutes** per command (default). Bazel's defaults per test target, applied here per test: `60 s` small, `300 s` medium, `900 s` large. Going over budget is recorded in the [[backlog]].

### 7. Flaky-test procedure
Quarantine with a [[backlog]] entry naming the test and its failure mode ([[testing]] §8). Never merge on failures that aren't in the backlog; retries may confirm flakiness but are never the fix.

### 8. How agent-written tests are reviewed
The reviewer checks assertions, mocks, skips and order dependence (running new tests alone and with their file).

### 9. What the project's agent instructions repeat (rule f)
`AGENTS.md` points to this file and repeats [[testing]] §10 (a)–(e):
- (a) a test asserts something; a test that only prints is a probe;
- (b) no new mock without a stated reason (in a code comment or the report);
- (c) file I/O only in temp dirs, seeds fixed, no real clock;
- (d) an assertion is never weakened, skipped or deleted without saying so in the report;
- (e) probes live outside the suite unless promoted on purpose.

`AGENTS.md` links here.

## Known exceptions

Every exception to [[testing]] or to the budgets above is tracked in the [[backlog]]:

| Exception / failing or slow test | Rule or budget | Backlog ID | Added |
|---|---|---|---|
| `_tools` tests are unmarked (all medium) | §5 sizes | None (known exception) | 2026-11-08 |
