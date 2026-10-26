# Changelog

## [Unreleased]
### Changed
- Updated §9 command table for `tool/backlog-cli` 0.2: added rows for `reject`, `cancel`, `amend`, `list`, and `next`, quoted task IDs, and updated the manual edit example.

## [0.2.0] - 2026-10-09
### Changed
- **BREAKING:** the skill is now the agent's operating procedure for all four backlog levels (single
  file, split files, item folders, external tracker): orient, choose, claim, record findings, close with
  evidence, review, and propose a change of level. It no longer restates the backlog format.
  **Migration:** none for projects. Agents follow the new steps; the format lives in `convention/backlog`.
- **BREAKING:** requires `convention/backlog@0.2` instead of `tool/backlog-cli@0.1`. The tool is needed
  only under tool-only writing.
  **Migration:** a project that writes through the tool adds `tool/backlog-cli` to its manifest itself.
- Agents don't edit by hand under tool-only writing unless the user allows it. The user may bypass the
  tool.
- Work someone else has In Progress stays theirs unless it is explicitly opened up.

### Added
- Settings `backlog_layout` and `backlog_dir`, with defaults, alongside `backlog_file`.
- A fallback for findings in projects without `protocol/issue-triage`, using the convention's severity,
  likelihood and priority rules.
- Reporting to the named writer, or to the user when there is none, for agents that don't own the
  backlog.

### Removed
- The copies of the convention's sections, entry template, ID formats, priority tiers and evidence rule.

## [0.1.0] - 2026-09-15
### Added
- Initial draft of the `backlog-governance` skill reconciling unified backlog convention and `backlog-cli` tooling.
