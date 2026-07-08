#!/usr/bin/env python3
"""
Model 1 orchestrator.

For a given --timeblock LABEL, sweep both scales and their U grids SEQUENTIALLY
(exactly one RT-container-under-test alive at a time), keeping the canary up the
whole time. Per cell:

  render manifest -> kubectl apply -> collect jobs until the per-cell stopping
  rule fires (convergence within [N_min, N_max], or the 3 h guard) -> collect
  CSVs into results/<timeblock>/<scale-dir>/U<U>/ -> kubectl delete -> record a
  cell metadata JSON. Idempotent & re-runnable; delete+recreate between cells.

This driver runs on your workstation and talks to the cluster via kubectl. It
reads node-side files (continuous sampler stream, rt-app logs after pod delete,
node facts) by exec-ing into the long-lived sampler DaemonSet pod, which mounts
the host /var/lib/model1 and has hostPID.

Prerequisites (see README): node labelled model1/rt-node=true; node-prep and
sampler DaemonSets applied; KubeDeadline (rt-DRA) driver installed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model1lib as m1  # noqa: E402
sys.path.insert(0, str(HERE / "parse"))
import convergence as conv_mod  # noqa: E402
import parse_rtapp  # noqa: E402


NS = "model1"


# --------------------------------------------------------------------------- #
# shell helpers
# --------------------------------------------------------------------------- #
def run(cmd: list[str], check=True, capture=True, input_text=None):
    return subprocess.run(
        cmd, check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True, input=input_text,
    )


def kubectl(*args, check=True, capture=True, input_text=None):
    return run(["kubectl", *args], check=check, capture=capture, input_text=input_text)


def log(msg: str):
    print(f"[model1] {msg}", flush=True)


def parse_cpuset(cpuset: str) -> set:
    """Parse a cpuset string like '1', '0,2', '0-1' into a set of ints."""
    out = set()
    for part in (cpuset or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                out.update(range(int(a), int(b) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            out.add(int(part))
    return out


# --------------------------------------------------------------------------- #
# node access via the sampler DaemonSet pod
# --------------------------------------------------------------------------- #
def sampler_pod(node: str | None) -> str | None:
    sel = "app=model1-sampler"
    args = ["get", "pods", "-n", NS, "-l", sel, "-o",
            "jsonpath={range .items[*]}{.metadata.name}{\" \"}{.spec.nodeName}{\"\\n\"}{end}"]
    r = kubectl(*args, check=False)
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        pod_node = parts[1] if len(parts) > 1 else ""
        if node is None or pod_node == node:
            return name
    return None


def node_cat(spod: str, path: str) -> str | None:
    r = kubectl("exec", "-n", NS, spod, "--", "cat", path, check=False)
    return r.stdout if r.returncode == 0 else None


def node_cat_to_file(spod: str, path: str, dest) -> bool:
    """Stream a node file directly to `dest` on disk, WITHOUT buffering the whole
    file in memory. The continuous sampler streams grow unboundedly (rate_hz for
    the whole sweep), so slurping them into a Python string OOM-kills the CP."""
    with open(dest, "wb") as fh:
        p = subprocess.run(["kubectl", "exec", "-n", NS, spod, "--", "cat", path],
                           stdout=fh, stderr=subprocess.DEVNULL, check=False)
    return p.returncode == 0


def node_exec(spod: str, *cmd, check=False) -> str:
    r = kubectl("exec", "-n", NS, spod, "--", *cmd, check=check)
    return r.stdout or ""


# --------------------------------------------------------------------------- #
# manifest render/apply/delete
# --------------------------------------------------------------------------- #
# Rendering is the pure-Python manifests/template/render.py (no envsubst/kubectl),
# imported directly so there is ONE rendering code path (also used for the
# committed per-U files via `render.py --all`).
sys.path.insert(0, str(HERE / "manifests" / "template"))
import render as _render  # noqa: E402


def render(scale: str, u: float, timeblock: str) -> str:
    return _render.render_cell(m1.load_config(), scale, u, timeblock)


def render_canary(timeblock: str) -> str:
    return _render.render_canary(m1.load_config(), timeblock)


def apply_yaml(yaml_text: str, dry_run: bool):
    if dry_run:
        log("DRY-RUN apply:\n" + yaml_text[:400] + ("...\n" if len(yaml_text) > 400 else ""))
        return
    kubectl("apply", "-f", "-", input_text=yaml_text)


def delete_cell(name: str, dry_run: bool):
    objs = [
        f"pod/{name}",
        f"resourceclaimtemplate/{name}-claim",
        f"rtclaimparameters/{name}-params",
        f"configmap/{name}-rtapp",
    ]
    if dry_run:
        log(f"DRY-RUN delete: {objs}")
        return
    for o in objs:
        kubectl("delete", "-n", NS, o, "--ignore-not-found", "--wait=true", check=False)


# --------------------------------------------------------------------------- #
# per-cell collection
# --------------------------------------------------------------------------- #
def wait_running(name: str, timeout_s: int = 300) -> bool:
    r = kubectl("wait", "-n", NS, f"pod/{name}",
                "--for=condition=Ready", f"--timeout={timeout_s}s", check=False)
    return r.returncode == 0


def fetch_rtapp_log(name: str) -> str | None:
    """Read the rt-app per-loop log from inside the (running) cell pod."""
    ls = kubectl("exec", "-n", NS, name, "--",
                 "bash", "-c", "ls /results/*.log 2>/dev/null | head -n1", check=False)
    path = (ls.stdout or "").strip()
    if not path:
        return None
    r = kubectl("exec", "-n", NS, name, "--", "cat", path, check=False)
    return r.stdout if r.returncode == 0 else None


def count_jobs(name: str) -> int:
    """CHEAP job count for the fixed-N stop: count data rows of the rt-app log
    ON THE NODE (one `grep -c`) instead of transferring + parsing the whole
    (continuously growing) log every poll. Data rows begin with the job index
    digit; the header/comment rows start with '#'. Returns 0 if the log is not
    present yet or nothing has been written. NO derived computation (p99.9/tail)
    runs here — that is all deferred to analyze.py (offline)."""
    r = kubectl("exec", "-n", NS, name, "--", "bash", "-c",
                "cat /results/*.log 2>/dev/null | grep -cE '^[[:space:]]*[0-9]'",
                check=False)
    out = (r.stdout or "").strip()
    try:
        return int(out.split()[0]) if out else 0
    except (ValueError, IndexError):
        return 0


def pod_rt_env(name: str) -> dict:
    """Read the DRA-injected reservation env (RT_CPUSET, RT_RUNTIME_PERIOD)."""
    out = {}
    for var in ("RT_CPUSET", "RT_RUNTIME_PERIOD"):
        r = kubectl("exec", "-n", NS, name, "--", "printenv", var, check=False)
        v = (r.stdout or "").strip()
        if v:
            out[var] = v
    return out


def collect_until_stop(cell: dict, name: str, cfg: dict, outdir: Path, dry_run: bool):
    sr = cfg["stopping_rule"]
    convc = sr["convergence"]
    n_min, n_max = cell["n_min"], cell["n_max"]
    guard_s = sr["max_duration_seconds"]
    # Abort a cell that becomes Ready but produces ZERO jobs within this long
    # (e.g. rt-app can't get its RT budget) instead of polling silently until the
    # 3 h guard. Generous enough to cover the apt-install + rt-app startup.
    no_jobs_timeout = sr.get("no_jobs_timeout_seconds", 300)
    warmup = sr["warmup_jobs"]
    period_s = cell["period_us"] / 1e6

    # Pure fixed-N stop? With n_min >= n_max (and no per-U convergence override)
    # the cell ALWAYS stops on N_max, so the running p99.9/POT convergence check
    # can never fire first — computing it every poll is dead weight ON THE
    # CRITICAL PATH (it also re-transfers + re-parses the whole growing log each
    # time). In that case poll a CHEAP node-side job COUNT and defer ALL derived
    # metrics to analyze.py (offline). The log is fetched + parsed ONCE at the
    # end of the cell. The convergence path is kept for the (currently unused)
    # n_min < n_max configuration.
    fixed_n = n_min >= n_max
    if fixed_n:
        # counting is cheap -> poll more often so the cell stops promptly once it
        # reaches N_max (less dead tail-wait, which matters most at tight scale).
        check_interval = max(5.0, min(30.0, 100 * period_s))
    else:
        # a few times the mean inter-arrival, floored at 15 s
        check_interval = max(15.0, min(60.0, 200 * period_s))

    start_wall_ns = time.time_ns()
    start_mono = time.monotonic()
    stop_reason = "unknown"
    # p99.9/tail are recorded as None on the fixed-N fast path (derived offline).
    last = {"n": 0, "p99_9": None, "rel_change": None,
            "running_max": None, "tail_index": None, "converged": False}

    if dry_run:
        log(f"DRY-RUN collect: cell={cell['cell_id']} n_min={n_min} n_max={n_max} guard={guard_s}s")
        return {"start_wall_ns": start_wall_ns, "end_wall_ns": time.time_ns(),
                "n_collected": 0, "stop_reason": "dry-run", **last}

    tmp_log = outdir / "rt-app.log"
    while True:
        elapsed = time.monotonic() - start_mono
        if fixed_n:
            # cheap: count data rows on the node, no transfer/parse/convergence.
            n = max(0, count_jobs(name) - warmup)
            last["n"] = n
            log(f"cell={cell['cell_id']} N={n} t={elapsed:.0f}s")
        else:
            text = fetch_rtapp_log(name)
            n = 0
            if text:
                tmp_log.write_text(text, encoding="utf-8")
                jobs = parse_rtapp.parse_log(str(tmp_log), warmup)
                r_vals = [j["R_us"] for j in jobs if isinstance(j["R_us"], (int, float))]
                n = len(r_vals)
                res = conv_mod.check_convergence(
                    r_vals, n_min=n_min,
                    rel_change_threshold=convc["rel_change_threshold"],
                    window_fraction=convc["window_fraction"],
                    min_window_jobs=convc["min_window_jobs"],
                )
                last = res
                log(f"cell={cell['cell_id']} N={n} p99.9={res['p99_9']:.1f}us "
                    f"rel={res['rel_change']:.4f} max={res['running_max']:.1f}us "
                    f"t={elapsed:.0f}s")

        if last["n"] >= n_max:
            stop_reason = "n_max"
            break
        if last["n"] == 0 and elapsed >= no_jobs_timeout:
            log(f"cell={cell['cell_id']} produced ZERO jobs after {elapsed:.0f}s "
                f"(rt-app not running? RT budget?); aborting cell")
            stop_reason = "no_jobs"
            break
        if not fixed_n and last.get("converged") and last["n"] >= n_min:
            stop_reason = "convergence"
            break
        if elapsed >= guard_s:
            stop_reason = "guard_3h"
            break
        time.sleep(check_interval)

    end_wall_ns = time.time_ns()
    return {"start_wall_ns": start_wall_ns, "end_wall_ns": end_wall_ns,
            "n_collected": last["n"], "stop_reason": stop_reason,
            "p99_9_us": last["p99_9"], "running_max_us": last["running_max"],
            "rel_change": last["rel_change"], "tail_index": last["tail_index"]}


def save_sampler_stream(spod: str | None, tb_dir: Path):
    """Copy the FULL continuous sampler stream ONCE at the end of the sweep.

    Per-cell covariate slicing is DEFERRED to analyze.py (offline), using each
    cell.json's [start_wall_ns, end_wall_ns] window. This replaces the old
    per-cell copy+slice that re-fetched and re-scanned the (continuously growing)
    stream for EVERY cell -> O(n_cells * stream). Now it is one copy total and no
    derived work runs on the sweep's critical path."""
    if not spod:
        log("WARN: no sampler pod; cannot save sampler stream")
        return
    samples_dir = "/host/var/lib/model1/samples"
    dest = tb_dir / "samples"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("server.csv", "covariates.csv"):
        if node_cat_to_file(spod, f"{samples_dir}/{name}", dest / name):
            log(f"saved sampler stream {name} -> {dest / name}")
        else:
            log(f"WARN: sampler stream {name} unavailable")


def node_facts(spod: str | None, node: str | None) -> dict:
    facts = {"node": node, "kernel": None, "lscpu": None,
             "sched_rt_runtime_us": None, "sched_rt_period_us": None, "cpu_map": None}
    if node:
        r = kubectl("get", "node", node, "-o",
                    "jsonpath={.status.nodeInfo.kernelVersion}", check=False)
        facts["kernel"] = (r.stdout or "").strip() or None
    if spod:
        facts["lscpu"] = node_exec(spod, "bash", "-c",
                                   "lscpu -e 2>/dev/null || lscpu").strip() or None
        facts["sched_rt_runtime_us"] = node_cat(spod, "/proc/sys/kernel/sched_rt_runtime_us")
        facts["sched_rt_period_us"] = node_cat(spod, "/proc/sys/kernel/sched_rt_period_us")
        cm = node_cat(spod, "/host/var/lib/model1/cpu-map.json")
        if cm:
            try:
                facts["cpu_map"] = json.loads(cm)
            except json.JSONDecodeError:
                facts["cpu_map"] = cm
    for k in ("sched_rt_runtime_us", "sched_rt_period_us"):
        if isinstance(facts[k], str):
            facts[k] = facts[k].strip()
    return facts


# --------------------------------------------------------------------------- #
# main sweep
# --------------------------------------------------------------------------- #
def ensure_canary(timeblock: str, dry_run: bool, skip: bool):
    if skip:
        log("skipping canary (per flag)")
        return
    r = kubectl("get", "deploy", "-n", NS, "model1-canary", check=False)
    if r.returncode == 0:
        log("canary already running")
        return
    log("starting continuous canary")
    apply_yaml(render_canary(timeblock), dry_run)
    if not dry_run:
        kubectl("rollout", "status", "-n", NS, "deploy/model1-canary",
                "--timeout=300s", check=False)


def resolve_node() -> str | None:
    r = kubectl("get", "nodes", "-l", "model1/rt-node=true",
                "-o", "jsonpath={.items[0].metadata.name}", check=False)
    n = (r.stdout or "").strip()
    return n or None


def main() -> int:
    ap = argparse.ArgumentParser(description="Model 1 sweep orchestrator")
    ap.add_argument("--timeblock", required=True, help="time-block label, e.g. tb-20260706-1200")
    ap.add_argument("--config", default=None)
    ap.add_argument("--scales", nargs="*", default=["tight", "soft"],
                    choices=["tight", "soft"])
    ap.add_argument("--only-u", nargs="*", type=float, default=None,
                    help="restrict to these U values (debug)")
    ap.add_argument("--results-root", default=None,
                    help="client-side results root (default: model1/results)")
    ap.add_argument("--skip-canary", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = m1.load_config(args.config)
    results_root = Path(args.results_root) if args.results_root else HERE / cfg["results"]["root"]

    node = resolve_node()
    if not node:
        log("WARN: no node labelled model1/rt-node=true found via kubectl")
    spod = sampler_pod(node)
    facts = node_facts(spod, node) if not args.dry_run else {"node": node}
    log(f"node={node} sampler_pod={spod} kernel={facts.get('kernel')}")

    # Canary's physical core = its SMT sibling set. The rt-DRA driver is SMT-blind
    # (worst-fit over logical CPUs), so it may place the RT cell on the canary's
    # sibling. We keep the RT cell OFF these CPUs (retry until a clean core).
    canary_cpu = int(cfg["cpu_assignment"]["canary_core_logical"])
    canary_core = {canary_cpu}
    if spod and not args.dry_run:
        sl = node_exec(spod, "cat",
                       f"/sys/devices/system/cpu/cpu{canary_cpu}/topology/thread_siblings_list")
        sib = parse_cpuset((sl or "").strip())
        if sib:
            canary_core = sib
    log(f"canary core CPUs (RT kept off) = {sorted(canary_core)}")

    ensure_canary(args.timeblock, args.dry_run, args.skip_canary)

    settle = cfg["execution"]["inter_cell_settle_seconds"]
    summary = []
    for cell in m1.iter_cells(cfg):
        if cell["scale"] not in args.scales:
            continue
        if args.only_u is not None and cell["u"] not in args.only_u:
            continue

        name = cell["cell_name"]
        outdir = results_root / args.timeblock / cell["scale_dir"] / f"U{m1.u_label(cell['u'])}"
        outdir.mkdir(parents=True, exist_ok=True)
        log(f"=== CELL {cell['cell_id']}  P={cell['period_us']}us Q={cell['q_us']}us "
            f"U={cell['u']} N_min={cell['n_min']} N_max={cell['n_max']} ===")

        # Robust cell start. The rt-DRA driver is SMT-UNAWARE (worst-fit over
        # logical CPUs) and can (a) hit a transient CDI-prepare race
        # ("rtCDIDevices is nil") so the pod never becomes Ready, or (b) place the
        # RT task on the CANARY's physical core (its SMT sibling), destroying
        # isolation. Retry delete+recreate until the pod is Ready AND on a core
        # OTHER than the canary's; give up after placement_max_attempts.
        rt_env = {}
        placement_ok = args.dry_run
        attempts = int(cfg["execution"].get("placement_max_attempts", 6))
        if args.dry_run:
            apply_yaml(render(cell["scale"], cell["u"], args.timeblock), True)
        else:
            for attempt in range(1, attempts + 1):
                delete_cell(name, args.dry_run)
                time.sleep(settle)                     # let the driver release the claim
                apply_yaml(render(cell["scale"], cell["u"], args.timeblock), args.dry_run)
                if not wait_running(name, timeout_s=120):
                    log(f"cell {name}: attempt {attempt}/{attempts} not Ready "
                        f"(CDI-prepare race?); retrying")
                    continue
                rt_env = pod_rt_env(name)
                got = parse_cpuset(rt_env.get("RT_CPUSET", ""))
                if not got:
                    log(f"cell {name}: attempt {attempt}/{attempts} no RT_CPUSET; retrying")
                    continue
                if got & canary_core:
                    log(f"cell {name}: attempt {attempt}/{attempts} RT_CPUSET="
                        f"{rt_env.get('RT_CPUSET')} shares canary core "
                        f"{sorted(canary_core)}; retrying for a clean core")
                    continue
                log(f"cell {cell['cell_id']} RT_CPUSET={rt_env.get('RT_CPUSET')} "
                    f"RT_RUNTIME_PERIOD={rt_env.get('RT_RUNTIME_PERIOD')} "
                    f"(clean core, off {sorted(canary_core)})")
                placement_ok = True
                break

        if not placement_ok:
            log(f"ERROR: cell {name} never Ready on a clean core after {attempts} "
                f"attempts; skipping")
            delete_cell(name, args.dry_run)
            summary.append({"cell": cell["cell_id"], "stop_reason": "no_clean_placement"})
            continue

        run_info = collect_until_stop(cell, name, cfg, outdir, args.dry_run)

        # final rt-app log + per-job CSV
        if not args.dry_run:
            text = fetch_rtapp_log(name)
            if text:
                (outdir / "rt-app.log").write_text(text, encoding="utf-8")
                jobs = parse_rtapp.parse_log(str(outdir / "rt-app.log"),
                                             cfg["stopping_rule"]["warmup_jobs"])
                import csv as _csv
                with open(outdir / cfg["results"]["per_job_csv"], "w", newline="",
                          encoding="utf-8") as fh:
                    w = _csv.DictWriter(fh, fieldnames=parse_rtapp.OUT_HEADER)
                    w.writeheader(); w.writerows(jobs)

        delete_cell(name, args.dry_run)

        # NOTE: covariate slicing is DEFERRED to analyze.py (offline). The sweep
        # only records this cell's [start,end] window in cell.json below; the
        # shared sampler stream is copied ONCE after the loop (save_sampler_stream)
        # instead of re-copying+rescanning the growing stream every cell.

        # cell metadata
        cpu_used = rt_env.get("RT_CPUSET")
        if cpu_used is None and isinstance(facts.get("cpu_map"), dict):
            cpu_used = facts["cpu_map"].get("rt_cpu")
        meta = {
            "cell_id": cell["cell_id"], "scale": cell["scale"],
            "P_us": cell["period_us"], "Q_us": cell["q_us"], "U": cell["u"],
            "m": cell["m"], "reservation_units": cfg["kubedeadline_reservation_spec"]["units"],
            "reservation": {"runtime": cell["reservation_runtime"],
                            "period": cell["reservation_period"],
                            "count": cell["reservation_count"]},
            "cpu_used": cpu_used,
            "rt_cpuset": rt_env.get("RT_CPUSET"),
            "rt_runtime_period": rt_env.get("RT_RUNTIME_PERIOD"),
            "n_min": cell["n_min"], "n_max": cell["n_max"],
            "timeblock": args.timeblock,
            **run_info,
            "node": facts.get("node"), "kernel": facts.get("kernel"),
            "sched_rt_runtime_us": facts.get("sched_rt_runtime_us"),
            "sched_rt_period_us": facts.get("sched_rt_period_us"),
            "cpu_map": facts.get("cpu_map"),
            "lscpu": facts.get("lscpu"),
        }
        (outdir / cfg["results"]["cell_metadata_json"]).write_text(
            json.dumps(meta, indent=2), encoding="utf-8")
        summary.append({"cell": cell["cell_id"], "N": run_info["n_collected"],
                        "stop_reason": run_info["stop_reason"],
                        "p99_9_us": run_info.get("p99_9_us")})
        log(f"cell {cell['cell_id']} done: {summary[-1]}")

        if not args.dry_run and settle > 0:
            time.sleep(settle)

    # ONE-SHOT: copy the whole continuous sampler stream after the sweep, so no
    # per-cell copy/slice ran on the critical path. Slicing happens in analyze.py.
    if not args.dry_run:
        save_sampler_stream(spod, results_root / args.timeblock)

    log("=== SWEEP SUMMARY (timeblock=%s) ===" % args.timeblock)
    for s in summary:
        log(json.dumps(s))
    (results_root / args.timeblock).mkdir(parents=True, exist_ok=True)
    (results_root / args.timeblock / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
