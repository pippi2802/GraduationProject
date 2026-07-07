#!/usr/bin/env python3
"""
Regenerate ALL Model 1 figures in one go.

Runs every fig*.py in this directory (in order) for the given --timeblock (or
'aggregate' to combine all time-blocks). Each figure is independently
regenerable; this is just a convenience wrapper.

Usage:  python plots/plot_all.py [--timeblock LABEL|aggregate]
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeblock", default="aggregate")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    scripts = sorted(HERE.glob("fig*.py"))
    rc = 0
    for s in scripts:
        argv = [str(s)]
        # fig10 always uses all time-blocks and takes no --timeblock
        if s.name.startswith("fig10"):
            pass
        else:
            argv += ["--timeblock", args.timeblock]
        if args.config:
            argv += ["--config", args.config]
        sys.stderr.write(f"\n=== {s.name} ===\n")
        old = sys.argv
        try:
            sys.argv = argv
            runpy.run_path(str(s), run_name="__main__")
        except SystemExit as e:
            if e.code not in (0, None):
                rc = e.code or rc
        except Exception as exc:  # keep going; report at end
            sys.stderr.write(f"[{s.name}] ERROR: {exc}\n")
            rc = 1
        finally:
            sys.argv = old
    return rc


if __name__ == "__main__":
    sys.exit(main())
