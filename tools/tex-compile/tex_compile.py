#!/usr/bin/env python3
"""Standalone CLI wrapper around the Tectonic LaTeX engine.

Compiles LaTeX documents (.tex) into publication-quality PDFs, automatically
resolving packages from the Tectonic bundle cache, managing multi-pass compilation,
and parsing diagnostics cleanly.

Usage:
    python tex_compile.py document.tex [--outdir PATH] [--tectonic-bin PATH]
    python tex_compile.py --check
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def find_tectonic(custom_bin: str | None = None) -> Path | None:
    """Locate the tectonic binary via custom path, env var, standard locations, or PATH."""
    if custom_bin:
        p = Path(custom_bin)
        if p.is_file():
            return p.resolve()
        which = shutil.which(custom_bin)
        if which:
            return Path(which).resolve()
        return None

    # Check environment variable
    env_bin = os.environ.get("TECTONIC_BIN")
    if env_bin:
        p = Path(env_bin)
        if p.is_file():
            return p.resolve()

    # Standard Windows install location
    if sys.platform == "win32":
        default_win = Path(r"C:\tools\tectonic.exe")
        if default_win.is_file():
            return default_win.resolve()

    # System PATH
    on_path = shutil.which("tectonic")
    if on_path:
        return Path(on_path).resolve()

    return None


def parse_tectonic_diagnostics(output: str) -> list[str]:
    """Extract actionable diagnostic messages and errors from compiler output."""
    diagnostics: list[str] = []
    lines = output.splitlines()

    for i, line in enumerate(lines):
        line_str = line.strip()
        # Rust / Tectonic driver error
        if line_str.startswith("error:"):
            diagnostics.append(line_str)
        # TeX engine fatal / syntax error
        elif line_str.startswith("!"):
            diag = line_str
            # Look ahead for line reference (e.g. l.42 \badcommand)
            for j in range(i + 1, min(i + 4, len(lines))):
                sub = lines[j].strip()
                if sub.startswith("l.") or sub.startswith("-->"):
                    diag += f" ({sub})"
                    break
            diagnostics.append(diag)
        # Missing font or package warnings
        elif "warning:" in line_str.lower() and ("font" in line_str.lower() or "package" in line_str.lower()):
            diagnostics.append(line_str)

    return diagnostics


def compile_tex(
    tex_path: Path,
    outdir: Path,
    tectonic_bin: Path,
    print_output: bool = False,
) -> int:
    """Run Tectonic to compile a .tex file into a PDF."""
    if not tex_path.is_file():
        print(f"Error: LaTeX source file not found: {tex_path}", file=sys.stderr)
        return 1

    outdir.mkdir(parents=True, exist_ok=True)
    expected_pdf = outdir / f"{tex_path.stem}.pdf"

    cmd = [
        str(tectonic_bin),
        "--outdir",
        str(outdir),
        str(tex_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as e:
        print(f"Error executing Tectonic ({tectonic_bin}): {e}", file=sys.stderr)
        return 1

    if print_output or proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout)

    if proc.returncode != 0:
        print("\n--- Compilation Failed ---", file=sys.stderr)
        diags = parse_tectonic_diagnostics(proc.stdout)
        if diags:
            print("Summary of errors:", file=sys.stderr)
            for d in diags:
                print(f"  * {d}", file=sys.stderr)
        else:
            print("No structured error signatures found. Inspect compiler log above.", file=sys.stderr)
        return proc.returncode

    if not expected_pdf.is_file():
        print(f"Error: Compiler reported success, but expected PDF was not found at {expected_pdf}", file=sys.stderr)
        return 1

    size_kb = expected_pdf.stat().st_size / 1024.0
    print(f"Compilation successful: {expected_pdf} ({size_kb:.1f} KB)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile LaTeX documents to PDF using the self-contained Tectonic engine."
    )
    parser.add_argument("tex_file", nargs="?", help="Path to the .tex file to compile")
    parser.add_argument("--outdir", "-o", help="Directory where generated PDF is written (default: same as .tex)")
    parser.add_argument("--tectonic-bin", help="Explicit path to tectonic executable")
    parser.add_argument("--print-output", action="store_true", help="Print full compiler output even on success")
    parser.add_argument("--check", action="store_true", help="Check Tectonic environment and installation")

    args = parser.parse_args(argv)

    tectonic_path = find_tectonic(args.tectonic_bin)

    if args.check:
        print("Tectonic Environment Check:")
        if tectonic_path:
            print(f"  Status: FOUND at {tectonic_path}")
            try:
                ver = subprocess.check_output([str(tectonic_path), "--version"], text=True).strip()
                print(f"  Version: {ver}")
                return 0
            except Exception as e:
                print(f"  Error running version query: {e}")
                return 1
        else:
            print("  Status: NOT FOUND")
            print("  Searched: TECTONIC_BIN env, C:\\tools\\tectonic.exe, PATH")
            print("  To fix: Install Tectonic or pass --tectonic-bin PATH")
            return 1

    if not args.tex_file:
        parser.print_help(sys.stderr)
        return 1

    if not tectonic_path:
        print(
            "Error: Tectonic compiler executable not found.\n"
            "Checked locations: custom argument, TECTONIC_BIN env, C:\\tools\\tectonic.exe, and system PATH.\n"
            "Please ensure Tectonic is installed or specify path with --tectonic-bin.",
            file=sys.stderr,
        )
        return 1

    target_tex = Path(args.tex_file).resolve()
    outdir = Path(args.outdir).resolve() if args.outdir else target_tex.parent

    return compile_tex(
        tex_path=target_tex,
        outdir=outdir,
        tectonic_bin=tectonic_path,
        print_output=args.print_output,
    )


if __name__ == "__main__":
    sys.exit(main())
