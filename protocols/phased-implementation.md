---
id: protocol/phased-implementation
version: 0.1.1
status: draft
summary: Plan, review, then build in phases with fresh or continued subagents, checkpoint commits, probe-backed reviews, one full test run per phase, and a session-log hand-over between phases.
applies-to: [codebase]
settings:
  memory_folder:
    description: "Folder for agent notes, plans and briefs"
    default: "AI"
  active_context_file:
    description: "File that tracks the active task context, inside memory_folder"
    default: "ACTIVE_CONTEXT.md"
  session_folder:
    description: "Folder where session logs are written"
    default: "AI/session"
requires: [protocol/session-log@0.2, protocol/working-memory@0.1, protocol/worktree-claims@0.1, protocol/phase-staffing@0.1, template/plan-document@0.1, template/implementation-brief@0.1, template/review-request@0.1, architecture/codebuff-orchestration@0.1]
replaces: null
---

# Phased Implementation Protocol

How one coordinating agent (the **Orchestrator**) delivers a large, design-heavy change across many sessions' worth of work without its own context filling up. The Orchestrator plans and decides; subagents implement and review; git commits are the checkpoints; a session log carries state across each phase boundary and context compaction.

It is the operating procedure for Tier 3 of [[codebuff-orchestration]] (the context firewall), extended from exploration to implementation and review: each implementer and reviewer starts with bounded scope, does one job, and returns only a report. The context-hygiene practices of that item's §5 (short-lived agents, git checkpoints, targeted tests, compaction at milestones) are operationalized into concrete steps.

## When to use it

Use it when most of these hold:
- The work spans **three or more phases** that each need a full implementer session.
- **Correctness depends on design**: state machines, concurrency, crash recovery, security boundaries.
- A wrong early decision would be expensive to undo.
- You need to **get the most out of limited model usage**: the Orchestrator's context stays small and nothing is re-derived.

Don't use it for a change one session can finish. Tier 1 (solo) or Tier 2 (author plus one ephemeral reviewer) in [[codebuff-orchestration]] is cheaper there.

## Roles

| Role | Who | Owns | Never does |
|---|---|---|---|
| **User** | The human | Every open decision in the plan; approval of the plan; deferring a review finding; compacting the Orchestrator's context (e.g. `/compact`) | — |
| **Orchestrator** | One long-lived top-level session | The plan, briefs, staffing decisions, checkpoint verification, triage, merges, tracking files, and session logs | Reads implementer or reviewer transcripts; writes feature code itself |
| **Implementer** | An implementer subagent (continued or fresh per [[phase-staffing]]) | Code, targeted tests, one commit per checkpoint step, a concise report citing raw files | Edits tracking files; runs full test suite before phase's final step; reopens settled decisions |
| **Reviewer** | A fresh subagent per review (always frontier model) | One review: findings with severity, each backed by an executable probe script | Fixes the code it reviews |

Reviewers always run on the strongest frontier reasoning model. Implementer models are selected per phase according to [[phase-staffing]].

## Artifacts

| Artifact | Where (default) | Written by | Purpose |
|---|---|---|---|
| Research and probe notes | `{{memory_folder}}/notes/NN_<topic>.md` | Orchestrator or a probe subagent | Ground truth the plan relies on |
| Plan | `{{memory_folder}}/PLAN_<slug>.md`, from [[plan-document]] | Orchestrator | The approved spec, split into phases |
| Brief, one per phase | `{{memory_folder}}/HANDOFF_<id>_<phase>.md`, from [[implementation-brief]] | Orchestrator | What the phase's implementers need, with staffing and decisions settled |
| Worktree and branch | Per [[worktree-claims]] | Orchestrator | Isolates the phase until it merges |
| Step commits | The phase branch | Implementers | The checkpoints |
| Review probes | The Orchestrator's scratchpad, `rv_<phase>/run_all.py` | Reviewer | Makes each finding reproducible and validates the fix |
| Session log with hand-over | `{{session_folder}}/<date>-<phase>.md`, per [[session-log]] | Orchestrator | Carries state across phase boundaries and context compactions |
| Active context | `{{memory_folder}}/{{active_context_file}}`, per [[working-memory]] | Orchestrator | The one file every session reads first |

## Stage 0 — Ground truth before design

1. **Research** how others solved the problem, if it is new to the project. Write it as a note.
2. **Probe what the design assumes.** Test every mechanism the design depends on against real tools, CLIs, or APIs, and record each as confirmed or refuted in a note. Fold results into the plan before building.

*Why: a plan built on an unverified tool behavior fails in the phase that first depends on it, after preceding work is already built.*

## Stage 1 — The plan

1. **Draft** from [[plan-document]]. Write every unresolved choice as a numbered open question with options and a recommendation.
2. **Design review** by a fresh reviewer (Variant A in [[review-request]]). Revise, then run **one confirmation review** of the revision.
3. **The user settles every open question.** Each becomes a settled decision: "don't reopen; if it looks wrong during implementation, stop and report".
4. **Cut it into phases, each sized for one implementer session.** Split a phase into `a`/`b` rather than let it grow unbounded. Give each phase a gate: named tests plus a green suite.
5. **The user approves** the plan.

## Stage 2 — The phase loop

Repeat for each phase:

```
re-read → staff phase → brief → worktree → [ implement step → verify checkpoint ] × N
  → review with probes → triage → fix step → re-run probes
  → full suite once → merge → hand-over → compact if heavy
```

1. **Re-read** the active context, the latest session log, and the plan section for this phase. After compaction, nothing else from before it is assumed.
2. **Staff the phase and write the brief.**
   - Decide staffing shape (size, coupling, model) per [[phase-staffing]].
   - Write the brief from [[implementation-brief]], opening with the staffing row and documenting settled **Orchestrator decisions**. Split into checkpoint steps. Commit the brief.
3. **Create the phase worktree and branch** from the integration branch, per [[worktree-claims]]. The Orchestrator, not the worker, marks the item In Progress and owns tracking files (replacing §4.1 step 4 and §4.5 step 2 of that protocol).
4. **Implement one step at a time.**
   - For tightly coupled steps, use one continued implementer subagent across steps; for large loosely coupled steps, spawn a fresh agent per step (per [[phase-staffing]]).
   - The implementer reads the brief, builds one step, runs only targeted tests, makes one commit, and reports: commit hash, touched files, targeted test results, deviations with reasons, weakened/removed assertions, and raw-file citations for measured data.
5. **Verify each checkpoint yourself:** commit exists, tree is clean, and the step's changed test files pass. **Do not run the full suite.** Answer open questions in the next step's prompt.
6. **Review the phase** with one fresh reviewer on the frontier model (Variant B in [[review-request]]). Each finding carries a severity (blocker, should-fix, nit) and an executable **probe script** that fails on current code and passes when fixed. Probes run via `run_all.py`.
7. **Triage.** Accept each finding, or adjust the fix and record why. **Blockers cannot be deferred.** Deferring any other finding requires user approval and converts it into a backlog item per [[review-request]].
8. **Fix step.** Confirmed by **re-running the probes**, not a second full review: passing probes demonstrate the defect is fixed. Add a second review pass only if fixes rework complex state machines or a finding cannot be reduced to a probe script.
9. **Run the full test suite once**, at the end of the last step. Run a second time only if the first run fails.
10. **Merge** into the integration branch with `--no-ff`. Remove worktree and branch.
11. **Write the hand-over.** Update:
    - Plan build-order table (done, merge commit, suite count).
    - Active context.
    - A session log per [[session-log]] carrying: interface delivered, decisions made, gotchas discovered, and open threads assigned to named later phases.
12. **Compact if the phase made the context heavy.** If review, fix, and verification rounds accumulated significant tokens, ask the user to run `/compact`. If the phase was light, skip and proceed directly to the next phase.

## Stage 3 — Close-out

1. **Live gates**, one at a time, from the primary tree against real tools and environments.
2. Archive the plan and close the backlog item.

## Rules

1. **Decisions are made once, in writing.** User decisions live in the plan; Orchestrator decisions in briefs. Implementers stop and report instead of reopening one.
2. **Staffing matches coupling.** Sizing, agent reuse vs. fresh agents, and models are determined per [[phase-staffing]]. Fresh reviewers always stand.
3. **Every checkpoint is a commit on a clean tree.**
4. **Targeted tests while working, the full suite once per phase.**
5. **Review findings require executable probes.** A probe turns opinion into reproducible evidence; re-running it confirms the fix objectively.
6. **Only the Orchestrator edits tracking files** (active context, plan, briefs, session logs, backlog).
7. **The Orchestrator never reads a subagent's transcript.** It verifies the commit and reads concise reports citing raw data.
8. **Write the hand-over before compacting, and compact only when it pays.**

## Fallbacks

| Situation | Action |
|---|---|
| Subagent hits a usage limit mid-task | Resume the same agent (send message) after reset; work so far is preserved. |
| User is away and cannot approve peer-session actions | Use subagents rather than top-level peer sessions. |
| Phase turns out too large for one session | Split it (`a`/`b`) at the next checkpoint and update the plan. |
| Reviewer's suggested fix breaks another probe | Choose a different fix that passes all probes; document rationale in session log. |
| Full suite fails before merge | Fix and run once more; report both results. |

## Choices a project may change

| Choice | Default | Change when |
|---|---|---|
| Implementer model | Per [[phase-staffing]] | Prescriptive briefs and isolated modules use mid-tier models; security/concurrency uses frontier models. |
| Steps per phase | 2–3 | Fewer for small phases; split phase if exceeding 4. |
| Reviews per phase | 1, plus probe re-run | Add second pass if probes cannot isolate the defect. |
| Where artifacts live | `{{memory_folder}}` and `{{session_folder}}` | Set in `.warehouse.yml` to match project layout. |

---

## Changelog

### [Unreleased]

### [0.1.1] - 2026-10-06
#### Fixed
- Added missing `architecture/codebuff-orchestration@0.1` to requires, ensuring projects pulling phased-implementation receive the tier definitions (Tier 1/2/3) it references.

### [0.1.0] - 2026-10-02
#### Added
- Initial draft, distilled from the Shadow Cursor #038 orchestration engine build (phases O0 to O5b) and refined with #063 phase staffing.
- Severity-to-priority mapping for deferred review findings; blockers can't be deferred.
- Review policy: probe re-runs confirm fixes, blockers included; a second review pass only when the probes can't carry the confirmation.
- Compaction is conditional on the phase having made the context heavy.
- Settings memory_folder, active_context_file and session_folder for artifact locations.
- Modular integration with protocol/phase-staffing for task sizing, coupling shapes, and model selection.
