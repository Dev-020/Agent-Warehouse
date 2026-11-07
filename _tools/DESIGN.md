# Warehouse tool — build design

Source of truth: [[warehouse-architecture]] §3–§6, [[warehouse-item]], [[versioning]], [[changelog]].
This document tells an Editor exactly what to build. Python 3.12, stdlib + PyYAML, pytest.

---

## 0. Decisions summary

| # | Topic | Decision |
|---|---|---|
| D1 | Released content | Read only from annotated tags `refs/tags/<id>@<version>` via `git ls-tree` + `git cat-file blob`. Working tree is never synced. |
| D2 | Tag legality | `<id>` grammar `kind/[a-z0-9][a-z0-9-]*` + `@` + `N.N.N` gives a legal ref: no `@{`, `..`, space, `~^:?*[\`, no component starting with `.`, no `.lock` suffix. Always address as `refs/tags/...` (never short name) to avoid branch ambiguity. Lowercase-only ids avoid case clashes on Windows. |
| D3 | Lock format | JSON (sorted keys, 2-space indent, LF, trailing newline). Deterministic, stdlib, no YAML type coercion (`1.10`, `on`). |
| D4 | Placeholders | Substituted only in `.md` files, only for names **declared** in the item's `settings`. Undeclared `{{x}}` stays literal (lets conventions document placeholders). |
| D5 | Allowed writes | Target folder + `.warehouse.lock` always; **`.warehouse.yml` only** by the explicit project commands `add`, `remove`, `pull --major`, `detach`, `bootstrap --write`; `template` writes only a new file at the user-given `<dest>`. `sync` never writes the manifest. |
| D6 | Hook ordering | `release` sets `WAREHOUSE_RELEASING=1` for its commit (hook no-ops), tags, then runs sync in-process. Hook runs `sync --auto --if-new-tags`: exits immediately unless the tag set changed since the last auto sync. |
| D7 | Promote | Line-mapped reverse substitution (no global string replace) + `git merge-file` 3-way merge into the master working tree. |
| D8 | Crash safety | Per-item lock journal (`pending`) + temp-file/`os.replace`. |
| D9 | Warehouse location | From the tool's own path, overridable by `--warehouse` / `WAREHOUSE_ROOT` (tests only use this). |

---

## 1. Module layout

```
_tools/
├── warehouse.py            entry: insert own dir in sys.path; `from warehouse_core.cli import main; sys.exit(main())`
├── warehouse               bash: exec python "$(dirname "$0")/warehouse.py" "$@"
├── warehouse.cmd           @python "%~dp0warehouse.py" %*
├── hooks/post-commit       shipped hook (§4.14)
├── hooks/post-merge        shipped hook (§4.14, User decision 5)
├── hooks/pre-push          shipped hook (§4.14b)
├── hooks/commit-msg        shipped hook (§4.14b)
├── DESIGN.md               this file
├── warehouse_core/         (refinement: named warehouse_core, not warehouse/, because a directory
│                            cannot share the name of the bash wrapper `_tools/warehouse`)
│   ├── __init__.py         TOOL_VERSION = "0.1.0"
│   ├── cli.py              argparse, global options, dispatch, exit codes, --json
│   ├── context.py          Context: warehouse root, config, git, catalog, today, report
│   ├── errors.py           exceptions carrying exit codes
│   ├── config.py           warehouse.config.yml (+ .local.yml)
│   ├── semver.py           Version, Pin, lines, matching
│   ├── frontmatter.py      split/parse/line-edit frontmatter
│   ├── items.py            kinds, id↔path, ItemMeta, working-tree discovery, lint
│   ├── changelog.py        parse, entries-between, BREAKING extraction, release edit
│   ├── gitrepo.py          Git (warehouse repo ONLY)
│   ├── catalog.py          released versions from tags, read release files
│   ├── manifest.py         .warehouse.yml load/validate + comment-preserving text edits
│   ├── lockfile.py         .warehouse.lock load/save/journal
│   ├── render.py           substitution, header insert/strip, rendered file set
│   ├── fsops.py            WriteGuard, safe_join, atomic_write, delete, prune dirs
│   ├── discovery.py        find projects under roots
│   ├── resolve.py          version + dependency resolution → Plan
│   ├── apply.py            execute Plan in one project (drift, writes, journal)
│   ├── inspect.py          per-file state of installed items (clean/eol/missing/drift)
│   ├── readme.py           <target>/README.md
│   ├── registry.py         _registry/projects.md
│   ├── index.py            00_INDEX.md regions
│   ├── software.py         requires-software / platforms checks
│   ├── merge.py            promote line mapping + merge-file
│   ├── report.py           Report model, text/json output
│   └── commands/           one module per command, each `run(ctx, args) -> int`
│       sync.py status.py pull.py add.py remove.py release.py check.py impact.py
│       registry_cmd.py index_cmd.py install_hook.py          (batch 1)
│       promote.py discard.py detach.py template.py bootstrap.py (batch 2; until built, batch2.py stubs
│       them: "not implemented (batch 2)", exit 2)
└── tests/                  pytest; see §8
```

### Key signatures

```python
# errors.py
class WarehouseError(Exception): code: int            # base
class UsageError(WarehouseError): code = 2            # bad args, invalid manifest/config, unknown id
class GitError(WarehouseError): code = 3              # git failure, missing tag, not a repo
class ConflictError(WarehouseError): code = 4
class ReleaseCheckError(WarehouseError): code = 5
class ConfirmationRequired(WarehouseError): code = 10
class GuardError(WarehouseError): code = 1              # I1 refusal; NOT an AssertionError; reported per item

# semver.py
@dataclass(frozen=True, order=True)
class Version: major: int; minor: int; patch: int
    @classmethod parse(s: str) -> Version            # ^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$ else UsageError
    line -> tuple                                    # (major,) if major>=1 else (0, minor)
    is_draft -> bool                                 # major == 0
    bump(level: str) -> Version                      # §3.3
@dataclass(frozen=True)
class Pin: major: int; minor: int|None; patch: int|None
    @classmethod parse(s: str) -> Pin                # "2" | "2.3" | "2.3.1"; "0" rejected
    matches(v: Version) -> bool
    line -> tuple
    text -> str                                      # "2.3"
    @classmethod default_for(v: Version) -> Pin      # Pin(M) or Pin(0, m)
    moved_to(v: Version) -> Pin                      # same granularity at v's line (§3.4)

# frontmatter.py
split(text: str) -> tuple[str|None, str]             # (yaml_block_without_fences, body); requires "---\n" at byte 0
parse(text: str) -> dict                             # yaml.safe_load; non-dict → UsageError
set_scalar(text: str, key: str, value: str) -> str   # replaces `^key:.*$` inside frontmatter only

# items.py
KINDS = {"architecture": "architecture", "protocol": "protocols", "convention": "conventions",
         "template": "templates", "skill": "skills", "tool": "tools"}
SYNCED_KINDS = {"architecture", "protocol", "convention", "skill", "tool"}
ID_RE = r"^(architecture|protocol|convention|template|skill|tool)/[a-z0-9][a-z0-9-]*$"
@dataclass(frozen=True)
class Setting: description: str; default: str|None     # default None = required (User decision 1)
@dataclass
class ItemMeta: id, version: Version, status, summary, applies_to: list[str],
    settings: dict[str, Setting], requires: list[tuple[str, Pin]], replaces: str|None,
    entrypoint: str|None, requires_software: list[str], platforms: list[str]
item_rel_path(id) -> str            # "protocols/session-log.md" | "skills/latex-pdf" (folder)
main_file(id) -> str                # "protocols/session-log.md" | "skills/latex-pdf/SKILL.md" | ".../TOOL.md"
changelog_file(id) -> str           # doc itself | "<folder>/CHANGELOG.md"
target_rel_path(id) -> str          # "session-log.md" | "skills/latex-pdf" | "tools/tex-compile"
parse_meta(text: str, expected_id: str|None) -> ItemMeta
discover_working_tree(root) -> dict[str, Path]       # id -> main file; skips _archive, reference, case-studies
lint_item(root, id, *, for_release=False) -> list[Problem]   # §2.2

# gitrepo.py
class Git:
    def __init__(self, root: Path)                   # root = warehouse toplevel
    def run(self, *args, check=True, env_extra=None) -> CompletedProcess
        # always ["git", "-C", str(root), *args]; env copy with GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE,
        # GIT_PREFIX removed; asserts realpath(root) == ctx warehouse root (invariant I2)
    def tags(self) -> list[TagInfo]                  # for-each-ref refs/tags --format=%(refname)%00%(objectname)%00%(creatordate:short)
    def tree_files(self, tag_ref, path) -> list[tuple[str, str]]   # ls-tree -r -z --full-tree <ref>^{tree} -- <path> → (path, blob)
    def blob(self, oid) -> bytes                     # cat-file blob
    def is_clean_state(self) -> bool                 # no MERGE_HEAD/REBASE dirs, HEAD on a branch
    def commit_only(self, paths, message) -> str     # add -A -- paths; commit --only -m msg -- paths (env WAREHOUSE_RELEASING=1)
    def tag(self, name, message) -> None             # tag -a name -m message
    def merge_file(self, ours: bytes, base: bytes, theirs: bytes) -> tuple[bytes, int]  # temp files, merge-file -p --diff3

# catalog.py
@dataclass
class Release: id: str; version: Version; tag: str; commit: str; date: str
class Catalog:
    def __init__(self, git: Git)                     # one tags() call, cached
    versions(id) -> list[Version]                    # ascending; ignores malformed tags (reported by check)
    latest(id, pin: Pin|None=None) -> Version|None
    release(id, v) -> Release                        # GitError(code 3) "missing-tag" if absent
    files(id, v) -> dict[str, bytes]                 # keys relative to item folder (docs: {"<name>.md": ...}); cached
    meta(id, v) -> ItemMeta                          # parsed from the tag's main file; id/version must match tag
    all_ids() -> list[str]
    tags_digest() -> str                             # sha256 of sorted "refname objectname\n"

# manifest.py
@dataclass
class ManifestEntry: id: str; pin: Pin|None; line_no: int
@dataclass
class Manifest: path: Path; auto_sync: bool; target: str; entries: list[ManifestEntry]; settings: dict[str, str]; raw: str
load(project_root) -> Manifest                       # §2.3 validation
add_or_replace_entry(m, id, pin) -> str              # returns new text
remove_entry(m, id) -> str
ensure_settings_keys(m, names_with_desc: dict) -> str
find_project_root(start: Path) -> Path               # walk up to .warehouse.yml; UsageError if none

# lockfile.py
load(project_root) -> Lock ; save(project_root, lock, guard)  # atomic
class Lock: items: dict[str, LockItem]
@dataclass
class LockItem: version, pin, source, required_by, settings_digest, synced, state, files: dict[str,str],
    promoted: dict|None, pending: dict|None

# render.py
PLACEHOLDER_RE = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
HEADER_RE = re.compile(r"\n> \[!info\] Warehouse item — (\S+) v(\d+\.\d+\.\d+) \(synced \d{4}-\d{2}-\d{2}\)\n> Maintained in the AI warehouse\.[^\n]*\n")
render_release(meta, files, settings, today, *, exclude) -> RenderResult  # .files: dict[rel, bytes] | .unfilled: list[str]
insert_header(text, id, version, today) -> str
strip_header(text) -> str
normalize_stamp(b: bytes) -> bytes                   # replaces "(synced YYYY-MM-DD)" with "(synced -)" for adoption compare
sha256(b: bytes) -> str                              # "sha256:<hex>"

# fsops.py
class WriteGuard:
    def __init__(self, project_root, target, *, allow_manifest=False, extra_files=())
    def check(self, path) -> Path                    # realpath inside target, or == lock/manifest/extra; else AssertionError
atomic_write(guard, path, data: bytes)               # temp "<name>.warehouse-tmp-<pid>" in same dir, fsync, os.replace; 3 retries on PermissionError (100 ms)
delete_file(guard, path); prune_empty_dirs(guard, start_dir)   # stops at target root
cleanup_temp_files(guard)                            # removes only names matching ^.+\.warehouse-tmp-\d+$ under target,
                                                     # plus .warehouse.lock / .warehouse.yml temps at the project root

# discovery.py
@dataclass
class Project: root: Path; manifest: Manifest|None; error: str|None
find_projects(config, warehouse_root) -> list[Project]

# resolve.py
@dataclass
class ItemAction: id; from_v: Version|None; to_v: Version|None; pin: Pin; source: "manifest"|"dependency"
    required_by: list[str]; kind: "install"|"update"|"downgrade"|"keep"|"blocked"|"remove"|"orphan"|"not-installable"|"pin-moved"
    narrowed: bool   # keep, manifest pin narrowed on the installed line (reported outside-pin)
    reason: str|None; compatible: Version|None; outside_pin: Version|None; major: Version|None
resolve(ctx, project, lock, *, mode: "sync"|"pull"|"major", ids: set[str]|None) -> list[ItemAction]

# apply.py
apply_actions(ctx, project, lock, actions, *, today) -> list[ReportLine]

# report.py
@dataclass
class ReportLine: project: str|None; status: str; id: str|None; detail: str
class Report: add(...); exit_code() -> int; render_text() -> str; render_json() -> str
```

**Global CLI options:** `--warehouse PATH`, `--config PATH`, `--project PATH`, `--json`, `--today YYYY-MM-DD`
(hidden; tests). Env equivalents: `WAREHOUSE_ROOT`, `WAREHOUSE_CONFIG`, `WAREHOUSE_TODAY`.

---

## 2. File formats

### 2.1 `warehouse.config.yml` (warehouse root, committed)

```yaml
config_version: 1
project_roots:
  - C:/projects/vaults
  - C:/projects/code
max_depth: 4                  # directory levels below a root searched for .warehouse.yml
skip_dirs:                    # directory NAMES never descended into (case-insensitive)
  - .git
  - node_modules
  - .claude                   # covers .claude/worktrees
  - .venv
  - venv
  - __pycache__
  - .pytest_cache
  - .obsidian
  - .trash
  - dist
  - build
  - worktrees
sync_exclude:                 # glob patterns (fnmatch, relative to item folder) never copied
  - "tests/**"                # tools only (always applied to tools even if removed here)
  - "**/desktop.ini"
  - "**/.gitkeep"
  - "**/__pycache__/**"
  - "**/*.pyc"
```

`warehouse.config.local.yml` (gitignored, optional) may override `project_roots`, `max_depth` only.
Validation: `config_version == 1`; roots are strings; missing roots are warned, not fatal; `max_depth` int
1–10; unknown keys → UsageError. Discovery also always skips: the warehouse root itself, symlinks and
junctions (`entry.is_symlink()`, `os.path.isjunction`), and each found project's own target folder.

### 2.2 Item frontmatter (reuse [[warehouse-item]])

Parsed with `frontmatter.parse`. Lint rules (`items.lint_item`), each a `Problem(level, code, msg)`:

| Code | Rule |
|---|---|
| `fm-missing` | File starts with `---\n` and has a closing `---` line. |
| `fm-field` | Required: id, version, status, summary, applies-to, settings, requires, replaces. Tools also: entrypoint, requires-software, platforms. |
| `id-path` | `id` matches `ID_RE` and `item_rel_path(id)` equals the file's location. |
| `version` | `version` is a **string** matching SemVer (unquoted `1.0` → error "quote it"). |
| `status` | `0.x` ⇒ `draft`; `≥1` ⇒ `canonical` or `deprecated`. |
| `settings` | dict name→ either a description string (required setting) or a mapping `{description: str, default: str\|number}` (optional setting, User decision 1); no other keys; names match `[a-z][a-z0-9_]*`. |
| `placeholder-undeclared` | Every `{{name}}` in `.md` files **outside fenced/inline code** is declared. (Inside code: ignored.) |
| `requires` | Each entry `id@pin`, pin mandatory, id exists (working tree or tags), no self/cycle; canonical items must not require drafts (warning). |
| `replaces` | null or an existing/archived id. |
| `deprecated-replacement` | `deprecated` item: warn if no item `replaces` it. |
| `name-collision` | Target paths unique: no two non-archived document items share `<name>` unless one `replaces` the other. |
| `case-collision` | No two files in a folder item differ only by case. |
| `entrypoint` | Tool entrypoint file exists in the folder. |
| `changelog` | §3.5 parse succeeds; `[Unreleased]` present; versions strictly descending; dates `YYYY-MM-DD`; newest released heading == frontmatter `version` unless `[Unreleased]` is the only content and no tag exists yet. |

### 2.3 `.warehouse.yml` (project root, project-owned)

```yaml
auto_sync: true               # optional, default true
target: warehouse/            # optional, default "warehouse/"
items:
  - protocol/session-log@2
  - convention/backlog@2.3
  - tool/backlog-cli@1.4.2
  - protocol/working-memory@0.3
settings:
  session_folder: AI/session
```

| Rule | Error |
|---|---|
| Top-level keys ⊆ {auto_sync, target, items, settings}; empty file = all defaults | `manifest-invalid: unknown key 'itmes'` |
| `auto_sync` bool | |
| `target`: relative, forward or back slashes, normalized; not empty/`.`; no `..`; not absolute; first component not `.git`; must not contain `.warehouse.yml` / `.warehouse.lock` | |
| `items`: block list of strings, grammar `^(?P<id>(architecture\|protocol\|convention\|skill\|tool)/[a-z0-9][a-z0-9-]*)(?:@(?P<pin>(?:0\|[1-9]\d*)(?:\.(?:0\|[1-9]\d*)){0,2}))?$` | `template/*` → "use `warehouse template`" |
| Pin `@0` rejected (draft pins need `@0.MINOR` or exact) | |
| Duplicate ids rejected | |
| `settings`: map name→str/int/float (bool, null, list, dict rejected); values must not contain `\n` | |

**Effective pin** of an entry: explicit pin; else lock's pin; else `Pin.default_for(latest canonical ≥1.0.0)`;
if only drafts exist, the entry is `not-installable` with reason "draft item needs an explicit @0.MINOR pin".

**Text edits** (`add_or_replace_entry`, `remove_entry`, `ensure_settings_keys`) operate on lines, preserving
comments: locate top-level `items:` (column 0); entries are following lines matching `^\s+-\s+`; replace the
matching entry line (keeping any trailing `# comment`), append after the last entry, or delete it. If `items:`
is absent, append `items:\n  - <entry>\n`. Flow style (`items: [..]`) → UsageError "edit .warehouse.yml by
hand". After editing, re-`load` the new text in memory; if it fails validation, write nothing. Settings keys
are appended under `settings:` as `  name: ""  # <description>` — only for settings **without a default**
(`settings: {}` is rewritten to block style first).

**Effective setting value** (User decision 1): the manifest value if present and not `""`; else the item's
`default`; else the setting is **unfilled**. Only unfilled settings block an item (I5). The settings digest
covers effective values, so changing a default re-renders projects that rely on it.

### 2.4 `.warehouse.lock` (project root, generated)

```json
{
  "lock_version": 1,
  "items": {
    "protocol/session-log": {
      "files": {"session-log.md": "sha256:9f2c..."},
      "pending": null,
      "pin": "2",
      "promoted": null,
      "required_by": [],
      "settings_digest": "sha256:41ab...",
      "source": "manifest",
      "state": "ok",
      "synced": "2026-09-20",
      "version": "2.1.0"
    },
    "tool/tex-compile": {
      "files": {"tools/tex-compile/TOOL.md": "sha256:...", "tools/tex-compile/compile.py": "sha256:..."},
      "pending": null, "pin": "1", "promoted": null,
      "required_by": ["skill/latex-pdf"], "settings_digest": "sha256:...",
      "source": "dependency", "state": "ok", "synced": "2026-09-20", "version": "1.2.0"
    }
  },
  "readme": "sha256:..."
}
```

- `files` keys: paths relative to target, `/` separators, exact bytes written.
- `settings_digest`: sha256 of `json.dumps({name: str(value) for declared names}, sort_keys=True)`.
- `state`: `ok` | `promoted`. `promoted` = `{"from_version": "2.1.0", "files": {path: sha256 of disk at promote time}}`.
- `pending` (journal): `{"version", "files", "synced", "settings_digest", "accepted"}` written before any file
  replace; cleared after. `accepted` = `{path: [sha256, ...]}`, every hash accepted for that path by earlier
  lock/pending generations, carried forward when a new pending replaces an unfinished one (review fix 1: a second
  interruption must not turn files written by the first into drift). A disk file whose hash equals `files`,
  `pending.files` or any `pending.accepted` hash is clean. Paths known only to the journal count as tracked
  (deleted by remove/stale cleanup when clean; "missing" for them is not a problem).
- Unknown `lock_version` → UsageError (never overwrite a newer lock).

### 2.5 `<target>/README.md` (generated)

```markdown
<!-- warehouse:generated — written by the warehouse sync tool. Do not edit; it is regenerated. -->
# Warehouse items

This project uses items from the AI warehouse. The files in this folder are synced copies. They may be
updated automatically (`auto_sync: true`) or with `warehouse pull`. Do not edit them here: change them in
the warehouse, or run `warehouse promote <id>` to send a local change upstream.

| Item | Version | Pin | Path | Notes |
|---|---|---|---|---|
| protocol/session-log | 2.1.0 | @2 | [session-log.md](session-log.md) | |
| skill/latex-pdf | 1.0.1 | @1 | [skills/latex-pdf/](skills/latex-pdf/SKILL.md) | |
| tool/tex-compile | 1.2.0 | @1 | [tools/tex-compile/](tools/tex-compile/TOOL.md) | required by skill/latex-pdf |
| convention/backlog | 2.3.1 | @2.3 | [backlog.md](backlog.md) | deprecated: use convention/backlog-v2 |

Manifest: `.warehouse.yml` at the project root.
```

Rows sorted by id. No dates (avoids churn). Written only when bytes differ. If `README.md` exists without the
first-line marker and is not in the lock → `collision`, never overwritten. Generated README is exempt from
drift protection (it is a notice, not an item); its hash is kept in `lock.readme` for reporting only.

### 2.6 Synced copy header

Inserted into the main file only (document `.md`, `SKILL.md`, `TOOL.md`), immediately after the closing
frontmatter line `---\n`:

```
---
<frontmatter bytes unchanged>
---

> [!info] Warehouse item — protocol/session-log v2.1.0 (synced 2026-09-20)
> Maintained in the AI warehouse. Edit it there, or run `warehouse promote protocol/session-log` to send a change upstream.

# Session log
```

Exact insertion string: `"\n> [!info] Warehouse item — {id} v{version} (synced {today})\n> Maintained in the AI warehouse. Edit it there, or run `warehouse promote {id}` to send a change upstream.\n"`.
Main file without frontmatter: lint error (never released). `<id>` in the second line is filled (refinement).

### 2.7 `_registry/projects.md` (generated, whole file)

```markdown
<!-- warehouse:generated — `warehouse registry`. Do not edit. -->
# Project registry

Generated 2026-09-20 from 3 projects.

## Projects

| Project | Auto-sync | Target | Items | Issues |
|---|---|---|---|---|
| C:/projects/my-vault | yes | warehouse/ | 4 | 1 drift |

## Items

| Item | Project | Pin | Installed | Source |
|---|---|---|---|---|
| protocol/session-log | C:/projects/my-vault | @2 | 2.1.0 | manifest |
```

Paths shown with `/`. Sorted. Invalid manifests listed with Issues = `invalid manifest`.

### 2.8 `00_INDEX.md` regions

Generated content lives only between markers; everything else (frontmatter except `updated:`, "How to
read", "Planned", "Reference") is preserved byte-for-byte.

```markdown
## Catalog

<!-- warehouse:catalog:start -->
| ID | Kind | Version | Released | Status | Summary | Applies to |
|---|---|---|---|---|---|---|
| [[protocols/session-log\|protocol/session-log]] | protocol | 2.2.0 | 2.1.0 | canonical | How and when agents write session logs. | vault, codebase |
<!-- warehouse:catalog:end -->

## Recent releases

<!-- warehouse:releases:start -->
- 2026-09-20 — protocol/session-log 2.1.0
<!-- warehouse:releases:end -->
```

- Catalog: all working-tree items (not `_archive/`), sorted by kind order then id. `Version` = frontmatter,
  `Released` = latest tag or `—`. Items that fail parsing appear with Status `invalid`.
- Releases: newest 15 tags by creator date then version. Empty → `No releases yet.`
- `updated:` in frontmatter set to today. Missing markers → UsageError (exit 2) "add the warehouse:*
  markers"; batch 1 adds them to the current `00_INDEX.md` once.

---

## 3. Version logic

### 3.1 Parse/compare
`Version.parse` strict (no pre-release/build, no leading zeros). Ordering = tuple order.

### 3.2 Pin matching

| Pin | `matches(v)` |
|---|---|
| `Pin(M)` (M≥1) | `v.major == M` |
| `Pin(0, m)` / `Pin(M, m)` | `v.major == M and v.minor == m` |
| `Pin(M, m, p)` | `v == Version(M, m, p)` |

`Pin.line`: `(M,)` if M≥1 else `(0, m)`; for exact pins it's `Version(M,m,p).line`.

### 3.3 Bumps (`Version.bump`)

| Current | major | minor | patch |
|---|---|---|---|
| `2.4.1` | `3.0.0` | `2.5.0` | `2.4.2` |
| `0.3.2` (draft) | `1.0.0` (sets `status: canonical`) | `0.4.0` (breaking-level) | `0.3.3` |

Level `initial`: no bump; releases the frontmatter version as-is; allowed only when no tag exists for the id.

### 3.4 Derived values (per installed item, from `Catalog.versions(id)` = tags)

| Name | Definition |
|---|---|
| `compatible` | max v with `pin.matches(v)` and `v > installed` |
| `outside_pin` | max v with `v.line == installed.line`, `not pin.matches(v)`, `v > installed` (e.g. `@2.3` and 2.4.0 exists) |
| `major` | max v with `v.line > installed.line` (for drafts `0.3→0.4` and `0.x→1.0.0` both count) |
| default pin on add | latest canonical ≥1.0.0 → `Pin(M)`; else latest draft → `Pin(0, m)` |
| `pin.moved_to(v)` | `Pin(M)`→`Pin(v.major)` (or `Pin(0, v.minor)` if v is draft); `Pin(M,m)`→`Pin(v.major, v.minor)`; exact→exact v. From a draft pin to v≥1: `Pin(v.major)` |

"Drafts aren't synced unless listed": a canonical pin never matches `0.x`; a `0.x` version is only ever chosen
through an explicit `@0.m`/exact pin or a `requires` pin.

---

## 4. Algorithms per command

**Exit codes (all commands):** `0` ok · `1` finished with skipped items/issues (drift, blocked, unfilled,
collision, per-project errors) · `2` usage/config/manifest error · `3` git error or missing tag · `4` merge
conflict · `5` release checks/tests failed · `10` confirmation required (re-run with `--yes`).

**Report format (text):**
```
warehouse sync --auto — 2026-09-20
C:/projects/my-vault  [auto]
  updated     protocol/session-log      2.1.0 -> 2.2.0
  major       convention/backlog        2.3.1 (3.0.0 available: warehouse pull convention/backlog --major)
  drift       protocol/working-memory   1.0.0 skipped: working-memory.md edited locally
  unfilled    skill/latex-pdf           needs settings: tex_root
C:/projects/my-app  [manual]  skipped: auto_sync is false
Summary: 1 updated · 1 major available · 1 drift · 1 unfilled · 1 project skipped
```
Status words (fixed vocabulary): `installed updated downgraded restored adopted removed unchanged compatible
outside-pin major drift promoted blocked unfilled collision deprecated orphan not-installable missing-tag
invalid-manifest untracked missing-software platform error needs-retry stale-pin`. `--json` prints
`{"command","date","exit_code","lines":[{"project","status","id","detail"}],"summary":{status: count}}`.
Statuses that raise exit 1: `drift blocked unfilled collision missing-tag invalid-manifest error
not-installable needs-retry` (plus `check`: any non-info status; `stale-pin` is info).

### 4.1 Shared: `resolve(ctx, project, lock, mode, ids)`

```
M = manifest entries; L = lock; C = catalog
fixed = ids-not-being-updated: if ids given, every locked id outside closure(ids) is fixed at its lock version
constraints: id -> list[(Pin, source)]   seeded: for e in M: (effective_pin(e), "manifest")
chosen: id -> Version|None
allowed(id, v):
    inst = L.version(id)
    if inst is None: return True
    if id in fixed: return v == inst
    if mode == "major" and id in ids: return v.line >= inst.line
    if mode == "sync": return v.line == inst.line and v >= inst
    if mode == "pull": return v.line == inst.line          # pull may downgrade to honour a narrowed pin
repeat (max 50 passes; on overflow add 'error' "unresolvable requires" for project, return []):
    changed = False
    for id in sorted(constraints):
        cands = sorted(v for v in C.versions(id)
                       if all(p.matches(v) for p,_ in constraints[id]) and allowed(id, v), reverse=True)
        pick = first v in cands where deps_ok(id, v)
        deps_ok(id, v): for (rid, rpin) in C.meta(id, v).requires:
            others = [p for p,s in constraints.get(rid, []) if s != id]
            exists w in C.versions(rid): rpin.matches(w) and all(p.matches(w) for p in others) and allowed(rid, w)
        if pick is None: pick = L.version(id) (may be None); mark blocked(id) with first failing requirement
        if chosen.get(id) != pick: chosen[id] = pick; changed = True
        replace constraints sourced from id with requires of pick (if pick)
        drop ids from constraints that have no remaining sources (and not in M)
    until not changed
actions:
    install     L none, pick set
    update      pick > inst ; downgrade pick < inst (mode pull only)
    keep        pick == inst
    blocked     marked; action keeps inst; reason "skill/x 1.3.0 needs tool/t@2 (project has 1.4.2): warehouse pull skill/x --major"
                (the hint names the requirer: pulling it with --major lets its dependencies cross lines)
    pin-moved   sync only: manifest pin is on another MAJOR line than inst → report `major` "pin changed; run pull <id> --major"
    keep+narrowed  sync only: pin narrowed on inst's line and inst no longer matches → keep, report `outside-pin`
                "run warehouse pull <id>" (pull downgrades). pin-moved and narrowed items keep inst's requires, so their
                dependencies are not orphaned.
    not-installable  L none and pick none (reason: no release matches pin / draft needs pin)
    remove      id in L, not in constraints, L.source == "manifest"   (hand-removed from manifest)
    orphan      id in L, not in constraints, L.source == "dependency"
    compatible/outside_pin/major filled per §3.4 against the version after the action
```

### 4.2 Shared: `apply_actions` (one project)

```
guard = WriteGuard(root, manifest.target); cleanup_temp_files(guard)
recover journal: for items with pending, treat pending hashes as clean (see §2.4)
for action in actions (dependencies before dependents: tools, then others, sorted by id):
  if kind in {blocked, not-installable, orphan}: report; continue
  if kind == remove: per file: delete clean/eol-only copies; keep drifted ones, keep the lock entry
                     with only those files and report drift; no drift → drop entry, report removed;
                     continue                                                         # User decision 3
  files = C.files(id, to_v) minus sync_exclude (tools: always minus tests/**)
  meta = C.meta(id, to_v)
  settings_needed = declared names in meta.settings
  missing = [n for n in settings_needed if no manifest value (absent or "") and no default]   # decision 1
  if missing: report unfilled "needs settings: a, b"; continue          # I5
  digest = settings_digest(...)
  if kind == keep and digest == L.settings_digest:
      st = inspect(item)   # per file: clean | eol-only | missing | drift
      if all clean/eol-only: report unchanged (suppressed in text unless --verbose); continue
      if any drift: report drift; continue
      only missing: re-render at inst with the lock's `synced` date (bytes == lock hashes) and write the
                    missing files → report restored; continue                     # User decision 2
  rendered = render_release(meta, files, settings, today)
  st = inspect(item)
  if any drift:
      if L.state == promoted and disk hashes == L.promoted.files and to_v > L.promoted.from_version: pass
      else: report drift "<paths> edited locally"; continue                # I3
  new_paths = {target_rel_path/…} ; untracked collisions = new paths existing on disk, not in L.files
  for each collision: if normalize_stamp(crlf→lf(disk)) == normalize_stamp(rendered): adopt (no write)
                      else: report collision "<path> exists and is not a warehouse copy"; skip item
  L.items[id].pending = {version, files: hashes(rendered), synced: today, settings_digest}; save lock
  for path, data in rendered: atomic_write(guard, target/path, data)
  for old path in L.files not in rendered and state clean: delete_file; prune_empty_dirs
  L.items[id] = LockItem(version=to_v, pin, source, required_by, digest, today, "ok", hashes, None, None); save lock
  report installed|updated|downgraded
  if meta.status == deprecated: report deprecated "use <successor via replaces index>"
after loop: regenerate README if bytes differ (guard); save lock
```

`inspect` comparisons: `sha(disk) == expected` → clean; `sha(disk.replace(b"\r\n", b"\n")) == expected` →
`eol-only` (clean; never rewritten just for EOL); file absent → `missing`; else `drift`.

### 4.3 `sync [--auto] [--if-new-tags] [--include-manual] [project]`

1. Acquire run lock `_tools/.state/run.lock` (O_EXCL, contains pid+time; stale after 30 min). Busy:
   `--auto` → exit 0 silently; else exit 3 "another warehouse run is active".
2. `--if-new-tags`: compare `C.tags_digest()` with `_tools/.state/auto-sync.json`; equal → exit 0, no output.
3. Projects: `[project]` given → just that one (must contain `.warehouse.yml`, else exit 2); else
   `find_projects`.
4. For each project: invalid manifest → `invalid-manifest`, continue. Without explicit `[project]`, skip
   `auto_sync: false` unless `--include-manual` (report `skipped: auto_sync is false`). An explicit `[project]`
   is synced regardless of `auto_sync` (it is a direct request).
5. `resolve(mode="sync")` → `apply_actions`. Report majors/outside-pin as info lines.
6. With `--auto`, write `auto-sync.json` `{tags_digest, at}` after the run (even with exit 1).
7. Never touches the warehouse working tree (no registry/index writes). Exit per report.

### 4.4 `status` (project-scoped)

Read-only. For each manifest entry and lock item:
```
protocol/session-log   installed 2.1.0  pin @2   compatible 2.2.0   major 3.0.0
  2.2.0 — Added: Optional "open threads" section for handoffs.
  3.0.0 — BREAKING: logs now require a `written_by` field.  Migration: add `written_by:` to existing logs.
convention/backlog     installed 2.3.1  pin @2.3  up to date  (2.4.0 outside pin)
protocol/working-memory  installed 1.0.0  drift: working-memory.md
tool/tex-compile       installed 1.2.0  pin @1   required by skill/latex-pdf
protocol/research-discipline  not installed  (run warehouse sync . or warehouse pull <id>)
```
Changelog entries come from the **latest tag's** changelog (§3.5 `entries_between(installed, target)`); for
major, only BREAKING bullets + their Migration continuation lines. Also shows drift, promoted, unfilled,
deprecated, orphan, blocked. Exit 0 (2/3 on errors).

### 4.5 `pull <id> | --all [--major]` (project-scoped, ignores `auto_sync`)

1. Exactly one of `<id>`/`--all`. `<id>` must be in manifest or lock (else exit 2).
2. `resolve(mode = "major" if --major else "pull", ids = {id} or all)`.
3. `--major`: target = `C.latest(id)` overall (for a canonical installed item, drafts are never newer). If no
   higher line → report `unchanged`, exit 0. Print `BREAKING:` entries between installed and target. If the
   id is `source: dependency` and any installed requirer's pin rejects the target → `blocked` exit 1
   ("required by skill/x@1"). Otherwise replace the manifest constraint for id with `pin.moved_to(target)`
   before resolving, apply, then write the manifest entry line (`WriteGuard(allow_manifest=True)`), only if the
   item was actually written.
4. Without `--major`, cross-line items show `major` lines only. Exit per report.

### 4.6 `add <id>[@pin] [--major]` (project-scoped)

1. Validate id grammar; `template/*` → exit 2; no tags for id → exit 2 "no released version of <id>".
2. Pin: explicit must match ≥1 release (else exit 2); else `default pin` (§3.4).
3. Already in manifest with same pin → just pull it. Different pin whose line differs from the installed line →
   require `--major` (exit 2 otherwise). Already a dependency-only lock item → becomes `source: manifest`.
4. Deprecated latest release → `deprecated` warning with successor (does not block).
5. Write manifest entry; `ensure_settings_keys` for declared settings **without a default** missing from the
   manifest (values `""`).
6. `resolve(mode="pull", ids={id})` → apply (pulls required tools). Unfilled → exit 1 with the settings list.

### 4.7 `remove <id> [--prune] [--force]` (project-scoped)

1. id must be in manifest (dependency-only → exit 2 "required by X; remove X instead").
2. If another installed item requires it → exit 1 `blocked` unless `--force`.
3. Drifted files → exit 1 `drift` ("use detach to keep your edits") unless `--force` (then deleted).
4. Remove manifest entry; delete item files; prune empty dirs; drop lock entry; resolve again: newly orphaned
   dependencies → with `--prune` deleted (if clean), else reported `orphan` and left installed (not updated).
5. Regenerate README. Exit 0/1.

### 4.8 `release <id> <major|minor|patch|initial> [--no-sync] [--message TEXT]` (warehouse)

```
1  git.is_clean_state() else exit 3; run lock acquired
2  lint_item(for_release=True); errors → exit 5 (print problems)
3  tags = C.versions(id); cur = frontmatter version
   level == initial: require no tags → new = cur
   else: require tags and max(tags) == cur (else exit 5 "frontmatter version X is not the latest tag Y")
         new = cur.bump(level); tag must not exist (exit 3)
4  unreleased = changelog.unreleased(text); require ≥1 bullet, except level=initial when a
   [cur] section already exists and Unreleased is empty (Phase-1 conventions)
5  new.major ≥ 2 and level == major: every bullet in Unreleased containing "BREAKING:" must contain
   "**Migration:**" (same bullet incl. indented continuation) and ≥1 BREAKING bullet exists → else exit 5
6  tool with tests/: python -m pytest <item>/tests -q -p no:cacheprovider, cwd = item dir,
   env PYTHONDONTWRITEBYTECODE=1; non-zero → exit 5, nothing modified
7  snapshot original bytes of main file, changelog file, 00_INDEX.md
8  edit: changelog.release_edit(text, new, today); frontmatter.set_scalar(version); if new == 1.0.0 from draft:
   set status canonical; write LF
9  lint again; failure → restore snapshot, exit 5
10 index regenerate with the pending release included
11 git.commit_only([item path, "00_INDEX.md"], f"release: {id}@{new}")   (env WAREHOUSE_RELEASING=1)
   failure → restore snapshot, exit 3
12 git.tag(f"{id}@{new}", f"{id} {new}"); failure → exit 3 with the exact manual command (commit kept)
13 unless --no-sync: invalidate catalog; run sync --auto logic in-process; write auto-sync.json
14 print release summary + sync report; exit 0 (1 if sync had skips)
```
`release` never pushes. Other staged changes in the warehouse are left staged and uncommitted (`--only`).

### 4.9 `check [--project PATH]` (read-only, all projects by default)

Warehouse section: `lint_item` for every item; malformed tags; tags whose content id/version mismatches;
warn "no tags found (git fetch --tags?)" when items exist but no tags. Profiles check: validates `profiles/*.yml`;
stale pins (pinned behind current release line) and deprecated items report `stale-pin` (info, exit 0); broken profile
entries (invalid entry syntax, invalid pin, unknown item id, or pin matching no released version) report `error`
(exit 1). Per project: `invalid-manifest`, drift, promoted, `compatible` (for manual projects), `outside-pin`, `major`,
`unfilled`, `deprecated`, `blocked`, `orphan`, `missing-tag` (lock version tag absent), `untracked` (files in target
not in lock, excluding README and temp files; info), `missing-software`, `platform`. Exit 0 if only info, else 1.

`software.check(entry)`: grammar `^(?P<name>[A-Za-z0-9_.-]+)\s*(?:(?P<op>>=|<=|==|>|<)\s*(?P<ver>\d+(?:\.\d+)*))?$`.
`python` → compare `sys.version_info`; else `shutil.which(name)`; if a version is required run
`[name, "--version"]` (timeout 5 s), first `\d+(\.\d+)+`; undeterminable → info "version unknown".
Platforms: `win32→windows`, `linux→linux`, `darwin→macos`.

### 4.10 `impact <id>`

Scan all projects; table `Project | auto_sync | Pin | Installed | Source (manifest / required by X) | Next
MAJOR would` (`report only`). Also list warehouse items whose latest release `requires` the id. Exit 0; unknown
id (no tags, not in working tree) exit 2.

### 4.11 `registry` / `index`

`registry`: scan projects, write `_registry/projects.md` (§2.7) atomically, no commit. `index`: regenerate
§2.8 regions, no commit. Exit 0 / 2.

### 4.12 Batch 2 commands

**`discard <id> [--yes] [--pull]`** — drifted (or promoted) item. Without `--yes`: print unified diff (disk vs
rendered lock version) and exit 10. With `--yes`: re-render **lock version** (tag must exist, else exit 3) with
current settings, write all files (bypassing drift), clear `promoted`, update hashes. `--pull` then runs `pull
<id>`.

**`promote <id> [--message TEXT] [--include-new] [--write-conflicts]`** — project-scoped, writes only the
warehouse working tree (+ project lock `state`).
```
1  item in lock, has drift (else exit 0 "nothing to promote"); V = lock version; tag V must exist (exit 3)
2  for each drifted file f (text = .md):
     T  = template bytes of f at tag V (placeholders intact)
     B  = rendered bytes at V with lock's settings (header with any date; strip header from both)
     D  = disk bytes, CRLF→LF, strip_header
     map lines: B and T have equal line counts (values contain no newlines); line i of B ↔ line i of T
     ops = difflib.SequenceMatcher(None, B_lines, D_lines, autojunk=False).get_opcodes()
     P = []  for equal: T[i1:i2]
             for replace: D[j1:j2] with reverse substitution: for each placeholder name n present in T[i1:i2],
                          replace occurrences of str(settings[n]) in these new lines with {{n}}
             for insert: D[j1:j2] literal; if any settings value occurs → warn "left literal, review"
             for delete: nothing
     non-.md files: P = D (no substitution happened)
3  ours = master working-tree bytes (LF-normalized); base = T; theirs = P
   ours == base → result = P ; else (merged, conflicts) = git.merge_file(ours, base, theirs)
   binary/non-UTF-8 and ours != base → conflict
4  new files in project item folder (not in lock, folder items): only with --include-new, copied verbatim;
   files deleted in project: reported, never deleted in master
5  any conflicts: without --write-conflicts write nothing, print conflicted hunks, exit 4;
   with it write merged-with-markers
6  write master files (warehouse working tree, atomic); append to changelog [Unreleased] under
   "Changed" (create the category heading at the right level if absent):
   "- Promoted from <project folder name>: <message or 'local edits to <files>'>"
7  print `git diff -- <item path>` output (read-only git in warehouse)
8  project lock: state = promoted, promoted = {from_version: V, files: current disk hashes}; exit 0
```
Sync skips promoted items quietly (`promoted` info line) until a newer version within the pin exists **and**
disk still equals `promoted.files`; then it overwrites and clears the state (§4.2). Disk changed after promote →
normal `drift`.

**`detach <id> [--force]`** — refuse (exit 1) if another installed item requires it, unless `--force`
(dependent becomes blocked). Strip header from main file (keeps content), remove lock entry and manifest entry
(dependency-only: lock only — but then refuse unless `--force`, since the requirer would re-pull it and
collide). Regenerate README. Files stay in place, now untracked; report "move out of <target> if you like".

**`template <id>[@version] <dest> [--set name=value ...]`** — `template/*` only; version default latest
release. Content from tag. Copies are clean (User decision 4): strip the warehouse frontmatter block
entirely and the trailing `## Changelog` section, then add a single first line
`<!-- from warehouse template <id> v<version> -->`. Substitute
declared placeholders from `--set`, then from the enclosing project's manifest settings if one is found;
unfilled ones stay literal with a warning. `<dest>` must not exist (exit 2); parent dir must exist. No lock,
no header, not tracked.

**`bootstrap [--write] [--include-drafts]`** — project-scoped (cwd, no manifest required).
Shared detection (`detect_project_types` in `discovery.py`): `vault` if `.obsidian/` directory exists; `codebase` if
any marker file (`package.json`, `pyproject.toml`, `requirements.txt`, `setup.py`, `go.mod`, `Cargo.toml`, `pom.xml`,
`tsconfig.json`, `deno.json`, `index.html`, `composer.json`, `Gemfile`, `build.gradle`) or glob (`*.csproj`, `*.sln`)
exists at root (both can be true). When nothing matches, prints `warehouse bootstrap: no vault or codebase markers found; assuming codebase`
and defaults to `codebase`. When types are detected and a profile's `applies-to` does not intersect them, warns to stderr
(also used by `warehouse profile apply`). Candidates: ids with a release, latest release `status: canonical` (drafts only with `--include-drafts`),
not deprecated, kind ≠ template, `applies-to ∩ types ≠ ∅`. Print the proposed manifest (items with default pins, `settings:` with `""` values
and description comments, `auto_sync: true`, `target: warehouse/`). `--write`: write `.warehouse.yml` only if absent
(exit 2 otherwise); never syncs. Exit 0.

### 4.13 `install-hook [--force]`

Hooks dir = `git rev-parse --git-path hooks` (warehouse). Copy `_tools/hooks/post-commit`,
`_tools/hooks/post-merge` (LF; User decision 5), `_tools/hooks/pre-push` and `_tools/hooks/commit-msg` (§4.14b). Per hook: existing file identical → "already installed";
different and no `--force` → exit 2 (nothing written); `--force` backs up to `<hook>.bak`. Ensure
`_tools/.state/` exists.

### 4.14 Hook `_tools/hooks/post-commit`

```sh
#!/bin/sh
# warehouse post-commit hook v2 — installed by `warehouse install-hook`
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX
mkdir -p "$root/_tools/.state" 2>/dev/null
log="$root/_tools/.state/hook.log"
stamp() { date '+%Y-%m-%dT%H:%M:%S' 2>/dev/null; }
if [ -n "$WAREHOUSE_RELEASING" ]; then
  echo "$(stamp) post-commit: skipped (release in progress; release runs its own sync)" >>"$log" 2>/dev/null
  exit 0
fi
if command -v python >/dev/null 2>&1; then py=python
elif command -v python3 >/dev/null 2>&1; then py=python3
else
  echo "$(stamp) post-commit: skipped (python not found)" >>"$log" 2>/dev/null
  exit 0
fi
echo "$(stamp) post-commit: sync --auto --if-new-tags" >>"$log" 2>/dev/null
"$py" "$root/_tools/warehouse.py" sync --auto --if-new-tags >>"$log" 2>&1
echo "$(stamp) post-commit: done (exit $?)" >>"$log" 2>/dev/null
exit 0
```
Every run appends timestamped lines to `_tools/.state/hook.log` (start, skip reason, or `done (exit N)`) so an idle run is distinguishable from a hook that never ran (added 2026-09-17). No loop: sync never commits. Cannot fail the commit (post-commit status is ignored; always `exit 0`). Fast when
no tags changed (one `for-each-ref`). Covers tags created by hand or fetched before a commit.

`_tools/hooks/post-merge` is the same script (header says `post-merge`). It runs after `git pull`/`git merge`
brings new commits, so release tags pulled from the remote trigger `sync --auto --if-new-tags`
(User decision 5). A `git fetch` or an "Already up to date" pull does not run it; the next commit's
post-commit hook, or a manual `warehouse sync`, covers that.

### 4.14b Hooks `_tools/hooks/pre-push` and `_tools/hooks/commit-msg` (added 2026-10-07)

`pre-push` blocks the push (exit 1) when:
1. `warehouse check --json` fails; or
2. a pushed commit changes `architecture/`, `protocols/`, `conventions/`, `skills/`, `tools/` or `templates/`
   and its subject does not start with `release: `. Item changes go through `warehouse release`.

Pushed commits come from the refs git passes on stdin: `<remote sha>..<local sha>` when the remote sha is known
locally, else `<local sha> --not --remotes=<remote>`. Ref deletions are skipped. Python missing → skip (exit 0).
`git push --no-verify` bypasses it.

`commit-msg` enforces `<type>(<scope>)?: <summary>` (types feat, fix, docs, style, refactor, perf, test, chore,
release; summary starts lowercase, 2–73 chars). Skips merge/revert/fixup/squash commits and commits made with
`WAREHOUSE_RELEASING` set (`release` and the test fixtures).

`.gitignore` additions: `_tools/.state/`, `warehouse.config.local.yml`, `__pycache__/`, `.pytest_cache/`
(`desktop.ini` is already ignored; `sync_exclude` and discovery skip it too).

### 4.15 Changelog module (`changelog.py`)

```python
@dataclass
class Section: name: str  # "Unreleased" | "2.1.0"
    date: str|None; start: int; end: int; body: list[str]   # line indices into text
parse(text, *, is_document: bool) -> list[Section]
    # document: last "## Changelog" heading OUTSIDE fenced code; levels 3 (version) / 4 (category)
    # CHANGELOG.md: "# Changelog"; levels 2 / 3
    # fences: toggle on lines matching ^\s*(```|~~~)
unreleased(sections) -> Section
entries_between(sections, low: Version, high: Version) -> list[Section]   # low < v <= high, newest first
breaking(section) -> list[str]         # bullets containing "BREAKING:" + indented continuation lines
release_edit(text, new: Version, today, is_document) -> str
    # replace Unreleased body with "" (heading kept, followed by one blank line), insert
    # "<hashes> [new] - today" + moved body directly after it
```

---

## 5. Dependency resolution rules

| Situation | Behaviour |
|---|---|
| Skill added/synced, requires `tool/t@1`, tool not installed | Installed as `source: dependency`, `required_by: [skill]`, pin `1`. |
| Tool already in manifest | Its manifest pin and the requirement pin must both match; the resolver picks the highest version matching all. |
| Skill's newest in-pin version needs a higher tool line than installed | Resolver picks the highest skill version whose requires are satisfiable; newest reported `blocked` with the `pull --major` hint. |
| Nothing satisfiable, skill not installed | `not-installable`. |
| Two skills require incompatible tool pins | Later-sorted skill `blocked`. |
| Skill removed, tool only used by it | Tool `orphan` (kept, not updated) unless `remove --prune`. |
| Remove/detach a required tool | Refused (exit 1) unless `--force`. |
| `pull tool/t --major` while a skill requires `@1` | `blocked`, exit 1. |
| Cycles in requires | Lint error at release; resolver pass cap → `error`. |

Resolution reads `requires` from the **tag** of the candidate version, never the working tree.

---

## 6. Safety invariants (enforced in code + tested)

| # | Invariant | Enforcement |
|---|---|---|
| I1 | Writes only inside target, `.warehouse.lock`, manifest (explicit commands), template dest (new file), warehouse working tree (release/promote/index/registry/hook install) | Every write/delete goes through `fsops` with a `WriteGuard`; `realpath` containment check; symlinked/junction target → error |
| I2 | Never runs git in a project | Only `gitrepo.Git` spawns git; raises GitError unless root == warehouse root (no bare assert); always `-C root`; strips `GIT_DIR`-family env |
| I3 | Never overwrites drifted files | `apply` inspects before writing; only `discard --yes` / `remove --force` bypass |
| I4 | Never auto-applies MAJOR or draft MINOR | `allowed()` line check in `sync`/`pull`; only `mode="major"` crosses lines |
| I5 | Never writes an item with unfilled placeholders | Render gate before journal; whole item skipped |
| I6 | Atomic writes, recoverable interruption | temp + `os.replace`; per-item `pending` journal; temp cleanup at start |
| I7 | Released content only from tags | `Catalog.files` is the sole content source for projects |
| I8 | Deprecated items are warned | `apply` + `status` + `check` emit `deprecated` |
| I9 | Sync never commits anywhere and never edits warehouse files | `sync` has no warehouse write path; only `release` calls `commit_only` |
| I10 | No partial item updates | Drift/collision/unfilled checks happen before any write of that item |

---

## 7. Edge cases

| Case | Decision |
|---|---|
| No `.warehouse.yml` (project command) | exit 2 "no .warehouse.yml found from <cwd> upward". |
| Invalid manifest during `sync` | `invalid-manifest` for that project, others continue, exit 1. |
| Unknown item id | add/pull/remove/impact: exit 2. Manifest entry in sync: `not-installable` "no releases". |
| Tag missing for lock version | Drift check still works (lock hashes). Updates to existing tags work. `discard`/`promote`/restore → `missing-tag` exit 3. |
| Non-warehouse files in target | Never touched; `check` reports `untracked` (info). Path clash with a new item file → `collision` unless adoptable. |
| Existing README.md in target without marker | `collision`; README not written; items still synced. |
| Synced file deleted by user | `missing` → restored on next sync/pull (same bytes as before), reported `restored` (user uses `detach`/`remove` to drop an item). User decision 2. |
| Entry deleted by hand from manifest | Next sync deletes the item's clean copies (`removed`); edited copies are kept, stay in the lock, and are reported `drift` on every sync until resolved. User decision 3. |
| Setting has a default, project doesn't set it | Default used; not unfilled. Adding a setting with a default is MINOR; adding one without is MAJOR. User decision 1. |
| File removed between versions | Deleted if clean; if drifted the whole item is skipped. |
| Renamed item (`replaces`) | No automatic migration. Projects on old id get `deprecated: replaced by <new>` with `add <new>` + `remove <old>` hint. Same target filename → `collision` until old removed. |
| Nested projects | Discovery continues into a project's subfolders except its target and `skip_dirs`. Outer target containing an inner project root → outer project `error` "target contains another project". Each project writes only its own target. |
| Lock deleted, copies remain | Files matching rendered content modulo stamp/EOL are `adopted`; others `collision`. |
| CRLF in project copies (autocrlf) | `eol-only` = clean; never rewritten for EOL alone; writes are LF. |
| CRLF in warehouse working tree | release/promote normalize to LF before parsing and writing. |
| Windows paths/case | Projects keyed by `os.path.normcase(os.path.realpath())`; lock keys `/`-separated as in the tag; case-collision lint; ids lowercase. |
| File locked by another process (Obsidian) | `os.replace` retried 3×; then `error` for that item, journal left `pending` (recovered next run). |
| Settings value changed | Items using it re-rendered (not a version change), subject to drift check; reported `updated` "settings changed". |
| Pin narrowed/widened by hand within line | `sync` never downgrades (reports `outside-pin`/keep); `pull` applies downgrade. |
| Pin moved to another line by hand | `sync`: `major` "pin changed; run pull <id> --major"; nothing written. |
| Draft-only item unpinned in manifest | `not-installable` "needs @0.MINOR pin". |
| Warehouse repo discovered under a project root | Always skipped. |
| Tag exists but tag content has different id/version | Ignored by catalog, `check` error. |
| Concurrent runs (hook + manual) | `run.lock`; hook exits silently when busy. |

---

## 8. Test plan (`_tools/tests/`)

**Fixtures (`conftest.py`):** `wh` — tmp git repo (local `user.name/email`, `commit.gpgsign=false`), folders,
`00_INDEX.md` with markers, `warehouse.config.yml` pointing `project_roots` at `tmp/projects`; helpers
`wh.write_item(id, version, body, settings={}, requires=[], files={})`, `wh.release(id, level)` (real command),
`wh.tag_raw(id, version)` (commit+tag shortcut). `project(name, manifest_text, git=True)` — fake project with
its own git repo and one commit. `run(*argv)` → `(exit_code, stdout)` calling `cli.main` with
`--warehouse/--config/--today`. `snapshot(root)` → `{relpath: sha256}`. `git_spy` — wraps `subprocess.run/Popen`
to record git invocations and cwd/`-C`. Tests never reference real paths; `conftest` asserts `WAREHOUSE_ROOT`
is under `tmp_path`.

| Test | Asserts |
|---|---|
| **semver / pins** | |
| `test_version_parse_strict` | rejects `1.0`, `01.2.3`, `1.2.3-rc1` |
| `test_pin_matching_levels` | `@2` takes 2.9.0 not 3.0.0; `@2.3` takes 2.3.1 not 2.4.0; exact takes nothing else |
| `test_draft_line_and_default_pin` | `0.3.2.line == (0,3)`; default pin for latest 0.3.2 is `0.3`; `@0` rejected |
| `test_bump_table` | §3.3 table incl. draft major → 1.0.0 |
| `test_pin_moved_to` | granularity preserved across lines, draft → canonical |
| `test_tag_name_is_valid_ref` | `git check-ref-format refs/tags/protocol/session-log@2.1.0` returns 0 |
| **formats** | |
| `test_manifest_defaults_and_validation` | defaults; unknown key, `@0`, dup id, template id, bool setting, `..` target rejected |
| `test_manifest_text_edit_preserves_comments` | add/replace/remove keep comments & order; flow style refused |
| `test_lock_roundtrip_deterministic` | save→load→save identical bytes; unknown lock_version refused |
| `test_frontmatter_set_scalar_only_in_frontmatter` | `version:` in body untouched |
| `test_changelog_ignores_fenced_examples` | conventions/warehouse-item.md parses the real changelog |
| `test_changelog_entries_between_and_breaking` | correct sections and BREAKING+Migration lines |
| `test_lint_rules` | one case per §2.2 code |
| `test_index_regenerates_only_marked_regions` | bytes outside markers unchanged; missing markers exit 2 |
| **catalog** | |
| `test_catalog_reads_tag_not_working_tree` | edit working tree after tag; synced bytes equal tag content |
| `test_old_pinned_version_gets_exact_tag_content` | exact pin 1.0.0 receives 1.0.0 bytes while 1.1.0 exists (§8 History) |
| `test_malformed_tag_ignored_and_checked` | |
| **sync** | |
| `test_sync_installs_with_header_and_lock` | header text exact, after frontmatter; lock hashes = written bytes; LF |
| `test_sync_auto_updates_minor_patch_in_pin` | |
| `test_sync_auto_skips_manual_projects` | manual project unchanged; status shows update (§8 Propagation) |
| `test_sync_explicit_project_ignores_auto_sync_false` | |
| `test_major_never_auto_applied` | 3.0.0 released; no project changes; report `major` (§8 MAJOR) |
| `test_draft_minor_never_auto_applied` | `@0.2` doesn't get 0.3.0 |
| `test_canonical_pin_never_selects_draft` | |
| `test_pin_levels_minor_and_exact` | `@2.3` gets 2.3.1 not 2.4.0; exact gets nothing (§8 Pins) |
| `test_unfilled_placeholder_blocks_item` | file not written, `unfilled` listed, exit 1; other items still written |
| `test_undeclared_placeholder_left_literal` | |
| `test_placeholders_only_in_md` | `{{x}}` in `.py` untouched |
| `test_settings_change_rerenders` | |
| `test_drift_skipped_and_reported` | edited copy untouched, exit 1 (§8 Drift) |
| `test_crlf_only_change_is_not_drift` | |
| `test_deleted_file_restored` | |
| `test_removed_file_between_versions_deleted_if_clean` | and empty dirs pruned, target root kept |
| `test_collision_with_untracked_file` / `test_adopt_matching_untracked_file` | |
| `test_readme_generated_and_foreign_readme_collision` | |
| `test_tool_tests_dir_never_copied` | |
| `test_hand_removed_manifest_entry_removes_clean_copy` | |
| `test_deprecated_item_warned` | |
| `test_invalid_manifest_does_not_stop_other_projects` | |
| `test_nested_projects_and_skip_dirs_and_depth` | node_modules/.claude/worktrees skipped; warehouse root skipped |
| `test_if_new_tags_noop_when_unchanged` | no output, no writes |
| `test_run_lock_busy` | `--auto` exit 0; manual exit 3 |
| **invariants** | |
| `test_writes_confined_to_target_lock` (parametrized over sync/pull/add/remove/discard/detach) | snapshot diff ⊆ target/** ∪ lock ∪ (manifest if allowed) |
| `test_no_git_in_projects` (all commands) | `git_spy` sees only warehouse `-C`; project HEAD, refs, index unchanged (§8 No commits) |
| `test_write_guard_rejects_escape` | `../`, absolute, junction/symlink target |
| `test_interrupted_apply_recovers` | monkeypatch `os.replace` to raise mid-item; next sync: no drift, completes, no temp files |
| `test_git_env_vars_stripped` | with `GIT_DIR` set to a project repo, catalog still reads warehouse |
| **status / pull / add / remove** | |
| `test_status_shows_compatible_major_and_changelog` | BREAKING + Migration text shown |
| `test_pull_manual_project_within_pin` / `test_pull_all` | |
| `test_pull_major_shows_breaking_moves_pin` | manifest line changed, comments kept |
| `test_pull_downgrades_to_narrowed_pin` | |
| `test_add_unpinned_records_current_major` / `test_add_draft_records_zero_minor` | |
| `test_add_writes_missing_settings_keys` | |
| `test_add_skill_pulls_required_tool` | (§8 Tools) |
| `test_skill_blocked_when_tool_major_needed` | skill kept at old version, hint shown |
| `test_remove_orphans_tool_and_prune` | |
| `test_remove_refuses_drift_and_required` | |
| **release** | |
| `test_release_minor_moves_unreleased_bumps_commits_tags` | only item + index in commit; other staged file still staged; tag annotated |
| `test_release_requires_nonempty_unreleased` | exit 5 |
| `test_release_major_requires_breaking_and_migration` | |
| `test_release_runs_tool_tests_and_aborts_on_failure` | files unmodified, no commit |
| `test_release_initial_for_phase1_items` | |
| `test_release_draft_major_sets_canonical` | |
| `test_release_triggers_sync_and_hook_noops` | hook installed; one sync run; auto-sync.json updated |
| `test_release_restores_files_on_commit_failure` | |
| **check / impact / registry / hook** | |
| `test_check_reports_all_categories` | drift, compatible, major, unfilled, deprecated, missing software, platform, orphan, missing-tag |
| `test_impact_lists_projects_and_dependents` | |
| `test_registry_generated` | |
| `test_install_hook_idempotent_and_force_backup` | |
| `test_hook_script_manual_tag_then_commit_syncs` | runs real `git commit` with hook; project updated |
| **batch 2** | |
| `test_discard_requires_yes_then_restores` | exit 10 then clean |
| `test_promote_reverse_substitutes_only_mapped_lines` | value in untouched line not replaced; replaced line with placeholder restored; inserted literal warned |
| `test_promote_merges_with_unreleased_master_edits` | non-overlapping edits merged |
| `test_promote_conflict_exit4_no_write` / `..._write_conflicts` | |
| `test_promote_folder_item_include_new` | |
| `test_promote_marks_lock_then_release_propagates` | promote → release → sync overwrites the promoting project and updates others (§8 Drift) |
| `test_promoted_then_edited_again_is_drift` | |
| `test_detach_strips_header_removes_entry` / `test_detach_refuses_required` | |
| `test_template_strips_item_frontmatter_and_changelog` / `test_template_refuses_existing_dest` | |
| `test_bootstrap_proposes_by_type_and_write_only_if_absent` | |

---

## 9. Build order

**Batch 1 — core + propagation** (independently testable with the batch-1 tests):
1. `errors`, `semver`, `frontmatter`, `items` (+ lint), `changelog` → unit tests.
2. `gitrepo`, `catalog`, `config`, `discovery`, `manifest`, `lockfile`, `fsops`, `render`, `inspect`, `report`.
3. `resolve`, `apply`, `readme`.
4. Commands: `sync`, `status`, `pull`, `add`, `remove`, `check`, `impact`, `registry`, `index`, `release`,
   `install-hook`; `cli`; wrappers; `hooks/post-commit`; `warehouse.config.yml`; `.gitignore` additions;
   markers in `00_INDEX.md`.
5. Invariant tests (I1–I10) run against every batch-1 command.

**Batch 2 — drift resolution + onboarding:** `merge`, `software` extensions if needed, commands `promote`,
`discard`, `detach`, `template`, `bootstrap`; add them to the parametrized invariant tests; README
"Commands" table updated to say built.

---

## User decisions (2026-09-14)

| # | Decision | Where it changes this design |
|---|---|---|
| U1 | **Settings may have defaults.** A `settings` entry is either a string (description; required) or a mapping `{description: ..., default: ...}`. Projects that don't set it get the default; only settings with no default and no project value are unfilled. Adding a setting **with** a default is MINOR; adding a required one is MAJOR. | §1 `Setting`, §2.2 `settings` lint, §2.3 effective value and `ensure_settings_keys`, §4.2 unfilled gate, §4.6 step 5, §7 |
| U2 | **A deleted synced file is restored** on the next sync (the item is still in the manifest). | §4.2 keep branch, §7 |
| U3 | **An entry removed from the manifest by hand:** sync deletes the item's unedited copies; edited copies are kept and reported. | §4.2 remove branch, §7 |
| U4 | **`template` copies are clean:** strip the warehouse frontmatter and the `## Changelog` section; add a single first line naming the source template id and version. | §4.12 `template` (batch 2) |
| U5 | **Ship a warehouse `post-merge` hook** alongside post-commit, installed by `install-hook`, so a `git pull` that brings new release tags runs `sync --auto --if-new-tags`. | §1 layout, §4.13, §4.14 |

---

## Batch-1 review fixes (2026-09-14)

Behaviour changed after the Reviewer's pass. Each has a regression test in `tests/test_regressions.py`.

| # | Change | Section |
|---|---|---|
| R1 | Journal keeps `pending.accepted` hashes across interrupted generations (no false drift after two interruptions). | §2.4, §4.2 |
| R2 | `apply` catches **any** exception per item and `sync` per project → `error`, run continues. `GuardError` is a `WarehouseError` (code 1), not an `AssertionError`. | §1, §4.2, §4.3 |
| R3 | Lint code `encoding`: every `.md` in an item must be UTF-8 (release refuses). Rendering an undecodable `.md` from a tag is a per-item `error`. | §2.2, §4.2 |
| R4 | `allowed()` in mode `major`: the named ids **and their installed dependency closure** may move to a higher line. `pull <id> --major` resolves in major mode even when `<id>` has no higher line (its dependency may). `pull <dep> --major` on a dependency-only item is refused only if a requirer that is not also being pulled rejects the target ("pull the requiring item with --major instead"). Hints for blocked items and dependency-only `major` lines name the requirer. Identical report lines are printed once. | §4.1, §4.5 |
| R5 | `release`: before committing, snapshot the index entries of the commit paths (`ls-files -s`); on commit failure restore the files **and** the index (`rm --cached -f` + `update-index --index-info`). | §4.8 step 11 |
| R6 | Same-line pin narrowing in `sync` → keep + `outside-pin` with plain `pull` advice (not `major`); kept items keep their requires. | §4.1 |
| R7 | On case-insensitive filesystems (Windows, macOS) target paths are compared case-folded: a case-only rename between versions is not a collision; the old spelling is deleted (if clean) before the new file is written. | §4.2 |
| R8 | Hand-removed entry / `remove` delete every tracked path, incl. files only in the pending journal. | §4.2, §4.7 |
| R9 | `replaces` lint: archived ids are read from frontmatter of `_archive/**/*.md` and matched exactly. | §2.2 |
| R10 | I2 check raises `GitError` (no bare `assert`; survives `python -O`). | §6 |
| R11 | `auto-sync.json` gains `needs_retry` (true if the run reported `error` or left any `pending` journal); `--if-new-tags` only no-ops when the digest is unchanged **and** `needs_retry` is false. A persistent error therefore re-runs sync on every hook call until fixed. | §4.3 |
| R12 | `software.check` searches absolute PATH entries only (never the current directory; PATHEXT on Windows). | §4.9 |
| R13 | Temp cleanup matches only the exact temp pattern and also covers `.warehouse.yml` temps. | §1 fsops |
| R14 | `apply`: an install/update/downgrade whose required item ended `unfilled`/`collision`/`error`/`missing-tag` in this run is `blocked` and not written. | §4.2 |
| R15 | `add --major` resolves against the new entry in memory and writes the manifest only if the item was written on the new line (same rule as `pull --major`). | §4.6 |
| R16 | Keep shortcut: a missing file is restored only if re-rendering reproduces its lock hash; otherwise `error` "cannot restore". | §4.2 |
| R17 | `remove` (and sync's orphan handling) drop requirers that are no longer installed from an orphan's `required_by`. | §4.7 |
| R18 | Discovery skips **linked git worktrees** (a `.git` file whose `gitdir:` points into `.../worktrees/...`), whatever the folder name; they are neither projects nor descended into. Refs named `desktop.ini` (Google Drive) are ignored when listing tags. | §2.1 |
| R19 | `apply` processes actions in dependency (topological) order, treating dependency cycles as error. | §4.2 |
| R20 | Requirers are blocked if their required item's resulting lock version does not match the constraint pin (catches drifted dependencies stuck on older versions). | §4.2 |
| R21 | `apply` major hint explicitly names the constraining requirer item (instead of an arbitrary one). | §4.2 |
| R22 | `apply` logs tracebacks for unexpected errors if --verbose, and appends them to .state/hook.log. | §4.2 |
| R23 | Case-insensitivity is determined by probing the target filesystem instead of assuming based on the OS. | §4.2 |
| R24 | check reports projects stuck in retry (`auto-sync.json` has `needs_retry`: true or pending journal entries). | §4.9 |
