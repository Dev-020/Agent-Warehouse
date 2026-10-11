---
id: template/active-context
version: 0.1.0
status: draft
summary: Copyable active-context folder — a short router note every session reads first, plus one file per work item holding only its current state.
applies-to: [codebase, vault]
settings:
  memory_folder:
    description: "Folder for agent notes, plans and working context"
    default: "AI"
  active_context_folder:
    description: "Folder inside memory_folder that holds the router note and one file per work item"
    default: "ACTIVE_CONTEXT"
requires: []
replaces: null
---

<!-- Used by [[working-memory]] and [[phased-implementation]]. Copy Part A into the router note and Part B once per work item, fill every [bracketed] placeholder, delete these comments. -->

# Active context: router and work-item files

The active context is a folder, not one growing file:

```
{{memory_folder}}/{{active_context_folder}}/
├── {{active_context_folder}}.md   the router (Part A): always read, 6,000 characters at most
├── [081-overlay].md               one file per work item (Part B)
└── [0xx-other]/                   only once an item outgrows one file
    ├── [0xx-other].md             that item's main file (Part B)
    └── …                          its extra files, linked from the main file
```

- **The router** says what is in progress, who owns it, and which file to read. It holds pointers, not
  stories.
- **One file per work item**, named after the item's backlog ID and a short slug. Key it by work item,
  never by session: sessions end through compaction, restarts or an engine switch, and the work goes
  on. The next session takes over the item's file and updates the owner in the router.
- **A work item gets a subfolder** only once it runs several threads side by side (e.g. two sub-phases
  built at once) or needs extra files of its own.

**The router's size is counted in characters** (`wc -m <file>`), not tokens, words or lines. Each engine turns the same
text into a different number of tokens, two words of the same length can cost different numbers of
tokens, and a line can be any length. The character count stays the same whichever engine reads the
file.

**Who writes:** each item's file has one writer, the session that owns the item. The router is shared:
each session edits only its own items' rows, re-reads the router just before editing, and keeps each
edit to whole lines.

---

## Part A: the router

Path: `{{memory_folder}}/{{active_context_folder}}/{{active_context_folder}}.md`. Hard cap: **6,000 characters.**

```markdown
# Active context: [project name]

_Updated [YYYY-MM-DD] by [engine, model, session name or ID]. Cap: 6,000 characters. One row per item; the detail lives in the item's file._

## Read this first

- **Everyone:** this note, to the end.
- **The session that owns an item:** that item's file, all of it, before doing anything else, and again after every compaction.
- **Everything else** (the plan, notes, older session logs): only when the item's file points you there.

## In progress

| Item | File | Owner | Status | Updated |
|---|---|---|---|---|
| [#081 Overlay foundation] | [[081-overlay]] | [claude-code, Opus 5.5, session "overlay"] | [A1a step S2 running] | [YYYY-MM-DD] |

## Waiting

Items started but with no owner right now: blocked, or waiting for the user.

| Item | File | Waiting on | Since |
|---|---|---|---|
| [#063 …] | [[063-middleman]] | [the user's live check] | [YYYY-MM-DD] |

## Where things live

| Kind | Home |
|---|---|
| Standing rules from the user | [`AGENTS.md` § …] |
| Decisions | [the plan, `PLAN_<slug>.md` §3] |
| History of finished work | [the session logs, `AI/session/`] |
| Open issues and findings | [the backlog, `docs/BACKLOG.md`] |
```

---

## Part B: a work item's file

Path: `{{memory_folder}}/{{active_context_folder}}/[id]-[slug].md`. No size cap. It must be current,
up to date and complete, and a cap would only cut what the owner needs. The hand-over clean-up below
keeps it to current state. Background and analysis belong in a note, linked from here.

```markdown
# [#081] [Overlay foundation]: active context

_Updated [YYYY-MM-DD] by [engine, model, session]. Backlog: [#081]. Plan: [PLAN_overlay_foundation.md]. Latest session log: [session/2026-10-11-081-overlay-foundation.md]._

## Now

- **Phase / step:** [A1a, step S2 of 2].
- **Branch / worktree:** [`feat/081-a1a-overlay-package` at `.claude/worktrees/…`].
- **Running:** [an implementer subagent on S2; its report arrives as an agent message].
- **Last verified:** [commit `0e3c763`, S1, checked; targeted tests green].

## Next

1. [Check S2's report and commit.]
2. [Review with probes, then a fix step if needed.]
3. [The user runs the full suite; merge `--no-ff`; remove the worktree.]

## Open questions

- [Question] (waiting on: [the user / the reviewer / a probe]).

## Watch out

Gotchas that matter for the next steps only. A gotcha that will still matter after this item closes goes in a note or `AGENTS.md`.

- [The full suite takes over 12 minutes: the user runs it, never an agent.]

## Done this phase

Cleared at every hand-over (see "Keeping it small").

- [S1 committed `0e3c763`: `src/overlay.py` became the `src/overlay/` package.]
```

---

## Keeping it small

**At every hand-over** (the end of a phase, before a compaction, or when an item changes owner), the
owner goes through its item's file line by line and sends each line to one place:

| The line is… | It goes to |
|---|---|
| Done | The session log for this hand-over |
| A decision | The plan (or the brief, for a decision about one phase) |
| An unresolved issue or finding | Handled per [[issue-triage]]: fixed now, a backlog task, or the Findings Register |
| A rule that will outlast the item | `AGENTS.md` (or the project's instruction file) |
| Still current | Stays |

Then the owner updates the item's row in the router.

**When the item closes**, its file is deleted, and its row leaves the router. Everything in it already has
a home by then; git keeps the old text.

**Signs something should have moved at the last hand-over:** a "Previous:" or history section, finished
work still listed, or the router passing 6,000 characters. A work-item file that keeps getting larger
even so usually means the item itself is too big: split it into smaller backlog items, or give it a
subfolder if it runs several threads side by side.

## Changelog

### [Unreleased]

### [0.1.0] - 2026-10-12
#### Added
- Initial template: a router note (6,000-character cap, read tiers, one row per work item with its
  owner) and one file per work item (Now, Next, Open questions, Watch out, Done this phase; no size cap).
- The router's size is counted in characters (`wc -m`), which stay the same whichever engine reads it.
- The hand-over eviction table: each line goes to the session log, the plan, [[issue-triage]],
  `AGENTS.md`, or stays; an item's file is deleted when the item closes.
- Generalised from Shadow Cursor's single `ACTIVE_CONTEXT.md`, which had grown to about 68 KB.
