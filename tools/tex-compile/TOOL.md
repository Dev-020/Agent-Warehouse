---
id: tool/tex-compile
version: 0.1.0
status: draft
summary: Standalone CLI script wrapping Tectonic to compile LaTeX documents to PDF.
applies-to: [vault, codebase]
entrypoint: tex_compile.py
requires-software: [python>=3.10, tectonic]
platforms: [windows, linux, darwin]
settings: {}
requires: []
replaces: null
---

# `tool/tex-compile` — Tectonic LaTeX Compilation Tool

Standalone CLI wrapper around the modern XeTeX-based **Tectonic** engine. Compiles `.tex` source files into
publication-grade PDFs, automatically handles multi-pass compilation, resolves packages from the Tectonic
CTAN bundle cache on the fly, and formats compilation diagnostics cleanly.

Used directly by agents or via [[latex-pdf]].

---

## 1. Prerequisites & Software Requirements

- **Python**: $\ge$ 3.10.
- **Tectonic**: A working Tectonic binary.
  - On Windows: standard path `C:\tools\tectonic.exe` is automatically detected.
  - Cross-platform: detected on system `PATH` or via `TECTONIC_BIN` environment variable.

---

## 2. Usage & CLI Options

```bash
# Check if Tectonic is installed and discoverable
python tools/tex-compile/tex_compile.py --check

# Compile a LaTeX document (PDF written to same directory)
python tools/tex-compile/tex_compile.py path/to/document.tex

# Compile with explicit output directory
python tools/tex-compile/tex_compile.py path/to/document.tex --outdir build/pdf/

# Specify an explicit tectonic binary
python tools/tex-compile/tex_compile.py path/to/document.tex --tectonic-bin /usr/local/bin/tectonic

# Print full compiler stdout/stderr
python tools/tex-compile/tex_compile.py path/to/document.tex --print-output
```

### Options

| Flag | Argument | Description |
|---|---|---|
| `<tex_file>` | Positional path | The `.tex` file to compile into PDF. |
| `--outdir`, `-o` | Directory path | Output directory for the resulting PDF. Defaults to target `.tex` folder. |
| `--tectonic-bin` | File path | Explicit path or command name for the Tectonic binary. |
| `--print-output` | Flag | Print raw compiler stream even if compilation succeeds. |
| `--check` | Flag | Validate executable existence and print installed version. |

---

## 3. Diagnostic & Error Parsing

When compilation encounters syntax errors, missing packages, or LaTeX runtime failures, `tex_compile.py`
extracts actionable diagnostics:
- TeX engine fatal errors (e.g., `! Undefined control sequence`) paired with line indicators (`l.42`).
- Tectonic engine errors (`error: ...`).
- Missing font and package warnings.

The tool exits with code `0` on successful PDF creation and non-zero on failure.
