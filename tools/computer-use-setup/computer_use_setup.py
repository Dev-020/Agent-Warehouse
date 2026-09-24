#!/usr/bin/env python3
"""Diagnostic, configuration, and skill-link CLI for cua-driver desktop automation."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

VERSION_FLOOR = (0, 28, 0)
TELEMETRY_ENV_VAR = "CUA_DRIVER_RS_TELEMETRY_ENABLED"


def find_cua_driver_binary(explicit_path: str | None = None) -> Path | None:
    """Find cua-driver executable on system or standard install locations."""
    if explicit_path:
        p = Path(explicit_path)
        return p if p.is_file() else None

    # Check PATH first
    found = shutil.which("cua-driver")
    if found:
        return Path(found)

    # Standard platform-specific locations
    home = Path.home()
    candidates: list[Path] = []
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs" / "Cua" / "cua-driver" / "bin" / "cua-driver.exe")
        candidates.append(home / ".cua-driver" / "packages" / "current" / "bin" / "cua-driver.exe")
    else:
        candidates.extend([
            home / ".cua-driver" / "packages" / "current" / "bin" / "cua-driver",
            home / ".local" / "bin" / "cua-driver",
            Path("/usr/local/bin/cua-driver"),
            Path("/opt/homebrew/bin/cua-driver"),
        ])

    for c in candidates:
        if c.is_file():
            return c
    return None


def parse_semver(version_str: str) -> tuple[int, int, int] | None:
    """Extract major, minor, patch from version string like 'cua-driver 0.28.1'."""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", version_str)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def run_command(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Execute command safely and capture output."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (subprocess.SubprocessError, OSError) as e:
        return -1, "", str(e)


def check_status(driver_path: Path | None) -> dict[str, Any]:
    """Check binary, version, daemon running state, and telemetry status."""
    report: dict[str, Any] = {
        "binary_found": False,
        "binary_path": None,
        "version": None,
        "version_ok": False,
        "version_floor": f"{VERSION_FLOOR[0]}.{VERSION_FLOOR[1]}.{VERSION_FLOOR[2]}",
        "daemon_running": False,
        "daemon_pid": None,
        "socket": None,
        "permission_mode": None,
        "telemetry": None,
        "ready": False,
        "errors": [],
    }

    if not driver_path or not driver_path.is_file():
        report["errors"].append("cua-driver binary not found on PATH or standard install paths")
        return report

    report["binary_found"] = True
    report["binary_path"] = str(driver_path)

    # 1. Version check
    rc, out, err = run_command([str(driver_path), "--version"])
    if rc != 0:
        report["errors"].append(f"Failed to query cua-driver --version: {err or out}")
        return report

    report["version"] = out
    parsed_v = parse_semver(out)
    if parsed_v and parsed_v >= VERSION_FLOOR:
        report["version_ok"] = True
    else:
        v_str = f"{parsed_v[0]}.{parsed_v[1]}.{parsed_v[2]}" if parsed_v else "unknown"
        report["errors"].append(
            f"Installed cua-driver version {v_str} is below required floor {report['version_floor']}"
        )

    # 2. Daemon status
    rc, out, _ = run_command([str(driver_path), "status"])
    if rc == 0 and "daemon is running" in out.lower():
        report["daemon_running"] = True
        pid_m = re.search(r"pid:\s*(\d+)", out, re.IGNORECASE)
        if pid_m:
            report["daemon_pid"] = int(pid_m.group(1))
        sock_m = re.search(r"socket:\s*([^\r\n]+)", out, re.IGNORECASE)
        if sock_m:
            report["socket"] = sock_m.group(1).strip()
        perm_m = re.search(r"permission mode:\s*([^\r\n]+)", out, re.IGNORECASE)
        if perm_m:
            report["permission_mode"] = perm_m.group(1).strip()
    else:
        report["errors"].append("cua-driver daemon is not running (start with `cua-driver serve`)")

    # 3. Telemetry status
    rc, out, _ = run_command([str(driver_path), "telemetry", "status"])
    if rc == 0:
        report["telemetry"] = out
    else:
        report["telemetry"] = "unknown"

    report["ready"] = report["binary_found"] and report["version_ok"] and report["daemon_running"]
    return report


def build_mcp_config(driver_path: str) -> dict[str, Any]:
    """Generate canonical MCP server JSON configuration with telemetry disabled."""
    # Convert backslashes for clean cross-platform JSON
    clean_path = driver_path.replace("\\", "/")
    return {
        "mcpServers": {
            "cua-driver": {
                "command": clean_path,
                "args": ["mcp"],
                "env": {
                    TELEMETRY_ENV_VAR: "0",
                },
            }
        }
    }


def configure_mcp(
    driver_path: Path,
    client: str,
    target_path: Path | None = None,
    write: bool = False,
    dry_run: bool = False,
) -> int:
    """Generate or update MCP configuration for an agent harness."""
    config = build_mcp_config(str(driver_path))
    driver_str = str(driver_path).replace("\\", "/")

    if client == "claude-cmd":
        # Print CLI command to register in Claude Code user scope
        cmd = f'claude mcp add --transport stdio cua-driver -e {TELEMETRY_ENV_VAR}=0 -- "{driver_str}" mcp'
        print("Run the following command to register cua-driver in Claude Code:")
        print(f"  {cmd}")
        return 0

    target = target_path or Path(".mcp.json")
    print(f"Target MCP configuration: {target}")

    existing_data: dict[str, Any] = {}
    if target.is_file():
        try:
            with open(target, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: could not parse existing {target}: {e}", file=sys.stderr)

    servers = existing_data.get("mcpServers", {})
    servers["cua-driver"] = config["mcpServers"]["cua-driver"]
    existing_data["mcpServers"] = servers

    formatted = json.dumps(existing_data, indent=2) + "\n"

    if dry_run or not write:
        print("\n--- Proposed Configuration ---")
        sys.stdout.write(formatted)
        print("-------------------------------")
        if not write and not dry_run:
            print("Note: run with --write to save this configuration to disk.")
        return 0

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(formatted)
        print(f"Successfully wrote MCP configuration to {target}")
        return 0
    except OSError as e:
        print(f"Error writing to {target}: {e}", file=sys.stderr)
        return 1


def cmd_check(args: argparse.Namespace) -> int:
    binary = find_cua_driver_binary(args.driver_path)
    report = check_status(binary)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["ready"] else 1

    print("=== cua-driver Environment Check ===")
    print(f"Binary found:    {report['binary_found']} ({report['binary_path'] or 'N/A'})")
    print(f"Version:         {report['version'] or 'N/A'} (Floor: {report['version_floor']})")
    print(f"Version OK:      {report['version_ok']}")
    print(f"Daemon running:  {report['daemon_running']} (PID: {report['daemon_pid'] or 'N/A'}, Socket: {report['socket'] or 'N/A'})")
    print(f"Permission mode: {report['permission_mode'] or 'N/A'}")
    print(f"Telemetry:       {report['telemetry'] or 'N/A'}")
    print("====================================")

    if report["ready"]:
        print("Status: READY - desktop automation is available.")
        return 0

    print("Status: NOT READY")
    for err in report["errors"]:
        print(f"  - {err}")
    return 1


def cmd_doctor(args: argparse.Namespace) -> int:
    binary = find_cua_driver_binary(args.driver_path)
    if not binary:
        print("Error: cua-driver binary not found.", file=sys.stderr)
        return 1

    cmd = [str(binary), "doctor"]
    if args.json:
        cmd.append("--json")

    rc, out, err = run_command(cmd, timeout=30)
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return 0 if rc == 0 else 1


def cmd_configure(args: argparse.Namespace) -> int:
    binary = find_cua_driver_binary(args.driver_path)
    if not binary:
        print("Error: cua-driver binary not found. Cannot configure MCP without driver path.", file=sys.stderr)
        return 1

    target = Path(args.target) if args.target else None
    return configure_mcp(
        driver_path=binary,
        client=args.client,
        target_path=target,
        write=args.write,
        dry_run=args.dry_run,
    )


def cmd_skills(args: argparse.Namespace) -> int:
    binary = find_cua_driver_binary(args.driver_path)
    if not binary:
        print("Error: cua-driver binary not found.", file=sys.stderr)
        return 1

    subaction = args.action
    cmd = [str(binary), "skills", subaction]
    rc, out, err = run_command(cmd, timeout=30)
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return 0 if rc == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnostic, configuration, and skill-link CLI for cua-driver desktop automation."
    )
    parser.add_argument(
        "--driver-path",
        help="Explicit path to cua-driver executable (defaults to automatic lookup).",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # check
    p_check = subparsers.add_parser("check", help="Verify binary presence, version floor, and daemon status.")
    p_check.add_argument("--json", action="store_true", help="Emit machine-readable JSON status.")
    p_check.set_defaults(func=cmd_check)

    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Run cua-driver diagnostic probe.")
    p_doctor.add_argument("--json", action="store_true", help="Emit doctor results as JSON.")
    p_doctor.set_defaults(func=cmd_doctor)

    # configure
    p_cfg = subparsers.add_parser("configure", help="Generate or update agent MCP configuration.")
    p_cfg.add_argument(
        "--client",
        choices=["generic", "claude-cmd", "antigravity"],
        default="generic",
        help="Target client harness format.",
    )
    p_cfg.add_argument("--target", help="Target config file path (default: .mcp.json).", default=None)
    p_cfg.add_argument("--write", action="store_true", help="Write updated config to target file.")
    p_cfg.add_argument("--dry-run", action="store_true", help="Preview output without writing.")
    p_cfg.set_defaults(func=cmd_configure)

    # skills
    p_skills = subparsers.add_parser("skills", help="Manage cua-driver skill pack links.")
    p_skills.add_argument(
        "action",
        choices=["status", "install", "update", "path"],
        help="Skill action to execute.",
    )
    p_skills.set_defaults(func=cmd_skills)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
