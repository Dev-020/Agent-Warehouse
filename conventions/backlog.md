---
id: convention/backlog
version: 0.2.0
status: draft
summary: Project backlog in four levels (single file, split files, item folders, external tracker), with two entry styles, severity and likelihood, dependencies, evidence-based acceptance and append-only history.
applies-to: [vault, codebase]
settings:
  backlog_layout:
    description: "Backlog layout: 'single' (one file), 'split' (a folder of files), 'folders' (one file or folder per item) or 'tracker' (an external issue tracker)"
    default: "single"
  backlog_file:
    description: "Path to the backlog file when backlog_layout is 'single'"
    default: "BACKLOG.md"
  backlog_dir:
    description: "Path to the backlog folder when backlog_layout is 'split', 'folders' or 'tracker'"
    default: "BACKLOG"
requires: []
replaces: null
---

# Backlog Convention

How a project records its tasks, bugs, technical debt and findings, so that people and AI agents can
read and update the same backlog. The backlog is the project's list of what to do next: an agent that
can't find it can't tell where the project should go.

**This project:** layout `{{backlog_layout}}`. A single-file backlog lives in `{{backlog_file}}`. Every
other layout keeps its files in `{{backlog_dir}}/`.

## How strict is this?

This convention is a framework, not a fixed implementation. A project may follow it word for word or
change parts of it, as long as the core is there.

| Every backlog keeps (the core) | A project may change |
|---|---|
| A header saying how the backlog is run (§3) | Section, file and folder names, and their emoji |
| Stable IDs that are never reused | The ID format and prefixes |
| A clear split between open and closed items, with a status on each | Status names, if the header maps them to the ones in §4.2 |
| A priority on every open item | Priority names, if the header maps them to P1–P3 |
| Evidence before a criterion is ticked or an item is closed | Entry style details: headings, field names, extra fields |
| Nothing deleted. Corrections are dated notes. | Whether to use severity, likelihood, dependencies and parents |
| One source of truth | The review interval, the ordering rules, the size thresholds |

**Write every change in the header** (its `Deviations` line), so an agent reading the backlog follows
the project's version instead of this text. Where the header and this convention disagree, the header
wins.

---

## 1. Levels

A backlog can be run at four levels. Each one adds structure for a specific problem. A project starts
at Level 1 and moves up only when it has that problem. It can move back down when the problem goes away
(§9).

| Level | Layout | What it is for | Move here when |
|---|---|---|---|
| **1. Single file** | `single` | Everything in one place. Cheap to start and to read. | Default for every new backlog. |
| **2. Split files** | `split` | Keeps the files agents read every session short, while history keeps growing. | The file passes about 75 KB, or Completed and Icebox are more than half of it, or agents keep loading old history just to find open work. |
| **3. Item folders** | `folders` | One file or folder per item. Agents list the folder instead of reading a long file, and a task keeps its plan, evidence and scripts beside it. | Tasks need plans, measurements or attachments, or open tasks are too long to read together, or several agents keep editing the same backlog file. |
| **4. External tracker** | `tracker` | A hosted issue tracker becomes the source of truth. | Other people report or follow issues, the project is public, work is spread across machines, or open items reach the hundreds and need filtering. |

**Who may write** (§6) is a separate choice: by hand, one named writer, or a backlog tool only. Levels
1–3 can use any of the three. At Level 4 the tracker plays that role.

---

## 2. Layouts

### 2.1. Single file (`single`)

One file, `{{backlog_file}}`, with these sections in this order:

```markdown
# Project Backlog

<!-- Header: see §3 -->

## 📋 In Progress

## 📌 Backlog (Open Tasks)

## ✅ Completed

## 🧊 Icebox (Not Doing / Rejected)

## 🔎 Findings Register
```

The Findings Register (§8) is optional. The other four sections are always present, even when empty.

### 2.2. Split files (`split`)

A folder, `{{backlog_dir}}/`, holding the same sections spread over files by how often they are read:

| File | Holds | Read |
|---|---|---|
| `00_BACKLOG.md` | The header (§3). Optionally a generated task map (§7.7). | First, every time |
| `Open.md` | `## 📋 In Progress` and `## 📌 Backlog (Open Tasks)` | Every session |
| `Closed.md` | `## ✅ Completed` and `## 🧊 Icebox (Not Doing / Rejected)` | Only when history is needed |
| `Findings.md` | The Findings Register (§8). Optional. | When relevant |

- **The Icebox belongs in `Closed.md`.** A rejected or cancelled task is a closed task that was never
  started.
- **`Closed.md` is append-only.** Entries are added at the bottom of their section and never edited
  afterwards, except to correct a broken link.
- **Add `merge=union` for `Closed.md` only.** When two branches each add an entry at the end of a
  section, git would normally report a conflict. A union merge keeps both. Put this line in the
  project's `.gitattributes`:
  ```
  {{backlog_dir}}/Closed.md merge=union
  ```
  Never add `Open.md`, `00_BACKLOG.md` or any prose file. On a file that gets edited rather than
  appended to, a union merge quietly interleaves two versions of the same paragraph.
- Entries use the same format as the single layout. Only the place each entry lives changes.

### 2.3. Item folders (`folders`)

Each item is its own file, or its own folder when it has supporting files. Where an item sits tells you
whether it is open or closed. Its frontmatter tells you the rest.

```
{{backlog_dir}}/
├── 00_BACKLOG.md                       header (§3)
├── open/
│   ├── 042-overlay-idle-repaint/       a full item with supporting files
│   │   ├── 042-overlay-idle-repaint.md     main file
│   │   ├── plan.md
│   │   ├── evidence/
│   │   │   └── idle-cpu-before-after.txt
│   │   └── measure_repaints.py
│   └── 051-ready-tasks-cost.md         a small item: one file
├── closed/
│   ├── 018-resource-trims/
│   └── 026-prompt-bar-visuals-through-mcp.md
└── Findings.md                         Findings Register (§8), optional
```

**Names**
- An item is named `<ID>-<slug>`: the ID without brackets or `#` (`#042` → `042`, `INF-45` → `INF-45`),
  then a short slug of the title in lowercase with hyphens.
- The name is fixed when the item is created. A later change of title changes only the `title` field,
  never the name, so links keep working.
- A folder's main file has the same name as the folder, plus `.md`. The name is unique, so wikilinks
  resolve, and it follows Obsidian's folder-note convention.

**One file or a folder**
- An item starts as one file. It becomes a folder when it gets its first supporting file: create the
  folder and move the file into it, keeping its name.
- This matches the entry styles (§5). Compact items usually stay one file. Full items often become
  folders.

**The main file**
- Starts with YAML frontmatter (§4.5), then a title heading, then the body in the project's entry
  style. Headings move up two levels from the single-file format: `# [#042] Title`, then `## Why`,
  `## Wanted` and so on.
- Lists every supporting file under a `## Files` heading, with one line saying what each one is.

**Supporting files**
- Plans, evidence, screenshots, logs, probe scripts, anything that explains or proves the item.
- Keep them small. Don't commit large outputs (dumps, recordings, anything over about 1 MB). Say where
  they are or how to regenerate them.
- No secrets: no tokens, keys, passwords or personal data.
- A script says how to run it, in its first lines and in `## Files`. A script that turns out useful
  beyond its task moves to the project's tools folder, and the item links to it there.

**Open and closed**
- `open/` holds items with status `Open` or `In Progress`. Claiming a task changes its status. It doesn't
  move.
- `closed/` holds items with status `Closed`, `Rejected` or `Cancelled`. Closing an item moves its file or
  folder from `open/` to `closed/` unchanged, apart from its status, its `resolved` date and its
  Outcome.
- **An item never moves back to `open/`.** If the problem returns, open a new item that links to the old
  one.
- An idea rejected at triage can be written straight into `closed/` with status `Rejected`.

**Finding things**
- `open/` is the list of open work. An agent lists it, picks an item and opens only that one.
- Priority, status and dependencies are in the frontmatter, so one search answers "which items are P1"
  (for example `grep -l "priority: P1" -r {{backlog_dir}}/open`).
- Don't keep a hand-written index of items: it drifts. A backlog tool may generate one (§7.7).
- Refer to items by ID. In a vault, wikilinks to a main file survive the move to `closed/`. In a code
  repository, a relative path into `open/` breaks when the item closes.

**No `merge=union`.** Every item is its own file, so two branches only conflict when they change the same
item.

### 2.4. External tracker (`tracker`)

A hosted issue tracker (for example GitHub Issues, GitLab Issues or Linear) holds the open and closed
items. The repository keeps `{{backlog_dir}}/00_BACKLOG.md`, with the header (§3), and optionally
`Findings.md`.

| This convention | In the tracker (GitHub as the example) |
|---|---|
| ID | The issue number. Write it as an imported ID (`[GH-128]`) wherever text refers to it. |
| `Open` / `In Progress` | An open issue. In Progress is an assignee, or a status field on a project board. |
| `Closed` | Closed as completed |
| `Rejected` / `Cancelled`, the Icebox | Closed as not planned, with the reason in the closing comment |
| Priority, severity, likelihood, labels | Labels (`priority:P1`, `severity:major`). On GitHub, issue fields and issue types are organisation features, so a personal account uses labels. |
| Why, Wanted, Acceptance Criteria | An issue template with those headings. Criteria become a task list. |
| Notes | Comments, which are append-only by nature |
| Outcome | The closing comment, linking the commits or pull request |
| Depends on, Parent | "Blocked by" links and sub-issues |
| Findings Register | Stays in the repository as `Findings.md`. Trackers have no good place for gaps that are known and accepted. |

- **One source of truth.** Never keep the tracker and Markdown files up to date by hand side by side.
  If agents need a file, generate a read-only export and mark it generated (§7.7).
- The header says which tracker and where it is, and which labels stand for priority, severity and
  likelihood.
- Agents use the tracker's command-line tool or API. They don't edit files to change an item.
- A claim is an assignee plus a branch named after the issue.
- The evidence rule (§4.7) doesn't change: a criterion is ticked only on evidence, cited in a comment.

---

## 3. The Header

Every backlog starts by saying how it is run. In a single file the header goes under the title. In
every other layout it is `00_BACKLOG.md`. Anyone opening the backlog reads the rules where the work
happens.

```markdown
> **How this backlog is run** (`convention/backlog`)
> - **Layout:** single file
> - **IDs:** `[#NNN]`, allocated as the highest existing number + 1, never reused
> - **Entry style:** full
> - **Writes:** by hand, one writer at a time
```

| Line | Values |
|---|---|
| Layout | `single file`, `split files`, `item folders`, or `external tracker: <tracker and location>` |
| IDs | The scheme from §4.1. With prefixes, add a table of prefixes and their meaning below the header. |
| Entry style | `full`, `compact`, or `full and compact` (§5) |
| Writes | `by hand, one writer at a time`, `by <named writer> only`, or `through <tool> only` (§6) |
| Extra fields | Optional. Any metadata the project adds to entries (e.g. `**Item**`, `**Project**`). |
| Labels | External tracker only: which labels stand for priority, severity and likelihood. |
| Deviations | Optional. Where this backlog differs from the convention, e.g. `statuses: Todo, Doing, Done, Won't do`. |

Change the header whenever the project changes level, ID scheme or entry style.

---

## 4. Rules for Every Entry

### 4.1. IDs

Pick one scheme and declare it in the header.

| Scheme | Example | Use when |
|---|---|---|
| Sequential | `[#042]` | One stream of work. |
| Prefixed | `[INF-15]`, `[UI-3]` | Distinct areas whose items are easier to find by category. List every prefix in the header. |
| Imported | `[GH-128]`, `[ISS-20260917-slug]` | Tasks come from another tracker that already gives stable, unique IDs. Say which tracker in the header. |

- IDs are **never reused or changed**, even after a task is rejected.
- Allocate the next ID from **every** backlog file or item, open and closed. If tasks may be opened on
  branches that haven't merged yet, check those branches too, or let a tool allocate IDs (§6).

### 4.2. Statuses

| Status | Single file | Split files | Item folders |
|---|---|---|---|
| `Open` | Backlog (Open Tasks) | `Open.md` | `open/` |
| `In Progress` | In Progress | `Open.md`, In Progress | `open/` |
| `Closed` | Completed | `Closed.md`, Completed | `closed/` |
| `Rejected`: decided against | Icebox | `Closed.md`, Icebox | `closed/` |
| `Cancelled`: no longer needed, or replaced by another task | Icebox | `Closed.md`, Icebox | `closed/` |

### 4.3. Priorities

| Priority | Meaning |
|---|---|
| `P1` | Do it now: it blocks other work, is a critical bug or security defect, or risks losing information. |
| `P2` | Clear value, no immediate blocker. |
| `P3` | Worth doing eventually: polish, minor debt, watch items. |

There is no `P0`. In a single file or `Open.md`, keep Backlog (Open Tasks) ordered P1, then P2, then
P3, and add a new task after the last task of its priority.

### 4.4. Severity and likelihood

Optional fields for bugs and findings. They record *why* an item has its priority, so the priority can be
argued with later. Features and ordinary tasks usually leave them out.

| Severity | How bad is it when it happens? |
|---|---|
| `Nitpick` | Wording, cosmetics, style. Nothing works differently. |
| `Minor` | Wrong in an edge case, with a workaround, or little harm. |
| `Major` | A feature people rely on doesn't work, or real harm is plausible. |
| `Critical` | Data loss, an action taken without the user's consent, code run from untrusted input, or credentials exposed. |

| Likelihood | Will it happen to this project's users, as the project is used today? |
|---|---|
| `Frequent` | In normal use, most days, or on every run. |
| `Occasional` | Some days, or in a common but not daily situation. |
| `Rare` | Needs an unusual setup, input or timing. |
| `Improbable` | Needs a deliberate attack or a contrived input, given who uses the project and how. |

**Default priority:**

| | Frequent | Occasional | Rare | Improbable |
|---|---|---|---|---|
| **Critical** | P1 | P1 | P1 | P1 |
| **Major** | P1 | P1 | P2 | P3 |
| **Minor** | P2 | P3 | P3 | P3 |
| **Nitpick** | P3 | P3 | P3 | P3 |

- An item that blocks other work is `P1`, whatever the table says.
- Anyone may set a different priority. Add a dated note saying why.

### 4.5. Metadata

Every entry has the same metadata, whatever its style. Single and split layouts write it as bold lines
under the heading. Item folders write it as YAML frontmatter at the top of the main file, because each
item is its own file and frontmatter is what tools, Obsidian Properties and GitHub can read.

**Bold lines** (single and split):

```markdown
### [#042] Short descriptive title
- **Status**: `Open` | **Priority**: `P2` | **Labels**: `Bug`, `UI`
- **Created**: 2026-10-08
- **Severity**: `Major` | **Likelihood**: `Occasional`
- **Depends on**: #039, #041
- **Parent**: #038
- **Resolved**: 2026-10-12
```

**Frontmatter** (item folders):

```yaml
---
id: "#042"
title: Short descriptive title
status: Open
priority: P2
labels: [Bug, UI]
created: 2026-10-08
severity: Major
likelihood: Occasional
depends_on: ["#039", "#041"]
parent: "#038"
resolved: 2026-10-12
---
```

| Field | Required? |
|---|---|
| Status, Priority, Created | Always. Item folders also need `id` and `title`. |
| Labels | Optional |
| Severity, Likelihood | Optional (§4.4) |
| Depends on, Parent | Optional (§4.6) |
| Resolved | Added when the status becomes `Closed`, `Rejected` or `Cancelled` |

- Quote IDs in YAML (`"#042"`). An unquoted `#` starts a comment, and a leading zero can turn an ID into a
  number.
- Extra fields go after Created (or at the end of the frontmatter) and are listed in the header.

### 4.6. Dependencies and parents

- **Depends on** lists the items that must be closed before this one can start.
- **Parent** names the item this one is part of, such as a phase or a larger feature. A parent closes
  only when all its children are closed, rejected or cancelled.
- If a dependency is rejected or cancelled, the item that depended on it gets a dated note: it is either
  no longer blocked, or it needs rethinking.
- An item is **ready** when its status is `Open` and every item it depends on is `Closed`. Ready items are
  what §7.5 picks from.

### 4.7. Evidence-based acceptance

- A criterion is ticked (`[x]`), or a task closed, **only on objective evidence**: a passing test
  command, real execution output, or a verified manual run.
- **Never tick on code presence, a grep match or intent.**
- **Write the evidence down:** after the criterion on the same line, in the Outcome, or, in an item
  folder, in a supporting file the Outcome names. Say what command, measurement or file proves it.

### 4.8. Changes after work starts

- Before a task is claimed, any part of it may be edited.
- After it is claimed, only status, priority and the dependency fields change in place. Everything else
  changes through a **dated note** that keeps the original wording readable, e.g.
  `- 2026-09-18: AC #3 dropped; the limitation is documented instead.`
- **Never delete an entry.** Completed tasks are the project's history. Icebox entries stop the same
  rejected idea being proposed again.

### 4.9. Linking commits

- Cite the commits that did the work in Notes or the Outcome.
- If every task merges as one `--no-ff` merge commit whose message names the task ID, that merge commit
  is the record and hashes may be left out: `git log --first-parent --grep=<ID>` finds it.

---

## 5. Entry Styles

Both styles share the metadata from §4.5 and the evidence rule from §4.7. They differ in how much
structure the body has. Declare the style in the header. A project may use both (§5.3).

| | Full | Compact |
|---|---|---|
| **Built for** | Work handed between sessions or agents, multi-step tasks, anything with several checkable outcomes | Many small items, quick capture, research and vault notes, solo work |
| **Strength** | Each part has a fixed place: a new session finds the plan, the open criteria and what was learned without reading everything | Cheap to write and cheap to scan: dozens of open items fit in one read |
| **Cost** | Long entries. A busy task can run to a hundred lines. | One "done when" sentence and free prose, so less to hand over and less to check off |
| **Pick it when** | Agents do most of the work, or tasks often span several sessions | People do most of the work, or tasks are usually done in one sitting |

The examples below use single-file headings. In an item folder's main file, each heading is two levels
higher (§2.3).

### 5.1. Full

```markdown
### [#042] Short descriptive title
- **Status**: `Open` | **Priority**: `P1` | **Labels**: `Core`, `Bug`
- **Created**: 2026-10-08

#### Why
The problem, its background, or the need.

#### Wanted
The target state or capability.

#### Acceptance Criteria
- [ ] #1 First verifiable criterion.
- [ ] #2 Second verifiable criterion.

#### Plan
(Optional, written after claiming) The intended steps. A revised plan goes below the old one, dated.
In an item folder the plan may be its own file, `plan.md`.

#### Notes
- (Optional, append-only, dated) Discoveries, decisions, amendments.

#### Outcome
(Filled on completion) What was done, the evidence, and the commits.
```

### 5.2. Compact

```markdown
### [INF-45] Short descriptive title
- **Status**: `Open` | **Priority**: `P2` | **Labels**: `Infrastructure`
- **Created**: 2026-10-08

What was found and why it matters, in prose. Dated corrections are added below, never written over.

*Wanted:* the target state.

*Done when:* one verifiable sentence.
```

When it is closed, add one line at the end:

```markdown
*Outcome (2026-10-12):* what was done, the evidence, and the commits.
```

### 5.3. Using both, and switching

- **Using both:** set the header to `full and compact`. Use compact for small items and full for work
  that will be handed over.
- **Growing an entry:** a compact entry may become full when the work turns out bigger. Add the full
  sections below the existing prose, and keep the prose as Why. Full entries never shrink to compact.
- **Switching styles:** change the header. New entries use the new style. Existing entries stay as they
  were written, because the history is never rewritten.

---

## 6. Who Writes

Levels 1–3 can use any of these rules. At Level 4 the tracker's own permissions and tools take their
place.

| Rule | How it works | Use when |
|---|---|---|
| **By hand, one writer at a time** | Whoever is working edits the backlog directly. | One person or agent works at a time. |
| **One named writer** | One session or role owns the backlog files. Other agents report what they did, and the owner records it. | Several agents work in parallel, but one coordinating session can own the tracking. |
| **Tool only** | Every change goes through a backlog tool, which allocates IDs, makes claims and moves entries. Nobody edits the files by hand. | No single session can own the backlog, or hand edits have caused collisions. |

Under **tool only**:
- The tool must support the project's layout.
- Agents make no hand edits, not even "just adding a line", unless the user allows it. An agent that
  copies the syntax by hand bypasses ID allocation, and that is how duplicate IDs happen.
- The user may bypass the tool when they need to, using the tool or editing by hand as they choose.
- The tool should refuse unknown ID prefixes, commit each change it makes, and leave nothing half-written
  when a step fails.
- A pre-commit or merge check should reject duplicate IDs and hand edits to generated sections. It
  should check only what the change introduces. A check that fails on old problems gets switched off.

---

## 7. Lifecycle

A backlog tool, if there is one, performs the same steps.

### 7.1. Opening a task
- Allocate the ID (§4.1).
- Give it a priority, from §4.4's table if it is a bug or finding.

| Layout | Where it goes |
|---|---|
| Single file, split files | Backlog (Open Tasks), after the last task of its priority |
| Item folders | A new file in `open/` |
| External tracker | A new issue from the template |

### 7.2. Claiming a task
- Set the status to `In Progress`. In a single file or `Open.md`, also move the entry to In Progress.
- Under the full style, write the Plan now.
- When several agents work at once, the claim also needs to be visible outside the backlog, for example a
  branch named after the task. Two agents setting the same status line can both believe they won.

### 7.3. Completing a task
- Check every acceptance criterion (or the "done when" sentence) against evidence (§4.7).
- Set the status to `Closed`, add the Resolved date, and write the Outcome.
- Move it:

| Layout | Where it goes |
|---|---|
| Single file, split files | The **bottom** of Completed. Bottom placement keeps the section in order and makes merges add lines rather than edit them. |
| Item folders | From `open/` to `closed/`, unchanged otherwise |
| External tracker | Close the issue as completed, with the Outcome as the closing comment |

### 7.4. Rejecting or cancelling a task
- Set the status to `Rejected` or `Cancelled` and add the Resolved date.
- Say why in the Outcome. Name the replacement task if there is one.
- Move it to the **bottom** of the Icebox (single or split), to `closed/` (item folders), or close the
  issue as not planned (external tracker).

### 7.5. Choosing what's next
Pick the highest-priority **ready** item (§4.6). Between items of equal priority, take the oldest. An item
that is `In Progress` belongs to whoever claimed it.

### 7.6. Reviewing open tasks
Open items left alone silt up the backlog until nobody reads it. Review an open item when it looks
stale: as a rough guide, when its newest date (its Created date or its last dated note) is about three
months old, or at the end of a phase in a phased project. This is a manual check that people do when
they can, and agents mention when they notice stale items. Nothing needs to run it on a schedule. For
each item, do one of these:
- change its priority, with a dated note;
- add a dated note that it still stands, and why;
- set it to `Cancelled` with the reason, and move it to the Icebox or `closed/`.

Nothing is deleted. A cancelled item stays as the record that the idea was considered.

### 7.7. Generated sections
A backlog tool may maintain views such as a task map, a list of active claims, or an export from an
external tracker. A generated section sits between markers and is never edited by hand:

```markdown
<!-- BEGIN TASK MAP -- generated, do not edit -->
...
<!-- END TASK MAP -->
```

A whole generated file says so in its first line. A hand-kept summary of other entries drifts out of
date. If one is needed, generate it.

---

## 8. Findings Register (Optional)

The Findings Register holds things that are not tasks but should not be forgotten. It is the last
section of a single file, or `Findings.md` in every other layout. Use these headings, leaving out any
that are empty:

```markdown
## 🔎 Findings Register

### Security Debt
### Untested Behaviour
### Known Gaps Accepted Deliberately
### Watch List
```

- Each finding is one bullet: what it is, why it matters, and the related task ID if there is one. A
  bug-like finding may carry its severity and likelihood (§4.4).
- When a finding is resolved, strike it through and say how, rather than deleting it:
  `- ~~The bridge has no authentication.~~ Resolved 2026-09-17 by #017.`
- **A finding with a fix in mind becomes a task.** Open the task and link it from the finding. A gap
  accepted on purpose stays in the register.

---

## 9. Starting, Migrating and Changing Level

### 9.1. Starting a backlog
1. Use Level 1 unless you already know you need more.
2. Create `{{backlog_file}}` with the sections from §2.1 and the header from §3.
3. Choose the ID scheme and entry style, and write them in the header.
4. If the backlog isn't at the default path, set `backlog_file` in the project's `.warehouse.yml`.

### 9.2. Migrating an existing backlog
- **Keep existing IDs.** Give IDs to items that have none, starting after the highest existing number.
- **Map statuses and priorities:** `P0` becomes `P1`. Other statuses (e.g. `Planned`) become `Open`.
- **Order Completed oldest first, once,** if it was kept newest first. Reordering is a move, not a
  rewrite.
- **Don't invent acceptance criteria for finished work.** Cite the evidence that was recorded at the
  time. If something was never verified, add it to the Findings Register under Untested Behaviour
  instead of ticking it.
- A prose register of risks and gaps becomes the Findings Register.
- Write the header last, describing what the backlog now is.

### 9.3. Single file to split files (Level 1 → 2)
1. Create `{{backlog_dir}}/`.
2. Move the header to `00_BACKLOG.md`, In Progress and Backlog (Open Tasks) to `Open.md`, Completed and
   Icebox to `Closed.md`, keeping their order, and the Findings Register to `Findings.md`.
3. Add the `merge=union` line for `Closed.md` (§2.2).
4. Set `backlog_layout: split` and, if needed, `backlog_dir` in `.warehouse.yml`. Update the header.
5. Fix links that pointed at the old file. Do the whole move in one commit, with no other changes.

### 9.4. To item folders (Level 1 or 2 → 3)
1. Create `open/` and `closed/` in `{{backlog_dir}}/` (create the folder first if coming from a single
   file), and put the header in `00_BACKLOG.md`.
2. Turn each entry into a file named `<ID>-<slug>.md`:
   - its bold metadata lines become frontmatter, field for field (§4.5);
   - its headings move up two levels;
   - In Progress and open entries go to `open/`, Completed and Icebox entries to `closed/`.
3. Move material the entries only linked to (plans, notes, measurements) into the item's folder where
   it belongs to one item. Leave shared material where it is.
4. The Findings Register becomes `Findings.md`.
5. Remove `Open.md`, `Closed.md` or the single file once every entry has its own file, and remove the
   `merge=union` line.
6. Set `backlog_layout: folders` in `.warehouse.yml` and update the header. Do the move in one commit, with
   no other changes.

### 9.5. To an external tracker (→ Level 4) and back
- **Moving there:**
  1. Create the labels and the issue template (§2.4).
  2. Create an issue for each open item, saying its old ID in the body ("Was #042").
  3. Leave closed items in the repository as the archive.
  4. Keep `00_BACKLOG.md`, rewritten to name the tracker, and `Findings.md`.
  5. Set `backlog_layout: tracker`.
- **Leaving:** export the issues into the item-folder layout (§2.3), using the issue numbers as imported
  IDs, and set the layout back.

### 9.6. Adopting or leaving tool-only writing
- **Adopting:** install the tool, check it supports the layout, change the header's `Writes` line, and
  from then on make no hand edits.
- **Leaving:** when one writer can own the backlog again, change the `Writes` line back. Generated
  sections either keep being regenerated or become ordinary text. Remove their markers if so.

### 9.7. Moving back down
A project may return to a lower level when the reason for the higher one has gone, for example when it
stops taking outside reports. Going from item folders or split files back to a single file is rarely
worth it: history only grows.

---

## Changelog

### [Unreleased]

### [0.2.0] - 2026-10-09
#### Added
- Four levels: single file, split files, item folders and external tracker, with when to move between
  them in both directions.
- `backlog_layout` setting (`single`, `split`, `folders` or `tracker`, default `single`) and
  `backlog_dir` setting (default `BACKLOG`) for every layout except the single file.
- Split layout: `00_BACKLOG.md`, `Open.md`, `Closed.md` (append-only, `merge=union`, holds the Icebox)
  and an optional `Findings.md`.
- Item-folder layout: `open/` and `closed/`, one file per item, which grows into a folder for its plan,
  evidence and scripts. YAML frontmatter for its metadata. Items move to `closed/` and never back.
- External-tracker layout, with how the convention maps onto a tracker and the rule of one source of
  truth.
- "Who writes" rules: by hand, one named writer, or tool only, with the safeguards tool-only writing
  needs. Any of them can be used at Levels 1–3. Under tool only, agents make no hand edits unless the
  user allows it, and the user may bypass the tool.
- "How strict is this?": the core every backlog keeps, what a project may change, and that the
  header's `Deviations` line wins over the convention.
- A required header stating the layout, ID scheme, entry style and who writes.
- Compact entry style next to the full style, with guidance on which to pick, using both, and switching.
- Optional severity and likelihood fields, with a table that sets the default priority from them.
- Optional `Depends on` and `Parent` fields, a definition of a ready item, and how to choose what's next.
- A manual review of open items that look stale: roughly three months untouched, or at the end of a
  phase.
- An imported ID scheme for tasks that come from another tracker.
- Rules for changing an entry after it is claimed (dated notes), recording evidence, and linking
  commits.
- Generated sections with markers that are never edited by hand.
- Findings Register format: fixed headings, one bullet per finding, struck through when resolved.
- Starting a new backlog, migrating an existing one, and changing level.

#### Changed
- **BREAKING:** a backlog must start with the header from §3.
  **Migration:** add the header under the title, filled in for how the backlog is run today.
- **BREAKING:** `Resolved` goes on its own metadata line and is also required for `Rejected` and
  `Cancelled` tasks.
  **Migration:** move any `Resolved` written on the Status line to its own line, and add it to Icebox
  entries.
- **BREAKING:** Backlog (Open Tasks) is ordered P1, P2, P3, and new tasks go after the last task of their
  priority.
  **Migration:** reorder the open tasks by priority once.
- `P1` now means "do it now", which a blocking item always is.
- The Findings Register gets its own `## 🔎 Findings Register` heading.

#### Removed
- Background on how the convention was drafted, and its link to a warehouse-only reference note.

#### Fixed
- Nested inline code in the lifecycle steps, which rendered incorrectly.

### [0.1.0] - 2026-09-15
#### Added
- Initial draft of the standardized backlog convention.
