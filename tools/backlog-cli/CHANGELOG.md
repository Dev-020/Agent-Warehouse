# Changelog

## [Unreleased]
### Added
- Settings `backlog_layout`, `backlog_file`, and `backlog_dir` read from the project's `.warehouse.yml` manifest.
- Layout implementations for `single`, `split`, and `folders` (`SingleFileLayout`, `SplitFilesLayout`, `ItemFoldersLayout`).
- CLI options for `task open`: `--new-prefix` to set/switch prefix schemes, repeatable `--criterion` (`-c`), and `--style` (`full` | `compact`).
- Surgical layout editing preserving untouched entries, original line endings (LF/CRLF), and UTF-8 BOMs byte-for-byte.
- Frontmatter parser and surgical updater for `ItemFoldersLayout` with `<ID>-<slug>` naming.
- `doctor` reports resolved settings with their configuration sources, and warns if `split` layout lacks `.gitattributes` `merge=union` for `Closed.md`.

### Changed
- Split `task.py` into internal `backlog_cli` package (`gitops`, `settings`, `ids`, `layouts`, `commands`, `model`).
- Core commands (`open`, `claim`, `close`, `abandon`, `adopt`, `status`) operate polymorphically across all three layouts.
- `claim` refuses before creating a branch if the target item does not exist or is not `Open`.
- `open` orders new entries in `Backlog (Open Tasks)` by priority (P1 to P5).
- `open` executed from inside a claim worktree writes to the claim worktree rather than the primary tree.
- Backlog modification commits are atomic: failure to commit rolls back disk changes and unstages the index.
- `Resolved` recorded as its own metadata field (`- **Resolved**: YYYY-MM-DD` or frontmatter `resolved:`) rather than amending the `Outcome` heading.
- `doctor --init` sets `vault.worktreeRoot` and creates the directory without writing `backlog.file` to git config.

### Removed
- Fallback to `BACKLOG/Open.md` when `BACKLOG.md` is missing (a project sets `backlog_layout`).
- Legacy `- [ ] **ID**` heading format in single and split layouts in favor of `### [ID] Title`.
- Placeholder acceptance criterion `[ ] #1 (criterion)` when none provided.

## [0.1.0] - 2026-09-15
### Added
- Initial draft of `task.py` backlog CLI supporting atomic worktree claims, section transitions, and multi-agent coordination.
