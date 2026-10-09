# AGENTS.md — rules for working on the warehouse

These rules are for AI agents working **on this warehouse repo**. They are not rules for other
projects.

## Purpose and scope

The warehouse stores reusable agentic items, versions them, lets projects choose items through a
manifest, and propagates releases to those projects.

It is responsible for: the warehouse structure, what goes into it, how items are managed and
versioned, how projects choose and pull items, and how updates reach projects.

**Out of scope:** how AI agents inside a project gather or load context. That is each project's own
business. Do not add items or notes about it.

## Read first

1. `README.md` — what the warehouse is and how it is laid out.
2. `00_INDEX.md` — what items exist, their versions and status.
3. The plan, `docs/warehouse-architecture.md`, when the task touches structure or process.

## Items

- **Edit items only here.** Project copies are outputs, never sources.
- Every item follows [[warehouse-item]] (frontmatter, folders, placeholders),
  [[versioning]] (SemVer) and [[changelog]] (Keep a Changelog).
- Put each item in the folder for its kind. Scripts go in `tools/` unless they are a small helper
  that means nothing outside one skill.
- `docs/`, `case-studies/` and `reference/` are documentation and notes, not items. They are never synced.

## Changes and releases

- **Never modify a released version.** Record every change under `[Unreleased]` in the item's
  changelog. It is released later with a SemVer bump.
- **MAJOR** changes must mark each breaking change `BREAKING:` and give `**Migration:**` steps.
- **Drafts are `0.x.y`.** An item becomes `1.0.0` only when it is canonical.
- **Deprecate, don't delete.** Set `status: deprecated`, name the replacement, keep the item until no
  project uses it, then move it to `_archive/`.
- **Ask the user before anything that changes an item's contract** (format, required steps,
  structure, setting names, placeholders, tool commands/arguments/output/behaviour).
- **Release only with `warehouse release <id> <major|minor|patch|initial>`.** Never hand-edit
  `version:` or create tags yourself; the command bumps the version, finalizes the changelog, commits
  and tags.

## Other projects

- **Never write inside another project, and never commit there.**
- Only the future sync tool writes to projects, and only to their `warehouse/` target folder and
  `.warehouse.lock`. It never commits in projects either.

## Housekeeping

- **Agent Workflow**: Agents working on the warehouse should run `warehouse inbox list` (or check `_inbox/`) at the start of a session to identify open requests/issues, and use `warehouse inbox triage <ticket_id>` to move them to the backlog. A ticket is resolved or
  rejected only after its `BACKLOG.md` entry has moved to Completed or the Icebox. It is never
  resolved straight from the inbox.
- **Tickets come from outside.** Inbox tickets are filed by agents working in other projects. When you
  find a problem while working in the warehouse, fix it directly (asking first if it changes an item's
  contract) instead of filing a ticket.
- **No secrets** in the warehouse: no tokens, keys, passwords or personal credentials, in items,
  settings examples or notes.
- **Keep `00_INDEX.md` current** when you add, release, deprecate or archive an item. Regenerate the
  catalog with `warehouse index` (`release` does this automatically).
- Use `[[wikilinks]]` by note filename for internal links.
- Write plainly: short sections, tables where they help, concrete examples.
