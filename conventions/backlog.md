---
id: convention/backlog
version: 0.1.0
status: draft
summary: Standardized project backlog format with structured tasks, acceptance criteria, and lifecycle sections.
applies-to: [vault, codebase]
settings:
  backlog_file:
    description: "Path to the project backlog file"
    default: "BACKLOG.md"
requires: []
replaces: null
---

# Backlog Convention

A unified project backlog specification for tracking tasks, bugs, technical debt, and architectural
improvements across repositories.

This convention reconciles project tracking practices across repositories, adopting structured
task entries, evidence-based acceptance criteria, and append-only completion records as recommended
in [[backlog-comparison]].

The backlog for a project is maintained in `{{backlog_file}}` (configured by the `backlog_file` setting).

---

## 1. Backlog File Layout

The project backlog consists of four primary lifecycle sections:

```markdown
# Project Backlog

## 📋 In Progress
<!-- Currently active tasks under implementation -->

## 📌 Backlog (Open Tasks)
<!-- Open, unclaimed tasks prioritized for upcoming work -->

## ✅ Completed
<!-- Finished tasks, appended chronologically to the bottom -->

## 🧊 Icebox (Not Doing / Rejected)
<!-- Deliberately rejected, cancelled, or superseded items with reasons -->
```

An optional **Findings Register** section may be appended at the end of the file to track non-task
system observations (security debt, untested behavior, accepted gaps).

---

## 2. Task Item Specification

Each task entry follows a standardized format with stable identifiers, explicit priority, and
structured sub-sections:

```markdown
### [ID] Short descriptive title
- **Status**: `Open` | **Priority**: `P1` | **Labels**: `Core`, `Bug`
- **Created**: 2026-09-15

#### Why
Description of the problem, background context, or user need.

#### Wanted
The target state, architecture, or capability to implement.

#### Acceptance Criteria
- [ ] #1 First verifiable criterion.
- [ ] #2 Second verifiable criterion.

#### Notes
- (Optional, append-only) Invariants, discoveries, or amendments during implementation.

#### Outcome
- (Filled on completion) Summary of implementation, test results, and resolved date.
```

### 2.1. Stable Identifiers
- Format: `[#NNN]` (e.g. `[#042]`) for sequential numbering, or `[PREFIX-N]` (e.g. `[INF-15]`) for
  category-prefixed projects.
- Identifiers are immutable and never reused, even if a task is abandoned or rejected.

### 2.2. Priority Levels
Projects standardize on three clear priority tiers:

| Priority | Level | Definition |
|---|---|---|
| `P1` | High | Blocking, critical bug, core architectural path, or security defect. |
| `P2` | Medium | Standard feature, enhancement, or scheduled milestone goal. |
| `P3` | Low | Minor polish, non-blocking technical debt, or optional optimization. |

*(Note: `P0` is deprecated in favor of `P1` because critical blockers and high-priority tasks
rarely differ in agent dispatch practice.)*

### 2.3. Evidence-Based Acceptance Criteria
- Acceptance criteria must be numbered checklist items (`- [ ] #1 ...`, `- [ ] #2 ...`).
- **Objective evidence rule:** An acceptance checkbox is marked `[x]` ONLY when substantiated by
  objective verification evidence (passing automated test commands, explicit execution outputs, or
  verified manual runs).
- **Never mark criteria complete** based solely on code presence, grep matching, or implementation
  intent.

---

## 3. Task Lifecycle Rules

### 3.1. Creating a Task
- Add new tasks to `## 📌 Backlog (Open Tasks)` under the appropriate priority.
- Allocate the next sequential ID by checking existing IDs across all sections.

### 3.2. Claiming Work
- Move the task item from `## 📌 Backlog (Open Tasks)` into `## 📋 In Progress`.
- Update metadata: `- **Status**: `In Progress``.
- Optionally add a `#### Plan` sub-section outlining intended execution steps before touching code.

### 3.3. Completing a Task
- Verify every acceptance criterion against objective evidence.
- Add resolved date: `- **Resolved**: YYYY-MM-DD` and update status: `- **Status**: `Closed``.
- Complete the `#### Outcome` section summarizing changes and test results.
- **Append-only rule:** Move the entire task entry to the **bottom** of `## ✅ Completed`.
  Never insert finished items at the top of the completed section; bottom placement preserves
  chronological progression and avoids merge conflicts when git branches merge.
- **Never delete completed items.** They serve as permanent audit history.

### 3.4. Rejecting or Cancelling a Task
- If an item is determined to be unnecessary, superseded, or rejected during review:
  - Update status: `- **Status**: `Rejected`` or `- **Status**: `Cancelled``.
  - Add an explanation under `#### Outcome` (or `#### Why`) documenting why the approach was declined.
  - Move the item to the **bottom** of `## 🧊 Icebox (Not Doing / Rejected)`.
- Never delete rejected items. Retaining them in the Icebox prevents future agents and contributors
  from repeatedly re-proposing previously rejected designs.

---

## 4. Findings Register (Optional)

For projects managing operational infrastructure, ongoing observation, or architectural debt,
an appendix register may be added below the Icebox:

1. **Security Debt:** Known security boundaries, pending credential rotations, or permission gaps.
2. **Untested Behaviour:** Functionality deployed without complete automated coverage.
3. **Known Gaps Accepted Deliberately:** Tradeoffs accepted for simplicity or latency.
4. **Watch List:** Latent risks or external dependencies monitored for performance or degradation.

---

## Changelog

### [Unreleased]

#### Added
- Initial draft of the standardized backlog convention.
