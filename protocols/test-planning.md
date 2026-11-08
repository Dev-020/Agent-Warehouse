---
id: protocol/test-planning
version: 0.1.0
status: draft
summary: How a project decides and records its own testing practice, and how its agents follow it.
applies-to: [codebase, warehouse]
settings:
  test_plan_file:
    description: "Where the project's filled-in test plan lives"
    default: "TESTING.md"
requires: [convention/testing@0.1, template/test-plan@0.1]
replaces: null
---

# Test Planning Protocol

How a project decides and records its own testing practice in {{test_plan_file}}, and how humans and AI
agents follow it. Generic rules for what makes a good test and a healthy suite live in [[testing]];
the copyable record form lives in [[test-plan]].

## 1. When this applies, and the three moments

Every project with code has a test plan in {{test_plan_file}} from day one; a project with no suite yet
says so and why. A project's suite matures through three moments:

1. **Structure from the first test:** the first test goes where the suite will live and runs with the
   suite's one command. There is never a loose "pile of tests" stage.
2. **Gate:** the suite blocks merges ("no failures that aren't in the backlog") once someone other than
   the original author changes the code (another person, or an agent working from a brief), or once the
   project has more than one feature.
3. **Requirement:** after the gate point, every behaviour change needs a test and every bug fix starts
   with a failing regression test.

## 2. The decisions a project records

Each project records these nine decisions in {{test_plan_file}}, starting from the defaults below:

| Decision | Default |
|---|---|
| Which tests a change needs | A behaviour change needs a test; a bug fix starts with a failing regression test |
| What runs while working | Targeted tests only |
| When the full suite runs, and who runs it | Once before merge, by the implementer |
| What blocks a merge or release | A full run with no failures that aren't already in the backlog |
| Which sizes run by default | Small, plus medium if they fit the budget |
| Time budget of the default run | **10 minutes** |
| Flaky-test procedure | Quarantine with a backlog entry ([[testing]] §8) |
| How agent-written tests are reviewed | The reviewer checks assertions, mocks, skips and order dependence |
| What the project's agent instructions repeat (rule f) | A pointer to the test plan, plus convention §10 (a)–(e) |

### Worked examples

- **The warehouse:** implementers run targeted tests while working; the full suite for a tool or the
  warehouse CLI runs before every release (`warehouse release` runs the tool's suite before tagging),
  within the 10-minute default budget.
- **Shadow Cursor:** implementers run only targeted test files while working and never run the full
  suite; the user runs the full suite once at the end of an implementation before merge, and any
  pre-existing failure or over-budget suite duration is tracked by ID in the [[backlog]].

## 3. Adopting it in a project

1. Pull `convention/testing`, `protocol/test-planning` and `template/test-plan`.
2. Copy the template into {{test_plan_file}} with:
   ```bash
   warehouse template template/test-plan {{test_plan_file}}
   ```
   Fill in the suite commands, the measured duration and date, and any decision in §2 that differs from
   the default.
3. Add one line to `AGENTS.md` (and any paired agent instruction file) pointing to `{{test_plan_file}}`
   and repeating [[testing]] §10 rules (a)–(e).
4. If the current suite breaks a rule in [[testing]] (for example, it exceeds the time budget or
   cannot pass in one run), open a [[backlog]] entry for each gap and list the backlog ID in
   {{test_plan_file}}; never hide a broken rule by weakening the plan.

## 4. What a brief states about tests

When a task or phase is handed to an implementer with [[implementation-brief]], the brief states:
- the **targeted test files** to run while working;
- **whether the implementer may run the full suite**, and in which step;
- the **time budget** for the new tests and the default run;
- **which rules of [[testing]]** the step must follow (such as using fakes over real I/O, temp dirs,
  and no sleeps).

## 5. Keeping the plan current

- Update {{test_plan_file}} whenever the suite's commands, size markers, time budget or merge/release
  gates change.
- Review {{test_plan_file}} and record a [[backlog]] entry whenever a measured run goes over the
  recorded time budget.

## 6. Choices a project may change

A project may change any decision in §2's table in {{test_plan_file}} to fit its architecture, runtime
or workflow.

A project may **not** drop the rules in [[testing]] for hermetic, order-independent tests (§3) or
flaky-test handling (§8: quarantine only with a backlog entry, and never merge on failures that aren't
in the backlog).

## Changelog

### [Unreleased]
#### Added
- First draft.
