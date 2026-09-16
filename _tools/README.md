# Warehouse tool

Syncs released warehouse items into projects. Design: [[DESIGN]]. Python 3.12 + PyYAML; tests use pytest.

## Run it

From Git Bash (`_tools/warehouse`), cmd/PowerShell (`_tools\warehouse.cmd`) or directly:

```sh
python _tools/warehouse.py sync --auto          # all auto_sync projects under the configured roots
python _tools/warehouse.py status --project C:/projects/my-vault
python _tools/warehouse.py release protocol/session-log minor
```

- Project commands (`status`, `pull`, `add`, `remove`) use the current directory, or `--project PATH`.
- `--json` prints a machine-readable report. Exit codes: 0 ok, 1 skipped items/issues, 2 usage or
  manifest error, 3 git error or missing tag, 5 release checks failed.
- Project roots, depth and skip-dirs are in `warehouse.config.yml` at the warehouse root. Per-machine
  overrides of `project_roots` / `max_depth` go in `warehouse.config.local.yml` (gitignored).
- The tool never commits in a project and writes only the project's target folder and
  `.warehouse.lock` (plus `.warehouse.yml` for `add`, `remove`, `pull --major`).

## Install the hooks

```sh
python _tools/warehouse.py install-hook          # add --force to replace (old hook saved as .bak)
```

Installs `post-commit` and `post-merge` from `_tools/hooks/` into the warehouse repo. Both run
`sync --auto --if-new-tags`, which does nothing unless release tags changed. Output goes to
`_tools/.state/hook.log`. `release` syncs by itself and the hooks skip its commit.

## Run the tests

```sh
python -m pytest _tools/tests -q                 # from the warehouse root
```

Tests build throwaway warehouse repos and fake projects under pytest's `tmp_path`. They never touch real
projects. The suite takes a few minutes on Windows (it runs many real git commands).

## Commands

See [[cli-reference]] in `reference/` for the complete reference guide and option breakdown.

| Command | Batch | Status |
|---|---|---|
| `sync [--auto] [--if-new-tags] [--include-manual] [project]` | 1 | built |
| `status` | 1 | built |
| `pull <id> \| --all [--major]` | 1 | built |
| `add <id>[@pin] [--major]` / `remove <id> [--prune] [--force]` | 1 | built |
| `release <id> <major\|minor\|patch\|initial> [--no-sync]` | 1 | built |
| `check`, `impact <id>`, `registry`, `index` | 1 | built |
| `install-hook [--force]` | 1 | built |
| `promote`, `discard`, `detach`, `template`, `bootstrap` | 2 | built |
| `profile <list\|show\|save\|delete\|apply>` | 2+ | built |
| `request`, `issue`, `inbox <list\|show\|resolve\|reject\|triage>` | 2+ | built |

`index` needs the `<!-- warehouse:catalog:start/end -->` and `<!-- warehouse:releases:start/end -->`
markers in `00_INDEX.md` (so does `release`, which regenerates the index).
