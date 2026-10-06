#!/usr/bin/env python3
"""
Unit and integration tests for tools/claude-cli-runner/claude_cli_runner.py
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

# Add parent directory to path so claude_cli_runner can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from claude_cli_runner import (
    ClaudeCliSession,
    EngineConfig,
    TurnContext,
    TurnResult,
    is_claude_not_logged_in,
    prepare_claude_profile,
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


class TestClaudeCliRunner(unittest.TestCase):

    def test_prepare_claude_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_dir = os.path.join(tmpdir, "test-profile")
            env = prepare_claude_profile(profile_dir)
            self.assertTrue(os.path.isdir(profile_dir))
            self.assertTrue(os.path.isfile(os.path.join(profile_dir, "settings.json")))
            self.assertEqual(env["CLAUDE_CONFIG_DIR"], os.path.abspath(profile_dir))
            self.assertEqual(env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"], "1")

    def test_is_claude_not_logged_in(self):
        self.assertTrue(is_claude_not_logged_in("Error: Not logged in. Please run /login to authenticate."))
        self.assertTrue(is_claude_not_logged_in("Authentication required for operation."))
        self.assertFalse(is_claude_not_logged_in("Token rate limit exceeded."))

    def test_command_generation(self):
        config = EngineConfig(
            claude_bin="custom-claude",
            profile_dir="/tmp/profile",
            workspace_dir="/tmp/workspace",
            model="claude-opus-4",
            effort="high",
            system_prompt="Be concise",
            strip_tools=True,
            strict_mcp_config=True,
            add_dirs=["/extra/dir"],
        )
        session = ClaudeCliSession(config)
        cmd = session._command()

        self.assertEqual(cmd[0], "custom-claude")
        self.assertIn("--verbose", cmd)
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-opus-4")
        self.assertIn("--effort", cmd)
        self.assertEqual(cmd[cmd.index("--effort") + 1], "high")
        self.assertIn("--system-prompt", cmd)
        self.assertEqual(cmd[cmd.index("--system-prompt") + 1], "Be concise")
        self.assertIn("--tools", cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertIn("--add-dir", cmd)
        self.assertEqual(cmd[cmd.index("--add-dir") + 1], "/extra/dir")

    def test_session_success_turn(self):
        config = EngineConfig(turn_timeout_sec=5.0)
        session = ClaudeCliSession(config)

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        pipe = MockPipe()

        def generate_success(data):
            return [
                json.dumps({"type": "system", "subtype": "init", "model": "claude-sonnet-5"}) + "\n",
                json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Chunk 1: "}]}}) + "\n",
                json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Chunk 2"}]}}) + "\n",
                json.dumps({
                    "type": "result",
                    "subtype": "success",
                    "result": "Chunk 1: Chunk 2",
                    "duration_api_ms": 450,
                    "usage": {"input_tokens": 15, "output_tokens": 8}
                }) + "\n",
            ]

        mock_proc.stdin = MockStdin(pipe, generate_success)
        mock_proc.stdout = pipe
        mock_proc.stderr = []

        chunks_received = []
        session.on_chunk = lambda c: chunks_received.append(c)

        with patch("subprocess.Popen", return_value=mock_proc):
            session.start()
            result = session.send_and_wait("Hello world", timeout=2.0)
            pipe.close()
            session.stop()

        self.assertTrue(result.success)
        self.assertEqual(result.text, "Chunk 1: Chunk 2")
        self.assertEqual(result.duration_api_ms, 450)
        self.assertEqual(result.usage.get("output_tokens"), 8)
        self.assertEqual(chunks_received, ["Chunk 1: ", "Chunk 2"])

    def test_session_error_turn(self):
        config = EngineConfig(turn_timeout_sec=5.0)
        session = ClaudeCliSession(config)

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        pipe = MockPipe()

        def generate_error(data):
            return [
                json.dumps({"type": "system", "subtype": "init"}) + "\n",
                json.dumps({
                    "type": "result",
                    "subtype": "error_max_turns",
                    "is_error": True,
                    "result": "Maximum turns exceeded",
                    "duration_api_ms": 100,
                }) + "\n",
            ]

        mock_proc.stdin = MockStdin(pipe, generate_error)
        mock_proc.stdout = pipe
        mock_proc.stderr = []

        with patch("subprocess.Popen", return_value=mock_proc):
            session.start()
            result = session.send_and_wait("Run infinite loop", timeout=2.0)
            pipe.close()
            session.stop()

        self.assertFalse(result.success)
        self.assertIn("Maximum turns exceeded", result.error)
        self.assertEqual(result.outcome, OUTCOME_ERROR)


if __name__ == "__main__":
    unittest.main()
