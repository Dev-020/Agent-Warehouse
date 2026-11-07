# Warehouse Profiles (Loadouts)

Profiles are curated loadouts of warehouse items, version pins, and recommended default settings. They implement **Progressive Context Disclosure** ([[progressive-context-disclosure]]) to prevent instruction bloat in agent workspaces.

Instead of dumping every catalog item into a new project, projects adopt a profile matching their operational scale.

---

## 1. Available Profiles

| Profile | Tier | Applies To | Summary | Items |
|---|---|---|---|---|
| **`starter`** | 0 | `[vault, codebase]` | Minimal viable posture. Prevents hallucinations and unverified changes. | `protocol/agent-protocol@0.1`<br/>`protocol/working-memory@0.2` |
| **`standard`** | 1 | `[vault, codebase]` | Operational single-repo workflow with task tracking and clean git history. | `starter` +<br/>`convention/commits@0.1`<br/>`convention/backlog@0.2`<br/>`protocol/session-log@0.2`<br/>`protocol/safe-write@0.1` |
| **`concurrency`** | 2 | `[vault, codebase]` | Multi-agent coordination with git worktree claims, CLI tasks, and swarm roles. | `standard` +<br/>`protocol/worktree-claims@0.1`<br/>`tool/backlog-cli@0.2`<br/>`skill/backlog-governance@0.3`<br/>`architecture/codebuff-orchestration@0.1` |
| **`academic`** | 3 | `[vault]` | Academic research vault with LaTeX authoring, audit, and Tectonic compilation. | `starter` +<br/>`tool/tex-compile@0.1`<br/>`skill/latex-pdf@0.1` |

---

## 2. Managing Profiles with the CLI

The `warehouse profile` command manages profiles:

```powershell
# List all available profiles (sorted by Tier)
python _tools/warehouse.py profile list
python _tools/warehouse.py profile list --json

# Show details of a specific profile
python _tools/warehouse.py profile show starter

# Apply a profile's items to the current project's .warehouse.yml
python _tools/warehouse.py profile apply standard

# Save or update a profile
python _tools/warehouse.py profile save data-science --tier 1 --description "Data science profile" --items protocol/agent-protocol@0.1,protocol/safe-write@0.1

# Create a profile from the current project's active manifest
python _tools/warehouse.py profile save my-loadout --from-manifest --tier 1 --description "Captured loadout"

# Delete a custom profile
python _tools/warehouse.py profile delete my-loadout --yes
```

---

## 3. Project Bootstrapping

`warehouse bootstrap` defaults to the **`starter`** profile to prevent instruction bloat:

```powershell
# In a project root: creates .warehouse.yml with starter items (Tier 0)
python <warehouse>\_tools\warehouse.py bootstrap --write

# Bootstrap with a higher-tier profile:
python <warehouse>\_tools\warehouse.py bootstrap --profile standard --write

# Bootstrap with domain-specific profile:
python <warehouse>\_tools\warehouse.py bootstrap --profile academic --write
```
