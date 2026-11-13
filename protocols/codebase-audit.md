---
id: protocol/codebase-audit
version: 0.1.0
status: draft
summary: How to audit a codebase for any purpose — set the purpose and criteria, pin a commit, build the core of units and relations with evidence, run the chosen lenses, verify, triage findings and hand over; also the scoped re-audit of what changed.
applies-to: [codebase]
settings:
  audit_folder:
    description: "Folder where audit records are kept, one subfolder per run"
    default: "docs/audits"
requires: [convention/audit-record@0.1, protocol/issue-triage@0.1]
replaces: null
---

# Codebase Audit Protocol

How an agent, or a person, audits a codebase and writes the record defined in [[audit-record]]
(`convention/audit-record`) under {{audit_folder}}.

The audit itself has no purpose of its own. **The purpose is chosen by the lenses that run**: a
structure lens for a codemap, a debt lens for a tech-debt map, a health lens for a health check. The
steps below are the same for every purpose; only the lenses, the criteria and the depth change. A
project pulls the lens items it needs; a lens is run by following its own item.

## 1. When to audit

There is no fixed schedule. Audit when someone needs an answer about the codebase as a whole:
- before building or refreshing a codemap;
- before a large change: a rewrite, a refactor, a move to a new framework;
- when taking over or returning to a codebase;
- for a health check or a tech-debt review the user asks for.

A refresh after changes is a **scoped re-audit** (§4), not a new full audit.

## 2. How the purpose shapes the audit

| Purpose | Lenses | Criteria from | Main evidence | Depth |
|---|---|---|---|---|
| Map the code | structure | none, or the project's own layering rules | code, build files, entry points | module or file |
| Health check | health | ISO/IEC 25010 characteristics; test, build and lint results | test and CI runs, coverage | module |
| Tech debt | debt, duplication | ISO/IEC 25010 maintainability; the project's rules | static analysis **and git history** | file in hotspots, module elsewhere |
| UI inventory | ui | the project's design system, if any | components, styles | file or symbol |

Combine lenses freely; the core is built once, at the deepest depth any of them needs.

## 3. The steps

### Step 1. Set the purpose
Agree these with the initiator (usually the user) before reading any code, and write them into the
header of `00_AUDIT.md` (`convention/audit-record` §3):
- **initiator and purpose:** who asked and why, in one line;
- **lenses:** which lens items run, from those the project has pulled;
- **criteria:** each lens proposes its criteria; the initiator may add the project's own rules;
- **scope:** what is included and excluded;
- **depth:** the deepest unit kind the core lists, at least what every lens declares it needs;
- **history:** the git-history window, if any lens needs history.

Show the user this set as a short table and wait for agreement. A purpose stated only in a chat is lost
by the next session.

### Step 2. Pin the commit
- Audit one commit, and record its full SHA. Every `path:line` in the record refers to it.
- If other agents or people are working in the repository, audit in a separate worktree at that commit
  (see [[worktree-claims]] when the project uses it), so the code doesn't change under the audit.
- Uncommitted changes are not audited. If they matter, ask for them to be committed first.
- Create the record folder: `{{audit_folder}}/<YYYY-MM-DD>-<short commit>/`.

### Step 3. Choose the measures
List the tools whose output will be evidence (dependency graphs, call graphs, clone detectors, linters,
coverage, `git log`), each with its version and exact command, in the header's `measures`. Prefer the
same tools and settings as the previous record for this repository, so results stay comparable. If a
tool is missing, say so and fall back to reading code; never present a guess as tool output.

### Step 4. Orient
Read, in order: the README and other top-level docs; the build and package manifests and lock files; the
CI configuration; the folder layout; the test layout. From this, write the `system` unit and a first
list of subsystems. Docs may be out of date: anything taken only from them is `INFERRED` until the code
confirms it.

### Step 5. List the units
Walk down from the subsystems to the agreed depth, writing units into `core.md`. Give each one a purpose
line and its entry point if it has one. Reuse the ids from the previous record for units that still
exist; mark moved or renamed ones with `was:`.

### Step 6. Trace the relations
In this order, recording evidence and confidence for each relation:
1. **Static tools first:** imports and dependency graphs from the measures in Step 3.
2. **Entry points by hand:** follow each entry point through the calls it makes, reading the code.
   Static tools miss dynamic calls, plugins, configuration-driven wiring and generated code.
3. **Tests to confirm:** a test that exercises a relation confirms it; note it as a `tests` relation.

Then list the **outside things** (data stores, services, libraries, config, environment variables) each
unit uses. Anything you could not trace goes under Gaps with the reason.

### Step 7. Collect history (when needed)
If a lens needs history, run the agreed `git log` command over the window and fill the History section
of `core.md` per unit. Record the command as a measure.

### Step 8. Run the lenses
For each lens, follow its item:
- check its declared needs against the core (depth, history) and deepen the core first if needed;
- write `lens-<name>.md` with its criteria, results, findings and gaps (`convention/audit-record` §5);
- label every finding with severity, likelihood and blocks per [[issue-triage]].

Lenses that don't depend on each other can run in parallel.

### Step 9. Verify
Before the record is called complete:
- **Evidence everywhere.** Every relation and every finding has evidence. List any that don't under
  `evidence-missing` in `00_AUDIT.md` and fix them; the list must be empty for `status: complete`.
- **Sample the `INFERRED` ones.** Re-check at least 5 or 20% of `INFERRED` relations, whichever is more
  (all of them if there are fewer than 5), by reading the code at the evidence. Record how many were
  upheld and which changed. If more than one in five changed, re-check all of them.
- **Lens contract.** Every lens entry points at an existing core unit id, and every finding cites a
  criterion (`convention/audit-record` §6).
- **Gaps listed.** Anything in scope that wasn't covered is under Gaps, with its reason and impact.

### Step 10. Triage and hand over
- Record findings in the backlog through [[issue-triage]]: fix-now findings are reported to the user at
  once; everything else becomes a backlog task or a Findings Register entry. Write each backlog id back
  into the finding.
- Write the Summary and Links sections of `00_AUDIT.md`.
- Report to the user: the record's path, the summary, the findings by label, the gaps, and anything
  that needs their decision.

## 4. Scoped re-audit

The same protocol with a smaller scope, used to refresh a record after changes (for example by a
codemap's upkeep).

1. **Start from the latest record** for the repository. Set `kind: scoped` and `previous: <its audit id>`.
   Keep its lenses, criteria, depth and measures unless the initiator changes them.
2. **Find what changed:** `git diff --name-status <previous commit>..<new commit>` within the scope.
3. **Re-audit** each changed unit, its parents up to the subsystem, and every relation into or out of
   them (Steps 5–7 on that set only). Units that no longer exist go under Gaps as removed.
4. **Carry forward** everything else from the previous record, marked `carried: <previous audit id>`
   (`convention/audit-record` §7). The new record is complete on its own.
5. **Re-run the lenses** on the changed units and on any lens result that points at them, then Steps 9
   and 10 as usual. A finding already in the backlog keeps its id; one that the changes fixed is noted in
   its backlog entry.

If more than about half the units changed, or the previous record used different measures, do a full
audit instead.

## 5. Sharing the work

For a large codebase, split Steps 5–8 by subsystem across subagents or sessions. Decide the staffing with
[[phase-staffing]] when the project uses it. Each worker writes its units and relations for its own
subsystem only, using the agreed id rules and the shared measures. The orchestrator then:
- merges the parts into one `core.md`, checking that ids are unique and that relations between
  subsystems are traced from both sides;
- runs Step 9 itself, on the merged record, before accepting any worker's part. A worker's report is a
  claim; the evidence in the record is what counts.

## 6. Rules

- **One commit per record.** Never mix evidence from two commits.
- **No fact without evidence and confidence.** A guess is `INFERRED` with a note, never left unmarked.
- **The core describes; lenses judge.** Don't put findings in the core or units in a lens.
- **Don't fix during the audit.** An audit records; fixes come later, through the backlog. A fix-now
  finding is reported, not patched in the audit's worktree.
- **Keep old records.** A new run gets a new folder; earlier records are never edited, except to add a
  backlog id to a finding.

## Changelog

### [Unreleased]

### [0.1.0] - 2026-11-13
#### Added
- First draft.
