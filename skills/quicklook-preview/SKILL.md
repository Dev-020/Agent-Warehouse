---
id: skill/quicklook-preview
version: 0.1.0
status: draft
summary: When and how AI agents show a generated file to the user in QuickLook — only on request or with the user's permission.
applies-to: [vault, codebase]
settings: {}
requires: []
replaces: null
---

# QuickLook Artifact Preview Skill

Standard operating procedures for AI agents to show the user a generated file — a compiled PDF, an
image, a Markdown report — in **QuickLook** (<https://github.com/QL-Win/QuickLook>), a lightweight
read-only preview window for Windows.

Companion items: `skill/latex-pdf` and `tool/tex-compile` (which produce PDFs worth previewing),
[[agent-protocol]] and [[session-log]].

---

## 1. Purpose & Agent Rationale

AI agents often produce files the user needs to look at: PDFs compiled from LaTeX, exported images and
charts, Markdown briefs and reports. Without a preview, the user has to find the file in Explorer and
open it in an editor or browser.

**This skill gives the user a quick way to look at such a file** — but a preview window takes focus
and appears on the user's desktop, so it is **only ever opened when the user asks, or after the user
agrees to it**.

---

## 2. Prerequisites (machine setup, not part of this skill)

QuickLook has no command line of its own. This skill assumes the machine has:

- **QuickLook** installed, and
- a **`ql` command** on `PATH` that previews a file: `ql <file>` opens it, `ql --close` closes the
  preview.

Check with `ql --help`. If `ql` is not available, do not try to install it: skip the preview and give
the user the file's path instead (see Step 4).

### QuickLook version — experimental build

> [!WARNING] Tested only against an experimental QuickLook build
> This skill was checked against **QuickLook `4.5.0-218-g3460ca3`**, a development build made after the
> 4.5.0 release, not a stable release. Development builds can change without notice. `ql` also relies on
> QuickLook's internal message channel (a named pipe), which QuickLook does not document or promise to
> keep, so a QuickLook update can stop `ql` from working.

- **Before relying on `ql`** (first use on a machine, or after QuickLook was updated), check the
  installed version: the *Product version* of `QuickLook.exe` (file Properties → Details, or
  `(Get-Item <path>\QuickLook.exe).VersionInfo.ProductVersion` in PowerShell).
- **If it differs from the tested version**, tell the user it is untested with this skill before
  previewing.
- **If `ql` breaks or misbehaves** (errors, no window, wrong file shown), stop retrying, give the user
  the file's path, and report it to the warehouse so the skill can be reviewed:
  ```bash
  warehouse issue skill/quicklook-preview --type bug \
    --summary "ql preview fails with QuickLook <version>" \
    --details "<QuickLook version, the ql command run, the error or behaviour seen>"
  ```

---

## 3. Invariants & Agent Behavioral Rules

> [!IMPORTANT] Rule 1: Only on Request or With Permission
> Open a preview only when the user asks for one. If you think a file is worth previewing, **ask
> first** (e.g. *"Want me to open `build/report.pdf` in QuickLook?"*) and run `ql` only after the user
> says yes. Permission covers that one file; ask again for the next one.

> [!IMPORTANT] Rule 2: Read-Only Invariant
> QuickLook is strictly a viewer. Never use this skill when the user's intent is to modify, edit, or
> refactor a file. Direct the user to their editor or IDE for file editing tasks.

> [!NOTE] Rule 3: Fire-and-Forget
> `ql` returns as soon as the request is handed to QuickLook (normally well under a second; a few seconds
> if QuickLook has to start first). Never wait for the preview window to close before continuing.

> [!NOTE] Rule 4: Single-Window Idempotency
> QuickLook shows one preview window at a time. Calling `ql` on a second file replaces the contents
> in-place. Agents do not need to call `ql --close` before opening a new file.

> [!TIP] Rule 5: Leave the Window to the User
> The user closes the preview themselves (Esc, or the window's close button). Do not ask them to close
> it, and do not call `ql --close` unless they ask.

---

## 4. What QuickLook Can Show

| Shows well | Examples |
|---|---|
| PDFs | compiled LaTeX output, exported reports |
| Images | `.png`, `.jpg`, `.gif` |
| Markdown | briefs, reports, notes |
| Text and source code | `.txt`, `.json`, `.csv`, `.tex`, `.py` (as plain or highlighted text) |
| Video and audio | `.mp4`, `.mp3` |

Other formats depend on which QuickLook plugins are installed. A file QuickLook cannot render shows only
its name and size — in that case, do not offer the preview; tell the user where the file is.

---

## 5. End-to-End Workflow

```
[1. Generate Artifact] ──> [2. Validate on Disk] ──> [3. Ask / Requested] ──> [4. Preview] ──> [5. Inform User]
```

### Step 1: Generate Artifact
Produce the target output file (e.g., compile LaTeX to PDF, export a chart, or write a Markdown summary).

### Step 2: Validate Existence on Disk
Verify that the output file exists, is non-empty, and has finished writing before previewing it.

### Step 3: Confirm the User Wants a Preview
If the user asked for the preview, continue. Otherwise, if the file is worth looking at, ask whether to
open it in QuickLook and wait for a yes. If the user declines or doesn't answer, skip to Step 5.

### Step 4: Trigger Preview

```bash
ql path/to/artifact.pdf
```

If `ql` is not found or exits with an error, do not retry: continue with Step 5, giving the file's
path, and report the failure as described in section 2.

### Step 5: Inform the User
Always give the file's path. If it was previewed, say so:
> *"The compiled document is open in QuickLook: `build/report.pdf`."*
