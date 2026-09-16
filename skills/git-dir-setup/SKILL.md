---
id: skill/git-dir-setup
version: 0.1.0
status: draft
summary: When and how to keep a git repository's database outside a cloud-synced folder (Google Drive desktop.ini corruption).
applies-to: [vault, codebase]
settings:
  git_dirs_root:
    description: "Folder outside every synced tree that holds relocated git databases"
    default: "C:/git-dirs"
requires: [tool/git-dir-relocate@0.1]
replaces: null
---

# Git database outside synced folders

Use this skill when a git repository lives inside a folder that a file syncer (Google Drive for
Desktop, OneDrive, Dropbox) mirrors. On this machine the git-dirs root is `{{git_dirs_root}}`. The
tool is [[git-dir-relocate]]. In a project that synced it, the script is
`warehouse/tools/git-dir-relocate/git_dir_relocate.py`. Below it is written as `relocate.py`.

## When to use it

**Any of these:**
- You are about to run `git init` or `git clone` inside a synced vault or project folder.
- Git prints `warning: ignoring broken ref refs/.../desktop.ini`.
- `git fetch` fails with `fatal: bad object refs/desktop.ini` (or any `.../desktop.ini`).
- `git fsck` reports `bad sha1 file` entries inside `objects/`.
- `.git` in the project is a **directory** and the folder is synced.

**Not needed** when `.git` is already a pointer file into `{{git_dirs_root}}`. Check with `status`.

## Procedure: existing repository

1. **Check.**
   `python relocate.py status <repo>`
   - `relocated -> ...` means you're done. If it reports marker files inside, run `clean <repo>`.
   - `IN-TREE .git directory` means continue.
2. **Prepare. Ask the user to confirm each point:**
   - Other machines that sync this folder have pushed their work and paused the syncer. The syncer
     will propagate the deletion of `.git/` to them.
   - Obsidian and any git tools on this repository are closed.
   - No merge or rebase is in progress.

   Uncommitted work is safe and stays in place, but **don't commit it just to relocate**. Committing
   belongs to the project's own workflow.
3. **Preview.**
   `python relocate.py relocate <repo> --git-dirs {{git_dirs_root}} --dry-run`
   - Pick `--name` if the folder name is generic or already taken in `{{git_dirs_root}}` (e.g. `AI` →
     `--name AI-Agent-Warehouse`).
   - If it refuses because of linked worktrees, add `--repair-worktrees`.
4. **Relocate.** Run the same command without `--dry-run`.
5. **Read the result.**
   - Exit 0: HEAD, branch, remotes and `git status` are verified unchanged, and `git fsck` is clean.
   - Exit 1: act on each warning. The common one is a sync workflow excluding `.git/**` but not a bare
     `.git` file; add the second exclude.
   - Exit 3: nothing changed. Fix the stated reason and rerun. A reported `git fsck` problem means
     existing damage; tell the user rather than working around it.
   - Exit 4 or 5: **stop, run no further git commands**, and give the user the full output.
6. **Report to the user:** the new database path, the number of marker files removed, and that hooks
   now live in `{{git_dirs_root}}/<name>.git/hooks/` and must be reinstalled on other machines.

## Procedure: new repository

- **New vault or project folder:**
  `python relocate.py init <path> --git-dirs {{git_dirs_root}} --initial-branch main`
- **Cloning into a synced folder:**
  `git clone --separate-git-dir {{git_dirs_root}}/<name>.git <url> <path>`

Never create an in-tree `.git` directory inside a synced folder. It will corrupt.

## Rules

- **Never delete or move a `.git` directory by hand.** Use the tool, which checks and verifies.
- **Never put the git-dirs root inside a synced folder.**
- **Relocating isn't a commit.** The pointer file is ignored by git automatically. Don't create
  commits in someone else's project as part of this.
- **If `git fetch` was already failing before relocation**, the local branch may be behind. After
  relocating, compare `git log -1 origin/<branch>` with `HEAD` and tell the user. Don't reset on
  your own.

## Changelog

See `CHANGELOG.md`.
