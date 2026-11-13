# Warehouse CLI Reference

Complete reference for `warehouse.py` (`warehouse` / `warehouse.cmd`), the tool used to manage, version, sync, and audit reusable agentic items across projects.

## Quick Cheat Sheet

| Command | Category | Short Description |
|---|---|---|
| [`bootstrap`](#bootstrap) | Project Onboarding | Propose or write an initial `.warehouse.yml` manifest using a profile. |
| [`sync`](#sync) | Project Sync | Propagate released warehouse items into project `warehouse/` folders. |
| [`status`](#status) | Project Audit | Show installed vs available versions, pins, and drift for a project. |
| [`pull`](#pull) | Project Update | Manually upgrade installed items within pin limits (or across MAJOR with `--major`). |
| [`add`](#add) | Project Manifest | Add an item and pin to `.warehouse.yml` and immediately install it. |
| [`remove`](#remove) | Project Manifest | Remove an item from `.warehouse.yml` and delete its project files. |
| [`detach`](#detach) | Drift / Lifecycle | Disconnect an item from warehouse tracking and leave project with sole ownership. |
| [`discard`](#discard) | Drift / Lifecycle | Revert local edits to an item and restore the canonical warehouse version. |
| [`promote`](#promote) | Drift / Lifecycle | Merge project-level edits back into the warehouse master catalog. |
| [`template`](#template) | Templates | Copy a template item into a project once with placeholders filled. |
| [`profile`](#profile) | Profiles / Loadouts | List, view, create, delete, and apply progressive disclosure profiles. |
| [`release`](#release) | Warehouse Release | Release a new version of an item: bump version, tag, commit, and auto-sync. |
| [`check`](#check) | Vault Governance | Read-only health check across all registered projects and lock integrity. |
| [`impact`](#impact) | Vault Governance | Show which projects depend on a specific item and their pin constraints. |
| [`registry`](#registry) | Vault Governance | Scan workspace roots and regenerate `_registry/projects.md`. |
| [`index`](#index) | Vault Governance | Scan catalog items and regenerate the catalog index in `00_INDEX.md`. |
| [`install-hook`](#install-hook) | Git Automation | Install `post-commit` and `post-merge` git hooks in the warehouse repo. |

---

## Global Options

These flags can be placed before or after any command:

- `--project <PATH>`: Directory of the target project. Defaults to the current working directory (`.`).
- `--warehouse <PATH>`: Path to the warehouse vault root. Defaults to auto-detecting the location of `_tools/warehouse.py`.
- `--config <PATH>`: Path to the configuration file (default: `<warehouse>/warehouse.config.yml`).
- `--json`: Output machine-readable JSON instead of human-friendly terminal text.
- `--verbose`: Enable detailed debug logging, including full Python stack traces on errors.
- `--version`: Print the tool version and exit.

> [!TIP]
> **Path Separators in Git Bash (Windows):**
> Git Bash (MINGW64) treats backslashes (`\`) as escape sequences. Always use **forward slashes** (`/`) for paths in Git Bash:
> ```bash
> python <warehouse>/_tools/warehouse.py status
> ```

---

## Command Reference

### `bootstrap`
Initializes a new project by generating a recommended `.warehouse.yml` manifest.

**Syntax:**
```bash
warehouse bootstrap [--profile <NAME>] [--write] [--include-drafts] [--project <PATH>]
```

**Options:**
- `--profile <NAME>`: Profile to bootstrap from (`starter`, `standard`, `concurrency`, `academic`, or `all`). Default: `starter`.
- `--write`: Write `.warehouse.yml` directly to the project root. If omitted, only prints the proposed manifest to stdout.
- `--include-drafts`: Include draft (`0.x.y`) items when bootstrapping with `--profile all`.

**Project-Type Detection:**
Shared project-type detection (`discovery.detect_project_types`) inspects the project root:
- **Vault:** `.obsidian/` directory.
- **Codebase:** `package.json`, `pyproject.toml`, `requirements.txt`, `setup.py`, `go.mod`, `Cargo.toml`, `pom.xml`, `tsconfig.json`, `deno.json`, `index.html`, `composer.json`, `Gemfile`, `build.gradle`, or globs `*.csproj` and `*.sln`.
- Both types can be detected simultaneously if markers for both exist.
- **Fallback:** When neither marker matches, prints `warehouse bootstrap: no vault or codebase markers found; assuming codebase` to stderr and defaults to `codebase` (no mismatch warning is printed).
- **Mismatch Warning:** When types are detected and the chosen profile's `applies-to` is non-empty and does not intersect them, prints `warehouse bootstrap: profile '<name>' applies to [<applies-to>]; this project looks like [<types>]` to stderr (manifest is still produced, exit 0). `warehouse profile apply` uses the same check.

**Examples:**
```bash
# Preview proposed starter manifest
python <warehouse>/_tools/warehouse.py bootstrap

# Write the standard loadout manifest to a project
python <warehouse>/_tools/warehouse.py bootstrap --profile standard --write --project C:/projects/my-vault
```

---

### `sync`
Propagates released warehouse items to projects according to their manifests and SemVer pins.

**Syntax:**
```bash
warehouse sync [--auto] [--if-new-tags] [--include-manual] [<PROJECT_PATH>]
```

**Options:**
- `<PROJECT_PATH>`: Sync a single project directory (e.g. `.` or `C:/path/to/project`).
- `--auto`: Discovers and syncs all projects with `auto_sync: true` under configured roots in `warehouse.config.yml`.
- `--if-new-tags`: Optimization flag used by Git hooks. Skips execution unless release tags changed in Git.
- `--include-manual`: Also sync projects marked with `auto_sync: false`.

**Behavior & Invariants:**
- Never commits in the target project.
- Only writes inside `target:` (e.g. `warehouse/`), `.warehouse.lock`, and `.warehouse.yml`.
- Never overwrites modified (drifted) files; reports them as skipped.
- Resolves dependencies topologically and blocks requirers if dependencies are missing or drifted.

**Examples:**
```bash
# Sync current project
python <warehouse>/_tools/warehouse.py sync .

# Auto-sync all projects across the workspace
python <warehouse>/_tools/warehouse.py sync --auto
```

---

### `status`
Displays current installed versions vs latest available releases, active SemVer pins, drift status, and unreleased changelog entries.

**Syntax:**
```bash
warehouse status [--project <PATH>] [--json]
```

**Output Columns:**
- `item`: Warehouse item ID (`kind/name`).
- `installed`: Currently installed version from `.warehouse.lock`.
- `pin`: The constraint declared in `.warehouse.yml` (e.g. `@0.1`).
- `status`: `up to date`, `upgrade available (X.Y.Z)`, `drifted`, or `blocked`.

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py status
```

---

### `pull`
Manually updates installed items to the highest allowed version.

**Syntax:**
```bash
warehouse pull [<ID>] [--all] [--major] [--project <PATH>]
```

**Options:**
- `<ID>`: Specific item ID to update (e.g. `protocol/session-log`).
- `--all`: Update all items declared in the manifest.
- `--major`: Allow crossing MAJOR version boundaries (e.g. `1.x.x` to `2.x.x`). Automatically advances the pin in `.warehouse.yml`.

**Examples:**
```bash
# Update a single item within its existing pin
python <warehouse>/_tools/warehouse.py pull protocol/session-log

# Upgrade an item to a new major version
python <warehouse>/_tools/warehouse.py pull protocol/session-log --major
```

---

### `add`
Adds a new item to `.warehouse.yml` and immediately installs it.

**Syntax:**
```bash
warehouse add <ID>[@<PIN>] [--major] [--project <PATH>]
```

**Options:**
- `<ID>[@<PIN>]`: Item ID with optional SemVer pin (e.g. `convention/frontmatter@0.1` or `tool/backlog-cli@1`).
- `--major`: Allow adding an item with a major version higher than installed dependencies.

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py add convention/frontmatter@0.1
```

---

### `remove`
Removes an item from the project manifest and deletes its installed files.

**Syntax:**
```bash
warehouse remove <ID> [--prune] [--force] [--project <PATH>]
```

**Options:**
- `--prune`: Also remove unused dependencies that were pulled in solely by this item.
- `--force`: Force removal even if another installed item lists this item in its `requires`.

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py remove tool/tex-compile
```

---

### `profile`
Commands for managing progressive context disclosure loadouts (stored in `profiles/*.yml`).

**Syntax:**
```bash
warehouse profile <list | show | save | delete | apply> [ARGS]
```

**Subcommands:**
- `warehouse profile list [--json]`: Lists all available profiles, their tiers, target project types, and item counts.
- `warehouse profile show <NAME> [--json]`: Displays full details, item list with pins, and settings for a profile.
- `warehouse profile save <NAME> [--description DESC] [--tier 0-3] [--items I1,I2] [--applies-to TYPES] [--from-manifest]`: Saves or updates a profile. If `--from-manifest` is used, extracts items and settings from the current project.
- `warehouse profile delete <NAME> [--yes]`: Deletes a profile from `profiles/<NAME>.yml`.
- `warehouse profile apply <NAME>`: Appends all items from the profile into the current project's `.warehouse.yml`.

**Examples:**
```bash
# View available profiles
python <warehouse>/_tools/warehouse.py profile list

# Inspect standard profile
python <warehouse>/_tools/warehouse.py profile show standard

# Apply concurrency profile to current project
python <warehouse>/_tools/warehouse.py profile apply concurrency
```

---

### `release`
Publishes a new release of a warehouse item.

**Syntax:**
```bash
warehouse release <ID> <major | minor | patch | initial> [--no-sync] [--message "<MSG>"]
```

**Steps Performed Automatically:**
1. Validates item format and frontmatter schema (lint checks).
2. Runs associated test suites (for tools).
3. Bumps version according to SemVer rules.
4. Moves notes from `[Unreleased]` in the item's changelog to the new version header with today's date.
5. Commits changes to the warehouse repository.
6. Creates Git tag `<ID>@<VERSION>`.
7. Regenerates `00_INDEX.md`.
8. Automatically triggers `warehouse sync --auto` across projects (unless `--no-sync` is given).

**Examples:**
```bash
# Release initial version (0.1.0)
python <warehouse>/_tools/warehouse.py release protocol/session-log initial

# Publish a patch fix
python <warehouse>/_tools/warehouse.py release tool/backlog-cli patch
```

---

### `promote`
Merges local modifications made to a synced project item back into the warehouse master catalog.

**Syntax:**
```bash
warehouse promote <ID> [--message "<MSG>"] [--include-new] [--write-conflicts] [--project <PATH>]
```

**Behavior:**
- Runs a 3-way merge using reverse placeholder mapping (restoring `{{placeholders}}` from concrete project settings).
- Updates the warehouse master item and logs the change under `[Unreleased]` in its changelog.
- Clears the drift status in the project's `.warehouse.lock`.

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py promote protocol/working-memory
```

---

### `discard`
Reverts local modifications made to an installed item and restores the clean, rendered copy from the warehouse.

**Syntax:**
```bash
warehouse discard <ID> [--yes] [--pull] [--project <PATH>]
```

**Options:**
- `<ID>`: The drifted item to revert.
- `--yes`: Confirm discarding local changes (required in non-interactive environments).
- `--pull`: After discarding, immediately pull the latest allowed version.

**Examples:**
```bash
# Preview differences
python <warehouse>/_tools/warehouse.py discard protocol/safe-write

# Discard changes and restore
python <warehouse>/_tools/warehouse.py discard protocol/safe-write --yes
```

---

### `detach`
Permanently disconnects an item from warehouse tracking while keeping the file in the project.

**Syntax:**
```bash
warehouse detach <ID> [--force] [--project <PATH>]
```

**Behavior:**
- Removes the warehouse header notice from the file.
- Removes the item from `.warehouse.yml` and `.warehouse.lock`.
- Leaves the file in place for the project to own independently.

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py detach convention/commits
```

---

### `template`
One-time copy of a template item into a project, populating placeholders without ongoing sync.

**Syntax:**
```bash
warehouse template <ID> <DEST_PATH> [--set KEY=VALUE ...]
```

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py template template/plan-document plans/pilot-plan.md --set title="Phase 4 Pilot"
```

---

### `check`
Audits the health and consistency of all registered projects.

**Syntax:**
```bash
warehouse check [--json]
```

**What it Checks:**
- Validates `.warehouse.yml` and `.warehouse.lock` integrity.
- Detects drifted (locally edited) files.
- Checks for projects stuck in retry or failed migrations.
- Confirms release tags exist in the Git repository.
- Profile pins: Validates profile definitions in `profiles/*.yml` and `*.yaml`. Stale pins and deprecated items report `stale-pin` (info); unparseable entries, invalid pins, unknown items, pins with no matching release, duplicate items and unreadable profile files report `error`.

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py check
```

---

### `impact`
Shows which projects depend on a specific warehouse item.

**Syntax:**
```bash
warehouse impact <ID> [--json]
```

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py impact protocol/agent-protocol
```

---

### `registry`
Scans directories specified in `warehouse.config.yml` and regenerates `_registry/projects.md`.

**Syntax:**
```bash
warehouse registry [--json]
```

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py registry
```

---

### `index`
Scans all catalog items in the warehouse and refreshes the summary tables in `00_INDEX.md`.

**Syntax:**
```bash
warehouse index
```

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py index
```

---

### `install-hook`
Installs `post-commit` and `post-merge` hooks into the `.git/hooks` folder of the warehouse repo.

**Syntax:**
```bash
warehouse install-hook [--force]
```

**Options:**
- `--force`: Overwrite existing hooks (backing up existing files to `.bak`).

**Examples:**
```bash
python <warehouse>/_tools/warehouse.py install-hook
```

---

## Exit Codes

| Code | Meaning | Typical Causes |
|---|---|---|
| `0` | Success | Command completed cleanly with no errors. |
| `1` | Skipped / Issues | Sync skipped drifted files, unmet dependencies, or lint warnings. |
| `2` | Usage Error | Invalid CLI arguments, unknown command, malformed YAML manifest. |
| `3` | Git Error | Git operation failed, release tag missing, or directory not a Git repository. |
| `4` | Merge Conflict | `promote` encountered unresolvable merge conflicts. |
| `5` | Release Check Failed | `warehouse release` failed item linting or test execution. |
| `10` | Confirmation Required | Command requires explicit confirmation flag (e.g. `--yes` on `discard`). |

---

### `request`
Files a request for a new item or capability in the warehouse.

**Syntax:**
```bash
warehouse request <SUMMARY> [--reason "<REASON>"] [--priority P1|P2|P3] [--project <PATH>]
```

**Examples:**
```bash
warehouse request "Create a safe file editor agent" --reason "We need a reliable way for agents to edit code without breaking things"
```

---

### `issue`
Files an issue against a specific warehouse item.

**Syntax:**
```bash
warehouse issue <ITEM_ID> --summary "<SUMMARY>" [--type typo|bug|inconsistency|enhancement] [--details "<DETAILS>"] [--priority P1|P2|P3] [--project <PATH>]
```

**Examples:**
```bash
warehouse issue tool/replace-content --summary "Cannot handle Unicode characters" --type bug --details "Fails when finding an emoji."
```

---

### `inbox`
Manages the warehouse inbox of incoming requests and issues.

**Syntax:**
```bash
warehouse inbox <list | show | resolve | reject | triage> [ARGS]
```

**Subcommands:**
- `warehouse inbox list [--status open|triaged|resolved|rejected|all] [--type request|issue] [--json]`: Lists inbox tickets.
- `warehouse inbox show <TICKET_ID> [--json]`: Shows detailed context and resolution notes for a ticket.
- `warehouse inbox resolve <TICKET_ID> [--message "<MSG>"]`: Marks a ticket as resolved and appends resolution notes. Refuses (exit 2) unless the ticket's `BACKLOG.md` entry is under Completed.
- `warehouse inbox reject <TICKET_ID> [--reason "<REASON>"]`: Marks a ticket as rejected and appends reason. Refuses (exit 2) unless the ticket's `BACKLOG.md` entry is under the Icebox.
- `warehouse inbox triage <TICKET_ID>`: Adds an open ticket to the warehouse `BACKLOG.md` (after the last open task of the same or higher priority) and updates the ticket status to `triaged`. Creates `BACKLOG.md`, with its header, if it does not exist.

**Examples:**
```bash
# List all open requests
warehouse inbox list --type request

# Show ticket details
warehouse inbox show REQ-20260916-new-feature

# Triage ticket to backlog
warehouse inbox triage ISS-20260916-bug-tool
```
