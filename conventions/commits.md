---
id: convention/commits
version: 0.1.1
status: draft
summary: Git commit message and execution standard for agents and humans.
applies-to: [codebase, vault, warehouse]
settings: {}
requires: []
replaces: null
---

# Commit Standards and Post-Change Workflow

Standardized git commit format, repository hygiene invariants, and post-change execution workflow
for AI agents and human contributors.

Related conventions and protocols: [[agent-protocol]], [[safe-write]], [[changelog]].

## 1. Commit Message Format

Commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```text
<type>(<scope>): <summary>

[optional body]

[optional footer(s)]
```

### 1.1. Summary Line Rules
- **Imperative mood:** Write in the imperative mood ("add", "fix", "refactor", not "added", "fixes", "refactoring").
- **Lowercase start:** The summary begins with a lowercase letter unless capitalized by proper noun or acronym.
- **No trailing period:** Do not put a period at the end of the summary line.
- **Length limit:** Keep the summary line within 72 characters.
- **Scope (optional):** A noun describing the section of the codebase (e.g. `feat(parser): ...`, `fix(auth): ...`).

### 1.2. Allowed Types

| Type | Purpose | Example |
|---|---|---|
| `feat` | A new user-visible feature or capability. | `feat(store): add blob dedup via content sha256` |
| `fix` | A bug fix or correction to unintended behavior. | `fix(session): correct transcript path resolution` |
| `docs` | Documentation changes only (markdown, docstrings). | `docs(api): document rate limit error responses` |
| `style` | Formatting, whitespace, or code style changes (no logic change). | `style(lint): fix indentation in config template` |
| `refactor` | Code restructuring that neither fixes a bug nor adds a feature. | `refactor(broker): split socket dispatch from handshake` |
| `perf` | A code change that improves execution performance. | `perf(cache): batch embedding lookups` |
| `test` | Adding missing tests or correcting existing tests. | `test(claims): add race condition coverage for worktrees` |
| `chore` | Maintenance tasks, tool configuration, dependency bumps. | `chore(deps): bump tectonic to 0.15.0` |

### 1.3. Breaking Changes
Mark breaking changes by adding an exclamation point before the colon (`feat(api)!: drop v1 endpoints`)
or including `BREAKING CHANGE:` in the body footer with explanation and migration instructions.

---

## 2. Commit Atomicity and Quality

1. **Single conceptual change:** Each commit should encapsulate a single logical change. Do not bundle
   unrelated refactorings, doc edits, and bug fixes into a single omnibus commit.
2. **Build integrity:** Every commit must leave the repository in a working, buildable state with tests
   passing (see [[testing]] for what "tests green" means). Never commit broken intermediate states.
3. **Bisectability:** Commits should be granular enough that `git bisect` can isolate the exact change
   introducing a defect.

---

## 3. Hygiene and Containment Invariants

Cleanliness is a non-negotiable security and audit boundary:

1. **Never commit secrets:** Never stage or commit API tokens, private keys, passwords, database
   credentials, or local environment files (`.env`, `id_rsa`, `KEY.txt`, `*.token`).
2. **Never commit OS artifacts:** Ensure `desktop.ini`, `.DS_Store`, `Thumbs.db`, and temporary editor
   swap files (`*.swp`, `*~`) are never added to version control.
3. **Never commit build or runtime scratch:** Scratch directories (`scratch/`, `tmp/`, `.cache/`,
   `__pycache__/`) and local build artifacts must be excluded.
4. **Never blind-add (`git add .` / `git add -A`):**
   - Always run `git status` and `git diff --cached` before committing.
   - Stage explicit files or paths (`git add <file1> <file2>`).
   - If using `git add -A`, immediately inspect staged files to verify no unwanted binaries, OS
     metadata, or secrets were caught.

---

## 4. Post-Change Commit Workflow for Agents

Following any change in a repository, agents must follow this structured lifecycle:

### Step 1: Verify Code and Changes
- Run automated unit tests, linters, and verification checks (see [[testing]] for what "tests green" means).
- For warehouse items, run `python _tools/warehouse.py check`.
- Verify that changes meet the acceptance criteria of the task.

### Step 2: Update Working Memory and Documentation
- If architecture, schemas, API contracts, or settings changed, update corresponding documentation
  or technical specifications.
- If gotchas, environmental quirks, or unexpected behaviors were encountered, document them.
- If warehouse items changed, record modifications under `### [Unreleased]` in the item's changelog
  per [[changelog]].

### Step 3: Review Staged Changes
- Check working tree status: `git status`
- Review the staged diff: `git diff --cached` (or `git diff`)
- Verify no stray, unintended, or secret files are present.

### Step 4: Decision — Commit, Stage, or Request Review

| Situation | Action |
|---|---|
| Routine, well-scoped change satisfying an approved task with green tests. | **Commit locally** with conventional commit message. |
| Changes requiring human verification, visual UI confirmation, or user preference choices. | **Stage changes** (or leave unstaged) and request user review. |
| High-risk operations touching credentials, production infrastructure, or breaking API changes. | **Do not commit unilaterally**; present the plan and diff for explicit human sign-off. |

### Step 5: Push Policy
- **Never push to remote (`main` or production) without explicit instruction.**
- Commits remain in the local branch or worktree until the human collaborator approves a push,
  or until an automated pipeline specifically gates remote integration.

---

## Changelog

### [Unreleased]

### [0.1.1] - 2026-11-08
#### Changed
- Linked [[testing]] in §2 (Build integrity) and §4 Step 1 for what "tests green" means.

### [0.1.0] - 2026-09-15
#### Added
- Initial draft of the git commit and post-change workflow convention.
