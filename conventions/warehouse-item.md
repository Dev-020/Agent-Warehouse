---
id: convention/warehouse-item
version: 0.1.0
status: draft
summary: The format every warehouse item follows — kinds, folders, frontmatter, placeholders and status.
applies-to: [warehouse]
settings: {}
requires: []
replaces: null
---

# Warehouse item format

Every item in the warehouse follows this format. Versioning rules are in [[versioning]]; changelog
rules are in [[changelog]].

## Item kinds

| Kind | Folder | Form | ID example |
|---|---|---|---|
| architecture | `architecture/` | single file | `architecture/codebuff-orchestration` |
| protocol | `protocols/` | single file | `protocol/session-log` |
| convention | `conventions/` | single file | `convention/backlog` |
| template | `templates/` | single file | `template/plan-document` |
| skill | `skills/<name>/` | folder | `skill/latex-pdf` |
| tool | `tools/<name>/` | folder | `tool/tex-compile` |

The ID is `<kind>/<name>`. The kind is singular; the folder is plural. `<name>` matches the file name
(without `.md`) or the folder name.

`case-studies/` and `reference/` hold notes, not items. They have no item frontmatter and are never synced.

## Single-file items and folder items

**Documents** (architecture, protocol, convention, template) are one markdown file:
- frontmatter at the top;
- `## Changelog` at the bottom.

**Skills** are a folder:
```
skills/latex-pdf/
├── SKILL.md        frontmatter + instructions
├── CHANGELOG.md
└── helpers…        private scripts or assets used only by this skill
```

**Tools** are a folder:
```
tools/tex-compile/
├── TOOL.md         frontmatter + usage
├── CHANGELOG.md
├── <code>          the entrypoint and any modules
└── tests/          stays in the warehouse; never synced
```

**Where a script goes:**
- In **`tools/`** if it works on its own or more than one skill uses it.
- In the **skill's folder** only if it is a small helper that means nothing outside that one skill.

## Frontmatter

Documents carry it at the top of the file. Skills carry it in `SKILL.md`, tools in `TOOL.md`.

| Field | Required? | Meaning | Example |
|---|---|---|---|
| `id` | yes | Stable identity. Never changes. | `protocol/session-log` |
| `version` | yes | Semantic version, see [[versioning]]. | `2.1.0` |
| `status` | yes | `draft`, `canonical` or `deprecated`. | `canonical` |
| `summary` | yes | One line saying what the item is for. Shown in the catalog. | `How and when agents write session logs.` |
| `applies-to` | yes | Kinds of project the item fits. Used by the catalog to suggest items. | `[vault, codebase]` |
| `settings` | yes | Per-project values the item needs: name → description. `{}` if none. | `session_folder: "Folder where session logs live (e.g. AI/session)"` |
| `requires` | yes | Other items this one depends on, with pins. `[]` if none. | `[tool/tex-compile@1]` |
| `replaces` | yes | ID this item supersedes, or `null`. | `null` |
| `entrypoint` | tools only | The file to run. | `compile.py` |
| `requires-software` | tools only | Software that must be installed. | `[python>=3.11, tectonic]` |
| `platforms` | tools only | Platforms the tool supports. | `[windows, linux]` |

## Dependencies (`requires`)

A skill declares the tools it needs in `requires`, using the pin syntax from [[versioning]]:

| Entry | Accepts |
|---|---|
| `tool/tex-compile@1` | any compatible `1.x.x` |
| `tool/tex-compile@1.4` | `1.4.x` only |
| `tool/tex-compile@1.4.2` | exactly `1.4.2` |

- Adding a skill to a project pulls its required tools.
- Removing a skill offers to remove tools nothing else in the project uses.
- If a skill needs a newer MAJOR of a tool than the project has, the skill is reported as blocked
  until the project pulls that MAJOR.

## Settings and placeholders

- Project-specific values in the body are written as `{{name}}`, e.g. `{{session_folder}}`.
- Every placeholder used in the body must be declared under `settings`, with a description.
- Each project fills the values in its `.warehouse.yml` under `settings`.
- Never hard-code a project-specific path, prefix or name in an item. Make it a setting.
- Tools read settings from the manifest or a project-owned config file. They never hard-code them.
- Renaming or removing a setting changes the contract (MAJOR, see [[versioning]]).

## Status lifecycle

```
draft (0.x.y)  →  canonical (1.0.0+)  →  deprecated
```

| Status | Meaning |
|---|---|
| `draft` | Version `0.x.y`. Anything may change. Not synced unless a project lists it explicitly. |
| `canonical` | Version `1.0.0` or later. Normal SemVer guarantees apply. |
| `deprecated` | Still available, but projects using it are warned. It should name its replacement. |

- A replacement item sets `replaces: <old id>`.
- A deprecated item moves to `_archive/` once no project uses it. Items are never deleted outright.

## What authors should know about synced copies

This is for information. The sync tool (Phase 2, not built yet) produces it; authors don't write it.

Each synced file in a project starts with this header:
```markdown
> [!info] Warehouse item — protocol/session-log v2.1.0 (synced 2026-09-20)
> Maintained in the AI warehouse. Edit it there, or run `warehouse promote <id>` to send a change upstream.
```

A project that uses items looks like this:
```
<project>/warehouse/
├── README.md                    notice + table of items and their versions
├── session-log.md               synced copy (header above; changelog at the bottom)
├── working-memory.md
├── backlog.md
├── skills/latex-pdf/            SKILL.md + CHANGELOG.md + helpers
└── tools/tex-compile/           TOOL.md + CHANGELOG.md + code (tests stay in the warehouse)
<project>/.warehouse.lock        GENERATED: item → version → fingerprint of what was written
```

So: write items so they still make sense as a standalone file in someone else's project, with
`{{placeholders}}` filled in.

## Example: a minimal document item

`protocols/session-log.md`:
```markdown
---
id: protocol/session-log
version: 0.1.0
status: draft
summary: How and when agents write session logs.
applies-to: [vault, codebase]
settings:
  session_folder: "Folder where session logs live (e.g. AI/session)"
requires: []
replaces: null
---

# Session log

Write a log in `{{session_folder}}` at the end of every working session.

## Changelog

### [Unreleased]

### [0.1.0] - 2026-09-14
#### Added
- Initial draft of the session log protocol.
```

## Changelog

### [Unreleased]

### [0.1.0] - 2026-09-14
#### Added
- Initial draft of the warehouse item format.
