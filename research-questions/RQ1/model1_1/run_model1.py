#!/usr/bin/env python3
"""
Model 1_1 orchestrator (acquisition only).

For a --timeblock LABEL, sweep both scales x the U grid SEQUENTIALLY (one RT
container-under-test alive at a time), keeping the canary up. The inner task is
the COMPILED matmul, which runs a FIXED N jobs and EXITS, so per cell we simply:
  render -> apply -> retry placement until Ready AND on a core disjoint from the
  canary's real SMT sibling -> WAIT for the pod to Complete (or wall-cap) ->
  copy jobs.csv (+ cell.json) via the sampler pod -> delete.
The continuous covariate streams are copied ONCE at the end; join happens offline
in analyze.py.

Prereqs: node labelled experiment-model=model1; node-prep + sampler DaemonSets
applied; kernel image pushed; CALIBRATION DONE (k_table.json). Calibration is
triggered automatically if the table is missing (unless --skip-calibration).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model1lib as m1  # noqa: E402
sys.path.insert(0, str(HERE / "manifests" / "template"))
import render as _render  # noqa: E402

NS = "model1-1"


def run(cmd, check=False, input_text=None, timeout=None):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, input=input_text, check=check, timeout=timeout)


def kubectl(*args, check=False, input_text=None, timeout=None):
    return run(["kubectl", *args], check=check, input_text=input_text, timeout=timeout)


def log(m):
    print(f"[model1_1] {m}", flush=True)


def parse_cpuset(s: str) -> set:
    out = set()
    for part in (s or "").split(","):
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
def resolve_node(cfg):
    r = kubectl("get", "nodes", "-l", cfg["node"]["node_label"],
                "-o", "jsonpath={.items[0].metadata.name}")
    return (r.stdout or "").strip() or None


def sampler_pod(node):
    r = kubectl("get", "pods", "-n", NS, "-l", "app=model1-1-sampler",
                "-o", "jsonpath={range .items[*]}{.metadata.name}{\" \"}{.spec.nodeName}{\"\\n\"}{end}")
    for line in (r.stdout or "").splitlines():
        p = line.split()
        if p and (node is None or (len(p) > 1 and p[1] == node)):
            return p[0]
    return None


def canary_pod():
    r = kubectl("get", "pods", "-n", NS, "-l", "app=model1-1-canary",
                "-o", "jsonpath={.items[0].metadata.name}")
    return (r.stdout or "").strip() or None


def pod_rt_env(name):
    out = {}
    for var in ("RT_CPUSET", "RT_RUNTIME_PERIOD"):
        r = kubectl("exec", "-n", NS, name, "--", "printenv", var, timeout=30)
        v = (r.stdout or "").strip()
        if v:
            out[var] = v
    return out


def node_cat_to_file(spod, path, dest):
    with open(dest, "wb") as fh:
        p = subprocess.run(["kubectl", "exec", "-n", NS, spod, "--", "cat", path],
                           stdout=fh, stderr=subprocess.DEVNULL)
    return p.returncode == 0


def node_exec(spod, *cmd, timeout=60):
    r = kubectl("exec", "-n", NS, spod, "--", *cmd, timeout=timeout)
    return r.stdout or ""


def host_dir(cfg, tb, cell):
    base = cfg["storage"]["host_path"]
    return f"/host{base}/{tb}/{cell['scale_dir']}/U{m1.u_label(cell['u'])}"


# --------------------------------------------------------------------------- #
def wait_ready(name, timeout_s=120):
    r = kubectl("wait", "-n", NS, f"pod/{name}", "--for=condition=Ready",
                f"--timeout={timeout_s}s")
    return r.returncode == 0


def pod_phase(name):
    r = kubectl("get", "pod", "-n", NS, name, "-o", "jsonpath={.status.phase}")
    return (r.stdout or "").strip()


def wait_completed(name, cell, cfg):
    """Wait until the matmul pod Completes (Succeeded) or the wall cap fires."""
    sr = cfg["stopping_rule"]
    period_s = cell["period_us"] / 1e6
    cap = min(sr["max_duration_seconds"],
              120 + sr["max_wall_seconds_factor"] * cell["n_jobs"] * period_s)
    t0 = time.monotonic()
    while True:
        ph = pod_phase(name)
        el = time.monotonic() - t0
        if ph in ("Succeeded",):
            return "completed", el
        if ph in ("Failed",):
            return "failed", el
        if el >= cap:
            return "wall_cap", el
        time.sleep(min(10.0, max(2.0, 20 * period_s)))


def delete_cell(name):
    for o in (f"pod/{name}", f"resourceclaimtemplate/{name}-claim",
              f"rtclaimparameters/{name}-params"):
        kubectl("delete", "-n", NS, o, "--ignore-not-found", "--wait=true")


# --------------------------------------------------------------------------- #
def ensure_canary(cfg, tb, skip):
    if skip:
        log("skip canary (flag)"); return
    r = kubectl("get", "deploy", "-n", NS, "model1-1-canary")
    if r.returncode == 0:
        log("canary already running"); return
    log("starting continuous canary")
    kubectl("apply", "-f", "-", input_text=_render.render_canary(cfg, tb), check=True)
    kubectl("rollout", "status", "-n", NS, "deploy/model1-1-canary", "--timeout=300s")


def node_facts(spod, node):
    facts = {"node": node, "kernel": None, "lscpu": None,
             "sched_rt_runtime_us": None, "sched_rt_period_us": None, "cpu_map": None}
    if node:
        r = kubectl("get", "node", node, "-o", "jsonpath={.status.nodeInfo.kernelVersion}")
        facts["kernel"] = (r.stdout or "").strip() or None
    if spod:
        facts["lscpu"] = node_exec(spod, "bash", "-c", "lscpu -e 2>/dev/null || lscpu").strip() or None
        for k, p in (("sched_rt_runtime_us", "/proc/sys/kernel/sched_rt_runtime_us"),
                     ("sched_rt_period_us", "/proc/sys/kernel/sched_rt_period_us")):
            facts[k] = node_exec(spod, "cat", p).strip() or None
        cm = node_exec(spod, "cat", "/host/var/lib/model1_1/cpu-map.json")
        try:
            facts["cpu_map"] = json.loads(cm) if cm.strip() else None
        except json.JSONDecodeError:
            facts["cpu_map"] = cm
    return facts


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Model 1_1 sweep orchestrator")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--scales", nargs="*", default=["tight", "soft"], choices=["tight", "soft"])
    ap.add_argument("--only-u", nargs="*", type=float, default=None)
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--skip-canary", action="store_true")
    ap.add_argument("--skip-calibration", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = m1.load_config(args.config)
    results_root = Path(args.results_root) if args.results_root else HERE / cfg["results"]["root"]

    # calibration gate
    ktab = m1.load_k_table(cfg)
    if not ktab and not args.skip_calibration and not args.dry_run:
        log("no calibration table found -> running calibration first")
        rc = subprocess.run([sys.executable, str(HERE / "calibration" / "calibrate.py")]).returncode
        if rc not in (0, 3):
            log("calibration failed; aborting"); return 1
        ktab = m1.load_k_table(cfg)

    node = resolve_node(cfg)
    if not node:
        log(f"WARN no node labelled {cfg['node']['node_label']}")
    spod = sampler_pod(node)
    facts = node_facts(spod, node) if not args.dry_run else {"node": node}
    log(f"node={node} sampler={spod} kernel={facts.get('kernel')}")

    ensure_canary(cfg, args.timeblock, args.skip_canary)

    # canary's REAL core (driver, not config, chooses it): keep RT cells off it.
    canary_cpu = int(cfg["cpu_assignment"]["canary_core_logical"])
    if not args.dry_run and not args.skip_canary:
        cpod = canary_pod()
        cset = parse_cpuset(pod_rt_env(cpod).get("RT_CPUSET", "")) if cpod else set()
        if cset:
            canary_cpu = sorted(cset)[0]
            log(f"canary actual RT_CPUSET -> cpu{canary_cpu}")
    canary_core = {canary_cpu}
    if spod and not args.dry_run:
        sl = node_exec(spod, "cat", f"/sys/devices/system/cpu/cpu{canary_cpu}/topology/thread_siblings_list")
        sib = parse_cpuset(sl.strip())
        if sib:
            canary_core = sib
    log(f"canary core (RT kept off) = {sorted(canary_core)}")

    settle = cfg["execution"]["inter_cell_settle_seconds"]
    attempts = int(cfg["execution"]["placement_max_attempts"])
    summary = []

    for cell in m1.iter_cells(cfg, ktab):
        if cell["scale"] not in args.scales:
            continue
        if args.only_u is not None and cell["u"] not in args.only_u:
            continue
        if not cell["K"]:
            log(f"SKIP {cell['cell_id']} (not calibrated)"); continue

        name = cell["cell_name"]
        outdir = results_root / args.timeblock / cell["scale_dir"] / f"U{m1.u_label(cell['u'])}"
        outdir.mkdir(parents=True, exist_ok=True)
        log(f"=== CELL {cell['cell_id']} P={cell['period_us']}us Q={cell['q_us']}us "
            f"U={cell['u']} K={cell['K']} N={cell['n_jobs']} ===")

        rt_env, placed = {}, args.dry_run
        if args.dry_run:
            log("DRY-RUN render:\n" + _render.render_cell(cfg, cell["scale"], cell["u"], args.timeblock)[:300])
        else:
            for att in range(1, attempts + 1):
                delete_cell(name)
                time.sleep(settle)
                kubectl("apply", "-f", "-", input_text=_render.render_cell(cfg, cell["scale"], cell["u"], args.timeblock))
                if not wait_ready(name, 120):
                    log(f"{name}: attempt {att}/{attempts} not Ready (CDI race?); retry"); continue
                rt_env = pod_rt_env(name)
                got = parse_cpuset(rt_env.get("RT_CPUSET", ""))
                if not got:
                    log(f"{name}: attempt {att}/{attempts} no RT_CPUSET; retry"); continue
                if got & canary_core:
                    log(f"{name}: attempt {att}/{attempts} RT_CPUSET={rt_env.get('RT_CPUSET')} "
                        f"shares canary core {sorted(canary_core)}; retry"); continue
                log(f"{cell['cell_id']} RT_CPUSET={rt_env.get('RT_CPUSET')} (clean core, off {sorted(canary_core)})")
                placed = True
                break

        if not placed:
            log(f"ERROR {name} no clean placement after {attempts}; skipping")
            delete_cell(name)
            summary.append({"cell": cell["cell_id"], "stop_reason": "no_clean_placement"})
            continue

        stop_reason, elapsed = ("dry-run", 0.0) if args.dry_run else wait_completed(name, cell, cfg)
        log(f"{cell['cell_id']} {stop_reason} after {elapsed:.0f}s")

        # copy jobs.csv from the node via the sampler (host mount)
        n_collected = 0
        if not args.dry_run and spod:
            hp = host_dir(cfg, args.timeblock, cell) + "/jobs.csv"
            if node_cat_to_file(spod, hp, outdir / "jobs.csv"):
                with open(outdir / "jobs.csv") as fh:
                    n_collected = sum(1 for ln in fh if ln[:1].isdigit())
                log(f"saved jobs.csv ({n_collected} jobs) -> {outdir/'jobs.csv'}")
            else:
                log(f"WARN could not read {hp}")

        meta = {
            "cell_id": cell["cell_id"], "scale": cell["scale"],
            "P_us": cell["period_us"], "Q_us": cell["q_us"], "U": cell["u"], "m": cell["m"],
            "K": cell["K"], "matrix_M": cell["matrix_M"],
            "reservation": {"runtime": cell["reservation_runtime"],
                            "period": cell["reservation_period"], "count": cell["reservation_count"]},
            "rt_cpuset": rt_env.get("RT_CPUSET"),
            "cpu_used": (sorted(parse_cpuset(rt_env.get("RT_CPUSET", "")))[0]
                         if rt_env.get("RT_CPUSET") else None),
            "canary_core": sorted(canary_core), "canary_cpu": canary_cpu,
            "n_jobs": cell["n_jobs"], "warmup": cell["warmup"], "n_collected": n_collected,
            "stop_reason": stop_reason, "elapsed_s": round(elapsed, 1),
            "timeblock": args.timeblock,
            "node": facts.get("node"), "kernel": facts.get("kernel"),
            "sched_rt_runtime_us": facts.get("sched_rt_runtime_us"),
            "sched_rt_period_us": facts.get("sched_rt_period_us"),
            "cpu_map": facts.get("cpu_map"), "lscpu": facts.get("lscpu"),
        }
        (outdir / cfg["results"]["cell_metadata_json"]).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        delete_cell(name)
        summary.append({"cell": cell["cell_id"], "N": n_collected, "stop_reason": stop_reason})
        log(f"{cell['cell_id']} done: {summary[-1]}")
        if not args.dry_run and settle > 0:
            time.sleep(settle)

    # copy the continuous covariate streams ONCE
    if not args.dry_run and spod:
        dest = results_root / args.timeblock / "samples"
        dest.mkdir(parents=True, exist_ok=True)
        for nm in ("cpu.csv", "tasks.csv", "server.csv"):
            if node_cat_to_file(spod, f"/host/var/lib/model1_1/samples/{nm}", dest / nm):
                log(f"saved sampler stream {nm}")
            else:
                log(f"WARN sampler stream {nm} unavailable")

    (results_root / args.timeblock).mkdir(parents=True, exist_ok=True)
    (results_root / args.timeblock / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log("=== SWEEP SUMMARY ===")
    for s in summary:
        log(json.dumps(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
