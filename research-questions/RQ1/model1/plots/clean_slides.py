#!/usr/bin/env python3
"""
Clean, slide-ready Model 1 plots (linear axes, one file per scale).

The full plots/ suite is research-grade (log axes, dense). For a presentation
those are hard to read, and a single fully-diverged cell (e.g. U=0.94 with a
187 s tail) squashes every healthy cell into an invisible sliver on any linear
axis. This script separates the two regimes so each figure is obvious:

  clean_response_vs_U_<scale>.png
      median / p99 / p99.9 response time (ms) vs U, with the deadline line.
      Cells that fully diverge (p50 > diverge_factor x deadline) are DROPPED
      from this "reservation holds" view and listed in the caption instead.

  clean_missrate_vs_U_<scale>.png
      deadline miss rate (%) vs U, ALL cells (0..100 %).

Usage:
    python3 plots/clean_slides.py --timeblock tb-YYYYMMDD-HHMM [--diverge-factor 3]
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.join(os.path.dirname(HERE), "results")


def load_cells(tb: str, root: str) -> list[dict]:
    cells = []
    for cj in sorted(glob.glob(os.path.join(root, tb, "*", "U*", "cell.json"))):
        cell_dir = os.path.dirname(cj)
        jobs = os.path.join(cell_dir, "jobs.csv")
        if not os.path.exists(jobs):
            continue
        meta = json.load(open(cj))
        R = []
        miss = 0
        with open(jobs) as fh:
            for r in csv.DictReader(fh):
                v = r.get("R_us")
                if not v:
                    continue
                R.append(float(v))
                if r.get("deadline_miss") == "1":
                    miss += 1
        if not R:
            continue
        R.sort()
        n = len(R)
        q = lambda p: R[min(n - 1, int(p * n))] / 1000.0  # us -> ms
        cells.append(dict(
            U=float(meta["U"]), scale=meta["scale"], P_ms=meta["P_us"] / 1000.0,
            p50=q(0.5), p99=q(0.99), p999=q(0.999), max=R[-1] / 1000.0,
            miss_pct=100.0 * miss / n, n=n,
        ))
    return cells


def plot_scale(scale: str, cells: list[dict], tb: str, root: str, diverge_factor: float):
    cells = sorted(cells, key=lambda c: c["U"])
    if not cells:
        return
    P_ms = cells[0]["P_ms"]
    fig_dir = os.path.join(root, tb, "figures")
    os.makedirs(fig_dir, exist_ok=True)

    # --- Figure 1: response time vs U (linear ms), healthy cells only ---------
    healthy = [c for c in cells if c["p50"] <= diverge_factor * P_ms]
    diverged = [c for c in cells if c["p50"] > diverge_factor * P_ms]
    if healthy:
        U = [c["U"] for c in healthy]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.plot(U, [c["p50"] for c in healthy], marker="o", label="median")
        ax.plot(U, [c["p99"] for c in healthy], marker="o", label="p99")
        ax.plot(U, [c["p999"] for c in healthy], marker="o", label="p99.9")
        ax.axhline(P_ms, ls="--", color="red", label=f"deadline = {P_ms:.0f} ms")
        ax.set_xlabel("reserved utilization  U = Q/P")
        ax.set_ylabel("response time R (ms)")
        title = f"Model 1 ({scale}, P={P_ms:.0f} ms): response time vs utilization"
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend()
        if diverged:
            note = "diverged (off-scale): " + ", ".join(
                f"U={c['U']:g} (p50={c['p50']/1000:.1f} s)" for c in diverged)
            ax.text(0.01, -0.22, note, transform=ax.transAxes, fontsize=8,
                    color="crimson", va="top")
        fig.tight_layout()
        out = os.path.join(fig_dir, f"clean_response_vs_U_{scale}.png")
        fig.savefig(out, dpi=130, bbox_inches="tight")
        plt.close(fig)
        print("wrote", out)

    # --- Figure 2: deadline miss rate vs U (all cells) ------------------------
    U = [c["U"] for c in cells]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(U, [c["miss_pct"] for c in cells], marker="s", color="crimson")
    for c in cells:
        ax.annotate(f"{c['miss_pct']:.0f}%", (c["U"], c["miss_pct"]),
                    textcoords="offset points", xytext=(0, 6), fontsize=8, ha="center")
    ax.set_xlabel("reserved utilization  U = Q/P")
    ax.set_ylabel("deadline miss rate (%)")
    ax.set_ylim(-5, 105)
    ax.set_title(f"Model 1 ({scale}, P={P_ms:.0f} ms): deadline miss rate vs utilization")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out = os.path.join(fig_dir, f"clean_missrate_vs_U_{scale}.png")
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def main() -> int:
    ap = argparse.ArgumentParser(description="clean slide-ready Model 1 plots")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--results-root", default=DEFAULT_ROOT)
    ap.add_argument("--diverge-factor", type=float, default=3.0,
                    help="cells with p50 > factor x deadline are dropped from the "
                         "response-vs-U figure (still shown in miss-rate)")
    args = ap.parse_args()

    cells = load_cells(args.timeblock, args.results_root)
    if not cells:
        print(f"no cells with jobs.csv found under {args.results_root}/{args.timeblock}")
        return 1
    by_scale: dict[str, list[dict]] = {}
    for c in cells:
        by_scale.setdefault(c["scale"], []).append(c)
    for scale, cs in by_scale.items():
        plot_scale(scale, cs, args.timeblock, args.results_root, args.diverge_factor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
