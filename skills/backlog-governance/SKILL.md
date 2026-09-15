---
id: skill/backlog-governance
version: 0.1.0
status: draft
summary: Agent skill to inspect, prioritize, claim, and maintain project backlogs.
applies-to: [vault, codebase]
settings:
  backlog_file:
    description: "Path to the project backlog file"
    default: "BACKLOG.md"
requires: [tool/backlog-cli@0.1]
replaces: null
---

# Backlog Governance Skill

Operational procedures for maintaining, prioritizing, claiming, and auditing project backlogs across
codebases and knowledge vaults according to [[backlog]] and [[worktree-claims]].

The primary task backlog for the project is maintained in `{{backlog_file}}`.

---

## 1. Backlog Topology & Lifecycle Sections

Every project backlog must maintain four primary lifecycle sections:

```markdown
# Project Backlog

## 📋 In Progress
<!-- Currently active tasks under implementation in worktrees -->

## 📌 Backlog (Open Tasks)
<!-- Open, unclaimed tasks prioritized for upcoming work -->

## ✅ Completed
<!-- Finished tasks, appended chronologically to the bottom -->

## 🧊 Icebox (Not Doing / Rejected)
<!-- Deliberately rejected, cancelled, or superseded items with reasons -->
```

An optional **Findings Register** (tracking security debt, untested behavior, and known gaps) may follow
the Icebox.

---

## 2. Standardized Task Item Structure

Every task entry follows this specification:

```markdown
### [ID] Descriptive task title
- **Status**: `Open` | **Priority**: `P1` | **Labels**: `Core`, `Bug`
- **Created**: YYYY-MM-DD

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
- Format: `[#NNN]` (e.g. `[#042]`) for sequential numbering, or `[PREFIX-N]` (e.g. `[INF-15]`) for category-prefixed projects.
- Identifiers are immutable and never reused, even if a task is abandoned or rejected.

### 2.2. Priority Tiers

| Priority | Definition | Examples |
|---|---|---|
| `P1` | High / Blocking | System crashes, regressions, core architectural path, security defect. |
| `P2` | Medium / Standard | Standard feature, scheduled milestone goal, operational capability. |
| `P3` | Low / Polish | Non-blocking refactor, minor cleanup, optional optimization. |

*(Note: Legacy `P0` is deprecated in favor of `P1`; critical blockers and high-priority tasks share the same dispatch urgency).*

---

## 3. Evidence-Based Acceptance Criteria Rule

> [!IMPORTANT] Objective Verification Requirement
> Acceptance checkboxes (`- [ ] #N`) are marked complete (`- [x] #N`) **ONLY** when substantiated by
> objective verification evidence:
> - Passing automated test command outputs.
> - Direct terminal execution results.
> - Verified manual reproduction logs.
>
> **Never mark criteria complete** based on code inspection, grep matches, or implementation intent.

---

## 4. Lifecycle Procedures via `tool/backlog-cli`

All lifecycle modifications should be driven via [[tool/backlog-cli]] to preserve multi-agent concurrency:

### 4.1. Creating a Task
1. Inspect `{{backlog_file}}` and run `python tools/backlog-cli/task.py status` to check active work.
2. Add the item using the CLI:
   ```bash
   python tools/backlog-cli/task.py open "Title" --prefix INF --priority P1
   ```
   This automatically allocates the next sequential ID across master and all active claim branches.

### 4.2. Claiming Work
1. Claim the task:
   ```bash
   python tools/backlog-cli/task.py claim <ID>
   ```
2. The tool creates branch `claim/<ID>`, provisions an isolated git worktree, and marks the task `In Progress`.
3. **Always switch to the printed worktree path** before editing any files or running builds.

### 4.3. Completing Work
1. Verify all acceptance criteria against objective test runs.
2. Commit all changes inside the worktree.
3. Close the task from the primary project directory:
   ```bash
   python tools/backlog-cli/task.py close <ID> --outcome "One-line past tense summary of verified changes"
   ```
4. **Append-only rule:** The CLI moves the task to the **bottom** of `## ✅ Completed` with resolved date
   and outcome, merges `--no-ff` under `merge.lock`, and removes the worktree.

### 4.4. Cancelling or Rejecting Work (Icebox)
If an item is determined to be unnecessary, superseded, or rejected:
1. Update status to `- **Status**: `Rejected`` or `- **Status**: `Cancelled``.
2. Document the rejection rationale under `#### Outcome` or `#### Why`.
3. Move the entry to the **bottom** of `## 🧊 Icebox (Not Doing / Rejected)`.
4. **Never delete rejected items.** Retaining them in the Icebox prevents future agents and contributors
   from repeatedly proposing previously declined solutions.
