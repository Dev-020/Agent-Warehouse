---
id: template/review-request
version: 0.1.0
status: draft
summary: Copyable requests for a fresh reviewer subagent — a design review of a plan, and a phase review of code backed by probe scripts.
applies-to: [codebase]
settings: {}
requires: []
replaces: null
---

# Review requests

Used by [[phased-implementation]] (Stage 1, step 2 and Stage 2, step 6). Two variants. Send one as the whole prompt to a **fresh** reviewer subagent. The reviewer gets only what is listed here and reads everything else itself.

## Severity scale (both variants)

| Severity | Meaning | What happens to it |
|---|---|---|
| **Blocker** | Wrong behaviour, lost data or work, a broken invariant, or a security boundary crossed, in a case that can really happen | Always fixed before the merge |
| **Should-fix** | A real defect in a narrow or unlikely case, or a missing test for a stated requirement | Fixed in the fix step unless the user approves deferring it |
| **Nit** | Clarity, naming, a small inefficiency, a misleading comment | Fixed if cheap; otherwise dropped with a note |

### Severity is not backlog priority

Severity grades a defect in code that hasn't merged yet. It decides whether one phase may merge, and it lasts only until the fix step. Backlog priority (`P1`–`P3`, [[backlog]]) ranks work against everything else in the project, for scheduling. The two meet only when a finding is **deferred**, which turns it into a backlog item:

| Finding | If deferred |
|---|---|
| Blocker | Can't be deferred; fixed before the merge |
| Should-fix touching correctness, security or data | `P1` |
| Other should-fix | `P2` |
| Nit | `P3`, or dropped with a note |

Every deferral needs the user's approval, and the backlog item names the phase, the finding's ID and its probe.

---

## Variant A — design review of a plan

```
You are reviewing a design plan before any of it is built. Read-only: do not edit any file.

Plan: [path]. Background it depends on: [paths to notes, prior session logs].
The plan's goal: [one sentence].
Settled by the user (do not re-argue; flag only if one is contradicted elsewhere): [list or § reference].

Review for:
1. States and transitions: can any state be reached with no owner, or changed from two places?
2. Races between concurrent actors, and check-then-act gaps.
3. Crash and restart: what does each step leave behind if the process dies right after it?
4. Security and trust boundaries: what can an agent or user do that the plan says it can't?
5. Phasing: is each phase buildable and testable on its own, and small enough for one implementer session?
6. Tests: does §[verification] name a test for every requirement, following [[testing]]?
7. Anything the plan relies on that nobody has checked against the real tool or API.

Report: findings numbered B1.. (blockers), SF1.. (should-fix), N1.. (nits). Each gives the plan section, the scenario that
breaks, and a suggested change. End with the open questions you would put to the user. Keep it under [N] words.
```

After revising, send **one confirmation review** with the same request, plus: "Revision [n]: the previous findings and how each was addressed are in [changelog or section]. Check the fixes and look for new defects the revision introduced."

---

## Variant B — phase review of code, with probes

```
You are reviewing phase [Phase] of [Item ID] before it merges. Do not edit files in the repository.

Worktree: [path], branch [branch]. The phase's commits: [base commit]..[head commit] (read them with git diff and git show).
Spec: [plan path, §]. The brief the implementers followed: [brief path] (its "Orchestrator decisions" are settled).
Invariants that must hold: [list].
Known and accepted limits (don't report these): [list].

Check test quality ([[testing]]): assertions are present (no print-only probes); any new mocks are justified; no assertions were
weakened, skipped or deleted without saying so in the report; and new tests have no order dependence (run the new tests alone and
with their file).

For every finding, write a probe script in [scratchpad path]/rv_[phase]/ named pNN_<slug>.py that FAILS on the current code
and would PASS once the finding is fixed. Use the project's fakes and test helpers where you can, and real dependencies only
where the defect needs them. Add a run_all.py that runs every probe and prints one PASS or FAIL line each and a total.
Run it before reporting. Don't run the full test suite.

Report: findings numbered B1.. (blockers), S1.. (should-fix), N1.. (nits). Each gives file:line, the scenario, the probe
name, and a suggested fix. Then the run_all.py output. Keep it under [N] words.
```

**Confirming the fix step:** re-run `run_all.py` after the fix commit. Every probe must pass. A fix that differs from the reviewer's suggestion is fine if every probe passes; record why in the session log.

## Changelog

### [Unreleased]
#### Added
- Variant A item 6 links [[testing]]; Variant B adds a test-quality check (assertions present, new mocks justified, no weakened or skipped assertions, and no order dependence when running new tests alone and with their file).

### [0.1.0] - 2026-10-02
#### Added
- Initial template: plan design review and phase code review with probe scripts, from the Shadow Cursor #038 build.
- "Severity is not backlog priority": the mapping from a deferred finding's severity to a backlog priority.
