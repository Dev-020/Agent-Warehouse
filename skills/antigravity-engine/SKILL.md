---
id: skill/antigravity-engine
version: 0.1.0
status: draft
summary: Operating protocol, instruction mounts, and headless patterns for driving projects using Antigravity CLI.
applies-to: [codebase, vault]
settings: {}
requires: [tool/antigravity-cli-runner@0.1]
replaces: null
---

# Antigravity Engine Skill: Headless CLI Orchestration Protocol

A comprehensive operating protocol for applications, background daemons, and agent harnesses driving
the Antigravity CLI (`agy`) as their primary autonomous runtime engine.

Distilled from production multi-agent systems in `discord-bot` (Artemis engine) and `shadow-cursor`
(resident desktop overlay engine), this skill documents the lifecycle contracts, stream-json NDJSON wire
format, profile sandboxing rules, glog error recovery, and permission grant schemas required to embed
Antigravity into any project.

Requires [[tool/antigravity-cli-runner]] for resident process execution, log diagnostics, and sandbox configuration.

---

## 1. Architectural Philosophy: The Autonomous Resident Engine

Embedded applications driving `agy` must run a **resident warm process** using bidirectional NDJSON
(`--input-format stream-json --output-format stream-json --model <model>`).

- **Sub-second turn dispatch:** A resident session answers prompts with ~1s latency, eliminating the 5–10s cold boot penalty of per-turn spawning.
- **Continuous reasoning streams:** Incremental thinking tokens and text deltas arrive in real time over `step_update` event frames.
- **Deterministic turn boundaries:** Every turn begins upon writing an inbound user event and completes strictly when the `result` event frame arrives.

---

## 2. Stream-JSON Wire Protocol (agy $\ge$ 1.1.22)

Antigravity communicates over standard input and standard output via newline-delimited JSON.

### 2.1. Inbound Envelope (Host $\to$ agy)
Each prompt turn must be written as a single line:
```json
{"event": "user", "message": {"role": "user", "content": "Your task prompt here..."}}
```
> [!WARNING] Multiline Newline Escaping
> `stdin` is read line-by-line; raw unescaped newlines in prompts will split the payload across multiple lines and break JSON parsing. Always serialize turns with `json.dumps()` so embedded newlines are properly escaped as `\n`.

### 2.2. Outbound Event Frames (agy $\to$ Host)
The CLI emits three distinct event types on `stdout`:

| Event Type | Payload Subkey | Description |
|---|---|---|
| `init` | `init`, `conversation_id` | Emitted immediately after spawn. Contains working directory, registered tools, and permission mode. |
| `step_update` | `step_update` | Streaming progress frames. Tracks tool invocations (`ACTIVE`/`DONE`), parameters, and agent response chunks (`text_delta`). |
| `result` | `result` | Terminal turn event. Contains final `status` (`SUCCESS` or failure), full `response`, `denied_actions`, and token `usage`. |

> [!IMPORTANT] Ready on Init Timing Invariant
> Unlike Claude Code (which is ready on spawn), Antigravity **emits an `init` event during startup**.
> The host process **must wait for the `init` frame** before writing the first prompt to `stdin`.
> Writing to `stdin` before `init` has been received will cause the initial message to be dropped or corrupt internal agent state.

---

## 3. Profile Sandboxing & Permission Grants

Headless execution runs without an interactive TTY, meaning `agy` cannot prompt the user for permission when an unapproved tool or file path is accessed. Unapproved operations are **auto-denied**.

### 3.1. Isolated Home and Temp Redirection
Each embedded project must isolate its engine environment:
1. Point `USERPROFILE` and `HOME` to an engine profile folder (e.g. `.agy-engine/`).
2. **Redirect `TEMP` and `TMP` into the profile:** Antigravity auto-allows reads and writes inside the directory pointed to by `TEMP`/`TMP`. Pointing both variables into the isolated profile prevents unconstrained host filesystem access.
3. **Authentication inheritance:** On Windows, authentication is managed via Windows Credential Manager (`gemini:antigravity`). The isolated profile inherits valid OAuth credentials without requiring an interactive browser sign-in.

### 3.2. Permission Grant Schema (`settings.json`)
Explicit tool and path permissions must be defined in `.gemini/antigravity-cli/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "read_file(C:/path/to/project)",
      "write_file(C:/path/to/project/output)",
      "command(pytest)"
    ]
  }
}
```

> [!CAUTION] Bare Paths vs Glob Patterns
> Directory grants in Antigravity must be **bare absolute paths with forward slashes**.
> Standard glob expressions such as `read_file(C:/path/**)` are **silently ignored** and grant zero access.
> A bare path (e.g. `read_file(C:/project)`) is automatically recursive.

### 3.3. Enabling AI Credits
In the isolated profile's `.gemini/config/config.json`, configure:
```json
{
  "userSettings": {
    "useAiCredits": true,
    "nonWorkspaceFileAccessPolicy": "AGENT_SETTING_POLICY_DENY"
  }
}
```
This ensures existing Gemini Advanced / Google One subscriptions are utilized ($0 per-token cost).

---

## 4. Diagnostic Error Recovery (The Glog Pattern)

When an Antigravity turn fails, the stream-json wire output conceals the actual root cause:
- `result.status` reports `"ERROR"`.
- `result.error` returns a generic placeholder: `"Agent execution terminated due to error."`
- The `error_message` step frame contains no diagnostic text.

The true failure reason (e.g. `INVALID_ARGUMENT (code 400)`, quota exhaustion, expired OAuth token) is written **only to Antigravity's internal log file**.

### Recovery Algorithm:
1. Locate the newest log matching `cli-*.log` in `~/.gemini/antigravity-cli/log/`.
2. Verify the log header contains the current workspace marker: `workspaceDirs=[<path>]`.
3. Scan backwards from the end of the file to find the turn's `sending message` marker.
4. Extract the last error line matching the Google glog format: `\bE\d{4} \d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\S+\]\s*(.+)$`.
5. Ignore generic wrappers (`run ended with error`, `Clearcut responded`) to extract the concrete exception message.

---

## 5. Output Conventions & Grounding Coordinates

When driving Antigravity as a multimodal or pointing engine:
- **Normalized 0–1000 Coordinate Grid:** Gemini vision models natively ground on a `0–1000` normalized axis across image width and height, rather than raw pixel coordinates.
- **Reply Tags:** To avoid multi-turn tool execution overhead, instruct the model to append structured reply tags to its text response (e.g. `[POINT:x,y:label]`, `[STATUS:ok]`, `[ACTION:command]`).
- **Unfinished Tool Detection:** If an auto-denied tool call occurs, the tool step goes `ACTIVE` but never reaches `DONE`. The host supervisor must detect any tool pending at the `result` event and label the turn as a permission denial.
