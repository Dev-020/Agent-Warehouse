---
id: template/live-check
version: 0.1.0
status: draft
summary: Copyable live check — steps the user runs against the real, running application after a phase merges, as a short section in the brief or a full sheet; the Orchestrator checks the results against raw evidence, triages what was found and records re-run triggers.
applies-to: [codebase]
settings: {}
requires: []
replaces: null
---

<!-- Used by [[phased-implementation]] (Stage 1 step 4, Stage 2 step 10, Stage 3) and [[plan-document]] §6.2. A live check shows that a phase works in the real application, not only in the test suite. It is optional: write one only when the phase changes something a person can see or the real environment can break, and when a live run is possible at all.

Two forms. Use one per check and delete the other:
- Form A, a short section at the end of the phase brief: a few numbered steps, one environment, no setup beyond starting the app.
- Form B, a sheet of its own, `LIVE_CHECK_<id>_<phase>.md` beside the briefs (a gate between phases: `LIVE_CHECK_<id>_gate<N>.md`): a scene to set up, several engines or environments, tables, a helper script, or a gate the next phase waits on.

One sheet per check. A later phase or gate gets a new sheet; don't add parts to an old one. A check that also covers an earlier phase lists it under "What this tests".

Roles: the Orchestrator writes the check, the user runs it from the primary tree after the merge, one check at a time, and the Orchestrator checks the user's results against raw evidence before calling it passed. Fill every [bracketed] placeholder and delete these comments. -->

## Form A — a section in the phase brief

## The live check after the merge (the user's)

**When:** after [phase] is merged and the app is restarted from `[integration branch]` [your usual way]. About [N] minutes. **If a step fails:** note the step and the time, and send [the raw file or log lines that show what happened, e.g. the newest file in `[stream folder]`, terminal lines containing `[pattern]`].

1. **[What it shows, in a few words].** [What the user does.] [What should happen.]
2. [...]
3. **From the review ([finding ID]).** [A step that shows a review finding is fixed in the real app.]

<!-- The user reports the results in chat. The Orchestrator checks them against the raw files, records the outcome in the hand-over (see "After the check" in Form B), and triages anything found. -->

---

## Form B — a sheet of its own

# Live check: [Item ID] [phase or gate N], [what it tests in a few words]

> **For:** [plan §, phase]. [Gate [N]: the next phase, [phase], waits until it passes. / A check after the merge; nothing waits on it.]
> **Run it:** after [what must be merged or done], with the app restarted from `[integration branch]` [at `[commit]`] [your usual way]. About [N] minutes.
> **Written by** the Orchestrator ([engine], [model]), [YYYY-MM-DD]. **Run by** the user, from the primary tree, one check at a time. **Checked by** the Orchestrator against raw evidence.

**What this tests:** [the behaviour, and the plan criteria or review findings it covers]. **What it doesn't:** [what is left to the test suite or to a later check].

## Before you start

**Set up the scene:**
- [Windows, data, accounts or files the steps need, and where they must be.]
- [What to swap in if something isn't available, and to say so in the notes.]

**Safety:**
- **What this touches:** [the real files, services, accounts or settings a step reads or changes]. [Anything that isn't undone by the steps themselves.]
- **Back up first:** [what, how, with the app closed if needed]. / Nothing to back up: [why].
- **Don't:** [actions that would harm the real environment or skew the check, e.g. approve a card a step says to decline].
- **To undo:** [how to restore the state after the check].
- **No secrets in the results:** no tokens, keys, passwords or personal data. Describe them ("the key was shown") instead of pasting them.

**The helper** (optional; [what it talks to; that it changes nothing else]):
```bash
[command]
```
Commands: [`one`, `two`, …]. Run them in a second terminal while the app runs.

**If a step fails:** note the step and the time, take a snip if it shows on screen, and send [the newest raw file in `[folder]` / terminal lines around it, especially any containing `[pattern]`]. These are what the Orchestrator checks against.

**A pass** is [what counts, e.g. the cursor landing on the thing asked for]. [A near miss, e.g. one icon off, counts as a miss; note what happened instead.]

## Part A — [area]

**A1. [What it shows].** [What the user does.] [What should happen.]
> Result:

**A2. [...]**
> Result:

<!-- A table instead, when the same steps run on several engines or environments: -->

| # | [Action or prompt] | Expected | [Engine 1] | [Engine 2] | Notes |
|---|---|---|---|---|---|
| 1 | [...] | [...] | | | |
| | **Passes** | | /[N] | /[N] | [a reference figure, if there is one] |

**What the result means:** [which failures hold the gate or the phase's close, and which become a finding for triage; e.g. "a worse score than note 13 is a finding; only plainly broken pointing holds the close"].

## Part B — [area]

[...]

## Results

<!-- Filled in by the user. One block per run; a rerun after a fix gets a new block. -->

**Run [1], [YYYY-MM-DD], on `[branch]` at `[commit]` (user):** [passed / failed at [step]]. [Anything seen in passing.]

| Step | Result | Notes |
|---|---|---|
| A1 | | |
| A2 | | |

## After the check (the Orchestrator)

**Checked against raw evidence:** [the raw files read, e.g. the stream, the store copy, the run folder, and what each confirmed]. [A step that left no trace to check, and why.] **Passed [YYYY-MM-DD].** / **Failed at [step]:** [what happened].

**After a fix:** run again from the first step, unless the Orchestrator names the steps the fix can't change and why. Each run gets its own block under Results.

**Issues found:** each with its evidence, labelled and routed per [[issue-triage]] (without it: severity, how likely, and whether it blocks; fix now only what blocks).

| Finding | Severity | Likelihood | Blocks? | Fix now, task or register |
|---|---|---|---|---|
| [what was seen, with its evidence] | | | | [task ID / register heading] |

**Re-run triggers:** [conditions that mean this check, or named steps of it, must run again, e.g. "steps A4 and A5 after any CLI update: they passed because of the CLI's own handling, not the app's rule"]. Each one is also written as a bullet under **Watch List** in the backlog's Findings Register ([[backlog]] §8), naming the steps, the reason and this sheet; without that register, in the project's instruction file. The sheet alone doesn't keep it: the trigger has to outlive the work item.

**Hand-over:** the outcome and the checks' commit go in the session log, and the plan's build-order table marks the gate passed.

## Changelog

### [Unreleased]

### [0.1.0] - 2026-10-17
#### Added
- Initial template: a live check the user runs against the real application after a phase merges, in two
  forms (a short section at the end of the phase brief, or a sheet of its own named
  `LIVE_CHECK_<id>_<phase>.md`, `LIVE_CHECK_<id>_gate<N>.md` for a gate); one sheet per check; the
  roles (the Orchestrator writes and checks, the user runs); the header with what it gates, the state it
  needs and the time; scene, safety, an optional helper and what to send when a step fails; checks as
  steps or tables with a definition of a pass and what a result means; results per run; the
  Orchestrator's check against raw evidence; reruns from the first step after a fix; issues triaged
  per [[issue-triage]]; re-run triggers recorded in the backlog's Findings Register Watch List.
- Generalised from Shadow Cursor's ten live-check sheets (#031 to #081 gate 1) and the live-check
  sections of its #063 phase briefs.
