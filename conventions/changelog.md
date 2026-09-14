---
id: convention/changelog
version: 0.1.0
status: draft
summary: Keep a Changelog rules for warehouse items — location, headings, categories and breaking changes.
applies-to: [warehouse]
settings: {}
requires: []
replaces: null
---

# Changelog

Every warehouse item keeps a changelog in the [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
format. Version numbers follow [[versioning]]; item layout follows [[warehouse-item]].

## Where it lives

| Item | Location |
|---|---|
| Document (architecture, protocol, convention, template) | a `## Changelog` section at the **bottom** of the file |
| Skill or tool | a `CHANGELOG.md` in the item's folder |

## Heading format

| | In a document | In `CHANGELOG.md` |
|---|---|---|
| Section / title | `## Changelog` | `# Changelog` |
| Unreleased | `### [Unreleased]` | `## [Unreleased]` |
| Version | `### [x.y.z] - YYYY-MM-DD` | `## [x.y.z] - YYYY-MM-DD` |
| Category | `#### Added` | `### Added` |

- **Newest version first**, directly under `[Unreleased]`.
- **Dates** are `YYYY-MM-DD`.
- **`[Unreleased]` is always present**, even when empty. Work in progress collects there until release.
- Only list categories that have entries.

## Categories

| Category | Use for |
|---|---|
| **Added** | New features, sections, settings, commands. |
| **Changed** | Changes to existing behaviour or content. |
| **Deprecated** | Things that still work but will be removed later. |
| **Removed** | Things that are gone. |
| **Fixed** | Bug fixes, typos, broken links, wrong examples. |
| **Security** | Fixes for vulnerabilities or unsafe instructions. |

## Breaking changes

In a MAJOR release, **every** breaking change:
- starts with **`BREAKING:`**;
- is followed by **`**Migration:**`** with the steps a project must take.

```markdown
#### Changed
- **BREAKING:** logs now require a `written_by` field.
  **Migration:** add `written_by:` to existing logs.
```

Breaking changes can sit under any category (usually Changed or Removed).

## What to write

Write for the projects that use the item, not for yourself.

| Good | Bad |
|---|---|
| New optional `tags` field on backlog entries. | Reworked section 3. |
| `add` now fails if the ID already exists instead of overwriting. | Refactored add handler. |
| Clarified that a log is required only for sessions that change files. | Fixed wording. |

- Say what changed for a project and, if it matters, what they need to do.
- One entry per change. Leave out internal edit notes.

## Releasing

> `warehouse release` is Phase 2 and not built yet. Until then, keep changes under `[Unreleased]`.

`warehouse release <id> <major|minor|patch>` will:
1. move everything under `[Unreleased]` into a new dated version heading;
2. bump `version` in the frontmatter;
3. run checks (and tests for tools);
4. commit in the warehouse and create the tag `<id>@<version>`.

The latest releases across all items are also listed in `00_INDEX.md` under "Recent releases".

## Example: document

Bottom of `protocols/session-log.md`:
```markdown
## Changelog

### [Unreleased]

### [2.1.0] - 2026-09-20
#### Added
- Optional "open threads" section for handoffs.
#### Fixed
- Clarified when a log is required.

### [2.0.0] - 2026-09-14
#### Changed
- **BREAKING:** logs now require a `written_by` field.
  **Migration:** add `written_by:` to existing logs.
#### Removed
- The `coordination_state` field.
```

## Example: tool `CHANGELOG.md`

`tools/backlog-cli/CHANGELOG.md`:
```markdown
# Changelog

## [Unreleased]
### Fixed
- `list` no longer crashes on an empty backlog.

## [2.0.0] - 2026-10-02
### Changed
- **BREAKING:** the `add` command is renamed to `new`.
  **Migration:** replace `backlog-cli add` with `backlog-cli new` in scripts and docs.
### Removed
- **BREAKING:** the `--prefix` argument. The prefix now comes from the `task_prefix` setting.
  **Migration:** add `task_prefix:` under `settings` in `.warehouse.yml` and drop `--prefix` from calls.

## [1.1.0] - 2026-09-25
### Added
- `--json` flag for machine-readable output.

## [1.0.0] - 2026-09-20
### Added
- First canonical release: `add`, `list`, `done` commands.
```

## Changelog

### [Unreleased]

### [0.1.0] - 2026-09-14
#### Added
- Initial draft of the changelog convention.
