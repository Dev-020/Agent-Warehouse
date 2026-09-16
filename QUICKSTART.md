# Warehouse Quickstart & Onboarding Guide

A practical, step-by-step guide to onboarding a new or existing project (codebase or Obsidian vault) to the **AI Agent Warehouse**.

If you haven't touched the warehouse in months or are starting a brand-new project, follow this document.

---

## 1. Quick Concept (How It Works)

```
[ Warehouse: <warehouse> ]
      │  (master source of truth for protocols, conventions, skills, tools)
      ▼  `warehouse sync`
[ Your Project: C:/.../MyProject ]
  ├── .warehouse.yml      <- Your manifest: lists what items you want & version pins
  ├── .warehouse.lock     <- Auto-generated: tracks installed versions & file checksums
  └── warehouse/          <- Auto-generated: synced read-only markdown files & tools
```

* **Never edit files in `warehouse/` directly.** Change them in the warehouse or use `warehouse promote`.
* **The warehouse never commits in your project.** It only creates/updates `warehouse/`, `.warehouse.lock`, and your manifest. You review and commit.

---

## 2. Fast Onboarding (3-Minute Setup)

### Step 1: Open a terminal at your project root
Ensure you are in the root directory of your project (e.g. `C:/projects/my-app` or `C:/projects/my-vault`).

> [!TIP]
> **Windows Git Bash Users:** Always use forward slashes (`/`) in paths to avoid backslash escaping issues:
> `<warehouse>/_tools/warehouse.py`

### Step 2: Bootstrap your project manifest (`.warehouse.yml`)
Run `bootstrap` with the profile that fits your project scale (see [Profiles](#3-profile-cheat-sheet) below):

```bash
# For most standard projects (recommended):
python <warehouse>/_tools/warehouse.py bootstrap --profile standard --write

# Or for a lightweight / minimal setup:
python <warehouse>/_tools/warehouse.py bootstrap --profile starter --write
```

This creates `.warehouse.yml` in your project root:
```yaml
auto_sync: true
target: warehouse/
items:
  - protocol/agent-protocol@0.1
  - protocol/working-memory@0.1
  - convention/commits@0.1
  - convention/backlog@0.1
  - protocol/session-log@0.1
  - protocol/safe-write@0.1
```

### Step 3: Run the initial sync
Pull the files into your project:

```bash
python <warehouse>/_tools/warehouse.py sync .
```

You will now have:
* `warehouse/` containing the canonical markdown protocols and conventions.
* `warehouse/README.md` listing installed items and pins.
* `.warehouse.lock` recording verified file hashes.

### Step 4: Direct your project's AI agents to the warehouse items
In your project's agent instruction file (`AGENTS.md`, `CLAUDE.md`, or IDE system prompt), point agents to the synced files:

```markdown
## Operating Protocols
Follow the protocols and conventions synced in `warehouse/`:
- Agent rules & boundaries: [[warehouse/agent-protocol]]
- Memory & notes: [[warehouse/working-memory]]
- Safe file modification: [[warehouse/safe-write]]
- Task tracking: [[warehouse/backlog]]
- Commit messages: [[warehouse/commits]]
- Session handoffs: [[warehouse/session-log]]
```

*(If you previously had duplicate hand-copied protocol notes in your project, delete them now to prevent confusion).*

### Step 5: Commit to git
Commit the newly generated files in your project:

```bash
git add .warehouse.yml .warehouse.lock warehouse/
git commit -m "chore: onboard project to ai agent warehouse (standard profile)"
```

**You are done!**

---

## 3. Profile Cheat Sheet

To prevent **instruction bloat** (overwhelming agent context with irrelevant rules), pick the lowest tier that satisfies your project:

| Profile | Tier | Best For | Included Items |
|---|---|---|---|
| **`starter`** | 0 | Small tools, utility scripts, solo explorations. | `protocol/agent-protocol`<br/>`protocol/working-memory` |
| **`standard`** *(Default)* | 1 | Standard production codebases or structured vaults. | `starter` +<br/>`convention/commits`<br/>`convention/backlog`<br/>`protocol/session-log`<br/>`protocol/safe-write` |
| **`concurrency`** | 2 | Parallel multi-agent sessions, git worktree swarms, CLI task queues. | `standard` +<br/>`protocol/worktree-claims`<br/>`tool/backlog-cli`<br/>`skill/backlog-governance`<br/>`architecture/codebuff-orchestration` |
| **`academic`** | 3 | Research vaults authoring academic papers with LaTeX. | `starter` +<br/>`tool/tex-compile`<br/>`skill/latex-pdf` |

To see full details of any profile:
```bash
python <warehouse>/_tools/warehouse.py profile show standard
```

---

## 4. Common Daily Commands

Run these from your project root (or pass `--project <PATH>`):

### Check status & available updates
Inspect which items are installed, their version pins, and whether newer releases exist:
```bash
python <warehouse>/_tools/warehouse.py status
```

### Add a new item from the catalog
Browse the catalog in [[00_INDEX]]. To install an additional item (e.g. `skill/latex-pdf`):
```bash
python <warehouse>/_tools/warehouse.py add skill/latex-pdf@0.1
```
*(This automatically adds the item to `.warehouse.yml` and syncs it immediately).*

### Remove an item
```bash
python <warehouse>/_tools/warehouse.py remove skill/latex-pdf
```

### Update items (Pulling releases)
* **Minor/Patch updates:** Automatically applied if `auto_sync: true`. To pull manually:
  ```bash
  python <warehouse>/_tools/warehouse.py pull --all
  ```
* **Major updates:** Breaking updates never arrive automatically. Require `--major`:
  ```bash
  python <warehouse>/_tools/warehouse.py pull protocol/agent-protocol --major
  ```

### Copy a one-off template
Templates in `templates/` are copied once and owned by your project:
```bash
python <warehouse>/_tools/warehouse.py template plan-document docs/my-plan.md
```

---

## 5. What If I Edit a Synced File? (Handling Drift)

If an agent or human accidentally modifies a file inside `warehouse/`:
1. `warehouse sync` will **refuse to overwrite it** and will flag it as `drifted`.
2. Choose one of three ways to resolve it:
   * **Discard changes** (revert back to warehouse canonical):
     ```bash
     python <warehouse>/_tools/warehouse.py discard <item-id>
     ```
   * **Promote changes** (send your improvements back to the warehouse catalog as an unreleased draft):
     ```bash
     python <warehouse>/_tools/warehouse.py promote <item-id>
     ```
   * **Detach item** (stop tracking it from the warehouse; your project permanently keeps its own copy):
     ```bash
     python <warehouse>/_tools/warehouse.py detach <item-id>
     ```

---

## 6. Shell Aliases / Shortcuts (Optional)

To avoid typing the full python path every time, you can add an alias to your `~/.bashrc` (Git Bash) or PowerShell `$PROFILE`:

**Git Bash (`~/.bashrc`):**
```bash
alias warehouse='python <warehouse>/_tools/warehouse.py'
```

**PowerShell (`$PROFILE`):**
```powershell
function warehouse { python <warehouse>/_tools/warehouse.py @args }
```

Then you can simply run:
```bash
warehouse status
warehouse sync .
warehouse add convention/commits@0.1
```

---

## 7. Where to Learn More

* **Catalog Index:** [[00_INDEX]] — All items, version statuses, and summaries.
* **Full CLI Manual:** [[cli-reference]] — Detailed documentation for all flags and commands.
* **Architecture & Invariants:** [[warehouse-architecture]] — Core design and propagation rules.
* **Context Engineering:** [[progressive-context-disclosure]] — Token economics and why tiered profiles exist.
