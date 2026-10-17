---
id: template/probe-brief
version: 0.1.0
status: draft
summary: Copyable brief for a probe — throwaway measurements that test what a plan assumes, with no product code and no reviewer; every result names its raw file and is marked CONFIRMED or INFERRED.
applies-to: [codebase]
settings: {}
requires: []
replaces: null
---

<!-- Used by [[phased-implementation]] (Stage 0, step 2) and [[phase-staffing]]. Save it as `BRIEF_<id>_<phase>_probe.md` beside the other briefs, fill every [bracketed] placeholder, delete these comments. If another engine runs the probe, add the "How this round runs" section from [[implementation-brief]] after the header. -->

# Probe brief — [Item ID] [Phase]: [the question, in a few words]

> **From:** the Orchestrator ([engine], [model]) | **To:** one probe agent ([model]) | **Written:** [YYYY-MM-DD]
> **Spec:** [where the question is written: plan §, backlog item or note]. [The item or plan decision the result decides.]
> **Branch / worktree:** none. No product code; nothing is committed.
> **Read first:** this brief; [the spec]; [the code the probe imports or imitates, with the function names]; [the note that says how this project measures things, if any].

## How this probe is staffed
<!-- Per [[phase-staffing]] -->

| Phase | Size (throwaway code; time) | Needs | Can be run beside | Agent |
|---|---|---|---|---|
| [Phase] | [lines of scripts; hours, plus a [N]-minute live session with the user] | [nothing / what must exist first] | [anything that doesn't load the machine or touch what is measured / nothing] | one probe agent, [model] |

- **Shape:** [one agent; why the parts belong together].
- **Model:** [model, and why: e.g. the brief fixes the candidates, the checks and the output].
- **No reviewer.** The probe adds no product code. Instead the Orchestrator checks the report's numbers against the raw files, and the user does the checks only a person can see. The review belongs to the plan this probe feeds.

## What [Phase] is

[Two or three short paragraphs: the decision waiting on this probe, the candidates it compares, and the main question nothing found so far answers. Name the rules or invariants at stake.]

This probe doesn't:
- change anything under [product and test folders], or commit anything;
- [run the live application, use its ports or hotkeys, or open its data folder];
- design [the item]. It reports what works and what it costs. The recommendation is the Orchestrator's and the user's.

## Rules

- **Probe folder:** everything goes in `[absolute path to a scratch folder outside the repository]/[probe]/`. Raw output in `raw/`, screenshots in `shots/`.
- **The project's code is imported read-only:** [modules or functions]. Never edit them.
- **Environment:** [OS], [shell], absolute paths. Already installed: [interpreter and library versions, CLIs]. **Nothing is installed globally.** If something is missing, stop and report.
- **One candidate at a time,** each in a fresh process, so measurements don't mix. Close everything the probe opened when a script ends, including on an error.
- **[Real input devices / live services]:** automated checks never [move the mouse, send keys, call the live service]. Anything that needs them is in the user's live session only.
- **Before measuring,** record [anything running that would skew the numbers, e.g. the app itself]. Write it in the report beside the numbers; don't stop it.
- **Evidence rule:** every number and observation in the report names the raw file it comes from, and is marked **CONFIRMED** (measured or seen) or **INFERRED** (reasoned from something measured). What wasn't measured says **not tested**.
- **Stop and report** instead of guessing if a candidate can't be built as written.

## Orchestrator decisions (settled; don't reopen)

[Every choice the probe could make on its own, made now. One numbered item each: the decision in bold, the detail, then a line of why.]

1. **The candidates:** [each candidate, with exactly how it is set up]. [Why these.]
2. **The test scene or input:** [the same for every candidate, at fixed positions or with fixed data, written to `raw/[scene].json` so checks can read it back].
3. **The load:** [what runs while costs are measured, and why it is close to the worst case].
4. **[Fallbacks:]** [what to try, in order, only if every candidate fails a named check].

## The checks

### Part A: automated (`[probe]/check_<candidate>.py`, one process per candidate)
For each candidate:
1. **[Check.]** [What to read or measure, how, and what counts as a pass.]
2. **[Cost:]** [the measuring method, the settle time and the sample time, for each of idle and under load; memory; start-up; frames or throughput]. If a counter can't be read, say so and move on.
3. **[What can't be measured on this machine]** (e.g. a second monitor): record it as not tested.

### Part B: [specifics of the leading candidate] (optional)
1. [Feature check, with the capture or output it produces.]
2. **Under the test runner's conditions:** [e.g. headless]. Does it load? What fails (errors and warnings, verbatim)?

### Part C: the user's live session (`[probe]/run_live.py <candidate>`, about [N] minutes)
Only candidates that passed Part A's [named checks] go to the live session. The report lists these steps for the user, per candidate, with a line for each answer:
1. [What the user looks at or does, and the question it answers.]
2. [...]

## Report

Write `[probe]/REPORT.md`:
- one table per check, candidates as columns, each cell CONFIRMED or INFERRED with its raw file;
- the cost table, with the note on what else was running;
- Part B's answers with their capture paths;
- the Part C checklist, ready for the user;
- anything that didn't work as written, and why;
- a short paragraph: which candidates keep every rule, and what each costs. **No recommendation.**

## After the probe (the Orchestrator)

1. Recompute a sample of the report's numbers from the raw files, and read the raw output wherever the report says how a tool behaved ([[phase-staffing]], "Reports are checked against their raw evidence").
2. Run the live session with the user.
3. Write the project note `[notes folder]/NN_[topic].md` from the report and the live session, marking each finding confirmed or refuted, and fold it into [the plan or item].

## Changelog

### [Unreleased]
#### Added
- Initial template: a brief for a probe subagent with no branch, commits or reviewer; a scratch probe
  folder with raw output; settled candidates, scene and load; automated checks, optional specifics and
  the user's live session; a report with every cell CONFIRMED or INFERRED and its raw file, and no
  recommendation; the Orchestrator's checks after the probe.
- Generalised from five Shadow Cursor probe briefs (#038 O0, #061 M0, #063 MM0 and MM0b, #084 P1).
