---
id: architecture/codebuff-orchestration
version: 0.1.2
status: draft
summary: Distilled Codebuff multi-agent architecture, cost scaling analysis, and tiered orchestration.
applies-to: [vault, codebase]
settings: {}
requires: []
replaces: null
---

# Codebuff Orchestration: Minimal Sufficient Architecture

A battle-tested multi-agent architecture distilled from the original Codebuff framework, empirical benchmarking across Claude Code and Antigravity, and industry research from Anthropic, Cognition, and Stanford.

---

## 1. The Multi-Agent Reality: The Coordination Tax

Multi-agent AI architectures are often marketed as intuitive analogies to human engineering teams (an orchestrator, architect, editor, reviewer, and tester). However, in LLM execution, **every agent added multiplies token consumption without linearly scaling output quality**.

### The Scaling Arithmetic

| Architecture | Token Multiplier | Measured Quality Gain | Cost vs Single Agent |
|---|---|---|---|
| **Chat / Direct Interaction** | 1× | Baseline | 1× |
| **Single Agent with Tools** | 3–4× | High (+65% SWE-bench) | ~3–4× |
| **Multi-Agent Committee (Codebuff 5–7 roles)** | **15–25×** (up to 220×) | Marginal (+72% SWE-bench) | **4–10×** |

### The Three Drivers of Budget Exhaustion

1. **Monotonic Context Re-ingestion (The Quadratic Trap):**
   Because LLMs are stateless, every tool call or turn re-sends the entire accumulated conversation. A 100-turn session where context grows from 20K to 500K tokens forces the model to re-read **tens of millions of cached tokens**. Re-sent context alone accounts for **>60% of total inference bills**.
2. **Review-Fix-Retest Loops:**
   A naive review loop (Editor writes → Runner tests → Reviewer audits → Editor fixes → Runner re-tests) runs multiple heavy test suites. In our empirical testing on Windows, full test runs dumped 15–30K tokens of logs per turn, accelerating context bloat exponentially.
3. **Context Rot & Degradation:**
   As documented by Anthropic and Stanford, over-stuffed context windows suffer from the "lost-in-the-middle" effect. Models in bloated contexts actually degrade in reasoning quality and frequently **revert previously completed fixes**.

---

## 2. Industry Ground Truth: When Multi-Agent Works

### Walden Yan (Cognition / Devin): "Don't Build Multi-Agents"
Multi-agent fragility is primarily architectural:
- Distributed agents make conflicting *implicit decisions* that are difficult to reconcile.
- The winning approach is a **single-threaded primary agent** paired with dedicated context compression and explicit checkpointing.

### Stanford (Tran & Kiela): The Compute-Parity Finding
When holding the thinking-token and compute budget constant, **single-agent systems match or outperform multi-agent systems** on complex multi-hop reasoning. The apparent gains of multi-agent swarms are almost entirely bought with raw unaccounted compute, not superior organizational structure.

### The Augment Code 5-Question Test
Before adding *any* additional agent, evaluate:
1. Do the subtasks have **no sequential dependencies**?
2. Do the subtasks touch **disjoint file sets**?
3. Is each subtask **independently specifiable**?
4. Is the task large enough to justify coordination setup overhead?
5. Can an engineer or automated gate verify the output in isolation?

If the answer to any of the first three is "No", **use a single agent**.

---

## 3. The 3-Tier Architecture: Minimal Sufficient Architecture

Instead of running a persistent multi-agent committee, sessions must dynamically match the orchestration tier to the task complexity:

### Tier 1: Solo (Primary Agent + Automated Tooling) — 80% of Tasks
- **Role:** Single agent equipped with file read/write and terminal tools.
- **Workflow:** Read spec → Implement changes → Run targeted unit tests (`pytest -k test_feature -q`) → Commit.
- **Context Hygiene:** Never dump full test logs or entire directory walks into context. Rely on targeted terminal feedback.
- **Best for:** Bug fixes, feature extensions, refactoring, documentation, routine commands.

### Tier 2: Paired (Author + Ephemeral Reviewer) — 15% of Tasks
- **Roles:** Primary Author + a temporary, single-turn **Ephemeral Reviewer** (using a frontier reasoning model).
- **The "Git Diff Review" Pattern:**
  1. Author completes the implementation until internal tests pass.
  2. Author generates `git diff` and passes **only the diff + architectural invariants** (the reviewer's brief) to the Reviewer in a **fresh context window**.
  3. The Reviewer audits the diff in a **single turn**, reporting defects, missing edge cases, and contract deviations.
  4. The Reviewer is **immediately terminated** (preventing multi-turn conversation bloat).
  5. The Author applies the fixes, runs validation, and commits.
- **Best for:** Core engine updates, security-critical boundaries, schema migrations, and merge algorithms.

### Tier 3: Context Firewall / Specialist — 5% of Tasks
- **Role:** Bounded, short-lived exploration, implementation, or review subagents.
- **Mechanism:** Spawned to read bulky external files (e.g. searching 50 logs, scanning large unfamiliar codebases, or reconciling disparate notes) or to implement/review bounded checkpoint steps.
- **The Firewall:** The subagent ingests the 50K+ tokens of raw material, distills findings into a concise report citing raw evidence, and **terminates**. The raw tokens evaporate with the subagent; only the distilled summary enters the main session context.
- **Operating Procedures:** See [[phased-implementation]] for multi-phase codebases and [[phase-staffing]] for sizing, coupling, and model tier selection.

---

## 4. Role Pruning Matrix

The original Codebuff framework introduced 7 distinct roles. Empirical testing reveals which deliver real value and which are pure coordination overhead:

| Codebuff Role | Value Delivered | Verdict | Action |
|---|---|---|---|
| **Orchestrator** | Coordinates user intent, manages state | **Essential** | Kept as session lead |
| **Editor** | Core implementation engine | **Essential** | Kept as Primary Agent |
| **Reviewer** | Found 8 defects tests missed; caught pathing and regex flaws | **Asymmetric High Value** | **Kept as Ephemeral Tier 2 auditor** (single-pass on git diff) |
| **Thinker / Architect** | Explored edge cases, authored `DESIGN.md` | High for 0-to-1 specs; zero for batch execution | **Reserved for initial architecture design only** |
| **File Picker** | Attempted to select files before edits | Negative (added turn latency, duplicated search) | **Pruned.** Primary agent views files directly |
| **Code Searcher** | Searched codebase | Redundant with `grep_search` and `find_by_name` | **Pruned.** Integrated into primary agent tools |
| **Basher / Runner** | Ran terminal commands and test scripts | Negative (passed stdout back and forth across turns) | **Pruned.** Automated testing belongs in scripts, not an LLM |

---

## 5. Operational Best Practices & Context Hygiene

1. **Short-Lived Agents Over Long-Running Partners:**
   Subagents should be treated as ephemeral workers (spawn → execute task → return result → terminate). Never keep subagents alive across multiple batch phases.
2. **Checkpoint-and-Restart via Git:**
   Git commits are the ultimate state resets. Once a batch is committed, earlier implementation traces and intermediate debug logs can be safely forgotten.
3. **Targeted Testing During Development:**
   During feature development, run only the relevant unit tests (`pytest -k test_feature -q`). Run the full test suite once as a final gate.
4. **Context Compaction at Milestones:**
   Before transitioning between major phases (e.g. from Tool Implementation to Item Reconciliation), summarize completed work and clear transient tool results.

---

## Changelog

### [Unreleased]

### [0.1.2] - 2026-10-17
#### Changed
- Tier 2's "Git Diff Handoff" pattern is now the "Git Diff Review" pattern: what the author passes
  is the reviewer's brief, not a hand-over, matching `protocol/phased-implementation`'s terms.

### [0.1.1] - 2026-10-02
#### Changed
- Linked protocol/phased-implementation and protocol/phase-staffing under Tier 3 as the operating procedures for implementation, code review, and model staffing.

### [0.1.0] - 2026-09-15
#### Added
- Initial draft of the distilled Codebuff orchestration architecture.
- Multi-agent cost scaling curves and empirical token consumption analysis.
- 3-Tier Minimal Sufficient Architecture (Solo, Paired, Context Firewall).
- Role pruning matrix based on empirical warehouse trial logs.
