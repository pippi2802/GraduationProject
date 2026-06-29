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
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# CARTS integration
# ---------------------------------------------------------------------------
# CARTS is invoked as:  java -jar carts.jar <input.xml> MPR2 <output.xml>
#   * input  : <system os_scheduler="gEDF"> with one <component> whose leaf
#              <task p="period" d="deadline" e="wcet" .../> entries are the set;
#   * output : each <component>'s <resource><model cpus period execution_time>
#              is its MPR interface, which we map:
#                period         -> p_us  (reservation period)
#                execution_time -> q_us  (budget supplied each period)
#                cpus           -> m     (reserved cores)
#
# CARTS launch command, e.g. "java -jar /path/to/carts/carts-dev/carts.jar".
# Prefer CARTS_JAR (path to carts.jar; safe with spaces) + optional CARTS_JAVA;
# CARTS_BIN is a fallback for non-jar launch strings. When none are set,
# run_carts() returns None and the analytic stub is used instead.
CARTS_JAR = os.environ.get("CARTS_JAR", "")
CARTS_JAVA = os.environ.get("CARTS_JAVA", "java")
CARTS_BIN = os.environ.get("CARTS_BIN", "")
# Resource model passed as CARTS argv[1]. MPR2 is the (gEDF) Multiprocessor
# Periodic Resource model; plain "MPR" is not supported for the supply-bound
# analysis by this CARTS build.
CARTS_MODEL = os.environ.get("CARTS_MODEL", "MPR2")
# CARTS' analysis time scales with the magnitude of the period/WCET integers,
# so the microsecond task values are scaled down into the same ~100-1000 range
# as CARTS' own examples (and scaled back afterwards). Target for the smallest
# task period after scaling.
CARTS_SCALE_TARGET = 100

CARTS_COMPONENT_NAME = "C0"


def _carts_command() -> list[str] | None:
    """Base argv to launch CARTS, or None if not configured."""
    if CARTS_JAR:
        return [CARTS_JAVA, "-jar", CARTS_JAR]
    if CARTS_BIN:
        # posix=False on Windows so backslash path separators survive.
        return shlex.split(CARTS_BIN, posix=(os.name != "nt"))
    return None


def _carts_scale(tasks: list[dict]) -> int:
    """Divisor that maps the smallest task period to ~CARTS_SCALE_TARGET."""
    min_t = min(t["t_us"] for t in tasks)
    return max(1, round(min_t / CARTS_SCALE_TARGET))


def write_carts_component(tasks: list[dict], scale: int) -> str:
    """Write a CARTS system XML (one gEDF component with all tasks) to a temp
    file and return its path. Times are scaled down by `scale`; deadlines are
    implicit (d = period). Returns the path the caller must clean up.
    """
    pi = max(1, round(min(t["t_us"] for t in tasks) / scale))  # interface period
    lines = [
        f'<system os_scheduler="gEDF" period="{pi}">',
        f'\t<component name="{CARTS_COMPONENT_NAME}" scheduler="gEDF" period="{pi}">',
    ]
    for t in tasks:
        p = max(1, round(t["t_us"] / scale))
        e = max(1, round(t["c_us"] / scale))
        lines.append(
            f'\t\t<task name="T{t["id"]}" p="{p}" d="{p}" e="{e}" '
            f'delta_rel="0" delta_sch="0" delta_cxs="0" delta_crpmd="0" > </task>'
        )
    lines.append("\t</component>")
    lines.append("</system>")
    fd, path = tempfile.mkstemp(prefix="carts-in-", suffix=".xml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def parse_carts_interface(out_path: str, scale: int) -> tuple[int, int, int] | None:
    """Read CARTS output XML and return (q_us, p_us, m) for our component, or
    None if the interface is absent/infeasible.

    The component's <resource><model> carries cpus -> m', period -> P, and
    execution_time -> Theta, where Theta is the TOTAL budget supplied across
    all m' processors per period P. A uniform per-core HCBS reservation runs
    the same (Q, P) on each of the m' cores, so the per-core budget is
    Q = Theta / m' (which always satisfies Q <= P since Theta <= m'*P).
    P and Q are rescaled back to microseconds.
    """
    root = ET.parse(out_path).getroot()
    # Output root is <component name="system">; our taskset is the nested one.
    comp = root.find(f"./component[@name='{CARTS_COMPONENT_NAME}']")
    model = comp.find("./resource/model") if comp is not None else None
    if model is None:
        return None
    m = int(model.attrib["cpus"])
    period = float(model.attrib["period"])
    theta = float(model.attrib["execution_time"])
    # CARTS emits cpus=0 with an INT_MAX-ish execution_time when no feasible
    # interface exists for the requested model; treat that as "no interface".
    if m < 1 or period <= 0 or theta >= 2_000_000_000:
        return None
    p_us = int(round(period * scale))
    q_us = int(round((theta / m) * scale))  # per-core budget
    return q_us, p_us, m


def run_carts(tasks: list[dict], cap_cores: int) -> dict | None:
    """Invoke CARTS for `tasks`. Return reservation dict or None if unavailable.

    Return contract: {"q_us": int, "p_us": int, "m": int, "source": "carts"}.
    Any failure (CARTS missing, crash, or no interface emitted) returns None so
    the caller falls back to the analytic stub.
    """
    cmd = _carts_command()
    if cmd is None:
        return None

    scale = _carts_scale(tasks)
    in_path = write_carts_component(tasks, scale)
    out_fd, out_path = tempfile.mkstemp(prefix="carts-out-", suffix=".xml")
    os.close(out_fd)
    try:
        subprocess.run(
            cmd + [in_path, CARTS_MODEL, out_path],
            check=True, capture_output=True, text=True,
        )
        parsed = parse_carts_interface(out_path, scale)
    except (subprocess.CalledProcessError, ET.ParseError, OSError, KeyError) as exc:
        print(f"WARN: CARTS failed ({exc}); using stub", file=sys.stderr)
        return None
    finally:
        for p in (in_path, out_path):
            try:
                os.remove(p)
            except OSError:
                pass

    if parsed is None:
        return None
    q_us, p_us, m = parsed
    # CARTS sizes the interface for m' cores. If that exceeds the node's core
    # budget, the (gEDF-MPR) interface is not realisable here -- this happens
    # for high-utilisation sets where MPR analysis is very pessimistic. Rather
    # than emit a clamped, under-provisioned reservation, defer to the stub.
    if m > cap_cores:
        print(f"WARN: CARTS interface needs {m} cores > cap {cap_cores}; "
              f"using stub", file=sys.stderr)
        return None
    return {"q_us": q_us, "p_us": p_us, "m": m, "source": "carts"}


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
        if _carts_command() is None:
            print("NOTE: CARTS not configured (set CARTS_JAR) -> analytic stub used.",
                  file=sys.stderr)
        else:
            print("NOTE: CARTS configured but some sets fell back to the stub.",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
