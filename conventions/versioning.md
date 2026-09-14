---
id: convention/versioning
version: 0.1.0
status: draft
summary: Semantic Versioning rules for warehouse items — contract, bumps, pins and auto-sync.
applies-to: [warehouse]
settings: {}
requires: []
replaces: null
---

# Versioning

Every warehouse item uses [Semantic Versioning 2.0.0](https://semver.org): `MAJOR.MINOR.PATCH`.
Item format is in [[warehouse-item]]; changelog rules are in [[changelog]].

## The contract

An item's **contract** is anything a project relies on. The version number tells projects whether the
contract changed.

| Kind | Contract |
|---|---|
| convention | the format it defines |
| protocol | the steps it requires |
| template | its structure |
| architecture | the setup and roles it defines |
| skill | its steps, and the tools it requires |
| tool | its commands, arguments, output and behaviour |
| any item | setting names, which settings are required, and `{{placeholders}}` |

## Bumps

| Bump | When | Auto-sync? |
|---|---|---|
| **MAJOR** `3.0.0` | The contract **breaks**: projects must change something to keep working. | **Never.** Reported only. |
| **MINOR** `2.2.0` | Something is **added** without breaking anything. | Yes |
| **PATCH** `2.1.1` | A **fix or clarification** that doesn't change meaning. | Yes |

### Examples

| Bump | Document (`convention/backlog`) | Skill (`skill/latex-pdf`) | Tool (`tool/backlog-cli`) |
|---|---|---|---|
| **MAJOR** | A required field is renamed from `prio` to `priority`. | Now requires `tool/tex-compile@2`; setting `tex_root` renamed to `source_folder`. | `add` command renamed to `new`; output switches from text to JSON. |
| **MINOR** | New optional `tags` field. | New optional step for bibliographies; new setting `bib_style` with a default. | New `--json` flag; existing output unchanged. |
| **PATCH** | Typo fixed; example clarified; broken link fixed. | Instruction reworded, same steps. | Bug fix: crash on empty backlog. |

## Rules

- **New items start at `0.1.0`.** `0.x.y` is draft: anything may change. Drafts aren't synced unless a
  project lists the draft explicitly. Within `0.x.y`, bump MINOR for contract changes and PATCH for
  everything else.
- **An item becomes `1.0.0` when it is canonical.**
- **A released version is never modified.** Every change, however small, gets a new version number.
- **Each release is tagged in git** as `<id>@<version>`, e.g. `protocol/session-log@2.1.0`. Tags are
  the version history, and they let a project pinned to an older version still receive that exact
  content.
- **Every release has a changelog entry** ([[changelog]]). MAJOR entries mark each breaking change
  `BREAKING:` and give migration steps.

## Pins

Projects pin items in `.warehouse.yml`. Skills pin tools in `requires` the same way.

| Pin | Example | Accepts |
|---|---|---|
| `@MAJOR` | `protocol/session-log@2` | MINOR and PATCH updates (any `2.x.x`) |
| `@MAJOR.MINOR` | `convention/backlog@2.3` | PATCH updates only (`2.3.x`) |
| `@MAJOR.MINOR.PATCH` | `tool/backlog-cli@1.4.2` | nothing; frozen |

**Unpinned add:** an item added without a pin is recorded at its current MAJOR (`@<MAJOR>`), so MAJOR
updates are never taken silently.

**Drafts (`0.x.y`) are the exception.** In a draft, a MINOR bump may break the contract. So for `0.x`
versions, **MINOR is treated as MAJOR**:
- An unpinned draft is recorded at `@0.<MINOR>` (e.g. `@0.2`), which accepts PATCH updates only.
- A draft MINOR bump (`0.2.x → 0.3.0`) never auto-syncs. It is taken with `--major`, like any breaking
  update.

## Auto-sync policy

> The sync tool is Phase 2 and not built yet. This is how it will behave.

- **`auto_sync: true`** (the default): MINOR and PATCH releases within the pin are written to the
  project automatically after a warehouse release.
- **`auto_sync: false`**: nothing is written automatically. The project runs `warehouse pull <id>` or
  `warehouse pull --all` to take updates within its pins.
- **MAJOR never auto-syncs, for any item, in any project.** It is reported as "major update available"
  and taken only with `warehouse pull <id> --major`, which shows the `BREAKING:` entries first and then
  moves the pin to the new MAJOR. Migrating the project is the project's job.

## Which bump do I need?

Answer in order. Stop at the first **yes**.

1. Is this the item's first release as canonical? → **`1.0.0`**
2. Would any project using the current version have to change something to keep working? → **MAJOR**
3. Did you rename or remove a setting, placeholder, required field, step, command, argument or
   output, or add a setting **without** a default? → **MAJOR**
4. Does a skill now need a new MAJOR of a tool? → **MAJOR**
5. Did you add something optional (section, setting with a default, command, flag, field)? → **MINOR**
6. Is it a fix, typo, wording change, link fix or bug fix that keeps the meaning and behaviour? → **PATCH**
7. None of the above, or unsure? → treat it as **MAJOR** and ask the owner.

## Changelog

### [Unreleased]
#### Changed
- Adding a setting with a default is MINOR; adding a required setting (no default) is MAJOR.

### [0.1.0] - 2026-09-14
#### Added
- Initial draft of the versioning convention.
