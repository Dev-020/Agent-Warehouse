---
id: protocol/worktree-claims
version: 0.2.0
status: draft
summary: Multi-agent git worktree claims, reservation semantics, branch claims, atomic locks, merge gate, and conflict avoidance across concurrent sessions.
applies-to: [vault, codebase]
settings: {}
requires: []
replaces: null
---

# Worktree Claims Protocol

A multi-agent concurrency protocol for claiming, isolating, gating, and merging tasks across parallel
agent sessions using native git worktrees.

Reconciled from production multi-agent vault infrastructure (`INF-22`). Companion to [[agent-protocol]],
[[commits]], and [[backlog]].

---

## 1. Core Architectural Principle: The Branch is the Claim

In multi-agent environments, multiple agents or humans work concurrently in the same repository.

> **The branch is the claim.**
> Creating the git branch `claim/<ID>` is a ref-atomic operation governed by git's own internal lockfile.
> If two agents attempt to claim the same task simultaneously, exactly one succeeds; the second receives a
> hard `fatal: a branch named 'claim/<ID>' already exists`.

### Why Shared Markdown Claims Fail
Marking a claim in a shared markdown file (e.g. `- [/] [claim:: Agent]`) governs only the *intent* to work.
Because git commits operate on the **working tree**, multiple concurrent agents sharing a working tree will
interleave uncommitted edits, cross-attribute changes across commits, and risk catastrophic data loss if any
session invokes `git reset --hard` or `git clean -fd`.

Markdown markers remain useful solely as *descriptive indicators* rendered inside an isolated worktree for
editor self-consistency. They are **never the lock**.

---

## 2. Actor Model & Write Permissions

| Actor | Primary Working Tree Writes | Worktree Writes | Merge Path |
|---|---|---|---|
| **Human / Maintainer** | Direct, unconstrained | Direct | Direct git commands or PR review |
| **Autonomous Agent** | **Prohibited** (must use worktrees) | Unconstrained within claimed tree | Automated gate via `task.py close` |
| **Merge Coordinator** | Only under exclusive `merge.lock` | N/A | Fast-forward or reviewed `--no-ff` |

**The Primary Tree Invariant:** No AI agent may make direct, uncommitted modifications to the primary
working tree while tasks are in flight. All active implementation takes place inside an isolated worktree.

---

## 3. Worktree Directory Topology

Where worktrees live depends on what watches or surrounds `<project-root>`:

- **Cloud sync & whole-folder indexers (vaults):** If the project lives inside a synced folder (Google Drive,
  OneDrive, Dropbox) or an Obsidian vault, any directory inside `<project-root>`—even when `.gitignore`d or
  dot-prefixed—is still synced and indexed $N+1$ times. Worktrees **must** live outside the synced tree.
- **Parent monorepos & shared workspaces (codebases):** If `<project-parent>` is itself a git working tree or a
  shared projects directory, a plain `../worktrees/` folder lands inside the parent repo as untracked files and
  can collide on task IDs across sibling repositories.

### 3.1. Supported Topologies

Pick the topology that matches the project's environment:

| Topology | Path Pattern | When to Use | Required Invariants |
|---|---|---|---|
| **External sibling** *(default)* | `<project-parent>/worktrees/<ID>` (or `../worktrees/<repo-name>/<ID>`) | Cloud-synced vaults; standalone repos with an unmonitored parent directory | Must sit outside any cloud-synced folder. Namespace by `<repo-name>` if sibling repos share `<project-parent>`. |
| **External user-local** | e.g. `%LOCALAPPDATA%/<app>/worktrees/<repo-name>/<ID>` | Repos inside a parent monorepo/workspace; orchestrated worker pools | Scope by `<repo-name>` (and run ID if applicable) so separate repos never collide on task IDs. |
| **In-repo dot-directory** | `<project-root>/.worktrees/<ID>` or `<project-root>/.claude/worktrees/<ID>` | Code repos **not** under cloud sync (including subagent harnesses) | 1. **Must be gitignored** (`.gitignore` or `.git/info/exclude`) so primary-tree dirt checks (§4.5 step 4) do not refuse merges.<br>2. **Must be dot-prefixed** (or excluded in `norecursedirs` / linter configs) so `pytest` and linters invoked from `<project-root>` do not collect worktree copies $N+1$ times. |

```
# External topology (vaults & standalone repos)      # In-repo topology (non-synced code repos)
<project-parent>/                                    <project-root>/
├── <project-root>/                                  ├── .git/
│   ├── .git/          # Or .git pointer file        ├── .gitignore         # Ignores .worktrees/ or .claude/worktrees/
│   └── BACKLOG.md                                   ├── BACKLOG.md
└── worktrees/         # Outside synced root         └── .worktrees/        # Dot-prefixed & gitignored
    ├── <ID-1>/        # claim/<ID-1>                    ├── <ID-1>/        # claim/<ID-1>
    └── <ID-2>/        # claim/<ID-2>                    └── <ID-2>/        # claim/<ID-2>
```

---

## 4. Lifecycle Workflow

```
[Backlog Item: Open]
        │
        ▼ (python _tools/task.py claim <ID>)
[Atomic Branch Creation: claim/<ID>]
        │
        ▼ (git worktree add <worktree-dir>/<ID> claim/<ID>)
[Isolated Implementation in Worktree]
        │
        ▼ (commit all changes inside worktree)
[Pre-Merge Sync: git merge master inside worktree]
        │
        ▼ (run test suite / merge gate)
[Verification Gate: PASS]
        │
        ▼ (acquire merge.lock on main tree)
[Atomic Merge: git merge --no-ff claim/<ID>]
        │
        ▼
[Teardown: remove worktree & delete claim branch]
```

### 4.1. Claiming Work (`claim`)
1. Verify task `<ID>` is currently unclaimed in the backlog.
2. Atomically create branch `claim/<ID>` and checkout into `<worktree-root>/<ID>`.
3. If editor-specific configuration (e.g. `.obsidian/` or local IDE settings) is gitignored, copy
   non-volatile configuration into the worktree so tooling functions identically.
4. Mark the task `- [/]` (In Progress) in the worktree's local copy of the backlog and commit immediately.

### 4.2. Working in Isolation
- All edits, dependencies, intermediate builds, and test runs occur strictly inside the worktree directory.
- Other concurrent agents working in parallel worktrees cannot see, overwrite, or revert these files.

### 4.3. Conflict Resolution & Pre-Merge Sync
**Rule: Conflicts are the branch owner's responsibility.**
Before closing, the agent merges `master` (or target branch) into `claim/<ID>` **inside the worktree**:
- If clean: proceeds to verification gate.
- If conflicts arise: the claiming agent resolves the conflict in its own worktree diff where the context is
  fresh. Never resolve branch conflicts directly on `master`.

### 4.4. Verification Gate
The test run required by the project's test plan ([[test-planning]], [[testing]]: no failures that aren't
already in the backlog), along with link validators, syntax linters, and type checkers, must pass before
merge. If the gate fails, the worktree remains open for debugging.

### 4.5. Closing & Atomic Merge (`close`)
1. Ensure the worktree working tree is completely clean (all implementation committed).
2. Update task entry in the backlog: mark closed/resolved with outcome summary. Commit in the worktree.
3. Acquire an exclusive process lockfile (`<gitdir>/merge.lock`). Only one session may merge into the
   primary tree at a time.
4. Verify the primary working tree is clean of untracked and modified files.
5. Execute `git merge --no-ff claim/<ID>` into master.
6. Teardown:
   - Run `close` from **outside** the worktree being deleted (Windows locks open working directories).
   - Remove worktree: `git worktree remove <worktree-path>`.
   - Delete branch: `git branch -d claim/<ID>`.
   - Release `merge.lock`.

### 4.6. Resuming Crashed Sessions (`adopt`)
If an agent crashes or loses connection mid-task:
- The worktree and branch remain untouched on disk.
- A new session runs `adopt <ID>` to locate the existing worktree path and resume execution without loss.

### 4.7. Abandoning Claims (`abandon`)
If a task is cancelled, blocked, or superseded:
- `abandon <ID>` safely removes the worktree and deletes the branch.
- **Safety invariant:** `abandon` must refuse if the worktree contains uncommitted changes unless explicit
  `--force` is passed, preventing accidental destruction of unsaved work.

---

## 5. Ephemeral Chores (Unowned Transports)

Some repository updates have no backlog task (e.g., session log hand-overs, timestamp updates, automated index
refreshes).

- **A chore is a transport, not a record:** Ephemeral branch `chore/<slug>` and worktree.
- Chores are never assigned backlog IDs.
- They merge with a concise commit message (`chore: <description>`) and delete immediately.
- When an agent *is* executing a backlog task, session logs belong inside that task's worktree and merge with it.

---

## 6. Critical Platform Invariants & Concurrency Gotchas

1. **Content Dirt vs Byte Dirt (CRLF Normalization):**
   On Windows with `core.autocrlf=true`, byte comparisons (`git status --porcelain`) report false modifications
   due to line-ending conversions. Tooling must check content-level diffs (`git diff --name-only HEAD` and
   `git ls-files --others --exclude-standard`) before asserting working tree dirt.

2. **Never `git stash` to Clear a Merge Refusal:**
   If a merge into main is refused due to dirty files, those files frequently belong to a concurrent session.
   Stashing pulls another agent's in-progress changes out of the tree. Inspect file provenance before acting.

3. **Windows Directory Locks:**
   Windows prevents deleting any directory that is the current working directory of an active shell or editor.
   Always execute `task close` or teardown commands from the main repository directory, never from inside the
   claimed worktree.

4. **ReadOnly File Attributes:**
   Certain package managers and IDE plugins set Windows `ReadOnly` file attributes. Worktree deletion routines
   must strip `stat.S_IWRITE` before invoking `rmdir` to prevent orphaned partial trees.

5. **Reflog vs Commit Timestamps:**
   To calculate claim age and detect stale claims, read the reflog creation timestamp. `git log -1` on a freshly
   branched claim returns the parent commit's timestamp, which could be days or weeks old.

---

## Changelog

### [Unreleased]

### [0.2.0] - 2026-11-08
#### Changed
- §4.4 (Verification Gate): the test requirement points to the project's test plan ([[test-planning]], [[testing]]).

### [0.1.2] - 2026-10-17
#### Changed
- Wording: "handoff" is now "hand-over" (state passed between sessions), matching
  `protocol/phased-implementation`'s terms. No rule changed.

### [0.1.1] - 2026-09-26
#### Changed
- Clarified worktree location drivers in §3 (cloud-synced vaults vs parent monorepos/codebases) and documented the three supported topologies (external sibling, external user-local, and gitignored dot-prefixed in-repo directories such as `.worktrees/` or `.claude/worktrees/`) with their dirt-check and test-discovery invariants.

### [0.1.0] - 2026-09-15
#### Added
- Initial draft of the worktree claims protocol.
