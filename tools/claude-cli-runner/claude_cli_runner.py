#!/usr/bin/env python3
"""
Claude Code CLI Resident Session Manager.
Drives resident `claude` CLI processes over bidirectional NDJSON (stream-json) streams
with profile isolation, turn queueing, watchdog timeouts, and automatic session recycling.
"""

import argparse
import collections
from dataclasses import dataclass, field
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

# Outbound turn outcomes
OUTCOME_ANSWERED = "answered"
OUTCOME_ERROR = "error"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_CANCELLED = "cancelled"


@dataclass
class EngineConfig:
    claude_bin: str = "claude"
    profile_dir: str = os.path.abspath(".claude-engine")
    workspace_dir: str = os.path.abspath(".")
    model: str = "claude-sonnet-5"
    effort: Optional[str] = "medium"
    system_prompt: Optional[str] = None
    turn_timeout_sec: float = 180.0
    turns_per_session: int = 10
    strict_mcp_config: bool = True
    mcp_config_path: Optional[str] = None
    add_dirs: List[str] = field(default_factory=list)
    strip_tools: bool = False


@dataclass
class TurnContext:
    prompt: str
    image_data: Optional[Dict[str, Any]] = None
    submitted_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    outcome: Optional[str] = None


@dataclass
class TurnResult:
    success: bool
    text: str
    error: Optional[str] = None
    duration_api_ms: Optional[int] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    outcome: str = OUTCOME_ANSWERED


def prepare_claude_profile(profile_dir: str) -> Dict[str, str]:
    """
    Initializes an isolated profile directory and returns the environment
    variables required to restrict Claude Code to this sandbox.
    """
    abs_dir = os.path.abspath(profile_dir)
    os.makedirs(abs_dir, exist_ok=True)

    # Managed local settings inside profile to prevent telemetry/plugin leakage
    settings_path = os.path.join(abs_dir, "settings.json")
    if not os.path.exists(settings_path):
        default_settings = {
            "permissions": {"allow": []},
            "mcpServers": {}
        }
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(default_settings, f, indent=2)

    return {
        "CLAUDE_CONFIG_DIR": abs_dir,
        "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
    }


def is_claude_not_logged_in(text: str) -> bool:
    return any(phrase in text.lower() for phrase in [
        "not logged in",
        "please run /login",
        "please log in",
        "authentication required",
        "unauthorized",
    ])


class ClaudeCliSession:
    """
    Resident Claude Code session manager.
    Accepts turns one at a time over a FIFO queue, writes NDJSON envelopes to stdin,
    parses stdout NDJSON events, drains stderr, and supervises timeouts and lifecycle.
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.proc: Optional[subprocess.Popen] = None
        self.lock = threading.RLock()
        self.pending: collections.deque = collections.deque()
        self.current_turn: Optional[TurnContext] = None
        self.current_turn_tools: List[str] = []
        self.current_turn_result_event = threading.Event()
        self.current_turn_result: Optional[TurnResult] = None
        self.watchdog: Optional[threading.Timer] = None
        self.is_ready = False
        self.stopping = False
        self.turns_in_session = 0
        self.spawned_at = 0.0

        # Event hooks
        self.on_chunk: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_done: Optional[Callable[[TurnResult], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_queue_change: Optional[Callable[[int], None]] = None

    def _command(self) -> List[str]:
        cmd = [
            self.config.claude_bin,
            "-p",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--verbose",
            "--model", self.config.model,
            "--setting-sources", "project,local",
            "--disable-slash-commands",
            "--no-session-persistence",
        ]
        if self.config.effort:
            cmd.extend(["--effort", self.config.effort])
        if self.config.strip_tools:
            cmd.extend(["--tools", ""])
        if self.config.strict_mcp_config:
            cmd.append("--strict-mcp-config")
        if self.config.mcp_config_path:
            cmd.extend(["--mcp-config", self.config.mcp_config_path])
        for d in self.config.add_dirs:
            cmd.extend(["--add-dir", d])
        if self.config.system_prompt:
            cmd.extend(["--system-prompt", self.config.system_prompt])
        return cmd

    def start(self):
        with self.lock:
            if self.stopping or (self.proc and self.proc.poll() is None):
                return
            env = os.environ.copy()
            env.update(prepare_claude_profile(self.config.profile_dir))
            cmd = self._command()
            os.makedirs(self.config.workspace_dir, exist_ok=True)
            self.spawned_at = time.time()
            self.turns_in_session = 0
            self.is_ready = False

            try:
                self.proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.config.workspace_dir,
                    env=env,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                )
            except Exception as e:
                self._emit_error(f"Failed to spawn Claude Code binary ({self.config.claude_bin}): {e}")
                return

            # Ready on spawn invariant: Claude accepts input immediately on pipe availability
            self.is_ready = True
            threading.Thread(target=self._stdout_loop, args=(self.proc,), daemon=True).start()
            threading.Thread(target=self._stderr_loop, args=(self.proc,), daemon=True).start()
            self._pump()

    def stop(self):
        with self.lock:
            self.stopping = True
            self._cancel_watchdog()
            proc = self.proc
            self.proc = None
            self.is_ready = False
            self.pending.clear()

        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def submit(self, prompt: str, image_data: Optional[Dict[str, Any]] = None) -> TurnContext:
        """Enqueues a turn to the session FIFO queue."""
        context = TurnContext(prompt=prompt, image_data=image_data)
        with self.lock:
            self.pending.append(context)
            if self.on_queue_change:
                self.on_queue_change(len(self.pending))
            if not self.proc or self.proc.poll() is not None:
                self.start()
            else:
                self._pump()
        return context

    def send_and_wait(self, prompt: str, timeout: Optional[float] = None, image_data: Optional[Dict[str, Any]] = None) -> TurnResult:
        """Synchronously executes a turn and waits for the final result."""
        evt = threading.Event()
        res_box: List[TurnResult] = []

        context = TurnContext(prompt=prompt, image_data=image_data)

        def _handle_result(res: TurnResult):
            res_box.append(res)
            evt.set()

        with self.lock:
            self.pending.append((context, _handle_result))
            if self.on_queue_change:
                self.on_queue_change(len(self.pending))
            if not self.proc or self.proc.poll() is not None:
                self.start()
            else:
                self._pump()

        wait_time = timeout or self.config.turn_timeout_sec + 5.0
        if not evt.wait(timeout=wait_time):
            return TurnResult(
                success=False,
                text="",
                error=f"Turn execution timed out after {wait_time}s",
                outcome=OUTCOME_TIMEOUT,
            )
        return res_box[0]

    def _pump(self):
        with self.lock:
            if not self.is_ready or not self.proc or self.current_turn or not self.pending:
                return
            item = self.pending.popleft()
            if isinstance(item, tuple):
                turn_ctx, callback = item
            else:
                turn_ctx, callback = item, None

            self.current_turn = turn_ctx
            self.current_turn_callback = callback
            self.current_turn_tools = []
            turn_ctx.started_at = time.time()
            self._start_watchdog(turn_ctx)

            # Build payload
            if turn_ctx.image_data:
                content = [turn_ctx.image_data, {"type": "text", "text": turn_ctx.prompt}]
            else:
                content = turn_ctx.prompt

            payload = {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": content
                }
            }

            try:
                line = json.dumps(payload) + "\n"
                self.proc.stdin.write(line)
                self.proc.stdin.flush()
            except Exception as e:
                self._emit_error(f"Failed to write turn to Claude stdin: {e}")
                self._complete_turn(self.proc, None, str(e), outcome=OUTCOME_ERROR)

    def _start_watchdog(self, turn: TurnContext):
        self._cancel_watchdog()
        self.watchdog = threading.Timer(self.config.turn_timeout_sec, self._on_timeout, args=(turn,))
        self.watchdog.daemon = True
        self.watchdog.start()

    def _cancel_watchdog(self):
        if self.watchdog:
            self.watchdog.cancel()
            self.watchdog = None

    def _on_timeout(self, turn: TurnContext):
        with self.lock:
            if self.current_turn is not turn:
                return
            proc = self.proc
            self.proc = None
            self.is_ready = False
            self.current_turn = None
            self._cancel_watchdog()

        if proc:
            try:
                proc.kill()
            except Exception:
                pass

        err_msg = f"No answer after {self.config.turn_timeout_sec}s timeout. Session restarted."
        self._emit_error(err_msg)
        result = TurnResult(success=False, text="", error=err_msg, outcome=OUTCOME_TIMEOUT)
        if hasattr(self, "current_turn_callback") and self.current_turn_callback:
            self.current_turn_callback(result)
        if self.on_done:
            self.on_done(result)

        if not self.stopping:
            self.start()

    def _stdout_loop(self, proc: subprocess.Popen):
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._handle_event(proc, data)
        except Exception:
            pass
        self._on_exit(proc)

    def _stderr_loop(self, proc: subprocess.Popen):
        try:
            for line in proc.stderr:
                line = line.strip()
                if not line:
                    continue
                if is_claude_not_logged_in(line):
                    self._emit_error(f"Claude authentication required: {line}")
        except Exception:
            pass

    def _handle_event(self, proc: subprocess.Popen, data: Dict[str, Any]):
        event_type = data.get("type")
        if event_type == "system" and data.get("subtype") == "init":
            model = data.get("model", self.config.model)
            if self.on_status:
                self.on_status(f"Claude ready ({model})")
        elif event_type == "assistant":
            msg = data.get("message") or {}
            content = msg.get("content") or []
            for block in content:
                b_type = block.get("type")
                if b_type == "text":
                    chunk = block.get("text", "")
                    if chunk and self.on_chunk:
                        self.on_chunk(chunk)
                elif b_type == "tool_use":
                    tool_name = block.get("name", "tool")
                    self.current_turn_tools.append(tool_name)
                    if self.on_status:
                        self.on_status(f"Using {tool_name}...")
        elif event_type == "result":
            is_error = data.get("is_error", False)
            subtype = data.get("subtype")
            text = (data.get("result") or "").strip()
            duration_ms = data.get("duration_api_ms")
            usage = data.get("usage") or {}

            if subtype == "success" and not is_error:
                self._complete_turn(proc, text, None, duration_ms, usage, OUTCOME_ANSWERED)
            else:
                err = text or "; ".join(map(str, data.get("errors") or [])) or subtype or "Unknown error"
                if is_claude_not_logged_in(str(err)):
                    err = f"Claude is not logged in. Run 'claude login' in profile: {self.config.profile_dir}"
                self._complete_turn(proc, None, str(err), duration_ms, usage, OUTCOME_ERROR)

    def _complete_turn(
        self,
        proc: subprocess.Popen,
        response: Optional[str],
        error: Optional[str],
        duration_ms: Optional[int] = None,
        usage: Optional[Dict[str, Any]] = None,
        outcome: str = OUTCOME_ANSWERED
    ):
        with self.lock:
            if proc is not self.proc:
                return
            turn = self.current_turn
            cb = getattr(self, "current_turn_callback", None)
            self.current_turn = None
            self.current_turn_callback = None
            self._cancel_watchdog()
            self.turns_in_session += 1

            recycle_needed = (
                self.config.turns_per_session > 0
                and self.turns_in_session >= self.config.turns_per_session
                and not self.stopping
            )
            recycle_proc = None
            if recycle_needed:
                recycle_proc = self.proc
                self.proc = None
                self.is_ready = False

        if turn:
            turn.outcome = outcome
            result = TurnResult(
                success=(error is None),
                text=response or "",
                error=error,
                duration_api_ms=duration_ms,
                usage=usage or {},
                outcome=outcome,
            )
            if cb:
                cb(result)
            if self.on_done:
                self.on_done(result)

        if recycle_proc:
            try:
                recycle_proc.terminate()
                recycle_proc.wait(timeout=2)
            except Exception:
                try:
                    recycle_proc.kill()
                except Exception:
                    pass
            self.start()

        with self.lock:
            self._pump()
            if self.on_queue_change:
                self.on_queue_change(len(self.pending))

    def _on_exit(self, proc: subprocess.Popen):
        with self.lock:
            if proc is not self.proc:
                return
            code = proc.poll()
            self.proc = None
            self.is_ready = False
            self._cancel_watchdog()
            turn = self.current_turn
            cb = getattr(self, "current_turn_callback", None)
            self.current_turn = None
            self.current_turn_callback = None
            restart = bool(self.pending) and not self.stopping

        if turn:
            err = f"Claude process exited before answering (exit code {code})"
            self._emit_error(err)
            result = TurnResult(success=False, text="", error=err, outcome=OUTCOME_ERROR)
            if cb:
                cb(result)
            if self.on_done:
                self.on_done(result)

        if restart:
            self.start()

    def _emit_error(self, msg: str):
        if self.on_error:
            self.on_error(msg)


# ---- CLI interface --------------------------------------------------------

def cmd_check(args: argparse.Namespace) -> int:
    claude_bin = shutil.which(args.bin)
    profile_dir = os.path.abspath(args.profile_dir)
    settings_file = os.path.join(profile_dir, "settings.json")
    cred_file = os.path.join(profile_dir, ".credentials.json")

    info = {
        "claude_bin": claude_bin,
        "claude_found": bool(claude_bin),
        "profile_dir": profile_dir,
        "profile_exists": os.path.isdir(profile_dir),
        "settings_exists": os.path.isfile(settings_file),
        "authenticated": os.path.isfile(cred_file),
    }

    if args.json:
        print(json.dumps(info, indent=2))
        return 0 if info["claude_found"] else 1

    print("Claude Code CLI Diagnostic:")
    print(f"  Binary:        {claude_bin or 'NOT FOUND'}")
    print(f"  Profile Dir:   {profile_dir} ({'exists' if info['profile_exists'] else 'missing'})")
    print(f"  Settings:      {'configured' if info['settings_exists'] else 'missing'}")
    print(f"  Credentials:   {'found' if info['authenticated'] else 'missing (run profile login)'}")

    if not info["claude_found"]:
        print("\nError: claude binary not found on PATH. Install via: npm install -g @anthropic-ai/claude-code")
        return 1
    return 0


def cmd_profile_setup(args: argparse.Namespace) -> int:
    profile_dir = os.path.abspath(args.profile_dir)
    env = prepare_claude_profile(profile_dir)
    print(f"Profile directory initialized at: {profile_dir}")
    print("Environment variables configured for isolation:")
    for k, v in env.items():
        print(f"  {k}={v}")
    return 0


def cmd_profile_login(args: argparse.Namespace) -> int:
    profile_dir = os.path.abspath(args.profile_dir)
    prepare_claude_profile(profile_dir)
    claude_bin = shutil.which(args.bin) or args.bin

    print(f"Launching one-time login for profile: {profile_dir}")
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = profile_dir
    env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] = "1"

    proc = subprocess.run([claude_bin, "login"], env=env)
    return proc.returncode


def cmd_run(args: argparse.Namespace) -> int:
    config = EngineConfig(
        claude_bin=args.bin,
        profile_dir=args.profile_dir,
        workspace_dir=args.workspace,
        model=args.model,
        effort=args.effort,
        turn_timeout_sec=args.timeout,
        system_prompt=args.system_prompt,
    )
    session = ClaudeCliSession(config)
    session.start()

    if not args.json:
        session.on_chunk = lambda c: print(c, end="", flush=True)

    result = session.send_and_wait(args.prompt)
    session.stop()

    if args.json:
        print(json.dumps({
            "success": result.success,
            "response": result.text,
            "error": result.error,
            "duration_ms": result.duration_api_ms,
            "usage": result.usage,
            "outcome": result.outcome,
        }, indent=2))
    else:
        print()
        if not result.success:
            print(f"\n[Error] {result.error}", file=sys.stderr)
            return 1
    return 0 if result.success else 1


def cmd_chat(args: argparse.Namespace) -> int:
    config = EngineConfig(
        claude_bin=args.bin,
        profile_dir=args.profile_dir,
        workspace_dir=args.workspace,
        model=args.model,
        effort=args.effort,
    )
    session = ClaudeCliSession(config)
    session.start()

    session.on_chunk = lambda c: print(c, end="", flush=True)
    session.on_status = lambda s: print(f"\n[{s}]", flush=True)

    print(f"Resident Claude Code Session ({config.model}). Type 'exit' or Ctrl+C to quit.\n")
    try:
        while True:
            prompt = input("You: ").strip()
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit"):
                break
            print("Claude: ", end="", flush=True)
            res = session.send_and_wait(prompt)
            print()
            if not res.success:
                print(f"[Error: {res.error}]")
            print()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting session...")
    finally:
        session.stop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Resident Claude Code CLI Session Manager")
    parser.add_argument("--bin", default="claude", help="Path to claude binary (default: claude)")
    parser.add_argument("--profile-dir", default=".claude-engine", help="Path to isolated profile dir")

    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_check = sub.add_parser("check", help="Verify environment, binary, and credentials")
    p_check.add_argument("--json", action="store_true", help="Output JSON")

    p_setup = sub.add_parser("profile", help="Manage engine profile")
    p_setup_sub = p_setup.add_subparsers(dest="profile_action", required=True)
    p_setup_sub.add_parser("setup", help="Scaffold isolated profile directory")
    p_setup_sub.add_parser("login", help="Launch claude login scoped to profile")

    p_run = sub.add_parser("run", help="Execute single prompt turn")
    p_run.add_argument("--prompt", required=True, help="Prompt text")
    p_run.add_argument("--workspace", default=".", help="Working directory")
    p_run.add_argument("--model", default="claude-sonnet-5", help="Model name")
    p_run.add_argument("--effort", default="medium", help="Reasoning effort tier")
    p_run.add_argument("--timeout", type=float, default=180.0, help="Turn timeout in seconds")
    p_run.add_argument("--system-prompt", default=None, help="System prompt override")
    p_run.add_argument("--json", action="store_true", help="Output JSON response")

    p_chat = sub.add_parser("chat", help="Start interactive resident conversation")
    p_chat.add_argument("--workspace", default=".", help="Working directory")
    p_chat.add_argument("--model", default="claude-sonnet-5", help="Model name")
    p_chat.add_argument("--effort", default="medium", help="Reasoning effort tier")

    args = parser.parse_args()

    if args.subcommand == "check":
        return cmd_check(args)
    if args.subcommand == "profile":
        if args.profile_action == "setup":
            return cmd_profile_setup(args)
        if args.profile_action == "login":
            return cmd_profile_login(args)
    if args.subcommand == "run":
        return cmd_run(args)
    if args.subcommand == "chat":
        return cmd_chat(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
