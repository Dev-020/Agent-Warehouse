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
- Commands `reject` and `cancel` (`--reason`) to close tasks that won't be done, moving them to the bottom of the Icebox or `closed/`, and adding notes to any dependent items in the same commit (Decision 29).
- Command `amend` (`--note`, `--priority`) to add dated notes and/or change priority, moving open items to their priority position in single/split layouts, writing to the claim worktree if claimed, and refusing changes on closed items (Decision 30).
- `Item.fields` populates metadata: `severity`, `likelihood`, `depends_on` (list), `parent`, and `resolved`, with normalized IDs (Decision 28).
- `primary_tree` discovery logic, and `doctor` reports `main tree: <path>` or `main tree: unknown from here (run from the main tree)` (Decision 27).
- Command `list` (`--status`, `--priority`) to output tab-separated items sorted by priority, created date, and position/name, with live claim overlay (Decision 31).
- Command `next` to find the highest-priority ready item with claim instructions, or report the count of blocked open items when none are ready (Decision 32).

### Changed
- `close` syncs with base branch before writing the close commit, automatically resolving backlog-only merge conflicts for single and split layouts (Decisions 34, 35).
- While an item is claimed, `reject` and `cancel` route dependent notes to the claim worktree after the main commit rather than editing claimed entries on main (Decision 36).
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
- F1: `close` executed from inside a claim worktree refuses cleanly before touching files, directing the user to run from the primary tree.
- F2: `close` re-run after resolving a sync conflict skips updating the item and creating a duplicate commit when the item is already `Closed`.
- F4: `claim` provisions branches strictly from `<base>` and reads the target item from `<base>` ref without checking out.
- F5: `claim`, `close`, and `abandon` check at start that `refs/heads/<base>` exists, refusing if missing; `abandon` revision logs execute with `check=True`.
- F9: `close` refuses before any write unless the primary tree is checked out on the base branch.
- F14: tool commits carry only the message summary without the `Co-Authored-By` trailer.
- F15: `claim` completion hint quotes the task ID so shell comment characters (`#`) are preserved.
- F3: layout methods return written paths and moves; `safe_commit` restores moved destinations back to sources before restoring bytes on commit failure without deleting moved paths.
- F7: layout file writes preserve the exact file tail (no final newline, one newline, or trailing blank lines).
- F8: layout file reads split lines strictly on `\n` without `str.splitlines()` to avoid mutating unicode line breaks (U+2028, U+0085, form feed).
- F11: section boundaries terminate at the next `## ` heading regardless of name, preventing icebox entries from landing after trailing sections like Findings Register.
- F6: folder frontmatter writes `title` in double quotes with backslash and `"` escaped, quotes strings containing YAML indicator characters, and unescapes on read.
- F10: labels on markdown entry status lines format per convention §4.5 as ``**Labels**: `Bug`, `UI` ``, and reader returns every label.
- F12: items with slugless titles use slug `item` (`<ID>-item.md`), and branch scans recognize `<ID>-`, `<ID>.md`, and `<ID>/` formats so IDs are not re-allocated.
- F13: folder branch scans read frontmatter `id` via `git cat-file --batch`, ensuring imported IDs (`ISS-20260917-slug`) classify as `other` and do not break sequential allocation.
- F16: in repositories whose git folder is outside the tree (`.git` pointer file), commands requiring the primary tree refuse with a clear message when run from linked worktrees where the primary tree is unknown (Decision 27).
- B1: `reject`, `cancel`, and `close` verify folder items are completely clean including untracked files before moving, refusing and naming uncommitted files (Decision 37).
- S1: `primary_tree` resolves `.git` pointer files pointing directly to the common git dir as primary, and prevents external git store directories from being misidentified as worktrees (Decision 38).
- S2: `reject` and `cancel` scan all items across active claim branches to warn about branch-only dependents missing from the primary tree (Decision 39).
- S3: frontmatter parser and updater support YAML block lists for `depends_on` and `labels` (Decision 40).
- S4: commands refuse `\r` and `\n` in single-line values (title, `--criterion`, `--note`, `--reason`, `--outcome`, `--labels`) and refuse leading `#` lines in `--why` and `--wanted` to prevent forged backlog entries (Decision 41).
- N1–N4: `next` excludes claimed items from the blocked count; metadata parser stops at the first non-bold-bullet line; `normalize_id` strips backticks; `list` validates `--status` and `--priority` inputs against allowed values (Decision 42).

### Removed
- Fallback to `BACKLOG/Open.md` when `BACKLOG.md` is missing (a project sets `backlog_layout`).
- Legacy `- [ ] **ID**` heading format in single and split layouts in favor of `### [ID] Title`.
- Placeholder acceptance criterion `[ ] #1 (criterion)` when none provided.
- Stale `status [--write]` reference in `task.py` CLI usage docstring (Decision 33).

## [0.1.0] - 2026-09-15
### Added
- Initial draft of `task.py` backlog CLI supporting atomic worktree claims, section transitions, and multi-agent coordination.
