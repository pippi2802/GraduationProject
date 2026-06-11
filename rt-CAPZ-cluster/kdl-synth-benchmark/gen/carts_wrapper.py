#!/usr/bin/env python3
"""CARTS wrapper: compute an MPR reservation interface (Q, P, m) for a task set.

For each task-set JSON produced by ``randfixedsum.py`` this attaches a
``reservation`` block:

    "reservation": { "q_us": 9000, "p_us": 33000, "m": 2, "source": "carts" }

The interface is the Multiprocessor Periodic Resource (MPR) model of
Easwaran et al., computed by the CARTS compositional analysis tool
(https://github.com/ -> search "CARTS").

CARTS is an external binary/tool that may not exist on the build machine.
The actual invocation is isolated in a single function, ``run_carts()``, so it
can be wired up in one place. Until then a documented analytic stub is used.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

# ---------------------------------------------------------------------------
# CARTS integration point
# ---------------------------------------------------------------------------
# CARTS input format assumptions (component file), per the tool's docs:
#   * one component with scheduling policy (EDF), and the leaf tasks as
#     (period, wcet, deadline) triples;
#   * CARTS emits the minimum-bandwidth MPR interface (Pi, Theta, m'):
#       Pi    -> reservation period          (we map to p_us)
#       Theta -> budget supplied each period (we map to q_us)
#       m'    -> number of reserved cores    (we map to m)
#
# To wire the real tool:
#   1. write `tasks` to a CARTS component file (see CARTS examples),
#   2. invoke the CARTS jar/binary via subprocess,
#   3. parse the emitted interface and return (q_us, p_us, m).
#
# TODO: wire CARTS binary/path here.
CARTS_BIN = os.environ.get("CARTS_BIN", "")  # e.g. "java -jar /opt/carts/carts.jar"


def run_carts(tasks: list[dict], cap_cores: int) -> dict | None:
    """Invoke CARTS for `tasks`. Return reservation dict or None if unavailable.

    Replace the body with the real CARTS subprocess call. Keep the return
    contract: {"q_us": int, "p_us": int, "m": int, "source": "carts"}.
    """
    if not CARTS_BIN:
        return None
    # ----------------------------------------------------------------------
    # TODO: wire CARTS binary/path.
    #   import subprocess, tempfile
    #   comp = write_carts_component(tasks)          # build CARTS input file
    #   out  = subprocess.check_output(CARTS_BIN.split() + [comp], text=True)
    #   pi, theta, m = parse_carts_interface(out)    # parse emitted MPR
    #   return {"q_us": int(theta), "p_us": int(pi), "m": int(m), "source": "carts"}
    # ----------------------------------------------------------------------
    raise NotImplementedError("CARTS_BIN set but run_carts() not yet wired")


def stub_interface(tasks: list[dict], cap_cores: int) -> dict:
    """Analytic fallback when CARTS is not available.

    A deliberately simple, *conservative* sizing so the benchmark is runnable
    end-to-end without CARTS. NOT a substitute for real MPR analysis.

      * total utilisation U = sum(c_i / t_i)
      * cores m = ceil(U), capped at cap_cores
      * period P = min task period (responsive supply)
      * budget Q = ceil(U / m * P)  (bandwidth m*Q/P >= U)
    """
    u = sum(t["c_us"] / t["t_us"] for t in tasks)
    m = max(1, min(cap_cores, math.ceil(u)))
    p_us = min(t["t_us"] for t in tasks)
    q_us = math.ceil((u / m) * p_us)
    q_us = min(q_us, p_us)  # cannot supply more than the full period per core
    return {"q_us": int(q_us), "p_us": int(p_us), "m": int(m), "source": "stub"}


def annotate_file(path: str, cap_cores: int, force: bool) -> str:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    if doc.get("reservation") and not force:
        return "skip"

    tasks = doc["tasks"]
    res = run_carts(tasks, cap_cores)
    if res is None:
        res = stub_interface(tasks, cap_cores)

    doc["reservation"] = res
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return res["source"]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Attach (Q,P,m) MPR interface to task sets")
    p.add_argument("--tasksets-dir",
                   default=os.path.join(os.path.dirname(__file__), "tasksets"))
    p.add_argument("--cap-cores", type=int, default=2,
                   help="m <= cap-cores (2 physical cores on the node)")
    p.add_argument("--force", action="store_true", help="recompute even if present")
    args = p.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.tasksets_dir, "*.json")))
    if not files:
        print(f"no task sets found in {args.tasksets_dir}", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for path in files:
        src = annotate_file(path, args.cap_cores, args.force)
        counts[src] = counts.get(src, 0) + 1

    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"processed {len(files)} task sets ({summary})")
    if counts.get("stub"):
        print("NOTE: CARTS not wired (CARTS_BIN unset) -> analytic stub used.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
