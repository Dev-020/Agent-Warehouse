---
id: template/test-plan
version: 0.1.0
status: draft
summary: Copyable project test plan recording suite commands, measured duration, the nine testing-practice decisions, and known backlog exceptions.
applies-to: [codebase, warehouse]
settings: {}
requires: []
replaces: null
---

<!-- Copy into the project root (the protocol's `test_plan_file` setting, default `TESTING.md`) with `warehouse template template/test-plan TESTING.md`. Fill every `[change me]` marker, keep the defaults that fit, and point `AGENTS.md` to this file. Follow [[test-planning]] and [[testing]]. -->

# Test Plan — [change me: Project name]

> **Stage:** [change me: Gate active / Pre-gate (single author, one feature) / No suite yet — state why]
> **Follows:** [[testing]] (`convention/testing`) and [[test-planning]] (`protocol/test-planning`).

## Commands and measured duration

One main suite per independently released component, each with one recorded default command; the time
budget applies per command ([[testing]] §11).

| Run | Command | Sizes included | Measured duration | Date measured |
|---|---|---|---|---|
| **Default run** | `[change me: e.g. <test-runner> --exclude-large]` | Small (plus medium if within budget) | `[change me: e.g. 1m 20s]` | `[change me: YYYY-MM-DD]` |
| **Full run** | `[change me: e.g. <test-runner>]` | All sizes in the main suite | `[change me: e.g. 3m 45s]` | `[change me: YYYY-MM-DD]` |
| **Marked larger sets** | `[change me: e.g. <test-runner> --only-large, or none]` | Large / end-to-end | `[change me: e.g. 8m 10s, or —]` | `[change me: YYYY-MM-DD]` |

## Project testing decisions

### 1. Which tests a change needs
A behaviour change needs a test; a bug fix starts with a failing regression test. `[change me: keep default or state project rule]`

### 2. What runs while working
Targeted tests only (the test files added or touched by the change). `[change me: keep default or state project rule]`

### 3. When the full suite runs, and who runs it
Once before merge, by the implementer. `[change me: e.g. before every release by the maintainer, or once at the end of an implementation by the user]`

### 4. What blocks a merge or release
A full run with no failures that aren't already in the [[backlog]]. `[change me: keep default or state tighter gate]`

### 5. Which sizes run by default
Small, plus medium if they fit the budget. Every non-small test is marked (`[change me: list markers or tags for medium and large tests]`).

### 6. Time budget of the default run
**10 minutes** per command (Bazel's defaults per test target, applied here per test: `60 s` small, `300 s` medium, `900 s` large). Going over budget is recorded in the [[backlog]]. `[change me: keep 10 minutes or set the project's budget; record any over-budget run under Known exceptions]`

### 7. Flaky-test procedure
Quarantine with a [[backlog]] entry naming the test and its failure mode ([[testing]] §8). Never merge on failures that aren't in the backlog; retries may confirm flakiness but are never the fix. `[change me: keep default or add quarantine marker name]`

### 8. How agent-written tests are reviewed
The reviewer checks assertions, mocks, skips and order dependence (running new tests alone and with their file). `[change me: keep default or add project checks]`

### 9. What the project's agent instructions repeat (rule f)
`AGENTS.md` points to this file and repeats [[testing]] §10 (a)–(e):
- (a) a test asserts something; a test that only prints is a probe;
- (b) no new mock without a stated reason (in a code comment or the report);
- (c) file I/O only in temp dirs, seeds fixed, no real clock;
- (d) an assertion is never weakened, skipped or deleted without saying so in the report;
- (e) probes live outside the suite unless promoted on purpose.

`[change me: name the instruction file(s) that link here, e.g. AGENTS.md]`

## Known exceptions

Every exception to [[testing]] or to the budgets above is tracked in the [[backlog]]:

| Exception / failing or slow test | Rule or budget | Backlog ID | Added |
|---|---|---|---|
| `[change me: None, or describe the gap]` | `[change me: e.g. §2 budget / §3 order dependence]` | `[change me: e.g. #102]` | `[change me: YYYY-MM-DD]` |

## Changelog

### [Unreleased]
#### Added
- First draft.
