#!/usr/bin/env python3
"""
Unit and integration tests for tools/antigravity-cli-runner/antigravity_cli_runner.py
"""

import io
import json
import os
import queue
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path so antigravity_cli_runner can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from antigravity_cli_runner import (
    AntigravityCliSession,
    EngineConfig,
    TurnContext,
    TurnResult,
    find_last_agy_log_error,
    prepare_agy_profile,
    OUTCOME_ANSWERED,
    OUTCOME_ERROR,
    OUTCOME_TIMEOUT,
)


class MockPipe:
    def __init__(self):
        self.q = queue.Queue()

    def feed(self, lines):
        for line in lines:
            self.q.put(line)

    def __iter__(self):
        while True:
            item = self.q.get()
            if item is None:
                break
            yield item

    def close(self):
        self.q.put(None)


class MockStdin:
    def __init__(self, pipe: MockPipe, response_generator):
        self.pipe = pipe
        self.response_generator = response_generator
        self.written = []

    def write(self, data):
        self.written.append(data)
        lines = self.response_generator(data)
        self.pipe.feed(lines)

    def flush(self):
        pass


class TestAntigravityCliRunner(unittest.TestCase):

    def test_prepare_agy_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_dir = os.path.join(tmpdir, "agy-profile")
            workspace_dir = os.path.join(tmpdir, "workspace")
            env = prepare_agy_profile(profile_dir, workspace_dir, grants=["command(git status)"])

            self.assertTrue(os.path.isdir(profile_dir))
            config_file = os.path.join(profile_dir, ".gemini", "config", "config.json")
            settings_file = os.path.join(profile_dir, ".gemini", "antigravity-cli", "settings.json")

            self.assertTrue(os.path.isfile(config_file))
            self.assertTrue(os.path.isfile(settings_file))

            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                self.assertTrue(cfg["userSettings"]["useAiCredits"])

            with open(settings_file, "r", encoding="utf-8") as f:
                st = json.load(f)
                grants = st["permissions"]["allow"]
                self.assertTrue(any("workspace" in g for g in grants))
                self.assertIn("command(git status)", grants)

            self.assertEqual(env["USERPROFILE"], os.path.abspath(profile_dir))
            self.assertEqual(env["TEMP"], os.path.join(os.path.abspath(profile_dir), "tmp"))

    def test_find_last_agy_log_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_dir = "C:/my/workspace"
            log_file = os.path.join(tmpdir, "cli-2026-09-24.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"workspaceDirs=[{ws_dir}]\n")
                f.write("sending message to model\n")
                f.write("E0924 12:00:01.123456   123 errorreport.go:200] calling model: INVALID_ARGUMENT (code 400)\n")
                f.write("E0924 12:00:02.123456   123 errorreport.go:210] Agent execution terminated due to error.\n")

            err = find_last_agy_log_error(tmpdir, ws_dir)
            self.assertEqual(err, "calling model: INVALID_ARGUMENT (code 400)")

    def test_session_success_turn(self):
        config = EngineConfig(turn_timeout_sec=5.0)
        session = AntigravityCliSession(config)

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        pipe = MockPipe()

        # Feeding init immediately upon process startup (as real agy does)
        pipe.feed([
            json.dumps({"event": "init", "conversation_id": "conv-101", "init": {"permission_mode": "request-review"}}) + "\n"
        ])

        def generate_success(data):
            return [
                json.dumps({
                    "event": "step_update",
                    "step_update": {"step_type": "agent_response", "state": "ACTIVE", "text_delta": "Hello from Gemini"}
                }) + "\n",
                json.dumps({
                    "event": "result",
                    "result": {
                        "status": "SUCCESS",
                        "response": "Hello from Gemini",
                        "duration_seconds": 1.4,
                        "usage": {"input_tokens": 30, "output_tokens": 12}
                    }
                }) + "\n"
            ]

        mock_proc.stdin = MockStdin(pipe, generate_success)
        mock_proc.stdout = pipe
        mock_proc.stderr = []

        chunks_received = []
        session.on_chunk = lambda c: chunks_received.append(c)

        with patch("subprocess.Popen", return_value=mock_proc):
            session.start()
            result = session.send_and_wait("Ping check", timeout=2.0)
            pipe.close()
            session.stop()

        self.assertTrue(result.success)
        self.assertEqual(result.text, "Hello from Gemini")
        self.assertEqual(result.duration_seconds, 1.4)
        self.assertEqual(result.usage.get("output_tokens"), 12)
        self.assertEqual(chunks_received, ["Hello from Gemini"])

    def test_session_unfinished_tool_denial(self):
        config = EngineConfig(turn_timeout_sec=5.0)
        session = AntigravityCliSession(config)

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        pipe = MockPipe()
        pipe.feed([
            json.dumps({"event": "init", "conversation_id": "conv-102"}) + "\n"
        ])

        def generate_denial(data):
            return [
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_index": 1,
                        "step_type": "tool",
                        "tool_name": "run_command",
                        "state": "ACTIVE"
                    }
                }) + "\n",
                json.dumps({
                    "event": "result",
                    "result": {
                        "status": "SUCCESS",
                        "response": "",
                        "denied_actions": [{"action": "run_command", "display_name": "RunCommand"}]
                    }
                }) + "\n"
            ]

        mock_proc.stdin = MockStdin(pipe, generate_denial)
        mock_proc.stdout = pipe
        mock_proc.stderr = []

        with patch("subprocess.Popen", return_value=mock_proc):
            session.start()
            result = session.send_and_wait("Execute forbidden command", timeout=2.0)
            pipe.close()
            session.stop()

        self.assertFalse(result.success)
        self.assertIn("RunCommand", result.error)
        self.assertEqual(result.outcome, OUTCOME_ERROR)


if __name__ == "__main__":
    unittest.main()
