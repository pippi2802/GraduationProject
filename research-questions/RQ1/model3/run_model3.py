#!/usr/bin/env python3
"""
Model 3 orchestrator (acquisition only) — hyper-thread vs physical-core pinning.

  run_model3.py --arm {physical,sibling} [--sibling-load LEVEL] --timeblock LABEL

For a --timeblock, sweep the arm's (scale, U) grid SEQUENTIALLY (delete + recreate
between cells). The RT task is the COMPILED matmul (REUSED ../common image); the
measured pod runs a FIXED N jobs and EXITS, so per cell we:
  render RT -> apply -> retry until Ready (record the actual RT_CPUSET) ->
  [sibling arm] derive the RT core's HT SIBLING logical cpu and launch the
  UNRESERVED interferer pinned there at the requested --sibling-load ->
  WAIT for the RT pod to Complete -> copy jobs.csv (+ interferer.csv + cell.json)
  via the sampler pod's host mount -> delete.

The SAME reused-K reservation is used for BOTH arms, so C(sibling)/C(physical) is a
pure HT-inflation factor. NO calibration runs here: K + C_baseline are REUSED from
../model1_1 (see model3lib / calibration).

Prereqs: node labelled experiment-model=model3; node-prep + sampler DaemonSets
applied; the ../common kernel image pushed AND ../model1_1/calibration/k_table.json
present.
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
import model3lib as m3  # noqa: E402
sys.path.insert(0, str(HERE / "manifests" / "template"))
import render as _render  # noqa: E402

NS = "model3"


def run(cmd, check=False, input_text=None, timeout=None):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, input=input_text, check=check, timeout=timeout)


def kubectl(*args, check=False, input_text=None, timeout=None):
    return run(["kubectl", *args], check=check, input_text=input_text, timeout=timeout)


def log(m):
    print(f"[model3] {m}", flush=True)


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


def first_cpu(cpuset: str):
    s = parse_cpuset(cpuset)
    return sorted(s)[0] if s else None


# --------------------------------------------------------------------------- #
def resolve_node(cfg):
    r = kubectl("get", "nodes", "-l", cfg["node"]["node_label"],
                "-o", "jsonpath={.items[0].metadata.name}")
    return (r.stdout or "").strip() or None


def sampler_pod(node):
    r = kubectl("get", "pods", "-n", NS, "-l", "app=model3-sampler",
                "-o", "jsonpath={range .items[*]}{.metadata.name}{\" \"}{.spec.nodeName}{\"\\n\"}{end}")
    for line in (r.stdout or "").splitlines():
        p = line.split()
        if p and (node is None or (len(p) > 1 and p[1] == node)):
            return p[0]
    return None


def pod_rt_env(name):
    out = {}
    for var in ("RT_CPUSET", "RT_RUNTIME_PERIOD"):
        r = kubectl("exec", "-n", NS, name, "--", "printenv", var, timeout=30)
        v = (r.stdout or "").strip()
        if v:
            out[var] = v
    return out


def pod_phase(name):
    r = kubectl("get", "pod", "-n", NS, name, "-o", "jsonpath={.status.phase}")
    return (r.stdout or "").strip()


def wait_ready(name, timeout_s=120):
    r = kubectl("wait", "-n", NS, f"pod/{name}", "--for=condition=Ready",
                f"--timeout={timeout_s}s")
    return r.returncode == 0


def node_cat_to_file(spod, path, dest):
    with open(dest, "wb") as fh:
        p = subprocess.run(["kubectl", "exec", "-n", NS, spod, "--", "cat", path],
                           stdout=fh, stderr=subprocess.DEVNULL)
    return p.returncode == 0


def node_exec(spod, *cmd, timeout=60):
    r = kubectl("exec", "-n", NS, spod, "--", *cmd, timeout=timeout)
    return r.stdout or ""


def count_jobs(path):
    if not Path(path).exists():
        return 0
    with open(path) as fh:
        return sum(1 for ln in fh if ln[:1].isdigit())


def sibling_of(spod, cpu, cpu_map=None):
    """The HT sibling logical cpu of `cpu`. Prefer the node-prep cpu-map.json;
    fall back to reading thread_siblings_list live via the sampler pod."""
    if cpu is None:
        return None
    if cpu_map:
        sib = (cpu_map.get("sibling_of") or {}).get(str(cpu))
        if sib is not None:
            return int(sib)
    if spod is not None:
        raw = node_exec(spod, "cat",
                        f"/host/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list").strip()
        for other in sorted(parse_cpuset(raw)):
            if other != cpu:
                return other
    return None


def delete_objects(objs, include_claims=True):
    for name in objs:
        kubectl("delete", "-n", NS, f"pod/{name}", "--ignore-not-found", "--wait=true")
        if include_claims:
            for o in (f"resourceclaimtemplate/{name}-claim", f"rtclaimparameters/{name}-params"):
                kubectl("delete", "-n", NS, o, "--ignore-not-found", "--wait=true")


def wait_completed(name, period_us, n_jobs, cfg, max_cell_seconds=None):
    sr = cfg["stopping_rule"]
    period_s = period_us / 1e6
    cap = max_cell_seconds if max_cell_seconds else min(
        sr["max_duration_seconds"],
        120 + sr["max_wall_seconds_factor"] * n_jobs * period_s)
    t0 = time.monotonic()
    while True:
        ph = pod_phase(name)
        el = time.monotonic() - t0
        if ph == "Succeeded":
            return "completed", el
        if ph == "Failed":
            return "failed", el
        if el >= cap:
            return "wall_cap", el
        time.sleep(min(10.0, max(2.0, 20 * period_s)))


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
        cm = node_exec(spod, "cat", "/host/var/lib/model3/cpu-map.json")
        try:
            facts["cpu_map"] = json.loads(cm) if cm.strip() else None
        except json.JSONDecodeError:
            facts["cpu_map"] = None
    return facts


def host_cell_dir(cfg, tb, cell):
    base = cfg["storage"]["host_path"]
    return f"/host{base}/{tb}/{cell['arm_dir']}/{cell['scale_dir']}/U{m3.u_label(cell['u'])}"


# --------------------------------------------------------------------------- #
def do_cell(cfg, cell, tb, outdir, spod, facts, attempts, settle, dry, max_cell_seconds):
    rt_name = cell["rt_name"]
    intf_enabled = cell["interferer"].get("enabled", False)
    intf_name = cell["interferer_name"]
    log(f"=== {cell['arm'].upper()} {cell['cell_id']} P={cell['period_us']}us U={cell['u']} "
        f"Q={cell['q_us']} K={cell['K']} C_baseline={cell['c_baseline_us']} "
        f"load={cell['sibling_load']} ===")

    rt_env, placed = {}, dry
    if dry:
        log("DRY-RUN RT render:\n" + _render.render_rt_cell(cfg, cell, tb)[:400])
        if intf_enabled:
            log("DRY-RUN interferer render (placeholder cpu):\n"
                + _render.render_interferer(cfg, cell, tb)[:300])
    else:
        for att in range(1, attempts + 1):
            delete_objects([rt_name]); delete_objects([intf_name], include_claims=False)
            time.sleep(settle)
            kubectl("apply", "-f", "-", input_text=_render.render_rt_cell(cfg, cell, tb))
            if not wait_ready(rt_name, 120):
                log(f"{rt_name}: attempt {att}/{attempts} not Ready; retry"); continue
            rt_env = pod_rt_env(rt_name)
            if not parse_cpuset(rt_env.get("RT_CPUSET", "")):
                log(f"{rt_name}: attempt {att}/{attempts} no RT_CPUSET; retry"); continue
            log(f"{cell['cell_id']} RT_CPUSET={rt_env.get('RT_CPUSET')}")
            placed = True; break
    if not placed:
        delete_objects([rt_name]); delete_objects([intf_name], include_claims=False)
        return {"cell": cell["cell_id"], "arm": cell["arm"], "stop_reason": "no_placement"}

    rt_cpu = first_cpu(rt_env.get("RT_CPUSET", ""))
    sibling_cpu = None
    intf_started = False
    if intf_enabled and not dry:
        sibling_cpu = sibling_of(spod, rt_cpu, facts.get("cpu_map"))
        if sibling_cpu is None:
            log(f"WARN could not resolve HT sibling of RT cpu{rt_cpu}; interferer NOT started")
        else:
            log(f"{cell['cell_id']} launching interferer on HT sibling cpu{sibling_cpu} "
                f"(RT cpu{rt_cpu}) load={cell['sibling_load']}")
            kubectl("apply", "-f", "-",
                    input_text=_render.render_interferer(cfg, cell, tb, sibling_cpu))
            intf_started = wait_ready(intf_name, 60)
            time.sleep(cfg["execution"].get("interferer_settle_seconds", 3))

    stop_reason, elapsed = ("dry-run", 0.0) if dry else wait_completed(
        rt_name, cell["period_us"], cell["n_jobs"], cfg, max_cell_seconds)
    log(f"{cell['cell_id']} {stop_reason} after {elapsed:.0f}s")

    n = 0
    if not dry and spod:
        hp = host_cell_dir(cfg, tb, cell)
        if node_cat_to_file(spod, f"{hp}/jobs.csv", outdir / "jobs.csv"):
            n = count_jobs(outdir / "jobs.csv")
        if intf_started:
            node_cat_to_file(spod, f"{hp}/interferer.csv", outdir / "interferer.csv")
    log(f"{cell['cell_id']} collected {n} job-rows")

    meta = {
        "arm": cell["arm"], "cell_id": cell["cell_id"], "scale": cell["scale"],
        "P_us": cell["period_us"], "U": cell["u"], "Q_us": cell["q_us"], "m": cell["m"],
        "K": cell["K"], "matrix_M": cell["matrix_M"], "c_baseline_us": cell["c_baseline_us"],
        "sibling_load": cell["sibling_load"],
        "interferer": {**cell["interferer"], "started": intf_started,
                       "sibling_cpu": sibling_cpu, "obj": intf_name if intf_enabled else None},
        "reservation": {"runtime": cell["reservation_runtime"],
                        "period": cell["reservation_period"], "count": cell["reservation_count"]},
        # placements block matches common.rtmetrics.covariates.join_percell (single
        # reservation -> one jobs.csv on the RT cpu; interferer.csv on the sibling cpu).
        "placements": {"rt_cpuset": rt_env.get("RT_CPUSET"), "rt_cpu": rt_cpu,
                       "sibling_cpu": sibling_cpu,
                       "target": {"file": "jobs.csv", "obj": rt_name,
                                  "rt_cpuset": rt_env.get("RT_CPUSET"), "cpu": rt_cpu}},
        "rt_cpuset": rt_env.get("RT_CPUSET"), "cpu_used": rt_cpu,
        "n_jobs": cell["n_jobs"], "warmup": cell["warmup"],
        "stop_reason": stop_reason, "elapsed_s": round(elapsed, 1), "timeblock": tb,
        "node": facts.get("node"), "kernel": facts.get("kernel"),
        "sched_rt_runtime_us": facts.get("sched_rt_runtime_us"),
        "sched_rt_period_us": facts.get("sched_rt_period_us"),
        "cpu_map": facts.get("cpu_map"), "lscpu": facts.get("lscpu"),
    }
    (outdir / cfg["results"]["cell_metadata_json"]).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not dry:
        delete_objects([intf_name], include_claims=False)
        delete_objects([rt_name])
    return {"cell": cell["cell_id"], "arm": cell["arm"], "n": n,
            "rt_cpu": rt_cpu, "sibling_cpu": sibling_cpu,
            "sibling_load": cell["sibling_load"], "stop_reason": stop_reason}


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Model 3 sweep orchestrator")
    ap.add_argument("--arm", required=True, choices=["physical", "sibling"])
    ap.add_argument("--sibling-load", default=None,
                    choices=["off", "light", "medium", "saturating"],
                    help="interferer intensity (sibling arm; default from config)")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--scales", nargs="*", default=["tight", "soft"], choices=["tight", "soft"])
    ap.add_argument("--only-u", nargs="*", type=float, default=None,
                    help="restrict to these utilisations")
    ap.add_argument("--max-cell-seconds", type=float, default=None)
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = m3.load_config(args.config)
    results_root = Path(args.results_root) if args.results_root else HERE / cfg["results"]["root"]

    # reused-calibration gate
    ktab = m3.load_source_ktable(cfg)
    if not ktab and not args.dry_run:
        log(f"ERROR: reused calibration table missing: {m3.source_table_path(cfg)}")
        log("Build it once in Model 1_1:  python ../model1_1/calibration/calibrate.py")
        return 1

    node = resolve_node(cfg)
    if not node:
        log(f"WARN no node labelled {cfg['node']['node_label']}")
    spod = sampler_pod(node)
    facts = node_facts(spod, node) if not args.dry_run else {"node": node, "cpu_map": None}
    log(f"arm={args.arm} load={args.sibling_load or '(config default)'} "
        f"node={node} sampler={spod} kernel={facts.get('kernel')}")

    settle = cfg["execution"]["inter_cell_settle_seconds"]
    attempts = int(cfg["execution"]["placement_max_attempts"])
    summary = []

    for cell in m3.iter_cells(cfg, args.arm, args.sibling_load, ktab):
        if cell["scale"] not in args.scales:
            continue
        if args.only_u is not None and cell["u"] not in args.only_u:
            continue
        outdir = (results_root / args.timeblock / cell["arm_dir"] / cell["scale_dir"]
                  / f"U{m3.u_label(cell['u'])}")
        outdir.mkdir(parents=True, exist_ok=True)
        res = do_cell(cfg, cell, args.timeblock, outdir, spod, facts, attempts, settle,
                      args.dry_run, args.max_cell_seconds)
        summary.append(res)
        log(f"{cell['cell_id']} done: {res}")
        if not args.dry_run and settle > 0:
            time.sleep(settle)

    # copy the continuous covariate streams ONCE
    if not args.dry_run and spod:
        dest = results_root / args.timeblock / "samples"
        dest.mkdir(parents=True, exist_ok=True)
        for nm in ("cpu.csv", "tasks.csv", "server.csv"):
            if node_cat_to_file(spod, f"/host/var/lib/model3/samples/{nm}", dest / nm):
                log(f"saved sampler stream {nm}")
            else:
                log(f"WARN sampler stream {nm} unavailable")

    tbdir = results_root / args.timeblock
    tbdir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.arm}" + (f"-{args.sibling_load}" if args.sibling_load else "")
    (tbdir / f"summary-{tag}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log(f"=== {args.arm.upper()} SWEEP SUMMARY ===")
    for s in summary:
        log(json.dumps(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
