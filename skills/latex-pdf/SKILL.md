---
id: skill/latex-pdf
version: 0.1.0
status: draft
summary: Agent skill for authoring, auditing, and compiling publication-grade LaTeX documents with Tectonic.
applies-to: [vault, codebase]
settings: {}
requires: [tool/tex-compile@0.1]
replaces: null
---

# LaTeX & PDF Authoring and Compilation Skill

Standard operating procedures for converting mathematical problem sets, handwritten proof drafts, and
academic assignments into publication-grade $\mathrm{\LaTeX}$ documents and compiled PDFs using
the Tectonic engine wrapped by [[tool/tex-compile]].

Companion protocol: [[agent-protocol]] and [[session-log]].

---

## 1. Toolchain & Dependencies

This skill relies on **`tool/tex-compile`** for deterministic, single-command document builds:
- **Engine**: Tectonic (XeTeX-based, on-demand CTAN bundle downloading).
- **Execution entrypoint**: `python tools/tex-compile/tex_compile.py <file.tex>`.
- **System requirement**: Python $\ge$ 3.10 and Tectonic installed (`C:\tools\tectonic.exe` or on PATH).

---

## 2. Invariants & Data Safety Rules

> [!CAUTION] Never Round-Trip LaTeX Through Google Docs
> Native Google Docs and Google Drive conversion silently strip backslashes (`\`), destroy curly braces (`{}`),
> and corrupt mathematical syntax (such as set notation and sub/superscripts).
> **Hard rule:** All `.tex` authoring and edits must remain strictly in local text files or markdown sources.

---

## 3. Four-Step End-to-End Workflow

```
[1. Scan & Rigor Audit] ──> [2. Verbatim AMS Authoring] ──> [3. Tectonic Compile] ──> [4. PDF Verification]
```

### Step 1: Scan Inspection & Mathematical Rigor Audit
When working from handwritten notes, images, or draft solutions:
1. Inspect the source images or scans thoroughly.
2. Conduct a line-by-line rigor audit on the mathematical reasoning:
   - **Quantifier order:** Check that universal ($\forall$) and existential ($\exists$) quantifiers are in valid dependency order.
   - **Inequality bounds:** Verify strict vs non-strict inequalities ($\le, <, \ge, >$), boundary values, and triangle inequality applications.
   - **Topological definitions:** Verify rigorous statements for open balls, limit points, interior points, and $\epsilon$-neighborhoods.
   - **Supremum / Infimum:** Check bounding conditions and the $\epsilon$-characterization of $\sup$ and $\inf$.
3. If logical gaps or missing boundary arguments are detected, highlight specific line items for the author before finalizing.

### Step 2: Verbatim AMS LaTeX Authoring
1. Structure the document using standard American Mathematical Society (`amsmath`, `amssymb`, `amsthm`) environments.
2. Transcribe proofs verbatim to preserve author step designations (e.g. `(i)`, `(ii)`), naming, and structure.
3. Use semantic environments:
   - `\begin{proof} ... \end{proof}` for formal proofs.
   - `\begin{equation*} ... \end{equation*}` or `\begin{align*} ... \end{align*}` for displayed formulas.
   - Contradiction markers: include `\usepackage{stmaryrd}` when using `\lightning` or `\usepackage{amssymb}` for standard symbols.

### Step 3: Compilation via `tool/tex-compile`
Invoke the compilation tool on the authored file:

```powershell
python tools/tex-compile/tex_compile.py "Semesters/path/to/DOCUMENT.tex"
```

If compilation fails, inspect the parsed error summary emitted by `tex_compile.py`:
- For syntax errors or unescaped characters (e.g., `%`, `_`, `&`, `#`), fix the offending line.
- For missing package errors, ensure the package name is supported in TeX Live / Tectonic bundle.

### Step 4: Verification & Artifact Organization
1. Confirm the output PDF exists and has non-zero byte size.
2. Verify visual layout (no overfull horizontal boxes clipping into margins).
3. Ensure companion files (original problem statement, scans, `.tex`, and rendered `.pdf`) share consistent names.

---

## 4. Problem Set File & Directory Naming Standard

For academic submissions and problem sets, organize files into dedicated assignment folders:

```
Course_Folder/Lecture/Unit_<N>/Problem_Sets/PS<#>/
├── <LASTNAME>_<COURSE>_PS<#>_RENDER.tex      # Primary LaTeX source
├── <LASTNAME>_<COURSE>_PS<#>_RENDER.pdf      # Compiled publication PDF
├── <LASTNAME>_<COURSE>_PS<#>_SCAN.pdf        # Combined handwritten scan
└── <COURSE>_PS<#>.pdf                        # Original assignment handout
```

---

## 5. Canonical Math Submission Template

Use this canonical template for problem sets, proof exercises, and mathematical reports:

```latex
\documentclass[11pt,a4paper]{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{enumitem}
\usepackage{stmaryrd} % For \lightning contradiction symbol

\title{\textbf{Mathematics Assignment Solutions}}
\author{\textbf{Author Name}}
\date{\today}

\begin{document}
\maketitle

\noindent\rule{\textwidth}{0.5pt}

\section*{Problem 1}
\noindent\textbf{Problem Statement:}
Let $(X, d)$ be a metric space. Prove that every open ball $B_r(x)$ is an open set.

\begin{proof}
Let $y \in B_r(x)$, so that $d(x, y) < r$. Define $\epsilon = r - d(x, y) > 0$.
We claim that the open ball $B_\epsilon(y) \subseteq B_r(x)$.

Let $z \in B_\epsilon(y)$. By the triangle inequality for metric spaces:
\begin{align*}
d(x, z) &\le d(x, y) + d(y, z) \\
        &< d(x, y) + \epsilon \\
        &= d(x, y) + (r - d(x, y)) = r.
\end{align*}
Hence $z \in B_r(x)$. Therefore $B_\epsilon(y) \subseteq B_r(x)$, which demonstrates that
$B_r(x)$ is an open set.
\end{proof}

\noindent\rule{\textwidth}{0.5pt}

\end{document}
```
