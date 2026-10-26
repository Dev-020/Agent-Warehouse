---
id: tool/backlog-cli
version: 0.1.0
status: draft
summary: CLI backlog manager for tool-only writing across single-file, split-files, and item-folders layouts with atomic worktree claims.
applies-to: [vault, codebase]
entrypoint: task.py
requires-software: [python>=3.10, git]
platforms: [windows, linux, darwin]
settings:
  backlog_layout:
    description: "Backlog layout: 'single' (one file), 'split' (a folder of files), 'folders' (one file or folder per item) or 'tracker' (an external issue tracker)"
    default: "single"
  backlog_file:
    description: "Path to the backlog file when backlog_layout is 'single'"
    default: "BACKLOG.md"
  backlog_dir:
    description: "Path to the backlog folder when backlog_layout is 'split', 'folders' or 'tracker'"
    default: "BACKLOG"
requires: []
replaces: null
---

# `tool/backlog-cli` — Backlog & Concurrency CLI Tool

## 1. What It Is

`tool/backlog-cli` provides the command set for tool-only writing (`convention/backlog` §6). It manages task allocation, lifecycle transitions, and atomic git worktree claims so parallel human and agent sessions work in isolation without colliding on IDs, files, or branches.

It supports three file-based backlog layouts:
- `single`: one central file, `{{backlog_file}}` (default `BACKLOG.md`).
- `split`: a directory `{{backlog_dir}}` holding `00_BACKLOG.md`, `Open.md`, and `Closed.md`.
- `folders`: a directory `{{backlog_dir}}` holding `00_BACKLOG.md`, `open/`, and `closed/` items.

External issue trackers (`tracker`) are out of scope: they have their own CLIs.

## 2. Requirements

- **Python**: $\ge$ 3.10.
- **Git**: installed and on system `PATH`.
- **Dependencies**: standard library only (no external packages).

## 3. Settings

Settings determine how the tool finds and updates backlog files and worktrees. Settings resolve in precedence order from highest to lowest:

| Setting | CLI option | Environment variable | Git config | Manifest (`.warehouse.yml`) | Default |
|---|---|---|---|---|---|
| layout | — | `BACKLOG_LAYOUT` | `backlog.layout` | `backlog_layout` | `single` (`{{backlog_layout}}`) |
| backlog file | `--backlog-path` (`claim`) | `BACKLOG_FILE`, then `BACKLOG_PATH` | `backlog.file` | `backlog_file` | `BACKLOG.md` (`{{backlog_file}}`) |
| backlog folder | — | `BACKLOG_DIR` | `backlog.dir` | `backlog_dir` | `BACKLOG` (`{{backlog_dir}}`) |
| worktree root | — | `WORKTREE_DIR` | `vault.worktreeRoot` | — | `<root>/../worktrees` |
| base branch | — | — | `backlog.baseBranch` | — | `main`, else `master`, else `main` |

Relative paths resolve against the repository root `<root>`.

## 4. Commands

All twelve commands provided by `task.py`:

| Command | Syntax & Options | Description | Example |
|---|---|---|---|
| `doctor` | `task.py doctor [--init]` | Checks git setup, main tree location, and backlog settings. `--init` configures `vault.worktreeRoot` and creates the directory. | `python task.py doctor --init` |
| `status` | `task.py status` | Lists active claims across `claim/*` branches, ahead commits, idle duration, and worktree paths. | `python task.py status` |
| `open` | `task.py open "<title>" [--prefix <P>] [--new-prefix] [--priority P1\|P2\|P3] [--labels <L>] [--why <W>] [--wanted <W>] [--criterion <C>] [--style full\|compact] [--claim]` | Allocates the next task ID and creates an entry. `--criterion` is repeatable. `--new-prefix` introduces a new prefix scheme. `--claim` claims immediately. | `python task.py open "Refactor auth" --prefix INF --priority P1 --criterion "Passes tests" --claim` |
| `claim` | `task.py claim '<ID>' [--backlog-path <path>]` | Provisions branch `claim/<clean_id>` from base and a dedicated worktree; sets status to `In Progress`. | `python task.py claim '#001'` |
| `adopt` | `task.py adopt '<ID>'` | Prints the worktree directory path of an active claim. | `python task.py adopt '#001'` |
| `close` | `task.py close '<ID>' --outcome "<summary>"` | Syncs base, sets `Closed` and `Resolved`, appends outcome, runs pre-merge check, merges `--no-ff` into base, and deletes worktree and claim branch. Run from main tree. | `python task.py close '#001' --outcome "Implemented and verified"` |
| `abandon` | `task.py abandon '<ID>' [--force]` | Releases a claim without merging. Refuses if the branch has unmerged commits unless `--force` is given (prints tip hash and restore command). | `python task.py abandon '#001' --force` |
| `reject` | `task.py reject '<ID>' --reason "<why>"` | Rejects an open item, sets `Rejected` and `Resolved`, moves it to Icebox/`closed/`, and notes open dependents. Run from main tree. | `python task.py reject '#001' --reason "Approach infeasible"` |
| `cancel` | `task.py cancel '<ID>' --reason "<why>"` | Cancels an open item, sets `Cancelled` and `Resolved`, moves it to Icebox/`closed/`, and notes open dependents. Run from main tree. | `python task.py cancel '#001' --reason "Superseded by #005"` |
| `amend` | `task.py amend '<ID>' [--note "<text>"] [--priority P1\|P2\|P3]` | Appends a dated note and/or updates priority (requires `--note`). Writes to the claim worktree if claimed, else main tree. | `python task.py amend '#001' --priority P1 --note "Elevated priority"` |
| `list` | `task.py list [--status <S>] [--priority P1\|P2\|P3]` | Displays items (ID, priority, status, created, title) sorted by priority and date. Default status: Open and In Progress. Accepts `--status all` or specific status. | `python task.py list --status Open --priority P1` |
| `next` | `task.py next` | Finds and displays the highest-priority ready item (dependencies closed) with claim instruction, or reports blocked item count. | `python task.py next` |

## 5. Workflow

The standard agent cycle follows four steps:
1. `open`: create the item. Inside a claim worktree, `open` writes and commits directly to that claim worktree so new items merge together with the work that found them. Otherwise, it writes to the primary tree.
2. `claim`: run `claim '<ID>'` from the main tree to provision `claim/<clean_id>` and `<worktree_root>/<clean_id>`.
3. Work in the worktree: develop code, edit files, and make commits inside `<worktree_root>/<clean_id>`.
4. `close`: run `close '<ID>' --outcome "..."` from the main tree.

### Where Each Command Writes
- `open`: inside a claim worktree, writes and commits to that worktree; otherwise writes to the primary tree.
- `claim`: branches from base and commits in the new claim worktree.
- `amend`: writes in the claim worktree if the item is claimed, otherwise in the primary tree.
- `reject` / `cancel`: writes in the primary tree; notes for dependents on active claim branches are committed directly in each dependent's claim worktree (`chore(backlog): note [<ID>]`).
- `close`: writes close metadata in the claim worktree, commits, and merges into the base branch in the primary tree.

### Sync Conflicts on Close
Before closing, `close` merges the base branch into the claim worktree:
- In `single` and `split` layouts, if merge conflicts occur solely on backlog files and the claim branch made no edits to unrelated tasks, `close` automatically resolves the conflict (retaining base tasks plus the claim's own entry and items opened in its worktree).
- If non-backlog files conflict, if unrelated tasks were edited on the branch, or under `folders`, `close` leaves the conflicted files for manual resolution. After resolving and committing the conflict in the worktree, re-running `close` continues cleanly.

## 6. Pre-Merge Check

Inside the merge lock, `close` runs a pre-merge check on what the branch introduced:
- **Blocking: new duplicate IDs**: Counts all IDs across open and closed items at the base tip and claim tip. If an ID appears more than once at the claim tip and more often than at the base tip, `close` halts before merging, lists every copy with its location (`file:line` or item path), and instructs the user to fix the duplicate in the worktree, commit, and re-run `close`. Pre-existing duplicates on base are ignored.
- **Warning: unticked criteria**: If the closing entry at the claim tip has unticked criteria (`- [ ]`) under its Acceptance Criteria heading, `close` prints a non-blocking warning: `Warning: [<ID>] closed with N unticked criteria: #2, #3`. Compact entries have no criteria list and produce no warning.
- No CLI flag bypasses the check. To bypass the tool, edit and merge in git by hand (`convention/backlog` §6).

## 7. What the Tool Never Does

- **Never skips hooks**: all commits run through repository hooks without `--no-verify`. On hook failure, the tool restores written files to their previous content, unstages modified paths, and leaves unrelated files untouched.
- **Never deletes a branch with work on it without `--force`**: `abandon` refuses to delete a claim branch that has unmerged commits unless `--force` is explicitly provided.
- **Never commits files it did not write**: commits stage and commit only the explicit paths modified by the command.
- **Never edits a closed entry**: closed task history is append-only.
- **Never edits a claimed entry from outside its claim**: changes to claimed tasks are routed to their claim worktrees.

## 8. Repositories With Git Folder Outside the Tree

In setups where `.git` is a pointer file referring to an external git directory (such as with `tool/git-dir-relocate`):
- Commands run normally from the primary tree.
- When run from a linked worktree where the primary tree cannot be resolved, commands that require the primary tree refuse and instruct the user to run from the main tree.
- If `GIT_DIR` or `GIT_WORK_TREE` environment variables are set, `claim`, `close`, `abandon`, `reject`, `cancel`, `amend`, and `open --claim` refuse to run, preventing worktree git commands from acting on the wrong directory.

## 9. Known Limits

- **No generated sections**: 0.2 maintains no generated views or task maps.
- **No external trackers**: does not integrate directly with third-party trackers; external trackers manage their own lifecycles.
- **No support for repositories reached solely via `GIT_DIR`/`GIT_WORK_TREE`**: requires a `.git` directory or pointer file in the tree.
- **Test suite duration**: the full test suite is slow (several minutes on Windows).
