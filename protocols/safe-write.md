---
id: protocol/safe-write
version: 0.1.0
status: draft
summary: "Five-step safe write sequence for modifying live, production, or fragile data."
applies-to: [vault, codebase]
settings: {}
requires: []
replaces: null
---

# Safe Write Protocol

Standard operating procedure for modifying live master files, production spreadsheets, shared databases, and fragile data stores where accidental clobbering, race conditions, or unverified writes cause silent data destruction.

Related protocols:
- Operating constraints and working posture: [[agent-protocol]]
- Session logs and audit trails: [[session-log]]
- Verification discipline: [[research-discipline]]

---

## Context and hazards

Direct, un-guarded writes to live data stores carry severe hazards:
- **Silent corruption:** Writes that succeed mechanically but destroy business formulas, validation rules, or formatting.
- **Race collisions:** Overwriting concurrent edits made by human collaborators or other automated agents.
- **Stale plan application:** Applying a modification plan derived from an earlier read after the underlying live data has already moved.

To eliminate these risks, any automated modification of live or shared master data must follow the 5-step safe write sequence.

---

## The 5-Step Safe Write Sequence

```
1. Rehearse on Copy ──> 2. Dry Run ──> 3. Pre-flight Guard ──> 4. Verify After ──> 5. Diff
   (Staging/Replica)     (before->after)  (Abort if moved)     (OK/MISMATCH)    (Assert diff)
```

### 1. Rehearse on the copy
Never execute a new or modified script directly against production data. Maintain a dedicated test copy or staging replica with an identical schema and IDs. Validate the script and verify that all transformations succeed on the replica before pointing tooling at production.

### 2. Dry run
Tooling must inspect live data and generate the complete set of proposed changes, printing every planned mutation as an explicit `before -> after` record:
```
Row 14 [EMAIL]: "user@example .com" -> "user@example.com"
Row 22 [PHONE]: "+1-555-0199 (home)" -> "+1-555-0199"
```
Inspect the dry-run output thoroughly before authorizing execution.

### 3. Pre-flight guard
APIs and database batches often lack native optimistic concurrency locks (`requiredRevisionId`). To protect against concurrent modifications:
- Immediately prior to executing the write call, re-read every target record or cell.
- Assert that each current value matches the exact `before` value expected by the plan.
- If **any** value has moved since the plan was computed, **abort the entire batch immediately**. Do not apply partial writes.

### 4. Verify after
Immediately following the write operation, re-read every written record or cell from the live data store. Assert that the live value matches the intended post-write state, reporting status per item:
```
Row 14 [EMAIL]: OK
Row 22 [PHONE]: OK
```
Flag any `MISMATCH` as an operational incident.

### 5. Diff
Compare the complete updated dataset against a pre-change snapshot or known-good baseline. Verify that:
- Every intended change landed accurately.
- No adjacent rows, columns, or metadata fields were altered.
- All structural formulas, validations, and constraints remain intact.

---

## Dual-flag execution protection

Tools that perform writes to production or master datasets must enforce explicit, dual-flag safety gates:
- **Default:** Running a script with no arguments defaults to a dry run against the staging copy.
- **Single flag (`--apply`):** Executes writes against the staging copy only.
- **Single flag (`--master`):** Executes a dry run against the live master.
- **Dual flags (`--master --apply`):** Required to perform actual writes to the live master.

Missing either flag must cause the tool to abort or stay in read-only/dry-run mode. Writes to production must never occur by accident or omission.

---

## Boundaries: Mechanical repairs vs Human decisions

Agents must respect the boundary between autonomous mechanical operations and decisions that require human authority:

### Permitted autonomous repairs
- Trimming leading/trailing whitespace.
- Normalizing phone numbers, dates, or casing to project standards.
- Deduplicating identical rows where unique keys match.
- Backfilling missing values that already exist authoritatively elsewhere in the same system of record.

### Decisions requiring human authority
- Resolving conflicting identity data (e.g. differing student IDs or conflicting phone numbers for the same name).
- Choosing between plausible values when source data is ambiguous.
- Altering access permissions, credentials, or emergency contact details.
- Making policy exceptions or business judgments not documented in the rules.

When encountering an ambiguous or disputed value, do not guess: skip the field, preserve existing state, and report the defect in [[session-log]] for human resolution.

---

## Concurrency and recovery discipline

1. **Recompute on every run:** Always fetch live data and compute a fresh plan at the moment of execution. Never store a plan in a temporary file or memory across turns and apply it later.
2. **Guards tripping is expected:** When a pre-flight guard aborts because a cell changed, the safety mechanism worked as designed. Never force-apply an aborted plan. Re-fetch current data, recompute the diff, and re-run.
3. **Take point-in-time snapshots:** Before executing batch modifications on critical data, export or copy a timestamped backup snapshot.

---

## Changelog

### [Unreleased]

#### Added
- Initial draft of the canonical safe write protocol.
