#!/usr/bin/env python3
"""
Antigravity CLI Resident Session Manager.
Drives resident `agy` CLI processes over bidirectional NDJSON (stream-json) streams
with ready-on-init synchronization, profile sandboxing, glog log error recovery,
watchdog timeouts, and unfinished tool auto-denial detection.
"""

import argparse
import collections
from dataclasses import dataclass, field
import glob
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

OUTCOME_ANSWERED = "answered"
OUTCOME_ERROR = "error"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_CANCELLED = "cancelled"

GLOG_ERROR_REGEX = re.compile(r"\bE\d{4} \d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\S+\]\s*(.+)$")
GENERIC_LOG_ERRORS = re.compile(
    r"run ended with error|Agent execution terminated due to error|not logged into Antigravity|Clearcut responded",
    re.IGNORECASE
)
PERMISSION_PROBLEM_REGEX = re.compile(
    r"auto-denied|permission check failed|denied permission",
    re.IGNORECASE
)


@dataclass
class EngineConfig:
    agy_bin: str = "agy"
    profile_dir: str = os.path.abspath(".agy-engine")
    workspace_dir: str = os.path.abspath(".")
    model: str = "gemini-3.8-flash-medium"
    turn_timeout_sec: float = 120.0
    turns_per_session: int = 15
    use_ai_credits: bool = True
    permission_grants: List[str] = field(default_factory=list)
    log_dir: Optional[str] = None


@dataclass
class TurnContext:
    prompt: str
    submitted_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    outcome: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    unfinished_tools: Dict[Any, str] = field(default_factory=dict)
    announced_steps: set = field(default_factory=set)


@dataclass
class TurnResult:
    success: bool
    text: str
    error: Optional[str] = None
    duration_seconds: Optional[float] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    denied_actions: List[str] = field(default_factory=list)
    outcome: str = OUTCOME_ANSWERED


def default_agy_log_dir() -> str:
    user_home = os.path.expanduser("~")
    return os.path.join(user_home, ".gemini", "antigravity-cli", "log")


def prepare_agy_profile(
    profile_dir: str,
    workspace_dir: str,
    grants: Optional[List[str]] = None,
    use_ai_credits: bool = True
) -> Dict[str, str]:
    """
    Sets up an isolated profile sandbox for Antigravity CLI and returns
    environment overrides. Redirects TEMP/TMP into the profile to prevent
    uncontrolled filesystem read/write access.
    """
    abs_profile = os.path.abspath(profile_dir)
    abs_workspace = os.path.abspath(workspace_dir).replace(os.sep, "/")
    gemini_dir = os.path.join(abs_profile, ".gemini")
    config_dir = os.path.join(gemini_dir, "config")
    agy_cli_dir = os.path.join(gemini_dir, "antigravity-cli")
    temp_dir = os.path.join(abs_profile, "tmp")

    for d in (config_dir, agy_cli_dir, temp_dir):
        os.makedirs(d, exist_ok=True)

    # 1. config.json - AI credits and file access policy
    config_json_path = os.path.join(config_dir, "config.json")
    config_data = {
        "userSettings": {
            "useAiCredits": bool(use_ai_credits),
            "nonWorkspaceFileAccessPolicy": "AGENT_SETTING_POLICY_DENY"
        }
    }
    with open(config_json_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    # 2. settings.json - bare recursive path grants
    allow_rules = [f"read_file({abs_workspace})"]
    if grants:
        for g in grants:
            if g not in allow_rules:
                allow_rules.append(g)

    settings_json_path = os.path.join(agy_cli_dir, "settings.json")
    settings_data = {"permissions": {"allow": allow_rules}}
    with open(settings_json_path, "w", encoding="utf-8") as f:
        json.dump(settings_data, f, indent=2)

    # 3. mcp_config.json - empty to isolate from global host MCP servers
    mcp_config_path = os.path.join(config_dir, "mcp_config.json")
    with open(mcp_config_path, "w", encoding="utf-8") as f:
        json.dump({"mcpServers": {}}, f, indent=2)

    return {
        "USERPROFILE": abs_profile,
        "HOME": abs_profile,
        "TEMP": temp_dir,
        "TMP": temp_dir,
    }


def find_last_agy_log_error(log_dir: str, workspace_dir: str, spawned_after: float = 0.0) -> Optional[str]:
    """
    Recovers the true error reason from Antigravity's internal glog files.
    Tails the newest cli-*.log file matching the target workspace directory.
    """
    if not os.path.isdir(log_dir):
        return None

    try:
        workspace_marker = f"workspacedirs=[{workspace_dir}]".lower()
        candidates = sorted(
            glob.glob(os.path.join(log_dir, "cli-*.log")),
            key=os.path.getmtime,
            reverse=True
        )[:10]

        for path in candidates:
            if spawned_after and os.path.getmtime(path) < (spawned_after - 10):
                break
            with open(path, "rb") as f:
                size = os.fstat(f.fileno()).st_size
                head = f.read(64 * 1024).decode("utf-8", "replace").lower()
                if workspace_marker not in head:
                    continue
                f.seek(max(0, size - 64 * 1024))
                lines = f.read().decode("utf-8", "replace").splitlines()

            # Scope to the last turn's 'sending message' marker
            start_idx = 0
            for i in range(len(lines) - 1, -1, -1):
                if "sending message" in lines[i]:
                    start_idx = i
                    break

            for line in reversed(lines[start_idx:]):
                match = GLOG_ERROR_REGEX.search(line)
                if match:
                    err_msg = match.group(1).strip()
                    if not GENERIC_LOG_ERRORS.search(err_msg):
                        return err_msg[:300]
    except Exception:
        return None
    return None


class AntigravityCliSession:
    """
    Resident Antigravity CLI session manager.
    Enforces ready-on-init synchronization, manages FIFO queueing, parses
    step_update streaming deltas, detects tool auto-denials, and performs glog recovery.
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.proc: Optional[subprocess.Popen] = None
        self.lock = threading.RLock()
        self.pending: collections.deque = collections.deque()
        self.current_turn: Optional[TurnContext] = None
        self.current_turn_callback: Optional[Callable[[TurnResult], None]] = None
        self.watchdog: Optional[threading.Timer] = None
        self.is_ready = False
        self.stopping = False
        self.turns_in_session = 0
        self.spawned_at = 0.0
        self.conversation_id: Optional[str] = None
        self.denials_seen = 0

        # Event hooks
        self.on_chunk: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_done: Optional[Callable[[TurnResult], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_queue_change: Optional[Callable[[int], None]] = None

    def _command(self) -> List[str]:
        return [
            self.config.agy_bin,
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--model", self.config.model,
        ]

    def start(self):
        with self.lock:
            if self.stopping or (self.proc and self.proc.poll() is None):
                return
            env = os.environ.copy()
            env.update(prepare_agy_profile(
                self.config.profile_dir,
                self.config.workspace_dir,
                self.config.permission_grants,
                self.config.use_ai_credits,
            ))
            cmd = self._command()
            os.makedirs(self.config.workspace_dir, exist_ok=True)
            self.spawned_at = time.time()
            self.turns_in_session = 0
            self.is_ready = False
            self.denials_seen = 0

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
                self._emit_error(f"Failed to spawn Antigravity CLI binary ({self.config.agy_bin}): {e}")
                return

            threading.Thread(target=self._stdout_loop, args=(self.proc,), daemon=True).start()
            threading.Thread(target=self._stderr_loop, args=(self.proc,), daemon=True).start()

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

    def submit(self, prompt: str) -> TurnContext:
        """Enqueues a prompt turn."""
        context = TurnContext(prompt=prompt)
        with self.lock:
            self.pending.append(context)
            if self.on_queue_change:
                self.on_queue_change(len(self.pending))
            if not self.proc or self.proc.poll() is not None:
                self.start()
            else:
                self._pump()
        return context

    def send_and_wait(self, prompt: str, timeout: Optional[float] = None) -> TurnResult:
        """Synchronously executes a turn and waits for the final result."""
        evt = threading.Event()
        res_box: List[TurnResult] = []

        context = TurnContext(prompt=prompt)

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

        wait_time = timeout or (self.config.turn_timeout_sec + 5.0)
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
            # Ready on Init timing invariant: agy must have emitted `init` before dispatch
            if not self.is_ready or not self.proc or self.current_turn or not self.pending:
                return
            item = self.pending.popleft()
            if isinstance(item, tuple):
                turn_ctx, callback = item
            else:
                turn_ctx, callback = item, None

            self.current_turn = turn_ctx
            self.current_turn_callback = callback
            turn_ctx.started_at = time.time()
            self._start_watchdog(turn_ctx)

            payload = {
                "event": "user",
                "message": {
                    "role": "user",
                    "content": turn_ctx.prompt,
                }
            }

            try:
                line = json.dumps(payload) + "\n"
                self.proc.stdin.write(line)
                self.proc.stdin.flush()
            except Exception as e:
                self._emit_error(f"Failed to write turn to agy stdin: {e}")
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

        err_msg = f"No result from agy after {self.config.turn_timeout_sec}s timeout. Session restarted."
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
                if PERMISSION_PROBLEM_REGEX.search(line):
                    self._emit_error(f"Antigravity headless permission denial: {line}")
        except Exception:
            pass

    def _handle_event(self, proc: subprocess.Popen, data: Dict[str, Any]):
        event = data.get("event")

        if event == "init":
            with self.lock:
                if proc is not self.proc:
                    return
                self.is_ready = True
                self.denials_seen = 0
                self.conversation_id = data.get("conversation_id")
                init_info = data.get("init") or {}
                perm_mode = init_info.get("permission_mode", "unknown")
                if self.on_status:
                    self.on_status(f"Antigravity ready ({self.config.model}, {perm_mode})")
                self._pump()

        elif event == "step_update":
            step = data.get("step_update") or {}
            turn = self.current_turn
            if not turn:
                return

            step_type = step.get("step_type")
            state = step.get("state")
            step_idx = step.get("step_index")

            if step_type == "tool":
                tool_name = step.get("tool_name") or "tool"
                tool_info = step.get("tool_info") or {}
                if state == "ACTIVE" and step_idx not in turn.announced_steps:
                    turn.announced_steps.add(step_idx)
                    turn.unfinished_tools[step_idx] = tool_name
                    turn.tools_used.append(tool_name)
                    if self.on_status:
                        self.on_status(f"Using {tool_name}...")
                elif state == "DONE":
                    turn.unfinished_tools.pop(step_idx, None)

            elif step_type == "agent_response":
                delta = step.get("text_delta")
                if delta and self.on_chunk:
                    self.on_chunk(delta)
                if state == "DONE" and self.on_status:
                    self.on_status("Thinking...")

        elif event == "result":
            res = data.get("result") or {}
            status = res.get("status")
            response = (res.get("response") or "").strip()
            duration_sec = res.get("duration_seconds")
            usage = res.get("usage") or {}

            denied = self._extract_denials(proc, res.get("denied_actions"))
            blocked = self._get_unfinished_tools()

            if status == "SUCCESS" and not response and (denied or blocked):
                all_blocked = list(dict.fromkeys(blocked + denied))
                names = ", ".join(all_blocked)
                err_msg = f"Operation blocked: Antigravity attempted to use {names} without permission grant."
                self._complete_turn(proc, None, err_msg, duration_sec, usage, denied, OUTCOME_ERROR)
            elif status == "SUCCESS":
                self._complete_turn(proc, response, None, duration_sec, usage, denied, OUTCOME_ANSWERED)
            else:
                detail = self._resolve_log_error()
                reason = detail or res.get("error") or status or "Unknown error"
                self._complete_turn(proc, None, reason, duration_sec, usage, denied, OUTCOME_ERROR)

    def _extract_denials(self, proc: subprocess.Popen, denied_actions: Any) -> List[str]:
        if not isinstance(denied_actions, list):
            return []
        with self.lock:
            if proc is not self.proc:
                return []
            if len(denied_actions) < self.denials_seen:
                self.denials_seen = 0
            fresh = denied_actions[self.denials_seen:]
            self.denials_seen = len(denied_actions)

        names = []
        for item in fresh:
            action = item.get("action") if isinstance(item, dict) else item
            display = item.get("display_name") if isinstance(item, dict) else None
            name = display or action or "a tool"
            if name not in names:
                names.append(str(name))
        return names

    def _get_unfinished_tools(self) -> List[str]:
        if not self.current_turn or not self.current_turn.unfinished_tools:
            return []
        return list(dict.fromkeys(self.current_turn.unfinished_tools.values()))

    def _resolve_log_error(self) -> Optional[str]:
        log_dir = self.config.log_dir or default_agy_log_dir()
        return find_last_agy_log_error(log_dir, self.config.workspace_dir, self.spawned_at)

    def _complete_turn(
        self,
        proc: subprocess.Popen,
        response: Optional[str],
        error: Optional[str],
        duration_sec: Optional[float] = None,
        usage: Optional[Dict[str, Any]] = None,
        denied_actions: Optional[List[str]] = None,
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
                duration_seconds=duration_sec,
                usage=usage or {},
                denied_actions=denied_actions or [],
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
            err = f"Antigravity CLI exited before answering (exit code {code})"
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
    agy_bin = shutil.which(args.bin)
    profile_dir = os.path.abspath(args.profile_dir)
    settings_file = os.path.join(profile_dir, ".gemini", "antigravity-cli", "settings.json")
    log_dir = default_agy_log_dir()

    info = {
        "agy_bin": agy_bin,
        "agy_found": bool(agy_bin),
        "profile_dir": profile_dir,
        "profile_exists": os.path.isdir(profile_dir),
        "settings_exists": os.path.isfile(settings_file),
        "log_dir": log_dir,
        "log_dir_exists": os.path.isdir(log_dir),
    }

    if args.json:
        print(json.dumps(info, indent=2))
        return 0 if info["agy_found"] else 1

    print("Antigravity CLI Diagnostic:")
    print(f"  Binary:        {agy_bin or 'NOT FOUND'}")
    print(f"  Profile Dir:   {profile_dir} ({'configured' if info['settings_exists'] else 'not set up'})")
    print(f"  Log Directory: {log_dir} ({'accessible' if info['log_dir_exists'] else 'missing'})")

    if not info["agy_found"]:
        print("\nError: agy binary not found on PATH. Ensure Antigravity CLI is installed.")
        return 1
    return 0


def cmd_profile_setup(args: argparse.Namespace) -> int:
    profile_dir = os.path.abspath(args.profile_dir)
    workspace_dir = os.path.abspath(args.workspace)
    env = prepare_agy_profile(profile_dir, workspace_dir)
    print(f"Antigravity profile initialized at: {profile_dir}")
    print(f"Workspace granted: {workspace_dir}")
    print("Environment overrides:")
    for k, v in env.items():
        print(f"  {k}={v}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = EngineConfig(
        agy_bin=args.bin,
        profile_dir=args.profile_dir,
        workspace_dir=args.workspace,
        model=args.model,
        turn_timeout_sec=args.timeout,
    )
    session = AntigravityCliSession(config)
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
            "duration_sec": result.duration_seconds,
            "usage": result.usage,
            "denied_actions": result.denied_actions,
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
        agy_bin=args.bin,
        profile_dir=args.profile_dir,
        workspace_dir=args.workspace,
        model=args.model,
    )
    session = AntigravityCliSession(config)
    session.start()

    session.on_chunk = lambda c: print(c, end="", flush=True)
    session.on_status = lambda s: print(f"\n[{s}]", flush=True)

    print(f"Resident Antigravity Session ({config.model}). Type 'exit' or Ctrl+C to quit.\n")
    try:
        while True:
            prompt = input("You: ").strip()
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit"):
                break
            print("Antigravity: ", end="", flush=True)
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


def cmd_log_diagnostics(args: argparse.Namespace) -> int:
    log_dir = args.log_dir or default_agy_log_dir()
    workspace_dir = os.path.abspath(args.workspace)
    err = find_last_agy_log_error(log_dir, workspace_dir)
    if err:
        print(f"Latest Antigravity glog error: {err}")
        return 0
    print("No recent glog errors found in log files.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Resident Antigravity CLI Session Manager")
    parser.add_argument("--bin", default="agy", help="Path to agy binary (default: agy)")
    parser.add_argument("--profile-dir", default=".agy-engine", help="Path to isolated profile dir")

    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_check = sub.add_parser("check", help="Verify environment, binary, and log access")
    p_check.add_argument("--json", action="store_true", help="Output JSON")

    p_setup = sub.add_parser("profile", help="Manage engine profile")
    p_setup_sub = p_setup.add_subparsers(dest="profile_action", required=True)
    p_init = p_setup_sub.add_parser("setup", help="Scaffold isolated profile directory")
    p_init.add_argument("--workspace", default=".", help="Workspace path to grant")

    p_run = sub.add_parser("run", help="Execute single prompt turn")
    p_run.add_argument("--prompt", required=True, help="Prompt text")
    p_run.add_argument("--workspace", default=".", help="Working directory")
    p_run.add_argument("--model", default="gemini-3.8-flash-medium", help="Model name")
    p_run.add_argument("--timeout", type=float, default=120.0, help="Turn timeout in seconds")
    p_run.add_argument("--json", action="store_true", help="Output JSON response")

    p_chat = sub.add_parser("chat", help="Start interactive resident conversation")
    p_chat.add_argument("--workspace", default=".", help="Working directory")
    p_chat.add_argument("--model", default="gemini-3.8-flash-medium", help="Model name")

    p_diag = sub.add_parser("log-diagnostics", help="Parse glog error from cli-*.log")
    p_diag.add_argument("--workspace", default=".", help="Working directory marker")
    p_diag.add_argument("--log-dir", default=None, help="Log directory override")

    args = parser.parse_args()

    if args.subcommand == "check":
        return cmd_check(args)
    if args.subcommand == "profile" and args.profile_action == "setup":
        return cmd_profile_setup(args)
    if args.subcommand == "run":
        return cmd_run(args)
    if args.subcommand == "chat":
        return cmd_chat(args)
    if args.subcommand == "log-diagnostics":
        return cmd_log_diagnostics(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
