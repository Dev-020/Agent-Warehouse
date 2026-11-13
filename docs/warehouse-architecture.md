---
type: plan
topic: warehouse-architecture
created: 2026-09-13
updated: 2026-09-14
status: draft, awaiting approval
tags: [plan, architecture, propagation, versioning]
---

# Warehouse Architecture

> **Background:** [[workspace-audit]] (what exists across projects and where it drifted) ·
> [[backlog-comparison]] · [[agentic-landscape]]

## Context

**Problem.** The same agentic workflows, protocols, conventions, skills and tools are hand-copied into
many projects, and the copies drift. `Obsidian_As_Working_Memory.md`, for example, now exists in 3
versions across 9 projects ([[workspace-audit]] §4).

**Goal.** Keep one master copy of each item in this warehouse. Projects choose the items they use, and
changes here reach every project that uses them.

**The warehouse is responsible for:**
1. How the warehouse is structured.
2. What goes into it.
3. How items are managed and versioned.
4. How projects choose and pull items.
5. How updates propagate to projects.

**Out of scope:** deciding or wiring how a project's agents load context (hooks, `@imports`,
session-start behaviour, how its instruction files are connected). Each project decides that. The only
agent-facing duty is a notice saying the project uses warehouse items and that they may be updated.

**In scope:** optional items that offer a practice for organizing or finding context, such as a
codemap, an active-context folder or working-memory notes. Like every item, a project uses one only if
it pulls it. (Clarified 2026-11-12: the original wording read as banning such items. It was meant to
stop the warehouse from dictating context loading.)

**Decisions (2026-09-13/14):**
- **Codebuff** is the architectural foundation, adapted to our environment.
- **The warehouse is a git repo with a private GitHub remote.**
- **Sync runs automatically** when the warehouse commits, and **manually** on demand.
- **Each project has an `auto_sync` setting, default `true`,** that works like software auto-update.
  Projects with it off pull updates themselves and may keep older versions. Per-item auto-sync
  granularity is deferred until real cases need it.
- **The warehouse never commits in any project.** Synced changes are left uncommitted for the project's
  owner or agents.
- **Tools are warehouse items.** They can stand alone or be required by skills.
- **Every item uses Semantic Versioning** (`MAJOR.MINOR.PATCH`) and a **Keep a Changelog** changelog.
  The changelog lives at the bottom of each document, or in `CHANGELOG.md` for folder items (option A).
- **MAJOR updates never auto-sync, for any item.** Projects pull them and handle the migration
  themselves.

---

## 1. Warehouse structure

```
AI/                               git repo · Obsidian vault
├── 00_INDEX.md                   catalog: every item, version, summary, what projects it fits
├── README.md                     how to use the warehouse (humans)
├── AGENTS.md / CLAUDE.md         rules for agents working ON the warehouse itself
│
├── architecture/                 system designs (Codebuff foundation, multi-agent setups)
├── protocols/                    procedures (session logs, working memory, research discipline …)
├── conventions/                  formats and standards (backlog, frontmatter, commits, naming)
├── templates/                    starting points, copied once
├── skills/                       <name>/SKILL.md + private helper scripts/assets + CHANGELOG.md
├── tools/                        <name>/TOOL.md + code + tests/ + CHANGELOG.md
├── case-studies/                 project-specific workflows kept as reference, never synced
├── reference/                    research and audits, never synced
│
├── _tools/warehouse.py           the sync tool itself
├── _registry/projects.md         GENERATED: which projects use which items at which version
└── _archive/                     retired items and old notes
```

- **Synced:** items in `architecture/`, `protocols/`, `conventions/`, `skills/` and `tools/`.
- **Copied once, then owned by the project:** `templates/`.
- **Stays in the warehouse:** `case-studies/` and `reference/`.
- **Where a script goes:**
  - It lives in **`tools/`** if it works on its own or is used by more than one skill.
  - It stays in the **skill's own folder** only if it's a small helper that means nothing outside that
    one skill.

---

## 2. What goes in (first batch)

These come from [[workspace-audit]] §5. Where drifted versions exist, they are reconciled into one
canonical version, which starts at `1.0.0`.

| Item | Kind | Sources to reconcile |
|---|---|---|
| codebuff-orchestration | architecture | all notes in `reference/legacy-architecture/`: `shared-agent-architecture.md`, `multi-agent-setup-readme.md`, `claude-code-setup.md`, `antigravity-setup.md`, `dual-agent-workflow.md` |
| working-memory | protocol | the 3 versions of `Obsidian_As_Working_Memory.md` |
| session-log | protocol | FACTORIO `_sessions/00_SESSIONS.md`, MONEY `Session_Logs_Workflow.md`, COLLEGE/GRIP logs |
| agent-protocol | protocol | COLLEGE / GRIP / discord-bot `00_AGENT_PROTOCOL.md` |
| research-discipline | protocol | FACTORIO `Research Discipline.md` |
| safe-write | protocol | GRIP protocol §3 |
| worktree-claims | protocol | FACTORIO `Worktree Protocol.md` |
| backlog | convention | [[backlog-comparison]] recommendations |
| frontmatter | convention | COLLEGE `Frontmatter_Schema.md` |
| commits | convention | `post-change-commit.md` variants |
| plan-document | template | discord-bot `docs/*-PLAN.md` structure |
| latex-pdf | skill | COLLEGE `LaTeX_PDF_Compilation_Workflow.md` (requires tool/tex-compile) |
| backlog-governance | skill | minecraft/dnd skill, rewritten to match the backlog convention (requires tool/backlog-cli) |
| tex-compile | tool | COLLEGE LaTeX workflow (Tectonic), turned into a script |
| backlog-cli | tool | FACTORIO `_tools/task.py`, generalized (prefixes and paths move to settings) |
| protocol-drift-check | tool | discord-bot `scripts/check-protocol-drift.ps1`, generalized. **Deferred 2026-09-16** until use cases from several projects are found (`warehouse check` already covers drift of synced copies). |

---

## 3. Item format, versioning and management

### 3.1 Frontmatter on every item
Documents carry it at the top of the file. Skills carry it in `SKILL.md`, tools in `TOOL.md`.
```yaml
---
id: protocol/session-log      # stable identity; never changes
version: 2.1.0                # Semantic Versioning (§3.2)
status: canonical             # draft | canonical | deprecated
summary: How and when agents write session logs.
applies-to: [vault, codebase] # used by the catalog to suggest items
settings:                     # per-project values the item needs
  session_folder: "Folder where session logs live (e.g. AI/session)"
requires: []                  # other items this one depends on, e.g. [tool/tex-compile@1]
replaces: null                # id this item supersedes, if any
---
```
**Tools add:**
- `entrypoint`: the file to run;
- `requires-software`: e.g. `python>=3.11`, `git`, `tectonic`;
- `platforms`: e.g. `[windows, linux]`.

**Placeholders.** Project-specific values in the body are written as `{{session_folder}}` and filled in
from each project's manifest. That removes the most common reason copies got forked by hand. For tools,
settings are read from the manifest or a project-owned config file and are never hard-coded.
A setting may declare a default, which projects get when they don't set it:
`log_heading: {description: "Heading of each log", default: "Session log"}`.

### 3.2 Versioning standard: Semantic Versioning 2.0.0 ([semver.org](https://semver.org))
**`MAJOR.MINOR.PATCH`, applied to every item.** An item's **contract** is anything a project relies on:
- the format a convention defines;
- the steps a protocol requires;
- a template's structure;
- setting names and placeholders;
- a tool's commands, arguments, output and behaviour.

| Bump | When | Auto-sync? |
|---|---|---|
| **MAJOR** `3.0.0` | The contract **breaks**: projects must change something to keep working | **Never.** Reported only |
| **MINOR** `2.2.0` | Something is **added** without breaking anything (new optional section, setting, command) | Yes |
| **PATCH** `2.1.1` | A **fix or clarification** that doesn't change meaning (typo, wording, link, bug fix) | Yes |

**Rules:**
- **New items start at `0.1.0`** (draft: anything may change). Drafts aren't synced unless a project
  explicitly lists the draft.
- **An item becomes `1.0.0`** when it is canonical.
- **A released version is never modified.** Every change, however small, gets a new version number.
- **Each release is tagged in git** as `<id>@<version>`, e.g. `protocol/session-log@2.1.0`. Tags are the
  version history, and they let a project pinned to an older version still receive that exact content.

### 3.3 Changelog standard: Keep a Changelog 1.1.0 ([keepachangelog.com](https://keepachangelog.com))
**Location (option A):**
- **Documents:** a `## Changelog` section at the bottom of the document.
- **Skills and tools:** a `CHANGELOG.md` in the item's folder.

**Format:**
```markdown
## Changelog

### [Unreleased]

### [2.1.0] - 2026-09-20
#### Added
- Optional "open threads" section for hand-overs.
#### Fixed
- Clarified when a log is required.

### [2.0.0] - 2026-09-14
#### Changed
- **BREAKING:** logs now require a `written_by` field.
  **Migration:** add `written_by:` to existing logs.
#### Removed
- The `coordination_state` field.
```
- **Categories:** Added · Changed · Deprecated · Removed · Fixed · Security.
- **Dates:** `YYYY-MM-DD`.
- **Order:** newest version first.
- **Unreleased:** work in progress collects under `[Unreleased]` until release.
- **Every MAJOR entry must mark each breaking change `BREAKING:` and give migration steps.**
- **Release command:** `warehouse release <id> <major|minor|patch>`. It moves `[Unreleased]` into a new
  dated version, bumps `version`, runs checks, commits, and creates the git tag.
- **Warehouse-wide log:** `00_INDEX.md` also lists the latest releases across all items.

### 3.4 Skill → tool dependencies
- **A skill declares the tools it needs:** `requires: [tool/tex-compile@1]` means any compatible 1.x.x.
- **Adding a skill** pulls its required tools.
- **Removing a skill** offers to remove tools that nothing else in the project uses.
- **Standalone tools** are added directly.
- **A skill that needs a newer MAJOR of a tool** than the project has is reported as blocked until the
  project pulls that MAJOR version.

### 3.5 Management rules
- **Edit only in the warehouse.** Improvements found inside projects come back through `promote` (§5.4).
- **Release every change** with a SemVer bump and a changelog entry.
- **Tools must pass their tests** before release (`warehouse release` runs them).
- **Deprecate, don't delete.** A deprecated item names its replacement. Projects using it are warned. It
  moves to `_archive/` once no project uses it.
- **Before a MAJOR release,** run `warehouse impact <id>` to see every project affected.
- **`00_INDEX.md` is regenerated** from item frontmatter.

---

## 4. How projects choose and pull items

### 4.1 Manifest: `.warehouse.yml` at the project root (the project commits it)
```yaml
auto_sync: true                  # default true; false = the project pulls updates itself
target: warehouse/               # folder where synced items are placed (project's choice)
items:
  - protocol/session-log@2       # any 2.x.x — gets MINOR/PATCH updates, never 3.0.0
  - protocol/working-memory      # same as @<current MAJOR> at the time it was added
  - convention/backlog@2.3       # 2.3.x only
  - tool/backlog-cli@1.4.2       # exactly this version
settings:
  session_folder: AI/session
  backlog_path: BACKLOG.md
```
**Pin levels:**
- `@MAJOR` accepts MINOR and PATCH updates.
- `@MAJOR.MINOR` accepts PATCH updates only.
- `@MAJOR.MINOR.PATCH` is frozen.

An item added without a pin is recorded at its current MAJOR, so MAJOR updates are never taken silently.
**Drafts are the exception.** For `0.x` versions MINOR is treated as MAJOR: an unpinned draft is recorded
at `@0.<MINOR>`, and a draft MINOR bump never auto-syncs.

### 4.2 What lands in the project
```
<project>/warehouse/
├── README.md                    notice + table of items and their versions
├── session-log.md               synced copy (header below; changelog at the bottom)
├── working-memory.md
├── backlog.md
├── skills/latex-pdf/            SKILL.md + CHANGELOG.md + helpers
└── tools/tex-compile/           TOOL.md + CHANGELOG.md + code (tests stay in the warehouse)
<project>/.warehouse.lock        GENERATED: item → version → fingerprint of what was written
```
Each synced file starts with:
```markdown
> [!info] Warehouse item — protocol/session-log v2.1.0 (synced 2026-09-20)
> Maintained in the AI warehouse. Edit it there, or run `warehouse promote <id>` to send a change upstream.
```
**`warehouse/README.md`** is the one agent-facing notice. It says the project uses warehouse items, lists
them with their versions, and says they may be updated. The warehouse never modifies the project's own
files outside `target`.

### 4.3 Choosing items
- **`00_INDEX.md`:** browse the catalog.
- **`warehouse add <id>[@pin]`:** adds the item to the manifest and pulls it, plus any required tools.
- **`warehouse bootstrap`:** an agent reads the index and the project and *proposes* a manifest. The user
  approves it before anything is written.
- **`warehouse remove <id>`:** removes the item from the manifest and deletes its synced copy.
- **`warehouse template <id> <dest>`:** one-time copy of a template. It isn't tracked afterwards.

---

## 5. Propagation

### 5.1 Auto-sync projects (`auto_sync: true`)
1. An item is released in the warehouse (`warehouse release` commits and tags it).
2. The warehouse repo's **git post-commit hook** runs `warehouse sync --auto`.
3. The tool scans the project roots (`C:\projects\vaults`, `C:\projects\code`) for
   `.warehouse.yml` files. For each auto-sync project using that item:
   - **MINOR or PATCH within the project's pin:** writes the new copy and updates
     `warehouse/README.md` and `.warehouse.lock`.
   - **MAJOR:** writes nothing. The project is reported as "major update available".
   - **Newly required tools** are pulled with the skill, unless that needs a MAJOR tool upgrade the
     project hasn't taken.
4. **Nothing is committed in the project.** Changes appear as uncommitted edits for the project's owner
   or agents.
5. A report lists updated projects, skipped projects, and the reasons.

### 5.2 Manual projects (`auto_sync: false`), and MAJOR updates for everyone
- **Manual projects are never touched by `--auto`.**
- **`warehouse status`** (run in the project) shows each item's current vs available version, split into
  compatible updates and MAJOR updates, with the changelog entries in between.
- **`warehouse pull <id>`** takes the latest version within the pin. **`warehouse pull --all`** does the
  same for every item.
- **`warehouse pull <id> --major`** is the only way to take a MAJOR update, in any project. It first shows
  the `BREAKING:` entries and migration steps, then updates the copy and moves the manifest pin to the
  new MAJOR. Migrating how the project uses the item is the project's job.
- **Pins** keep items on the chosen version level.

### 5.3 Manual trigger for everyone
`warehouse sync [project]` does §5.1 on demand. Use it after adding a new project, or if the post-commit
hook didn't run.

### 5.4 Drift: local edits to synced copies
- **Detection:** before writing, the tool compares the file on disk with its fingerprint in
  `.warehouse.lock`. A mismatch means someone edited the copy locally.
- **A locally edited copy is never overwritten.** It is skipped and reported.
- **The user resolves it with one of three commands:**
  - **`warehouse discard <id>`:** drop the local edit and take the warehouse version.
  - **`warehouse promote <id>`:** bring the local edit into the warehouse master under `[Unreleased]`.
    Once released (with the appropriate SemVer bump), it propagates to everyone.
  - **`warehouse detach <id>`:** stop tracking the item. The copy becomes the project's own file.
- **`warehouse check`** is a read-only report across all projects covering: drift, available compatible
  and MAJOR updates, unfilled settings, deprecated items, and missing tool software.

### 5.5 Other machines and environments
Any environment that clones the warehouse from the private GitHub remote can run `warehouse sync`
against its local projects.

---

## 6. The tool: `_tools/warehouse.py`

| Command | Purpose |
|---|---|
| `sync [--auto] [project]` | Propagate releases (§5.1, §5.3) |
| `status` | Current vs available versions for this project, with changelog entries (§5.2) |
| `pull <id> \| --all [--major]` | Manual update; `--major` required for MAJOR (§5.2) |
| `add <id>[@pin]` / `remove <id>` | Change the manifest, then pull or delete, including tool dependencies |
| `template <id> <dest>` | One-time template copy |
| `bootstrap` | Propose a manifest for a new project |
| `release <id> <major\|minor\|patch>` | Bump the version, finalize the changelog, run checks and tool tests, commit, tag |
| `check` | Read-only health report (§5.4) |
| `discard` / `promote` / `detach <id>` | Resolve drift (§5.4) |
| `impact <id>` | List the projects that use an item and their pins |
| `registry` | Regenerate `_registry/projects.md` |
| `index` | Regenerate `00_INDEX.md` |

**Built-in rules:**
- Writes only to projects' `target` folders and `.warehouse.lock`.
- Never runs git in projects.
- Never overwrites local edits.
- Never auto-applies MAJOR updates.
- Always prints a report.

Python standard library plus PyYAML; pytest test suite.

---

## 7. Build phases

Work is delegated to Codebuff-style roles ([[codebuff-trial-log]]).

### Phase 1: Foundation
- `git init`, `.gitignore` (`.obsidian/workspace.json`, `desktop.ini`), and the private GitHub remote.
  **The user creates the remote repo.**
- Create the §1 folders. Move the existing notes:
  - setup and architecture notes → `reference/legacy-architecture/` (moved out of `architecture/` in
    Phase 2, because that folder is reserved for real items);
  - landscape, audits and source links → `reference/`;
  - `phase-0-findings.md` → `_archive/`;
  - delete `Welcome.md`.
- Write the warehouse's `AGENTS.md` / `CLAUDE.md`, `README.md` and the `00_INDEX.md` skeleton.
- Document the standards as items:
  - `conventions/warehouse-item` (frontmatter, placeholders, folder vs single-file items);
  - `conventions/versioning` (SemVer rules and contract definition, §3.2);
  - `conventions/changelog` (Keep a Changelog rules, §3.3).

### Phase 2: The tool
- First: `sync`, `status`, `pull`, `add`, `remove`, `release`, `check`, `impact`, `registry`, `index`.
- Second: `promote`, `discard`, `detach`, `template`, `bootstrap`.
- The warehouse repo's post-commit hook for `sync --auto`.
- pytest with sample projects, covering:
  - auto vs manual sync;
  - pin levels;
  - MAJOR never auto-applied;
  - settings fill-in;
  - drift skip and promote;
  - skill→tool dependencies;
  - deprecation;
  - release, tagging, and retrieving pinned old versions.

### Phase 3: First items
- Reconcile the §2 batch.
- For each drifted item, show the user the differences between the existing versions and get approval
  before releasing `1.0.0`.

### Phase 4: Pilot projects (Completed 2026-09-16)
- **doc-scanner** (codebase, `starter` profile), **GRIP** (vault, `standard` profile), **COLLEGE** (vault, `academic` + `frontmatter`).
- All 3 pilots bootstrapped, synced, pinned, locked, and verified with zero drift (`warehouse check`).
- Project registry generated at `_registry/projects.md`. Legacy `AI/` cleanups left to project agents to prevent cross-project context bloat.

### Phase 5: Transition from Centralized Rollout to On-Demand Adoption (Decided 2026-09-16)
- **Decision:** The planned centralized push-rollout across remaining projects is officially dropped.
- **Rationale:**
  1. **Instruction Bloat Avoidance:** Forcing warehouse items into codebases or vaults without an active task or project context causes noise, attention degradation, and instruction bloat (see [[progressive-context-disclosure]]).
  2. **Project Sovereignty (Pull vs Push):** AI agents working inside target projects hold the necessary operational context. They should independently decide when to adopt warehouse items via `warehouse bootstrap --profile <name>` or `warehouse add <id>`.
  3. **Operational State:** The warehouse engine, catalog, packaging, and sync tool are feature-complete. Future adoption occurs lazily as projects require capabilities.

---

## 8. Verification
- **pytest** covers every command and rule in §3–§6.
- **Propagation:** release a MINOR in the warehouse. The auto-sync pilots update; the manual pilot doesn't,
  but `status` shows it.
- **MAJOR:** release a MAJOR. No pilot updates. `status` shows `BREAKING:` notes. `pull --major` applies it
  and moves the pin.
- **Pins:** `@2.3` receives `2.3.1` but not `2.4.0`. An exact pin receives nothing.
- **History:** a project pinned to an old version receives that version's exact content from its git tag.
- **Drift:** hand-edit a synced copy. Sync skips it and reports it. `promote` → `release` → it reaches the
  other pilots.
- **Tools:** adding a skill pulls its tool. `check` reports missing software.
- **No commits:** `git log` in every pilot project is unchanged after any sync.

## 9. Open questions (non-blocking)
- **Per-item auto-sync:** deferred until real cases appear.
- ~~Default `target` folder~~ **Decided 2026-09-14:** `warehouse/`, visible, because there's no reason to
  hide it.
- **Remote:** https://github.com/Dev-020/AI-Agent-Warehouse (private).
