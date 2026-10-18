---
id: template/fix-round-brief
version: 0.1.0
status: draft
summary: Copyable brief for a fix round after a phase review — the phase brief still applies, the triaged findings and their probes are the spec, the same worktree and branch, and the probes re-run as the proof.
applies-to: [codebase]
settings: {}
requires: []
replaces: null
---

<!-- Used by [[phased-implementation]] (Stage 2, step 8) after the review and the triage. Save it as `BRIEF_<id>_<phase>_fix.md` (`_fix2`, `_fix3` for later rounds) beside the phase brief, fill every [bracketed] placeholder, delete these comments. Keep it short: it adds only what the phase brief doesn't say. A failed live check ([[live-check]]) gets the same brief, with the failing check standing in for the probe. -->

# Brief — [Item ID] [Phase] fix round[ N]: [the findings, in a few words]

> **From:** the Orchestrator ([engine], [model]) | **To:** [the implementer that built [Phase] (continued) / a fresh [model] implementer; this brief stands alone] | **Written:** [YYYY-MM-DD]
> **Worktree / branch:** the same as [Phase]: `[branch]` at `[worktree path]`, at `[commit]`. Don't create a new one.
> **Read first:** this brief; the phase brief `[path to BRIEF_<id>_<phase>.md]` (its rules, its "How this round runs" and its decisions all still apply); the probes in `[probe folder]` (each probe's docstring says what fails and what makes it pass).

## What this round is

A fresh [model] reviewer checked [Phase] ([steps or commits]). It found [N] blockers, [N] should-fix and [N] nits. **The user chose to fix [which: all of them / the blockers and F1–F4]** ([YYYY-MM-DD]); [the rest went to the backlog as [IDs] / were rejected, with why]. Each finding below has a probe that fails today and must pass afterwards.

Same rules as the phase brief: targeted tests only, **never the full suite**; only this worktree; [the off-limits files and services]; no assertion weakened. [Anything this round adds or relaxes, e.g. a desktop test run allowed once.]

## The findings and the fixes (settled; don't reopen)

<!-- One block per finding, numbered F1.. in this round; keep the reviewer's number beside it. Blockers first. -->

**F1 (review [B1], [blocker/should-fix/nit], [likelihood]) — [the defect in one line].** [What is wrong, with file, function and line, and the scenario that breaks.]
- Fix: [the fix the Orchestrator settled on, including what must stay unchanged and the test that covers it].
- Probe: `[pNN_slug.py]`.

**F2 (review [S1], [severity], [likelihood]) — [the defect].** [...]
- Fix: [...]
- Probe: `[pNN_slug.py]`.

## Steps

### Step F — [all [N] findings, one commit / one commit per finding]
- **First, bring this brief and the probes into the worktree** ([`git merge [integration branch]`; it adds only this brief and the probes, so the merge is clean / they stay outside the repository at `[path]`]). If the merge isn't clean, stop and report.
- The fixes above, with the tests named.
- Tests (targeted, report each result line verbatim): `[targeted test command and files]`.
- Probes: `[command to run [probe folder]/run_all.py against the worktree]` — **expect [N]/[N] passed**. [Earlier probe sets that must stay as they are, with their expected result.]
- [Mutation check, where a probe can't show a line is wired up: delete [the line], name the test that fails, revert.]
- Commit: `[commit message]`, ending `[attribution line]`.

## Report
Write `[report path]` in the worktree and commit it with the step. Commit hashes; files changed; for **each finding**, the file and function changed and the test that covers it; every command verbatim with its result line copied from the output; the probes' output in full; [the mutation check]; every assertion removed or weakened (expected: none); anything you couldn't do as written, and why; the model you ran on. Then stop.

## After the round (the Orchestrator)

1. Check the commits and re-run `run_all.py` yourself. Every probe must pass. A fix that differs from the settled one is fine if every probe passes; record why in the session log ([[review-request]], "Confirming the fix step").
2. A second review only if the fixes reworked a complex state machine or a finding couldn't be reduced to a probe ([[phased-implementation]] step 8). Its findings get the next round, `_fix2`.
3. Then the phase continues at step 9: the full suite once.

## Changelog

### [Unreleased]

### [0.1.0] - 2026-10-18
#### Added
- Initial template: a brief for the fix step after a phase review. The phase brief still applies; the
  triaged findings, each with its severity, likelihood, settled fix and probe, are the spec; the same
  worktree and branch at a named commit; the probes re-run as the gate; a report per finding; the
  Orchestrator's checks after the round. A failed live check uses it too.
- Generalised from Shadow Cursor fix rounds (#063 MM1, #070 B fix2, #081 A2a).
