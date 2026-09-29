"""Run a command on the worker node: locally, or over ssh, with --dry-run.

Used by pod_gen.py/campaign.py to start/stop enemies and housekeeping load
and to run kubectl. Kept as one small class so every orchestration script
gets --dry-run and the local/ssh choice for free, and so tests never need to
actually ssh or run kubectl (see tests/test_campaign.py: --dry-run only
prints the commands it would run).
"""
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass


@dataclass
class NodeExecutor:
    mode: str = "local"          # "local" or "ssh"
    ssh_host: str | None = None
    ssh_user: str | None = None
    ssh_key: str | None = None
    dry_run: bool = False

    def _wrap(self, cmd: list[str]) -> list[str]:
        if self.mode == "local":
            return cmd
        if self.mode == "ssh":
            if not self.ssh_host:
                raise ValueError("ssh mode requires ssh_host")
            target = f"{self.ssh_user}@{self.ssh_host}" if self.ssh_user else self.ssh_host
            ssh_cmd = ["ssh"]
            if self.ssh_key:
                ssh_cmd += ["-i", self.ssh_key]
            ssh_cmd += [target, " ".join(cmd)]
            return ssh_cmd
        raise ValueError(f"unknown node_exec mode: {self.mode!r}")

    def run(self, cmd: list[str], **kwargs) -> subprocess.CompletedProcess | None:
        """Run `cmd` (already tokenized, e.g. ["kubectl", "apply", "-f", path]).
        In --dry-run mode, prints the fully wrapped command and returns None."""
        wrapped = self._wrap(cmd)
        if self.dry_run:
            print("[dry-run]", " ".join(wrapped))
            return None
        return subprocess.run(wrapped, check=False, **kwargs)

    def run_background(self, cmd: list[str]) -> subprocess.Popen | None:
        """Like run(), but starts the command detached (for enemies / hk_load)
        and returns the Popen so campaign.py can terminate it later."""
        wrapped = self._wrap(cmd)
        if self.dry_run:
            print("[dry-run, background]", " ".join(wrapped))
            return None
        return subprocess.Popen(wrapped)


def main():
    p = argparse.ArgumentParser(description="Run a command locally or over ssh, with --dry-run")
    p.add_argument("--mode", choices=["local", "ssh"], default="local")
    p.add_argument("--ssh-host")
    p.add_argument("--ssh-user")
    p.add_argument("--ssh-key")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("cmd", nargs=argparse.REMAINDER, help="command to run, after --")
    args = p.parse_args()

    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        p.error("no command given")

    executor = NodeExecutor(mode=args.mode, ssh_host=args.ssh_host, ssh_user=args.ssh_user,
                             ssh_key=args.ssh_key, dry_run=args.dry_run)
    result = executor.run(cmd)
    if result is not None:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
