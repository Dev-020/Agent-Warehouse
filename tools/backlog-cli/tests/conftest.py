"""Pytest fixtures and configuration for backlog-cli tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Add tools/backlog-cli to sys.path so backlog_cli and task are importable
CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import task


def make_repo(path: Path) -> Path:
    """Create a temporary git repository with user config and an initial commit on main."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=str(path), check=True)
    (path / "README.md").write_text("# Test Repository\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=str(path), check=True)
    return path


class RunResult:
    """Result of running task.main CLI helper."""

    def __init__(self, exit_code: int, output: str, stdout: str = "", stderr: str = ""):
        self.exit_code = exit_code
        self.output = output
        self.stdout = stdout
        self.stderr = stderr

    def __iter__(self):
        return iter((self.exit_code, self.output))

    def __getitem__(self, item):
        return (self.exit_code, self.output)[item]

    def __eq__(self, other):
        if isinstance(other, tuple) and len(other) == 2:
            return (self.exit_code, self.output) == other
        return super().__eq__(other)

    def __repr__(self):
        return f"RunResult(exit_code={self.exit_code}, output={self.output!r})"


@pytest.fixture
def run_cli(monkeypatch, capsys):
    """Run task.main in the specified directory, returning (exit_code, output)."""

    def _run(cwd: Path, *args: str) -> RunResult:
        monkeypatch.chdir(cwd)
        try:
            exit_code = task.main(list(args))
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        return RunResult(exit_code, combined, captured.out, captured.err)

    return _run
