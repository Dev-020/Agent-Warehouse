# Changelog

## [Unreleased]
### Added
- Settings `backlog_layout`, `backlog_file`, and `backlog_dir` read from the project's `.warehouse.yml` manifest.
- `doctor` reports resolved settings (layout, backlog file or folder, worktree root, base branch) with their configuration sources.

### Changed
- Split `task.py` into internal `backlog_cli` package (`gitops`, `settings`, `ids`, `layouts`, `commands`, `model`).
- `doctor --init` sets `vault.worktreeRoot` and creates the directory without writing `backlog.file` to git config.

## [0.1.0] - 2026-09-15
### Added
- Initial draft of `task.py` backlog CLI supporting atomic worktree claims, section transitions, and multi-agent coordination.
