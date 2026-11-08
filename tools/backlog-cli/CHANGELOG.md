# Changelog

## [Unreleased]

### Changed
- The test suite builds its start state directly via fixtures and seeds instead of CLI arrangement, and runs in 260 s instead of 344 s (182 tests). Pure unit tests are un-marked and run in under 1 s with `-m "not medium"`, while integration tests are marked `medium`. No tool code or behaviour changed.

## [0.2.0] - 2026-10-26
### Added
- Settings `backlog_layout`, `backlog_file`, and `backlog_dir` read from the project's `.warehouse.yml` manifest.
- Support for `split` (`Open.md`, `Closed.md`) and `folders` (`open/`, `closed/`) backlog layouts alongside `single` file across all commands.
- Commands `reject` and `cancel` (`--reason`) to close open tasks to the Icebox or `closed/`, recording notes on dependent items.
- Command `amend` (`--note`, `--priority`) to append dated notes or update priority on open and claimed items.
- Command `list` (`--status`, `--priority`) to display backlog items with status and live claim overlay.
- Command `next` to find the highest-priority ready item with claim instructions, or report blocked open item count.
- Pre-merge check in `close`: blocks on new duplicate IDs introduced by the branch (naming every copy across files or item paths), and warns on unticked acceptance criteria for full entries.
- CLI options for `open`: repeatable `--criterion`, `--style` (`full` | `compact`), and `--new-prefix`.
- `doctor` reports git discovery mechanism, main tree path, resolved settings, and warns if `split` layout lacks `.gitattributes` union merge for `Closed.md`.

### Changed
- **BREAKING:** `open` no longer defaults `--prefix` to `TASK`; it infers the prefix from existing IDs or requires `--prefix`.
  **Migration:** pass `--prefix <P>` (and `--new-prefix` if introducing a new prefix) when opening items in a fresh or multi-prefix backlog.
- **BREAKING:** `doctor --init` no longer writes `backlog.file` to git config.
  **Migration:** set `backlog_file` under `settings` in `.warehouse.yml` if using a non-default backlog file.
- **BREAKING:** commit messages created by the tool now use conventional `chore(backlog): <verb> [ID] ...` format.
  **Migration:** update any external scripts or hooks that parse the tool's commit message format.
- **BREAKING:** `close` refuses to run from inside its claim worktree.
  **Migration:** run `task.py close` from the primary repository tree.
- **BREAKING:** `claim` refuses an ID that is not an Open item on the base branch.
  **Migration:** open the item first, or claim it by its exact ID.
- `claim` branches from the base branch (0.1.0 branched from HEAD).
- `close` refuses unless the primary tree is on the base branch, and checks both trees for uncommitted changes.
- `close` syncs the base branch before writing the close commit, automatically resolving backlog-only merge conflicts for single and split layouts.
- `open` places new items in `Backlog (Open Tasks)` by priority order rather than at the top.
- `open` executed inside a claim worktree writes and commits directly to that claim worktree.
- While an item is claimed, notes from `reject`, `cancel`, and `amend` are routed to the claim worktree.
- Worktree lifecycle and task mutation operations (`claim`, `close`, `abandon`, `reject`, `cancel`, `amend`, `open --claim`) refuse when `GIT_DIR` or `GIT_WORK_TREE` environment variables are set.

### Removed
- **BREAKING:** the automatic fallback to `BACKLOG/Open.md` when `BACKLOG.md` is missing is removed.
  **Migration:** configure `backlog_layout: split` and `backlog_dir` in `.warehouse.yml`.
- **BREAKING:** the legacy `- [ ] **ID**` entry heading format is no longer read; entries must use `### [ID] Title`.
  **Migration:** convert any legacy `- [ ] **ID**` headings to `### [ID] Title`.
- Placeholder criterion `[ ] #1 (criterion)` when none is provided.
- Stale `status [--write]` reference from usage docstring.

### Fixed
- `claim --backlog-path` creates and configures the worktree using the specified backlog path.
- Task ID allocation checks active `claim/*` branches and base branch tip in addition to the target tree so parallel claims never receive duplicate IDs.
- `abandon` checks for unmerged commits on the claim branch; refuses deletion without `--force` and outputs tip hash with restoration instructions.
- `open` no longer ignores failed commits; all tool commits execute atomically and roll back disk modifications and staged paths on hook failure.
- Removed `--no-verify` from `claim` and `close` commits; all commits run repository hooks.
- `close` records `Resolved` as its own metadata field (`- **Resolved**: YYYY-MM-DD` or frontmatter `resolved:`) rather than appending to the Status line.
- Surgical layout editing preserves untouched entries, original line endings (LF/CRLF), and UTF-8 BOM byte-for-byte.
- Clean refusals and standard guidance when running outside a git repository or without git on `PATH`.
- In repositories with an external git directory (`.git` pointer file), commands requiring the primary tree refuse when run from linked worktrees where the main tree cannot be determined.

## [0.1.0] - 2026-09-15
### Added
- Initial draft of `task.py` backlog CLI supporting atomic worktree claims, section transitions, and multi-agent coordination.
