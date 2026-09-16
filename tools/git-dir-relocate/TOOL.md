---
id: tool/git-dir-relocate
version: 0.1.0
status: draft
summary: Moves a git repository's database out of a cloud-synced folder and leaves a .git pointer file behind.
applies-to: [vault, codebase]
entrypoint: git_dir_relocate.py
requires-software: [python>=3.10, git>=2.20]
platforms: [windows, linux, darwin]
settings: {}
requires: []
replaces: null
---

# `tool/git-dir-relocate`: keep `.git` out of synced folders

File syncers such as **Google Drive for Desktop** write marker files (`desktop.ini`) into every folder
they sync, including `.git/`. Git then breaks:

| Where the marker lands | What git does |
|---|---|
| `.git/refs/...` | reads it as a broken ref: `warning: ignoring broken ref refs/tags/desktop.ini`, and `git fetch` can fail with `fatal: bad object refs/desktop.ini` |
| `.git/objects/xx/` | `git fsck` fails with `bad sha1 file` for each one |

Deleting the files doesn't last, because the syncer writes them into every new ref or object folder.
**The lasting fix** moves the database outside the synced tree and leaves a one-line pointer file:

```
<repo>/.git                     (a file)   gitdir: <git-dirs root>/<name>.git
<git-dirs root>/<name>.git/     (the real repository)
```

The procedure comes from two vaults that fixed this by hand before the tool existed (2026-08-09 and
2026-08-25). This tool packages it with safety checks. Agents use it through [[git-dir-setup]].

---

## 1. Requirements

- **Python** ≥ 3.10 and **git** ≥ 2.20, both on `PATH`.
- **A git-dirs root outside every synced folder.** Pass `--git-dirs <dir>` or set `GIT_DIRS_ROOT`.
  The tool never guesses it. Git Bash style paths (`/c/...`) are accepted on Windows.

## 2. Commands

```bash
# Where does each repository's database live? Any syncer litter inside? (read-only; exit 1 if something needs attention)
python git_dir_relocate.py status <repo> [<repo> ...]

# Move an existing in-tree .git out (preview first)
python git_dir_relocate.py relocate <repo> --git-dirs <git-dirs root> --dry-run
python git_dir_relocate.py relocate <repo> --git-dirs <git-dirs root> [--name NAME]

# Create a brand-new repository with its database outside
python git_dir_relocate.py init <path> --git-dirs <git-dirs root> --initial-branch main

# Delete marker files inside a git dir (relocated or not)
python git_dir_relocate.py clean <repo> [--dry-run]
```

| Flag | Command | Meaning |
|---|---|---|
| `--git-dirs <dir>` | relocate, init | git-dirs root (default: `$GIT_DIRS_ROOT`) |
| `--name <name>` | relocate, init | database is `<root>/<name>.git`; default is the folder name. Letters, digits, `.`, `_`, `-` only |
| `--dry-run` | relocate, clean | print what would happen; change nothing |
| `--repair-worktrees` | relocate | allow linked worktrees and run `git worktree repair` after the move |
| `--gc` | relocate | run `git gc` after moving. It never uses `--prune=now`, so recently unreachable objects (e.g. dropped stashes) are kept |
| `--initial-branch` | init | e.g. `main` |

## 3. Before you run `relocate` on a synced folder

- **Drive also syncs the deletion of `.git/`.** Every other machine syncing this folder loses its
  in-tree `.git`, including any commits there that haven't been pushed. Push from those machines first
  and pause the syncer on them. Afterwards they need the same git-dirs root path, or a fresh clone
  (§5).
- **Close Obsidian and any git tools** (Obsidian Git, IDEs) using the repository. A lock held during
  the move is refused, and a background commit racing the move is unsafe.

## 4. What `relocate` does

**Checks first; any failure refuses with nothing changed (exit 3):**

| Refused when | Why |
|---|---|
| `.git` is a symlink or junction | git would move the link target and leave the repository half-moved |
| the repository is bare, or `<repo>` isn't its top level | the procedure only applies to a normal working tree root |
| `.git` is already a pointer somewhere other than the git-dirs root | it would move twice; "already relocated" under the same root exits 0 |
| the target `<root>/<name>.git` exists, or the root is the repository or inside it | it would collide, or leave the database in the synced tree |
| `core.worktree` or a relative `include.path` is set | they would resolve against the new location and point git at the wrong files |
| a merge/rebase/cherry-pick/revert/bisect is in progress, or any `*.lock` exists in `.git` | the move could capture a half-finished operation |
| `.git/modules` exists (submodules) | submodule pointers are relative; move by hand |
| linked worktrees exist without `--repair-worktrees` | their pointers must be repaired |
| `git fsck` reports problems other than marker files | fix existing damage first so it isn't confused with damage from the move |

**Then:**
1. Records HEAD, branch, all refs, remotes, local config and `git status`, plus a byte copy of
   `.git/config`.
2. Deletes marker files (`desktop.ini`, `Thumbs.db`, `.DS_Store`) inside `.git/`. It doesn't follow
   links, and it never deletes a file whose content is a real ref, even one named `desktop.ini`.
3. Runs `git init --separate-git-dir <target>`, which moves the database and writes the pointer file.
4. Restores the original `config` bytes (reinitialising rewrites values such as
   `core.repositoryformatversion` and `core.filemode`), repairs linked worktrees if requested, and
   deletes any remaining markers.
5. **Verifies** HEAD, branch, refs, remotes, config and `git status` are identical, and that `git fsck`
   is clean. Any difference is exit 4 with instructions, not a warning.
6. Warns if a `.github/workflows` file excludes `.git/**` without a bare `.git` (it no longer matches
   the pointer **file**), or reads exclude/filter files that need checking by hand.

## 5. After relocating

- **Hooks** live in `<root>/<name>.git/hooks/`. They are per-machine, and a clone doesn't carry them.
- **`git worktree list`** shows the database path for the main worktree. That's cosmetic.
- **The pointer file syncs with the folder.** Other machines need the same git-dirs root path, or clone
  with `git clone --separate-git-dir <root>/<name>.git <url> <path>`.

## 6. Exit codes

| Code | Meaning |
|---|---|
| 0 | done (or already relocated) |
| 1 | done, with warnings (read them); for `status`, something needs attention |
| 2 | usage error |
| 3 | refused before changing anything (marker-file deletion aside) |
| 4 | failed after the change began; the printed message says the exact state and what to do |
| 5 | unexpected crash (traceback printed); inspect the repository before running git |

## Changelog

See `CHANGELOG.md`.
