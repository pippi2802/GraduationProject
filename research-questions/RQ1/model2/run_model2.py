#!/usr/bin/env python3
"""
Model 2 orchestrator (acquisition only) — co-located contention.

  run_model2.py --variant {intra,inter} --timeblock LABEL

For a --timeblock, sweep the chosen variant's cell grid SEQUENTIALLY (delete +
recreate between cells). The inner tasks are the COMPILED matmul (REUSED Model 1_1
image); the MEASURED pod(s) run a FIXED N jobs and EXIT, so per cell we:
  render -> apply -> retry until the measured pod(s) are Ready (record every
  participant's actual RT_CPUSET so co-location is auditable) -> WAIT for the
  measured pod to Complete -> copy the per-job CSVs (+ cell.json) via the sampler
  pod's host mount -> delete.

  intra: ONE pod, k matmul tasks share one reservation -> collect task{i}.csv.
  inter: 1 target + n neighbour pods co-scheduled -> collect target.csv (+ neighbour
         logs); the over-subscribe arm may leave neighbours Pending (recorded).

NO calibration runs here: K is REUSED from ../model1_1 (see model2lib / calibration).
Continuous covariate streams are copied ONCE at the end; join happens offline in
analyze.py.

Prereqs: node labelled experiment-model=model2; node-prep + sampler DaemonSets
applied; Model 1_1's kernel image pushed AND its calibration/k_table.json present.
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
import model2lib as m2  # noqa: E402
sys.path.insert(0, str(HERE / "manifests" / "template"))
import render as _render  # noqa: E402

NS = "model2"


def run(cmd, check=False, input_text=None, timeout=None):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, input=input_text, check=check, timeout=timeout)


def kubectl(*args, check=False, input_text=None, timeout=None):
    return run(["kubectl", *args], check=check, input_text=input_text, timeout=timeout)


def log(m):
    print(f"[model2] {m}", flush=True)


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
    r = kubectl("get", "pods", "-n", NS, "-l", "app=model2-sampler",
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


def delete_objects(objs):
    for name in objs:
        for o in (f"pod/{name}", f"resourceclaimtemplate/{name}-claim",
                  f"rtclaimparameters/{name}-params"):
            kubectl("delete", "-n", NS, o, "--ignore-not-found", "--wait=true")


def wait_completed(name, period_us, n_jobs, cfg):
    sr = cfg["stopping_rule"]
    period_s = period_us / 1e6
    cap = min(sr["max_duration_seconds"],
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
        cm = node_exec(spod, "cat", "/host/var/lib/model2/cpu-map.json")
        try:
            facts["cpu_map"] = json.loads(cm) if cm.strip() else None
        except json.JSONDecodeError:
            facts["cpu_map"] = cm
    return facts


def host_intra_dir(cfg, tb, cell):
    base = cfg["storage"]["host_path"]
    return f"/host{base}/{tb}/intra/{cell['scale_dir']}/{cell['cell_id']}"


def host_inter_dir(cfg, tb, cell):
    base = cfg["storage"]["host_path"]
    return f"/host{base}/{tb}/inter/{cell['scale_dir']}/{cell['arm']}/{cell['cell_id']}"


# --------------------------------------------------------------------------- #
def do_intra(cfg, cell, tb, outdir, spod, facts, attempts, settle, dry):
    name = cell["cell_name"]
    log(f"=== INTRA {cell['cell_id']} P={cell['period_us']}us U={cell['u']} "
        f"k={cell['k']} split={cell['split']} taskK={cell['task_K']} ===")
    rt_env, placed = {}, dry
    if dry:
        log("DRY-RUN render:\n" + _render.render_intra_cell(cfg, cell, tb)[:400])
    else:
        for att in range(1, attempts + 1):
            delete_objects([name]); time.sleep(settle)
            kubectl("apply", "-f", "-", input_text=_render.render_intra_cell(cfg, cell, tb))
            if not wait_ready(name, 120):
                log(f"{name}: attempt {att}/{attempts} not Ready; retry"); continue
            rt_env = pod_rt_env(name)
            if not parse_cpuset(rt_env.get("RT_CPUSET", "")):
                log(f"{name}: attempt {att}/{attempts} no RT_CPUSET; retry"); continue
            log(f"{cell['cell_id']} RT_CPUSET={rt_env.get('RT_CPUSET')}")
            placed = True; break
    if not placed:
        delete_objects([name])
        return {"cell": cell["cell_id"], "stop_reason": "no_placement"}

    shared_cpu = first_cpu(rt_env.get("RT_CPUSET", ""))
    stop_reason, elapsed = ("dry-run", 0.0) if dry else wait_completed(
        name, cell["period_us"], cell["n_jobs"], cfg)
    log(f"{cell['cell_id']} {stop_reason} after {elapsed:.0f}s")

    tasks_meta, n_total = [], 0
    for i in range(cell["k"]):
        fn = f"task{i}.csv"
        role = None
        if cell.get("victim_index") is not None:
            role = "victim" if i == cell["victim_index"] else "greedy"
        n = 0
        if not dry and spod:
            if node_cat_to_file(spod, f"{host_intra_dir(cfg, tb, cell)}/{fn}", outdir / fn):
                n = count_jobs(outdir / fn); n_total += n
        tasks_meta.append({"file": fn, "index": i, "u": cell["task_utilizations"][i],
                           "target_C_us": cell["task_C_us"][i], "K": cell["task_K"][i],
                           "role": role, "cpu": shared_cpu, "n_collected": n})
    log(f"{cell['cell_id']} collected {n_total} job-rows across {cell['k']} task(s)")

    meta = {
        "variant": "intra", "cell_id": cell["cell_id"], "scale": cell["scale"],
        "P_us": cell["period_us"], "U": cell["u"], "Q_us": cell["q_us"], "m": cell["m"],
        "k": cell["k"], "split": cell["split"], "matrix_M": cell["matrix_M"],
        "task_utilizations": cell["task_utilizations"], "task_C_us": cell["task_C_us"],
        "task_K": cell["task_K"], "victim_index": cell.get("victim_index"),
        "reservation": {"runtime": cell["reservation_runtime"],
                        "period": cell["reservation_period"], "count": cell["reservation_count"]},
        "placements": {"shared_rt_cpuset": rt_env.get("RT_CPUSET"),
                       "shared_cpu": shared_cpu, "tasks": tasks_meta},
        "n_jobs": cell["n_jobs"], "warmup": cell["warmup"],
        "stop_reason": stop_reason, "elapsed_s": round(elapsed, 1), "timeblock": tb,
        "node": facts.get("node"), "kernel": facts.get("kernel"),
        "sched_rt_runtime_us": facts.get("sched_rt_runtime_us"),
        "sched_rt_period_us": facts.get("sched_rt_period_us"),
        "cpu_map": facts.get("cpu_map"), "lscpu": facts.get("lscpu"),
    }
    (outdir / cfg["results"]["cell_metadata_json"]).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not dry:
        delete_objects([name])
    return {"cell": cell["cell_id"], "n": n_total, "stop_reason": stop_reason}


def do_inter(cfg, cell, tb, outdir, spod, facts, attempts, settle, dry):
    names = _render.inter_object_names(cell)
    target = names["target"]; nbs = names["neighbours"]
    all_objs = [target] + nbs
    log(f"=== INTER {cell['cell_id']} arm={cell['arm']} P={cell['period_us']}us "
        f"targetU={cell['target_u']} nb={cell['n_neighbours']}x{cell['neighbour_unit_u']} "
        f"oversub={cell['oversubscribe']} targetK={cell['target_K']} ===")
    tgt_env, placed = {}, dry
    nb_status = []
    if dry:
        log("DRY-RUN render:\n" + _render.render_inter_cell(cfg, cell, tb)[:400])
    else:
        for att in range(1, attempts + 1):
            delete_objects(all_objs); time.sleep(settle)
            # PHASE 1: admit the TARGET ALONE first, so the measured reservation is
            # guaranteed before the (possibly over-subscribing) neighbours compete.
            kubectl("apply", "-f", "-", input_text=_render.render_inter_target(cfg, cell, tb))
            if not wait_ready(target, 120):
                log(f"{target}: attempt {att}/{attempts} target not Ready; retry"); continue
            tgt_env = pod_rt_env(target)
            if not parse_cpuset(tgt_env.get("RT_CPUSET", "")):
                log(f"{target}: attempt {att}/{attempts} no RT_CPUSET; retry"); continue
            # PHASE 2: target is admitted — now add the neighbours (best-effort; the
            # over-subscribe arm may legitimately leave some/all of them Pending).
            nb_manifest = _render.render_inter_neighbours(cfg, cell, tb)
            if nb_manifest.strip():
                kubectl("apply", "-f", "-", input_text=nb_manifest)
            placed = True; break
            placed = True; break
    if not placed:
        delete_objects(all_objs)
        return {"cell": cell["cell_id"], "stop_reason": "no_placement"}

    # give neighbours a moment to admit, then record each one's phase + RT_CPUSET
    if not dry and nbs:
        for nb in nbs:
            wait_ready(nb, 60)
    tgt_cpu = first_cpu(tgt_env.get("RT_CPUSET", ""))
    nb_meta = []
    admitted = 0
    for i, nb in enumerate(nbs):
        ph = pod_phase(nb) if not dry else "dry-run"
        env = pod_rt_env(nb) if (not dry and ph == "Running") else {}
        cpu = first_cpu(env.get("RT_CPUSET", ""))
        if ph == "Running":
            admitted += 1
        nb_meta.append({"file": f"neighbour{i}.csv", "index": i, "obj": nb,
                        "phase": ph, "rt_cpuset": env.get("RT_CPUSET"), "cpu": cpu})
        nb_status.append(ph)
    colocated = sum(1 for n in nb_meta if n["cpu"] is not None and n["cpu"] == tgt_cpu)
    log(f"{cell['cell_id']} target cpu={tgt_cpu}; neighbours admitted={admitted}/"
        f"{len(nbs)} colocated_with_target={colocated}")

    stop_reason, elapsed = ("dry-run", 0.0) if dry else wait_completed(
        target, cell["period_us"], cell["n_jobs"], cfg)
    log(f"{cell['cell_id']} {stop_reason} after {elapsed:.0f}s")

    n_target = 0
    if not dry and spod:
        if node_cat_to_file(spod, f"{host_inter_dir(cfg, tb, cell)}/target.csv", outdir / "target.csv"):
            n_target = count_jobs(outdir / "target.csv")
        for nb in nb_meta:
            node_cat_to_file(spod, f"{host_inter_dir(cfg, tb, cell)}/{nb['file']}",
                             outdir / nb["file"])
    log(f"{cell['cell_id']} target collected {n_target} job-rows")

    meta = {
        "variant": "inter", "arm": cell["arm"], "cell_id": cell["cell_id"], "scale": cell["scale"],
        "P_us": cell["period_us"], "matrix_M": cell["matrix_M"],
        "target_U": cell["target_u"], "target_Q_us": cell["target_q_us"], "target_K": cell["target_K"],
        "neighbour_unit_u": cell["neighbour_unit_u"], "neighbour_q_us": cell["neighbour_q_us"],
        "neighbour_K": cell["neighbour_K"], "n_neighbours": cell["n_neighbours"],
        "aggregate_neighbour_u": cell["aggregate_neighbour_u"], "oversubscribe": cell["oversubscribe"],
        "admission": {"neighbours_requested": len(nbs), "neighbours_admitted": admitted,
                      "colocated_with_target": colocated},
        "reservation": {"target_runtime": cell["target_reservation_runtime"],
                        "neighbour_runtime": cell["neighbour_reservation_runtime"],
                        "period": cell["target_reservation_period"], "count": cell["reservation_count"]},
        "placements": {"target": {"file": "target.csv", "obj": target,
                                  "rt_cpuset": tgt_env.get("RT_CPUSET"), "cpu": tgt_cpu},
                       "neighbours": nb_meta},
        "n_jobs": cell["n_jobs"], "warmup": cell["warmup"],
        "stop_reason": stop_reason, "elapsed_s": round(elapsed, 1), "timeblock": tb,
        "node": facts.get("node"), "kernel": facts.get("kernel"),
        "sched_rt_runtime_us": facts.get("sched_rt_runtime_us"),
        "sched_rt_period_us": facts.get("sched_rt_period_us"),
        "cpu_map": facts.get("cpu_map"), "lscpu": facts.get("lscpu"),
    }
    (outdir / cfg["results"]["cell_metadata_json"]).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not dry:
        delete_objects(all_objs)
    return {"cell": cell["cell_id"], "n": n_target, "admitted": admitted,
            "stop_reason": stop_reason}


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Model 2 sweep orchestrator")
    ap.add_argument("--variant", required=True, choices=["intra", "inter"])
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--scales", nargs="*", default=["tight", "soft"], choices=["tight", "soft"])
    ap.add_argument("--only-cell", nargs="*", default=None,
                    help="restrict to these cell_ids")
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = m2.load_config(args.config)
    results_root = Path(args.results_root) if args.results_root else HERE / cfg["results"]["root"]

    # reused-calibration gate
    ktab = m2.load_source_ktable(cfg)
    if not ktab and not args.dry_run:
        log(f"ERROR: reused calibration table missing: {m2.source_table_path(cfg)}")
        log("Build it once in Model 1_1:  python ../model1_1/calibration/calibrate.py")
        return 1

    node = resolve_node(cfg)
    if not node:
        log(f"WARN no node labelled {cfg['node']['node_label']}")
    spod = sampler_pod(node)
    facts = node_facts(spod, node) if not args.dry_run else {"node": node}
    log(f"variant={args.variant} node={node} sampler={spod} kernel={facts.get('kernel')}")

    settle = cfg["execution"]["inter_cell_settle_seconds"]
    attempts = int(cfg["execution"]["placement_max_attempts"])
    summary = []

    for cell in m2.iter_cells(cfg, args.variant, ktab):
        if cell["scale"] not in args.scales:
            continue
        if args.only_cell is not None and cell["cell_id"] not in args.only_cell:
            continue

        if args.variant == "intra":
            outdir = results_root / args.timeblock / "intra" / cell["scale_dir"] / cell["cell_id"]
            outdir.mkdir(parents=True, exist_ok=True)
            res = do_intra(cfg, cell, args.timeblock, outdir, spod, facts, attempts, settle, args.dry_run)
        else:
            outdir = (results_root / args.timeblock / "inter" / cell["scale_dir"]
                      / cell["arm"] / cell["cell_id"])
            outdir.mkdir(parents=True, exist_ok=True)
            res = do_inter(cfg, cell, args.timeblock, outdir, spod, facts, attempts, settle, args.dry_run)

        summary.append(res)
        log(f"{cell['cell_id']} done: {res}")
        if not args.dry_run and settle > 0:
            time.sleep(settle)

    # copy the continuous covariate streams ONCE
    if not args.dry_run and spod:
        dest = results_root / args.timeblock / "samples"
        dest.mkdir(parents=True, exist_ok=True)
        for nm in ("cpu.csv", "tasks.csv", "server.csv"):
            if node_cat_to_file(spod, f"/host/var/lib/model2/samples/{nm}", dest / nm):
                log(f"saved sampler stream {nm}")
            else:
                log(f"WARN sampler stream {nm} unavailable")

    tbdir = results_root / args.timeblock
    tbdir.mkdir(parents=True, exist_ok=True)
    (tbdir / f"summary-{args.variant}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log(f"=== {args.variant.upper()} SWEEP SUMMARY ===")
    for s in summary:
        log(json.dumps(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
