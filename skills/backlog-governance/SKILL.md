---
id: skill/backlog-governance
version: 0.3.0
status: draft
summary: "How an agent works a project's backlog at any level: orient, choose, claim, record findings, close with evidence, review, and know when to propose a change of level."
applies-to: [vault, codebase]
settings:
  backlog_layout:
    description: "Backlog layout: 'single', 'split', 'folders' or 'tracker'"
    default: "single"
  backlog_file:
    description: "Path to the backlog file when backlog_layout is 'single'"
    default: "BACKLOG.md"
  backlog_dir:
    description: "Path to the backlog folder for every other layout"
    default: "BACKLOG"
requires: [convention/backlog@0.2]
replaces: null
---

# Backlog Governance

How to work a project's backlog, from the start of a session to closing a task. The format is in
[[backlog]] (`convention/backlog`). This skill says what to do with it.

This project's backlog: layout `{{backlog_layout}}`, in `{{backlog_file}}` (single file) or
`{{backlog_dir}}/` (every other layout).

## 1. The project's header wins

Every backlog starts with a header saying how it is run: layout, ID scheme, entry style, who writes,
and any deviations from the convention. **Read it first, and follow it where it differs from the
convention.** The convention is a framework; the project's version of it is the one that counts.

If there is no header, work as if it were Level 1 by hand, and propose adding one to the user.

## 2. At the start of a session: orient

Read only what you need to see the open work. Don't load closed history unless the task needs it.

| Layout | Read |
|---|---|
| Single file | The header, In Progress and Backlog (Open Tasks). Skip Completed and the Icebox. |
| Split files | `00_BACKLOG.md`, then `Open.md` |
| Item folders | `00_BACKLOG.md`, then list `open/`. Read each item's frontmatter, not its body. |
| External tracker | `00_BACKLOG.md`, then the tracker's open issues, through its command-line tool |

Also note what is In Progress and who holds it.

## 3. Choosing what to work on

1. **The user's request comes first.** If it matches an existing item, work under that item. If it
   doesn't, open one (§5) before starting, unless the user says it's too small to track.
2. **Your own unfinished claim** comes next: resume it.
3. **Otherwise propose the next ready item** (convention §7.5: highest priority, every dependency
   closed, oldest first) and wait for the user's go-ahead.
4. **Leave items other people have In Progress alone.** Work that isn't yours stays theirs unless it's
   explicitly opened up: its owner can't continue, or has said they're open to working on it together.
   If you do pick it up, add a dated note saying who handed it over and why.

## 4. Claiming

Follow the header's "Writes" rule:

| Writes | To claim |
|---|---|
| By hand, one writer at a time | Set the status to In Progress yourself, and move it to In Progress in a single or split backlog |
| One named writer | Ask the writer to claim it for you. Don't edit the backlog yourself. |
| Tool only | Run the tool's claim command (§9) and work where it tells you |
| External tracker | Assign the issue, and use a branch named after it |

When several agents work at once, also work on a branch named after the item. Under the full entry
style, write the Plan straight after claiming.

**If you don't own the backlog,** report instead of editing: to the named writer if the project has one,
or to the user if it has none (for example, when several orchestrator agents each run part of the
project). The same applies to opening and closing items.

## 5. While working

- **Opening an item:** allocate the ID from every open and closed item, give it a priority, and write it
  in the project's entry style. Under one named writer or tool only, go through the writer or the tool.
- **New work found along the way** becomes a new item, linked from the current one. Don't widen the
  current item's scope.
- **Findings** (bugs, gaps, risks) are triaged with [[issue-triage]] if the project has it. Without it,
  the convention alone is enough:
  - label the finding's severity and likelihood, and take its priority from the convention's table
    (§4.4). Anything that blocks other work is P1;
  - **P1 means do it now**: raise it with the user before carrying on;
  - everything else is recorded at once: as an item if a fix is in mind, or in the Findings Register if
    the gap is accepted (convention §8).

  Never leave a finding only in chat or in a report.
- **Notes are dated and added, never rewritten.** After claiming, change only the status, priority and
  dependencies in place.
- **Item folders:** put plans, evidence and probe scripts in the item's folder, and list them under
  `## Files` in its main file.

## 6. Closing

1. Check every acceptance criterion against evidence: a test run, real output, or a verified manual
   check. Never tick on code being present or on intent.
2. Write the Outcome: what was done, the evidence, and the commits.
3. Set the status to `Closed`, add the Resolved date, and move the item (convention §7.3). If you don't
   own the backlog (§4), give the Outcome to the writer, or to the user, instead.
4. Tell the user what was closed and where the evidence is.

**Rejecting or cancelling is the user's decision.** Propose it with a reason, and record it only when
they agree.

## 7. Reviewing

> **This is a manual check, not an automated one.** Nothing schedules it and no tool runs it. You notice
> stale items while you're handling backlog tasks, and mention them. The user reviews them whenever they
> can. The three months is a rough guide, not a deadline.

When you come across open items that look stale (roughly three months without a dated change, or
untouched at the end of a phase), list them for the user with a suggestion for each: change its
priority, confirm it still stands, or cancel it. Change nothing until the user decides.

## 8. Proposing a change of level

Tell the user when you see the signs from convention §1, and suggest the next level. **Never migrate on
your own.** Signs to watch for:

- the backlog file is over about 75 KB, or mostly history;
- you keep loading closed items to find open ones;
- tasks keep collecting plans and evidence elsewhere in the repo;
- agents collide on IDs or on the same file;
- other people need to report issues.

## 9. Under tool-only writing

The project uses a backlog tool for every change, such as `tool/backlog-cli` from the warehouse. Pull it
if the project doesn't have it, and check that it supports the project's layout.

| Step | `tool/backlog-cli` |
|---|---|
| Check the setup | `task.py doctor` |
| See active claims | `task.py status` |
| Open | `task.py open "<title>" --prefix <P> --priority <P1-P3>` |
| Claim | `task.py claim '<ID>'`, then work in the printed worktree |
| Resume a claim | `task.py adopt '<ID>'` |
| Close | `task.py close '<ID>' --outcome "<one line, past tense>"`, run from the main tree |
| Release without merging | `task.py abandon '<ID>'` |
| Reject or cancel | `task.py reject '<ID>' --reason "<why>"` or `task.py cancel '<ID>' --reason "<why>"`, run from the main tree |
| Amend | `task.py amend '<ID>' --note "<text>" [--priority <P1-P3>]` |
| List items | `task.py list [--status <status>] [--priority <P1-P3>]` |
| What's next | `task.py next` |

- **Agents don't edit by hand, not even a single line, unless the user allows it.** A hand edit bypasses
  ID allocation and the tool's checks. The user's permission covers what they said it covers, and no
  more.
- **The user may bypass the tool** whenever they need to, and choose between the tool and editing by
  hand. The rule binds agents, not the user.
- If the tool has no command for a step (for example, editing a claimed item's dependencies or criteria,
  convention §4.8), ask the user how to proceed rather than editing by hand.

## 10. Never

- Delete an item, or reuse an ID.
- Tick a criterion, or close an item, without evidence.
- Edit an item someone else has In Progress, unless it has been explicitly opened up to you (§3).
- Edit a generated section, or hand-edit anything under tool-only writing, unless the user has said you
  may (§9).
- Keep two sources of truth. One is the source, and anything else, such as a Markdown export of tracker
  issues, is generated from it and never edited by hand.
- Change the project's level, layout or rules without the user.
