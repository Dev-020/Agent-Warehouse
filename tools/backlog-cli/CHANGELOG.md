# Changelog

## [Unreleased]
### Added
- Settings `backlog_layout`, `backlog_file`, and `backlog_dir` read from the project's `.warehouse.yml` manifest.
- Layout implementations for `single`, `split`, and `folders` (`SingleFileLayout`, `SplitFilesLayout`, `ItemFoldersLayout`).
- CLI options for `task open`: `--new-prefix` to set/switch prefix schemes, repeatable `--criterion` (`-c`), and `--style` (`full` | `compact`).
- Surgical layout editing preserving untouched entries, original line endings (LF/CRLF), and UTF-8 BOMs byte-for-byte.
- Frontmatter parser and surgical updater for `ItemFoldersLayout` with `<ID>-<slug>` naming.
- `doctor` reports resolved settings with their configuration sources, and warns if `split` layout lacks `.gitattributes` `merge=union` for `Closed.md`.
- Task ID allocation across branches: collects IDs across target tree, base branch tip, and all active `claim/*` branches without checkout (Decision 23, D1).
- `abandon` checks for commits on the branch not on base; prints tip hash and restoration instructions under `--force` (Decision 24, D2, S10).
- `doctor` reports git discovery mechanism (`.git folder`, `.git pointer file -> <git dir>`, or `GIT_DIR/GIT_WORK_TREE environment`) (Decision 26).

### Changed
- Split `task.py` into internal `backlog_cli` package (`gitops`, `settings`, `ids`, `layouts`, `commands`, `model`).
- Core commands (`open`, `claim`, `close`, `abandon`, `adopt`, `status`) operate polymorphically across all three layouts.
- `claim` refuses before creating a branch if the target item does not exist or is not `Open`.
- `open` orders new entries in `Backlog (Open Tasks)` by priority (P1 to P3).
- `open` executed from inside a claim worktree writes to the claim worktree rather than the primary tree.
- Backlog modification commits are atomic: failure to commit rolls back disk changes and unstages the index.
- Removed `--no-verify` everywhere; all tool commits execute through `safe_commit` with atomic rollback and index reset on hook failure without disturbing unrelated staged or modified files (Decision 25, D4).
- `close` handles merge failures cleanly: aborts merge on failure, preserves worktree and branch, and leaves sync merge conflicts for manual resolution (Decision 25).
- Worktree lifecycle operations (`claim`, `close`, `abandon`) refuse when `GIT_DIR` or `GIT_WORK_TREE` environment variables are set (Decision 26).
- Commands detect absence of git or repository and stop with standard guidance (Decision 26).
- `Resolved` recorded as its own metadata field (`- **Resolved**: YYYY-MM-DD` or frontmatter `resolved:`) rather than amending the `Outcome` heading.
- `doctor --init` sets `vault.worktreeRoot` and creates the directory without writing `backlog.file` to git config.

### Fixed
- B1: `close` placed `- **Resolved**:` after any line in the entry starting with `- **` (such as in Why); resolved date now strictly appends to the metadata block directly under the heading.
- B2: `append_note` placed new notes after the blank line ending Notes; new notes now append immediately following the last note bullet, preserving one blank line before the next heading.
- B3: `close` in single layout left two blank lines after Outcome; entries and section boundaries are now separated by exactly one blank line.

### Removed
- Fallback to `BACKLOG/Open.md` when `BACKLOG.md` is missing (a project sets `backlog_layout`).
- Legacy `- [ ] **ID**` heading format in single and split layouts in favor of `### [ID] Title`.
- Placeholder acceptance criterion `[ ] #1 (criterion)` when none provided.

## [0.1.0] - 2026-09-15
### Added
- Initial draft of `task.py` backlog CLI supporting atomic worktree claims, section transitions, and multi-agent coordination.
