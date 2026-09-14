# AI Agent Warehouse

One master copy of every reusable agentic item: architectures, protocols, conventions, templates,
skills and tools. Items are versioned here, projects pick the ones they want, and new releases reach
those projects without anyone hand-copying files.

It is an Obsidian vault and a git repo (private remote on GitHub).

## Folder map

```
AI/
├── 00_INDEX.md          catalog: every item, version, summary, what projects it fits
├── README.md            this file
├── AGENTS.md / CLAUDE.md  rules for agents working on the warehouse itself
│
├── architecture/        system designs (Codebuff foundation, multi-agent setups)
├── protocols/           procedures (session logs, working memory, research discipline …)
├── conventions/         formats and standards (backlog, frontmatter, commits, naming)
├── templates/           starting points, copied once
├── skills/              <name>/SKILL.md + private helper scripts/assets + CHANGELOG.md
├── tools/               <name>/TOOL.md + code + tests/ + CHANGELOG.md
├── case-studies/        project-specific workflows kept as reference, never synced
├── reference/           research and audits, never synced
│
├── _tools/warehouse.py  the sync tool (Phase 2 — not built yet)
├── _registry/projects.md  GENERATED: which projects use which items at which version
└── _archive/            retired items and old notes
```

## Item kinds

| Kind | Folder | Form | What happens to it |
|---|---|---|---|
| architecture | `architecture/` | single file | synced |
| protocol | `protocols/` | single file | synced |
| convention | `conventions/` | single file | synced |
| skill | `skills/<name>/` | folder with `SKILL.md` | synced |
| tool | `tools/<name>/` | folder with `TOOL.md` | synced (tests stay here) |
| template | `templates/` | single file | copied once, then the project owns it |
| case study | `case-studies/` | note | never leaves the warehouse |
| reference | `reference/` | note | never leaves the warehouse |

Every item's format is defined in [[warehouse-item]].

## How a project uses it

1. **Manifest.** The project has a `.warehouse.yml` at its root, which the project commits:
   ```yaml
   auto_sync: true            # default; false = the project pulls updates itself
   target: warehouse/         # where synced items land
   items:
     - protocol/session-log@2 # any 2.x.x
     - convention/backlog@2.3 # 2.3.x only
     - tool/backlog-cli@1.4.2 # exactly this version
   settings:
     session_folder: AI/session
   ```
2. **Items land in the project's `warehouse/` folder**, each with a header saying it is a warehouse
   item, plus a `warehouse/README.md` listing the items and their versions. `{{placeholders}}` in the
   items are filled from `settings`. A generated `.warehouse.lock` records what was written.
3. **Updates arrive according to `auto_sync` and pins.**
   - `auto_sync: true`: MINOR and PATCH releases within the pin are written automatically after a
     warehouse release.
   - `auto_sync: false`: nothing is written until the project pulls.
   - MAJOR releases never arrive on their own, in any project. They are pulled with `--major`.
   - A synced copy that was edited locally is never overwritten; it is skipped and reported.
4. **The warehouse never commits in a project.** Synced changes are left as uncommitted edits for the
   project's owner.

## Standards

**Versioning.** Every item uses Semantic Versioning (`MAJOR.MINOR.PATCH`). MAJOR means the item's
contract broke, MINOR means something was added, PATCH is a fix or clarification. New items start at
`0.1.0` (draft); released versions are never modified; each release is tagged `<id>@<version>`.
Details: [[versioning]].

**Changelog.** Every item keeps a Keep a Changelog 1.1.0 changelog: a `## Changelog` section at the
bottom of a document, or a `CHANGELOG.md` in a skill or tool folder. Work collects under
`[Unreleased]` until release; breaking changes are marked `BREAKING:` with migration steps.
Details: [[changelog]].

## Commands

> **Phase 2 — not built yet.** `_tools/warehouse.py` does not exist. This is the planned command set.

| Command | Purpose |
|---|---|
| `warehouse sync [--auto] [project]` | Propagate releases to projects |
| `warehouse status` | Current vs available versions for this project, with changelog entries |
| `warehouse pull <id> \| --all [--major]` | Manual update; `--major` required for MAJOR |
| `warehouse add <id>[@pin]` / `remove <id>` | Change the manifest, then pull or delete (incl. required tools) |
| `warehouse template <id> <dest>` | One-time template copy |
| `warehouse bootstrap` | Propose a manifest for a new project (user approves first) |
| `warehouse release <id> <major\|minor\|patch>` | Bump version, finalize changelog, run checks and tests, commit, tag |
| `warehouse check` | Read-only health report across projects |
| `warehouse discard` / `promote` / `detach <id>` | Resolve local edits to synced copies |
| `warehouse impact <id>` | List projects that use an item and their pins |
| `warehouse registry` | Regenerate `_registry/projects.md` |
| `warehouse index` | Regenerate `00_INDEX.md` |

## Status

**Phase 2 of 5: The tool.** Batch 1 of `_tools/warehouse.py` is built and under review; batch 2
(`promote`, `discard`, `detach`, `template`, `bootstrap`) is next. The three standards are drafted as
items in `conventions/`. Old notes live in `reference/` (legacy architecture notes in
`reference/legacy-architecture/`) and `_archive/`. No items are released yet and nothing syncs.

| Phase | What |
|---|---|
| 1. Foundation | Repo, folders, these docs, the standards as items ← **now** |
| 2. The tool | `_tools/warehouse.py` and its tests |
| 3. First items | Reconcile the first batch into `1.0.0` releases |
| 4. Pilot projects | doc-scanner, GRIP, COLLEGE |
| 5. Roll out | Remaining projects, one at a time |

Full plan: [[warehouse-architecture]]. Catalog: [[00_INDEX]].
