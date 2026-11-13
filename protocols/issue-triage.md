---
id: protocol/issue-triage
version: 0.1.0
status: draft
summary: Label every finding by severity, likelihood and whether it blocks; fix now only what blocks or is critical, or major and likely; record everything else in the backlog so it stays known.
applies-to: [codebase, vault]
settings: {}
requires: [convention/backlog@0.2]
replaces: null
---

# Issue Triage Protocol

How an agent decides **what to fix now and what to record for later** whenever a finding turns up: in a
review, a live check, a test run, or while working on something else. Every finding gets three labels.
Only a few are fixed at once. The rest go into the project's backlog with their labels, so they stay
known, acknowledged and worked around instead of being fixed on the spot.

The labels and the backlog format come from [[backlog]] (`convention/backlog`). This protocol says how to
use them. It works alongside [[phased-implementation]], whose reviews and checks produce most findings,
and [[phase-staffing]], which decides who builds a fix round, when the project uses them.

## Why it exists

Without a rule, an agent treats every finding that touches a stated rule as a blocker, whatever its
odds. In the case this protocol came from, a phase that had been built, reviewed and fixed went through
four more fix rounds. Each one fixed an unlikely corner case, and each round's tests found another. The
next phase was delayed by hours, on an application with one user that was still in development.

Two things are true at once:
- **A perfect implementation can't be reached.** Nobody can check every detail all the time, and chasing
  the last corner cases costs more than it saves.
- **An unseen bug is worse than a known one.** A gap that is found, labelled and recorded can be worked
  around and fixed later. One that is never written down surfaces at the worst moment.

So the aim is not to fix everything. It is to **see everything, and fix the right things now**.

## The three labels

Give every finding all three before proposing anything.

1. **Severity:** `Nitpick`, `Minor`, `Major` or `Critical`, as defined in `convention/backlog` §4.4.
2. **Likelihood:** `Frequent`, `Occasional`, `Rare` or `Improbable`, as defined there. Judge it for the
   project's real situation: how many users, how far along it is, and what its inputs are in practice.
3. **Blocks:** yes or no. A finding blocks only if one of these is true:
   - the test suite can't run, or the main branch would stay red;
   - a merged feature people use is broken in normal use;
   - the next piece of work is built directly on the broken part;
   - it is `Critical`, at any likelihood.

## The rule

**Fix now** a finding that blocks, is `Critical`, or is `Major` and `Frequent` or `Occasional`. These are
the findings whose default priority is `P1` (`convention/backlog` §4.4).

**Everything else is recorded at once**, never left only in a chat or a report:
- **A finding with a fix in mind** becomes an open task in the backlog. It carries its severity and
  likelihood, the priority from the convention's table, the evidence (the command, the input, the
  output), and one line saying what is wanted.
- **A gap accepted on purpose**, with no fix planned, goes in the Findings Register: under Known Gaps
  Accepted Deliberately, Untested Behaviour, or Security Debt for a security gap.

**The user can overrule any label or decision.** The report shows the labels so they can.

## The delay budget

Fixing costs something too. Every fix round is a brief, an agent run, a check, often a test run, and a
delay to the next piece of work. So:
- **One agreed fix round per phase.** After a phase is built and reviewed, its fix-now findings go into
  one round. Anything found after that round starts is labelled and recorded, not fixed, unless it
  blocks or is `Critical`.
- **Stop when the corners keep coming.** If a fix round's own tests or checks keep finding more findings
  of the same kind, the approach is probably the problem. Say so, record a task for the simpler
  approach, and record the corner cases instead of patching them one by one.
- **Name the cost when proposing a fix:** roughly how long it takes and what it delays. A fix worth less
  than the delay it causes is recorded, not made.

## Reporting

Report findings to the user in one table:

| Finding | Severity | Likelihood | Blocks? | Fix now, task or register |
|---|---|---|---|---|
| … | … | … | … | … |

- Propose a fix round only for the fix-now rows.
- Record the other rows in the backlog in the same turn, and say where they went (task IDs, register
  heading).
- If a likelihood is uncertain, say what would settle it (a probe, a test), and label it by the more
  likely case.

## Example

| Finding | Labels | Decision |
|---|---|---|
| Two tests still expect the previous database schema, so the suite is red on every run | Minor, Frequent, blocks | Fix now: it blocks |
| A test run hangs the terminal in one test | Major, Occasional | Fix now |
| A confirmation is offered for an action that is then correctly refused | Minor, Rare | Task, P3 |
| A preview's escaping misses a contrived input that needs hostile content and a click, in a single-user app | Minor, Improbable | Task, P3, or the register if no fix is planned |

## Changelog

### [Unreleased]

#### Removed
- The link to the case study behind the example; the case study is no longer published.

### [0.1.0] - 2026-10-09
#### Added
- Initial draft: three labels per finding (severity, likelihood, blocks), the fix-now rule, recording
  everything else as a task or in the Findings Register, the delay budget, and the report table.
- Uses the severity, likelihood and priority definitions from `convention/backlog`, so both items share
  one vocabulary.
