---
id: skill/computer-use
version: 0.1.0
status: draft
summary: Harness-agnostic operating protocol and safety rules for desktop automation via cua-driver.
applies-to: [vault, codebase]
settings: {}
requires: [tool/computer-use-setup@0.1]
replaces: null
---

# Computer Use Skill: Background Desktop Automation Protocol

A harness-agnostic operating protocol for AI agents driving desktop applications and browsers.
Built on `cua-driver`, this skill establishes the execution ladder, background-first interaction rules,
safety boundaries, and verification sequences across client harnesses (Claude Code, Antigravity, OpenClaw, Codex, etc.).

Requires [[tool/computer-use-setup]] for environment verification, MCP wiring, and skill-pack linking.

---

## 1. Operating Philosophy: Narrowest Semantic Route First

Agents must never jump straight to GUI automation when a faster, deterministic, lower-overhead route exists.
Always traverse the action ladder from narrowest to widest:

| Rung | Route | When to Use | Failure / Fallback Condition |
|---|---|---|---|
| **1** | **Direct Filesystem / Specialized Tool** | Reading or modifying files, project configs, databases, or local code. | Target is an external running application without direct file access. |
| **2** | **CLI / Local or Remote API** | Interacting with running services, git, system commands, curl, or public APIs. | Action requires interactive GUI state (e.g. desktop app or authenticated browser session). |
| **3** | **Background GUI via Accessibility Tree** | Driving desktop applications or Chromium browsers via `cua-driver` accessibility nodes. | Element has no accessibility node (e.g. custom canvas, complex game, or remote desktop). |
| **4** | **Coordinate / Vision Clicking (Last Resort)** | Canvas elements, video players, or visual artifacts lacking semantic accessibility tokens. | None (only fallback for purely visual interfaces). |

---

## 2. Background Execution Protocol

`cua-driver` interacts with applications via the operating system's native accessibility API (UI Automation on Windows,
AX on macOS, AT-SPI on Linux) without moving the user's mouse cursor or stealing keyboard focus.

Agents must follow this interaction sequence:

### Step 1: Identify Target Window
Find the application by title, process ID (PID), or bundle ID:
- Use `list_windows` to inspect active application windows.
- Bind subsequent actions to the specific target `window_id` or `pid`.

### Step 2: Take a Pre-Action Snapshot
**Never send input blindly.** Always obtain the semantic accessibility tree before acting:
- Call `get_window_state` for the target window.
- Identify the target element and its `element_token` (or `element_index` paired with `snapshot_id`).
- For text-only or token-constrained contexts, the returned markdown accessibility hierarchy provides complete structural context without requiring a visual screenshot.

### Step 3: Act via Semantic Element Tokens
Post events directly to the target element:
- Call `click(element_token=...)`, `type_text(...)`, `press_key(...)`, or `invoke_menu(...)`.
- **Bare element indices are prohibited**: Always pass `element_token` to guarantee the click hits the intended element even if the UI dynamically shifted.
- Keep `delivery_mode: "background"` (default). Never activate or bring windows to the foreground unless explicitly instructed.

### Step 4: Verify Post-Action State
Confirm the intended mutation occurred:
- Call `get_window_state` or `verify_state` to confirm the resulting modal, navigation, or text entry matches expectations.
- If the expected state change did not occur, stop and diagnose rather than repeating keystrokes or blind clicks.

---

## 3. Hard Safety Boundaries & Escalation Gates

### 3.1. Prohibited Keystrokes & Commands
Agents are strictly forbidden from emitting or triggering:
- System power operations: shutdown, restart, sleep, or sign-out.
- Screen lock or session termination shortcuts (e.g. `Win+L`, `Ctrl+Alt+Del`).
- Unattended credential modification or permission elevation prompts (UAC / `sudo`).
- Shell piping of unverified remote scripts (e.g. `curl | bash`, PowerShell `iwr | iex`).
- Mass deletion commands with wildcards against system or project root directories.

### 3.2. Foreground Escalation Gate
> [!IMPORTANT] Human Consent Required for Foreground Focus
> Background execution is the non-negotiable default. Switching to `delivery_mode: "foreground"`,
> simulating raw hardware mouse movement across the global display, or forcing a background window
> to the active foreground disrupts user work and requires **explicit user authorization**.

---

## 4. Setup & Integration

To verify and wire computer use in any project:

1. **Verify Environment**:
   ```bash
   python warehouse/tools/computer-use-setup/computer_use_setup.py check
   ```
2. **Configure MCP Server**:
   ```bash
   # For project-level .mcp.json (generic MCP clients):
   python warehouse/tools/computer-use-setup/computer_use_setup.py configure --client generic --write

   # For Claude Code user-level registration:
   python warehouse/tools/computer-use-setup/computer_use_setup.py configure --client claude-cmd
   ```
3. **Link Detailed Skill Pack**:
   ```bash
   python warehouse/tools/computer-use-setup/computer_use_setup.py skills install
   ```

---

## 5. Platform Mechanics & Upstream Reference

For low-level OS mechanics, browser DevTools protocol attachment, and advanced recording/replay workflows,
refer directly to the upstream documentation provided in the linked `cua-driver` skill pack:
- `WINDOWS.md`: Windows UI Automation (UIA) tree patterns and legacy Win32 controls.
- `MACOS.md`: Accessibility permissions (TCC), AX API, and window management.
- `LINUX.md`: AT-SPI, Wayland vs X11 caveats, and headless virtual displays.
- `BROWSER.md`: Chromium remote debugging attachment and DOM element resolution.

---

## Attribution & Credits

Safety heuristics, escalation ladder principles, and background-first execution guidelines adapted from
`f-trycua` (Francesco Bonacci) and the `Hermes Agent` project under the MIT License.
