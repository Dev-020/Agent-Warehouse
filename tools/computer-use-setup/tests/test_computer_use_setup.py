from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PARENT_DIR = str(Path(__file__).resolve().parents[1])
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import computer_use_setup as cus


def test_parse_semver():
    assert cus.parse_semver("cua-driver 0.28.1") == (0, 28, 1)
    assert cus.parse_semver("0.28.0-nightly") == (0, 28, 0)
    assert cus.parse_semver("1.2.3") == (1, 2, 3)
    assert cus.parse_semver("invalid string") is None


def test_find_cua_driver_binary_explicit(tmp_path: Path):
    fake_bin = tmp_path / "cua-driver.exe"
    fake_bin.write_text("dummy")
    assert cus.find_cua_driver_binary(str(fake_bin)) == fake_bin
    assert cus.find_cua_driver_binary(str(tmp_path / "nonexistent")) is None


def test_build_mcp_config():
    cfg = cus.build_mcp_config("C:\\Tools\\cua-driver.exe")
    server = cfg["mcpServers"]["cua-driver"]
    assert server["command"] == "C:/Tools/cua-driver.exe"
    assert server["args"] == ["mcp"]
    assert server["env"]["CUA_DRIVER_RS_TELEMETRY_ENABLED"] == "0"


def test_check_status_binary_missing():
    report = cus.check_status(None)
    assert not report["binary_found"]
    assert not report["ready"]
    assert len(report["errors"]) > 0


@patch("computer_use_setup.run_command")
def test_check_status_success(mock_run: MagicMock, tmp_path: Path):
    driver = tmp_path / "cua-driver"
    driver.write_text("dummy")

    def side_effect(cmd, timeout=15):
        if "--version" in cmd:
            return 0, "cua-driver 0.28.1", ""
        if "status" in cmd and "telemetry" not in cmd:
            return 0, "daemon is running\nsocket: \\\\.\\pipe\\cua-driver\npid: 18708\npermission mode: standard", ""
        if "telemetry" in cmd:
            return 0, "Telemetry: disabled", ""
        return 0, "", ""

    mock_run.side_effect = side_effect
    report = cus.check_status(driver)

    assert report["binary_found"]
    assert report["version_ok"]
    assert report["daemon_running"]
    assert report["daemon_pid"] == 18708
    assert report["socket"] == "\\\\.\\pipe\\cua-driver"
    assert report["permission_mode"] == "standard"
    assert report["ready"]
    assert len(report["errors"]) == 0


@patch("computer_use_setup.run_command")
def test_check_status_version_too_low(mock_run: MagicMock, tmp_path: Path):
    driver = tmp_path / "cua-driver"
    driver.write_text("dummy")

    def side_effect(cmd, timeout=15):
        if "--version" in cmd:
            return 0, "cua-driver 0.27.5", ""
        if "status" in cmd and "telemetry" not in cmd:
            return 0, "daemon is running\npid: 123", ""
        return 0, "", ""

    mock_run.side_effect = side_effect
    report = cus.check_status(driver)

    assert report["binary_found"]
    assert not report["version_ok"]
    assert not report["ready"]
    assert any("below required floor" in err for err in report["errors"])


@patch("computer_use_setup.run_command")
def test_check_status_daemon_stopped(mock_run: MagicMock, tmp_path: Path):
    driver = tmp_path / "cua-driver"
    driver.write_text("dummy")

    def side_effect(cmd, timeout=15):
        if "--version" in cmd:
            return 0, "cua-driver 0.28.1", ""
        if "status" in cmd and "telemetry" not in cmd:
            return 1, "daemon is stopped", ""
        return 0, "", ""

    mock_run.side_effect = side_effect
    report = cus.check_status(driver)

    assert report["version_ok"]
    assert not report["daemon_running"]
    assert not report["ready"]
    assert any("daemon is not running" in err for err in report["errors"])


def test_configure_mcp_write(tmp_path: Path):
    target = tmp_path / "sub" / ".mcp.json"
    driver = tmp_path / "cua-driver.exe"
    driver.write_text("dummy")

    rc = cus.configure_mcp(driver, client="generic", target_path=target, write=True)
    assert rc == 0
    assert target.is_file()

    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "mcpServers" in data
    assert "cua-driver" in data["mcpServers"]
    entry = data["mcpServers"]["cua-driver"]
    assert entry["command"] == str(driver).replace("\\", "/")
    assert entry["args"] == ["mcp"]
    assert entry["env"]["CUA_DRIVER_RS_TELEMETRY_ENABLED"] == "0"


def test_configure_mcp_claude_cmd(capsys, tmp_path: Path):
    driver = tmp_path / "cua-driver.exe"
    driver.write_text("dummy")

    rc = cus.configure_mcp(driver, client="claude-cmd")
    assert rc == 0
    out = capsys.readouterr().out
    assert "claude mcp add" in out
    assert "CUA_DRIVER_RS_TELEMETRY_ENABLED=0" in out


@patch("computer_use_setup.check_status")
def test_cli_check_command(mock_status: MagicMock, tmp_path: Path):
    mock_status.return_value = {
        "binary_found": True,
        "binary_path": "test",
        "version": "0.28.1",
        "version_ok": True,
        "version_floor": "0.28.0",
        "daemon_running": True,
        "daemon_pid": 111,
        "socket": "sock",
        "permission_mode": "standard",
        "telemetry": "disabled",
        "ready": True,
        "errors": [],
    }

    assert cus.main(["check"]) == 0
    mock_status.return_value["ready"] = False
    assert cus.main(["check"]) == 1
