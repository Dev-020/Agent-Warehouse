---
id: protocol/audit-lens-health
version: 0.1.0
status: draft
summary: Audit lens for the current state of a codebase — whether it builds, its tests pass and its linter is clean, its test coverage, and how complex and how large its units are; with the areas that are unhealthy.
applies-to: [codebase]
settings: {}
requires: [protocol/codebase-audit@0.1]
replaces: null
---

# Health Lens

A lens for [[codebase-audit]] (`protocol/codebase-audit`). It reads the audit's core and writes
`lens-health.md` in the record, following [[audit-record]] §5 and the lens contract (§6).

## 1. Purpose

**The question it answers:** is the codebase in working order today, and which parts of it are hard
to maintain?

It checks the basics (build, tests, linter, coverage) and measures the maintainability properties of
the SIG maintainability model that can be counted per unit: volume, complexity and unit size,
judged by ISO/IEC 25010 maintainability. It is a snapshot. Where the costs are, and where to pay
first, is the debt lens's question.

What it leaves to other lenses, so nothing is measured twice:

| Property | Measured by | This lens |
|---|---|---|
| Duplication | duplication lens | cites its system total when that lens ran |
| Coupling, central units | structure lens | cites them when that lens ran |
| Change frequency, hotspots | debt lens | not used |

## 2. What it needs from the core

| Need | Value |
|---|---|
| Depth | `file`. Complexity and size are measured per function or method by the tool, then reported against the core's file units, with the function named in the evidence. |
| Relations | none |
| History | not needed |

The lens file records `needs: { depth: file, history: false }`.

**Running the build and the tests runs the project's code.** Do it only with the initiator's agreement,
recorded in the header's scope. Without it, take the status from the latest CI run for the audited
commit and set `source: ci`. If there is none, set `result: not-run` and list it under Gaps.

## 3. Criteria

Defaults. The project may change the numbers; the lens file records the values used.

| Id | Source | Rule | When |
|---|---|---|---|
| H1 | ISO/IEC 25010 (functional suitability) | The documented build succeeds from a clean checkout of the audited commit | Always |
| H2 | ISO/IEC 25010 maintainability: testability | Every test passes. Skipped and expected-to-fail tests are listed with their reason | When the project has tests |
| H3 | The project's linter configuration | The linter reports no errors | When a linter is configured |
| H4 | The project's coverage target | Line coverage meets the project's target | Only when the project sets a target; otherwise coverage is reported, not judged |
| H5 | SIG maintainability model (Heitlager, Kuipers, Visser 2007) | No unit at very high complexity risk (cyclomatic complexity over 50), and the system's complexity rating is at least `o` | Always |
| H6 | SIG guideline of 15 lines per unit (Visser, *Building Maintainable Software*, 2016); band edges are this lens's defaults | No unit over the very-high size band (over 60 lines) | Always |

**Complexity bands** (cyclomatic complexity per function, SIG 2007): 1–10 low, 11–20 moderate, 21–50
high, over 50 very high. **Complexity rating:** the share of code lines in moderate, high and
very-high units, at most:

| Rating | Moderate | High | Very high |
|---|---|---|---|
| `++` | 25% | 0% | 0% |
| `+` | 30% | 5% | 0% |
| `o` | 40% | 10% | 0% |
| `-` | 50% | 15% | 5% |
| `--` | more | more | more |

**Size bands** (code lines per function): up to 15 low, 16–30 moderate, 31–60 high, over 60 very high.
Sizes are reported as a profile; they get no rating, since SIG's published size ratings aren't
available to check.

## 4. The steps

1. **Check the needs** (§2). Agree with the initiator whether the build and tests may run.
2. **Set the criteria** (§3). Read the project's build, test, lint and coverage commands from its docs
   and CI. A project's own thresholds replace the defaults; quote their source.
3. **Build** (H1). Run the documented build in the audit's worktree, or read the CI result. Record the
   command, the result and where the log is.
4. **Tests** (H2). Run the suite, or read the CI result. Record passed, failed and skipped counts, and
   each skip's reason as the code gives it. A failing test is not fixed during the audit; it is a
   finding.
5. **Linter** (H3) and **coverage** (H4), if the project has them. Use the project's configuration
   unchanged.
6. **Volume.** Count code lines (non-blank, non-comment) in scope, per subsystem and in total.
7. **Complexity and size** (H5, H6). Run a metrics tool for the languages (for example `radon` or
   `lizard`) over production code. Tests and generated code are left out.
   - For the system and each subsystem: the share of code lines in each band, and the complexity
     rating.
   - List the worst functions: every one in the very-high band, and the top 10 by complexity and by
     size, against their file unit.
8. **Unhealthy areas.** Name the subsystems and modules that carry most of the findings, or have a
   `-` or `--` rating, with the findings that put them there.
9. **Measures.** Add every tool and command (build, test runner, linter, coverage, metrics) to the
   record's `measures` with `used-by: [protocol/audit-lens-health]`.
10. **Findings.**
    - A failed build breaks H1: `Critical`, `blocks: true`.
    - Each failing test breaks H2 (`Major`); group tests that fail for one cause.
    - Linter errors break H3 (`Minor`): one finding per rule, not per line.
    - Coverage under the target breaks H4 (`Minor`).
    - A system or subsystem rated `-` or `--` breaks H5 (`Major`). Each file holding very-high
      complexity or very-high size functions breaks H5 or H6 (`Minor`): one finding per file, naming
      the functions.
    - Label each through [[issue-triage]]. These are starting points; adjust for the project.
11. **Gaps.** In the [[audit-record]] §4.5 format: steps not run, languages the metrics tool doesn't
    support, tests that need services not available.

## 5. Results format

```yaml
status:
  build:    { result: pass | fail | not-run, source: local | ci, command: "<cmd>", evidence: "<log path or CI run>" }
  tests:    { result: pass | fail | not-run, source: local | ci, command: "<cmd>", passed: <n>, failed: <n>, skipped: <n>, evidence: "<log>" }
  lint:     { result: pass | fail | not-run, command: "<cmd>", errors: <n>, warnings: <n>, evidence: "<log>" }   # null if no linter
  coverage: { line: <percent>, branch: <percent or null>, target: <percent or null>, command: "<cmd>", evidence: "<report>" }   # null if not measured

skipped-tests:
  - { test: "<test id>", reason: "<as given in the code>", evidence: "<path:line>" }

thresholds:
  complexity: [10, 20, 50]        # upper edges of low, moderate, high
  size: [15, 30, 60]

volume:
  - { unit: <core unit id>, lines: <n> }

profiles:                         # percent of code lines per band
  - { unit: <core unit id>, metric: complexity, low: <n>, moderate: <n>, high: <n>, very-high: <n>, rating: "++" | "+" | "o" | "-" | "--" }
  - { unit: <core unit id>, metric: size, low: <n>, moderate: <n>, high: <n>, very-high: <n> }

worst:
  - { unit: <core file unit id>, function: "<name>", metric: complexity | size, value: <n>, at: "<path:line>" }

cited:                            # from other lenses in the same audit, or null
  duplication: { percent: <n.n>, rating: "<rating>", from: "lens-duplication.md" }

unhealthy:
  - { unit: <core unit id>, findings: [F<n>, ...] }
```

## 6. Example

For the `notes-cli` record in [[audit-record]] §8, with the build and tests run locally (agreed in the
header's scope).

````markdown
---
type: audit-lens
audit-id: 2026-11-12-a1b2c3d
lens: protocol/audit-lens-health
lens-version: 0.1.0
needs: { depth: file, history: false }
---

## Criteria
```yaml
criteria:
  - { id: H1, source: "ISO/IEC 25010 functional suitability", rule: "The documented build succeeds" }
  - { id: H2, source: "ISO/IEC 25010 testability", rule: "Every test passes" }
  - { id: H3, source: "pyproject.toml [tool.ruff]", rule: "ruff reports no errors" }
  - { id: H5, source: "SIG maintainability model (2007)", rule: "No function over complexity 50; rating at least o" }
  - { id: H6, source: "SIG 15-line guideline; lens bands", rule: "No function over 60 lines" }
```

## Results
```yaml
status:
  build: { result: pass, source: local, command: "pip install -e .", evidence: "audit log, step 3" }
  tests: { result: fail, source: local, command: "pytest -q", passed: 41, failed: 1, skipped: 1, evidence: "audit log, step 4" }
  lint:  { result: pass, command: "ruff check src", errors: 0, warnings: 3, evidence: "audit log, step 5" }
  coverage: null
skipped-tests:
  - { test: "tests/test_db.py::test_wal_mode", reason: "needs SQLite 3.45", evidence: "tests/test_db.py:88" }
thresholds: { complexity: [10, 20, 50], size: [15, 30, 60] }
volume:
  - { unit: notes-cli, lines: 1840 }
profiles:
  - { unit: notes-cli, metric: complexity, low: 78, moderate: 14, high: 8, very-high: 0, rating: "o" }
  - { unit: notes-cli, metric: size, low: 52, moderate: 25, high: 15, very-high: 8 }
worst:
  - { unit: src/notes/storage/db.py, function: "NoteStore.migrate", metric: size, value: 94, at: "src/notes/storage/db.py:120" }
  - { unit: src/notes/storage/db.py, function: "NoteStore.migrate", metric: complexity, value: 18, at: "src/notes/storage/db.py:120" }
cited:
  duplication: { percent: 3.5, rating: "+", from: "lens-duplication.md" }
unhealthy:
  - { unit: storage, findings: [F1, F2] }
```

## Findings
```yaml
findings:
  - { id: F1, units: [tests/test_db.py], criterion: H2, what: "test_search_unicode fails: search lowercases with str.lower, not casefold", evidence: "tests/test_db.py:61", confidence: CONFIRMED, severity: Major, likelihood: Occasional, blocks: false, backlog: WH-34 }
  - { id: F2, units: [src/notes/storage/db.py], criterion: H6, what: "NoteStore.migrate is 94 lines", evidence: "src/notes/storage/db.py:120-213", confidence: CONFIRMED, severity: Minor, likelihood: Rare, blocks: false, backlog: WH-35 }
```

## Gaps
```yaml
gaps:
  - { id: G1, area: "coverage", reason: "No coverage tool configured", impact: "H4 not judged" }
```
````

## 7. Done when

- [ ] Running the build and tests was agreed with the initiator, or their status comes from CI, or
  they are `not-run` with a gap.
- [ ] Every status entry names its command and evidence, and every tool is in the record's `measures`.
- [ ] `thresholds` gives the bands used, and profiles follow them.
- [ ] Every `worst` entry points at a core file unit, with the function and its line.
- [ ] Duplication and coupling are cited from their lenses, not measured here.
- [ ] Every finding cites a criterion and has triage labels and a backlog id, or a reason it has none.

## Changelog

### [Unreleased]

### [0.1.0] - 2026-11-13
#### Added
- First draft.
