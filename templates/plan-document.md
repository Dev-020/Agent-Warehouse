---
id: template/plan-document
version: 0.1.0
status: draft
summary: Copyable template for technical implementation plans with risk tiers, verification, and recovery.
applies-to: [codebase, vault]
settings: {}
requires: []
replaces: null
---

# [Plan Title] — Implementation Plan

> **Status:** Proposed [YYYY-MM-DD] | **Author:** [Author / Agent] | **Task/Issue:** [[#NNN]]

---

## 1. Goal & Problem Statement

### 1.1. Context and Problem
Explain the current state, limitation, defect, or need. Why is this change necessary? What happens
if we do nothing?

### 1.2. Intended Outcome
Describe the target state after this implementation completes. State explicitly what capabilities,
fixes, or architectural properties are delivered.

---

## 2. User Review Required

> [!important] Critical decisions and breaking changes requiring explicit operator approval
> Summarize architectural tradeoffs, breaking changes, permission shifts, or new external dependencies
> that require user consent before proceeding.

| Area | Decision / Change | Rationale | Impact |
|---|---|---|---|
| [Component / Area] | [Proposed change] | [Why this choice] | [System impact / risk] |

---

## 3. Open Questions

Track unresolved ambiguities, API uncertainties, or environment dependencies:

- **[DECIDE] Question 1:** Description of the decision, options, and recommended default.
- **[DECIDE] Question 2:** Description of the decision, options, and recommended default.

---

## 4. Proposed Changes

Group changes logically by component, subsystem, or layer. Order dependencies first.

### [Component / Subsystem A]

Summary of architectural changes in this component.

#### [NEW] `[path/to/new-file.ext]`
- Purpose: Description of new module or file.
- Key functions / exports:
  - `fn1()`: Description.
  - `fn2()`: Description.

#### [MODIFY] `[path/to/modified-file.ext]`
- Modifications:
  - Description of specific function, schema, or configuration edits.
  - Invariants preserved.

#### [DELETE] `[path/to/deleted-file.ext]`
- Reason for removal and verification that no active dependencies remain.

---

### [Component / Subsystem B]

Summary of changes in this component.

#### [MODIFY] `[path/to/modified-file.ext]`
- Modifications:
  - Description of changes.

---

## 5. Rejected Alternatives & Tradeoffs

Document alternatives considered and the technical rationale for rejecting them:

| Alternative Considered | Why Rejected |
|---|---|
| [Alternative approach 1] | [Technical drawback, performance bottleneck, or security risk] |
| [Alternative approach 2] | [Maintenance overhead, architectural mismatch, or scope creep] |

---

## 6. Verification Plan

Every implementation plan must specify how correctness will be validated before completion.

### 6.1. Automated Tests
- Test suites or commands to execute:
  ```bash
  # Unit and integration test suite
  pytest
  # or: npm test
  # or: python _tools/warehouse.py check
  ```
- Specific test cases to implement:
  - [ ] Test case 1: Happy path verification.
  - [ ] Test case 2: Error handling, edge cases, or timeout behavior.
  - [ ] Test case 3: Regression defense.

### 6.2. Manual Verification & Live Gates
- Steps to manually verify in the runtime environment:
  1. [Step 1: Setup test environment or start services]
  2. [Step 2: Trigger action via CLI, UI, or API]
  3. [Step 3: Inspect output, logs, or database state]
  4. [Step 4: Confirm expected result]

---

## 7. Rollback & Safe Recovery Plan

If the change fails during or after deployment:

1. **Failure indicators:** How do we know the change is failing (e.g. error logs, failed test gates, container crash)?
2. **Rollback steps:**
   - Git revert command: `git revert <commit-hash>`
   - State/data recovery: Steps to roll back schema migrations or restore cached state.
3. **Data preservation:** Ensure in-flight or partial data is not corrupted during rollback.

---

## Changelog

### [Unreleased]

#### Added
- Initial draft of the technical plan document template.
