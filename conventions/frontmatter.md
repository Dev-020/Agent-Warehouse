---
id: convention/frontmatter
version: 0.1.0
status: draft
summary: Closed-vocabulary YAML frontmatter schema for markdown notes across vaults and projects.
applies-to: [vault, codebase, warehouse]
settings: {}
requires: []
replaces: null
---

# Frontmatter Schema

A standardized YAML frontmatter contract for markdown documentation across vaults and codebases.
Its purpose is to ensure documents and notes remain queryable, machine-readable, and consistent
across projects without arbitrary frontmatter proliferation.

Warehouse item format rules are defined in [[warehouse-item]]. Operating protocols for agents are in
[[agent-protocol]].

## 1. Principles

1. **Closed vocabulary:** Note `type` must come from an explicitly defined, closed set of values.
   Free-form or unconstrained types lead to fragmentation (e.g. `session_log`, `sessionLog`, and
   `Session-Log` becoming three unrelated queries).
2. **Distinct facts use distinct keys:**
   - `created` records when the artifact was originally created.
   - `date` records when an external real-world event occurred (e.g. a meeting or lecture date).
   - `updated` records when the note content was last meaningfully revised.
3. **No mechanical update churn:** Normalizing frontmatter, fixing typos, or repairing links does
   not bump `updated`. The `updated` timestamp indicates meaningful content evolution.
4. **Machine-verifiable schemas:** Where conventions exist, automate their verification (e.g. via
   linters or CI checks) rather than relying on agent memory.

---

## 2. Core Universal Fields

Every tracked markdown note carries these core fields at the top of its YAML frontmatter block:

| Field | Type | Meaning | Example |
|---|---|---|---|
| `type` | string (closed enum) | The kind of note (from the closed vocabulary below). | `type: reference` |
| `created` | string (`YYYY-MM-DD`) | Date when the file was created. | `created: 2026-09-15` |
| `updated` | string (`YYYY-MM-DD`) | Date when note content was last meaningfully modified. | `updated: 2026-09-15` |
| `status` | string | Lifecycle status: `draft`, `active`, `stable`, `canonical`, `deprecated`, or `archived`. | `status: stable` |
| `tags` | list of strings | Classification tags for indexing and discovery. | `tags: [api, authentication]` |
| `summary` | string | Single-line summary of note purpose and scope. | `summary: OAuth token refresh flow.` |

> [!note] Immutability of session logs
> A `session-log` is an immutable historical record of a single working session. Because it is not
> revised post-handoff, it carries `date` (and `created`) rather than an `updated` field.

---

## 3. Closed `type` Vocabulary

Note types are restricted to the following closed set:

| Type | Description | Typical Location |
|---|---|---|
| `concept` | Fundamental concepts, topical explanations, domain theory. | `concepts/`, `wiki/` |
| `session-log` | Agent handoff log or developer work session record. | `AI/session/`, `sessions/` |
| `note` | General atomic note, meeting notes, or raw capture. | `notes/` |
| `index` | Structural maps, directory catalogs, navigation hubs. | `00_INDEX.md`, root |
| `workflow` | Standard operational procedures and recurring playbooks. | `workflows/`, `AI/` |
| `protocol` | Binding operational rules for agents and systems. | `protocols/`, `warehouse/` |
| `convention` | Binding formats, naming standards, and coding conventions. | `conventions/`, `warehouse/` |
| `template` | Boilerplate structures intended to be copied and filled. | `templates/` |
| `architecture` | High-level system architecture, component boundaries, designs. | `architecture/`, `docs/` |
| `reference` | External specifications, cheat sheets, third-party API summaries. | `reference/` |
| `archive` | Preserved historical records, superseded artifacts. | `_archive/` |

---

## 4. Type-Specific Extensions

Certain note types require or support specialized fields alongside the universal set.

### 4.1. Session logs (`type: session-log`)

Session logs document agent activities and cross-session handoffs (see [[session-log]]):

| Field | Required | Description |
|---|---|---|
| `date` | Yes | Date of session (`YYYY-MM-DD`). |
| `audience` | Yes | Usually `agent` or `team`. |
| `written_by` | Yes | Agent engine or developer identifier (e.g. `claude-code`, `antigravity`). |
| `coordination_state` | Optional | Multi-agent coordination state (e.g. `solo`, `pair`, `subagent`). |
| `open_threads` | Optional | Pointers to active investigations or incomplete handoffs. |

### 4.2. Warehouse items (`convention`, `protocol`, `architecture`, `template`)

Items managed by the warehouse must conform to the 8 required warehouse frontmatter keys
specified in [[warehouse-item]]:

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Unique ID formatted as `<kind>/<name>`. |
| `version` | Yes | Semantic version string (e.g. `"0.1.0"`). |
| `status` | Yes | `draft`, `canonical`, or `deprecated`. |
| `summary` | Yes | Single-line catalog summary. |
| `applies-to` | Yes | List of project kinds (e.g. `[vault, codebase]`). |
| `settings` | Yes | Map of configuration parameters, or `{}`. |
| `requires` | Yes | List of dependency pins (e.g. `[tool/tex-compile@1]`), or `[]`. |
| `replaces` | Yes | Prior item ID superseded by this item, or `null`. |

### 4.3. Educational and Course material (in course vaults)

In academic or course-scoped vaults:

| Field | Description |
|---|---|
| `course` | Canonical course folder name (e.g. `MATH162`). |
| `semester` | Academic term (e.g. `2026-2027 1st Sem`). |
| `lecture` | Integer lecture or deck number. |
| `capture_status` | Status of transcription (`transcribed`, `partial`, `pending-materials`). Used instead of `status` to prevent collision with task trackers. |
| `derived_from` | Wikilink to source notes for summaries (prevents silent staleness). |

---

## 5. Prohibited Practices

1. **Unstructured frontmatter proliferation:** Do not invent ad-hoc top-level keys (`my_notes:`,
   `random_flag:`, `misc:`) without formalizing them in this schema.
2. **Casing and separator inconsistencies:** Field names must be lowercase alphanumeric with
   underscores (`[a-z][a-z0-9_]*`) or hyphens where specified by warehouse standard. Never use camelCase
   or PascalCase keys.
3. **Redundant keys:** Do not provide overlapping fields such as `last_modified` alongside `updated`,
   or `author` alongside `written_by`.
4. **Invalid YAML syntax:** Unquoted colons in values (e.g. `summary: Note: check this`) break YAML
   parsers. Strings containing punctuation, colons, or brackets must be quoted.

---

## Changelog

### [Unreleased]

### [0.1.0] - 2026-09-15
#### Added
- Initial draft of the closed-vocabulary frontmatter convention.
