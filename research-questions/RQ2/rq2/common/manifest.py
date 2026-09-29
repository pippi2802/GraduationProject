"""Run manifests: what a run directory needs so a later stage (or a human)
can tell what produced it and whether it finished, without re-reading logs.
"""
from __future__ import annotations

import getpass
import json
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def git_commit_hash(cwd: Path | None = None) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_manifest(config: dict[str, Any], command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    """Build the manifest at the start of a run; write again with status
    'complete' (see `finish_manifest`) once it succeeds."""
    return {
        "status": "running",
        "config": config,
        "command": command,
        "git_commit": git_commit_hash(cwd),
        "hostname": socket.gethostname(),
        "user": getpass.getuser(),
        "python_version": sys.version,
        "start_time_utc": utc_now_iso(),
        "end_time_utc": None,
    }


def finish_manifest(manifest: dict[str, Any], status: str = "complete") -> dict[str, Any]:
    manifest = dict(manifest)
    manifest["status"] = status
    manifest["end_time_utc"] = utc_now_iso()
    return manifest


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


def read_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def is_complete(path: Path) -> bool:
    manifest = read_manifest(path)
    return bool(manifest) and manifest.get("status") == "complete"
