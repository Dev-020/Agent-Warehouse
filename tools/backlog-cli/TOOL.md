---
id: tool/backlog-cli
version: 0.1.0
status: draft
summary: CLI backlog manager with atomic git worktree claims, ID allocation, and structured sections.
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

A command-line task manager implementing the [[worktree-claims]] concurrency protocol and [[backlog]]
specification. Provides atomic git worktree provisioning, task ID allocation, lifecycle transitions,
and merge gating across concurrent human and AI agent sessions.

Default project backlog file is tracked in `{{backlog_file}}`.

---

## 1. Prerequisites & Installation

- **Python**: $\ge$ 3.10.
- **Git**: Installed and available on system PATH.

---

## 2. Commands & Workflow

```bash
# Verify environment and configuration
python tools/backlog-cli/task.py doctor [--init]

# Check active claims from git branch refs
python tools/backlog-cli/task.py status

# Open a new task and allocate next sequential ID
python tools/backlog-cli/task.py open "Refactor database client" --prefix DB --priority P1 [--claim]

# Claim an existing open task (allocates git branch claim/<ID> + worktree)
python tools/backlog-cli/task.py claim DB-1

# Adopt an active claim in case of reconnection
python tools/backlog-cli/task.py adopt DB-1

# Close, verify, gate, and merge task into base branch
python tools/backlog-cli/task.py close DB-1 --outcome "Replaced legacy driver with async connection pool"

# Abandon claim without merging
python tools/backlog-cli/task.py abandon DB-1 [--force]
```

---

## 3. Core Commands Reference

| Command | Arguments | Purpose |
|---|---|---|
| `doctor` | `[--init]` | Check backlog path, worktree directory, and git configuration. `--init` configures defaults. |
| `status` | `[--write]` | Inspect all active `claim/*` branch refs, commit counts, idle duration, and stale flags. |
| `open` | `<title> [--prefix P] [--priority P1\|P2\|P3] [--claim]` | Allocate next ID and create a structured task entry under Backlog. |
| `claim` | `<id>` | Atomically create `claim/<id>` branch and dedicated worktree; mark task In Progress. |
| `adopt` | `<id>` | Print worktree directory path of an existing active claim. |
| `close` | `<id> --outcome <text>` | Move task to Completed (append-only), sync base branch, take merge lock, and merge `--no-ff`. |
| `abandon` | `<id> [--force]` | Remove worktree and delete `claim/<id>` branch. Refuses if worktree is dirty unless `--force`. |

---

## 4. Settings & Environment Overrides

- `backlog_file`: Path to the project backlog markdown file (default: `BACKLOG.md`).
- Can also be set via `BACKLOG_FILE` environment variable or git config `backlog.file`.
- Worktree directory defaults to `../worktrees` outside repository root, overridable via `WORKTREE_DIR`
  environment variable or git config `vault.worktreeRoot`.
