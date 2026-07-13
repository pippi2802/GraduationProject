#!/usr/bin/env python3
"""
Model 4 orchestrator (acquisition only) — IRQ steering.

  run_model4.py --arm {off,on} [--irq-load LEVEL] --timeblock LABEL

For a --timeblock, sweep the arm's (scale, U) grid SEQUENTIALLY (delete + recreate
between cells). Per arm:
  (optionally) start the IRQ source at --irq-load  ->  for each cell: apply RT ->
  retry until Ready (record RT_CPUSET) -> pick the OTHER physical core's cpu ->
  STEER device IRQs onto (on) / away from (off) the RT core via the irq-control pod
  -> [preflight] verify the RT core's IRQ rate actually moved (else STOP/ASK) ->
  WAIT for the RT pod to Complete -> copy jobs.csv (+ per-cell IRQ snapshot + cell.json)
  via the sampler pod's host mount -> delete. At the very end: RESTORE IRQ affinity +
  irqbalance, and delete the IRQ source.

The SAME reused-K reservation is used for BOTH arms, so the R-tail difference is a
pure IRQ effect. NO calibration runs here: K + C_baseline are REUSED from
../model1_1 (IRQ is a delay effect; C stays flat).

Prereqs: node labelled experiment-model=model4; node-prep + sampler + irq-control
DaemonSets applied; the ../common kernel image pushed AND
../model1_1/calibration/k_table.json present.
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
import model4lib as m4  # noqa: E402
sys.path.insert(0, str(HERE / "manifests" / "template"))
import render as _render  # noqa: E402

NS = "model4"


def run(cmd, check=False, input_text=None, timeout=None):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, input=input_text, check=check, timeout=timeout)


def kubectl(*args, check=False, input_text=None, timeout=None):
    return run(["kubectl", *args], check=check, input_text=input_text, timeout=timeout)


def log(m):
    print(f"[model4] {m}", flush=True)


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


def pod_by_label(label, node=None):
    r = kubectl("get", "pods", "-n", NS, "-l", label,
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


def node_internal_ip(node):
    """The node's InternalIP (the hostNetwork IRQ-source server binds to)."""
    if not node:
        return None
    r = kubectl("get", "node", node, "-o",
                "jsonpath={.status.addresses[?(@.type=='InternalIP')].address}")
    out = (r.stdout or "").strip()
    return out.split()[0] if out else None


def wait_ready(name, timeout_s=120):
    r = kubectl("wait", "-n", NS, f"pod/{name}", "--for=condition=Ready", f"--timeout={timeout_s}s")
    return r.returncode == 0


def node_cat_to_file(spod, path, dest):
    with open(dest, "wb") as fh:
        p = subprocess.run(["kubectl", "exec", "-n", NS, spod, "--", "cat", path],
                           stdout=fh, stderr=subprocess.DEVNULL)
    return p.returncode == 0


def node_exec(pod, *cmd, timeout=60):
    r = kubectl("exec", "-n", NS, pod, "--", *cmd, timeout=timeout)
    return r.stdout or ""


def count_jobs(path):
    if not Path(path).exists():
        return 0
    with open(path) as fh:
        return sum(1 for ln in fh if ln[:1].isdigit())


# --------- IRQ helpers (via the irq-control pod) ---------------------------- #
def other_core_cpu(cpu_map, rt_cpu):
    """A logical cpu on the OTHER physical core (different core-leader)."""
    if not cpu_map or rt_cpu is None:
        return None
    core_of = cpu_map.get("core_of") or {}
    rt_leader = core_of.get(str(rt_cpu))
    for cpu_s, leader in sorted(core_of.items(), key=lambda kv: int(kv[0])):
        if leader != rt_leader:
            return int(cpu_s)
    # fallback: any core leader != rt's
    for core in cpu_map.get("cores", []):
        if core.get("leader") != rt_leader:
            return int(core["leader"])
    return None


def irq_rate_on_cpu(ipod, cpu, seconds):
    """Interrupts/sec delivered to `cpu` over `seconds` (delta of that cpu's column
    of /proc/interrupts, summed across numbered IRQ lines)."""
    col = int(cpu) + 2   # /proc/interrupts: col 1 is the IRQ id, cpu0 is col 2
    awk = "awk 'NR>1 && $1 ~ /^[0-9]+:/ {s+=$%d} END{print s+0}' /proc/interrupts" % col
    script = f"a=$({awk}); sleep {seconds}; b=$({awk}); echo $(( (b-a)/{max(1, seconds)} ))"
    out = node_exec(ipod, "bash", "-c", script, timeout=seconds + 20).strip()
    try:
        return int(out.split()[-1])
    except (ValueError, IndexError):
        return None


def irq_snapshot(ipod, cpu):
    """Top interrupt lines on `cpu` by count (dominant-source identification)."""
    col = int(cpu) + 2
    awk = ("awk 'NR>1 && $1 ~ /^[0-9]+:/ {d=\"\"; for(i=NF-2;i<=NF;i++) d=d\" \"$i; "
           "print $1, $%d, d}'" % col)
    script = f"{awk} /proc/interrupts | sort -k2 -nr | head -n 12"
    return node_exec(ipod, "bash", "-c", script, timeout=30).strip()


def steer(ipod, arm, rt_cpu, other_cpu, steerable_regex):
    r = kubectl("exec", "-n", NS, ipod, "--", "env",
                f"ARM={arm}", f"RT_CPU={rt_cpu}", f"OTHER_CPU={other_cpu}",
                f"STEERABLE_REGEX={steerable_regex}", "bash", "/tmp/steer.sh", timeout=60)
    txt = (r.stdout or "") + (r.stderr or "")
    m = node_exec(ipod, "cat", "/host/var/lib/model4/irq-map.json")
    try:
        return json.loads(m) if m.strip() else None, txt
    except json.JSONDecodeError:
        return None, txt


def restore_irq(ipod):
    kubectl("exec", "-n", NS, ipod, "--", "bash", "/tmp/restore.sh", timeout=60)


# --------------------------------------------------------------------------- #
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
        sr["max_duration_seconds"], 120 + sr["max_wall_seconds_factor"] * n_jobs * period_s)
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


def node_facts(spod, ipod, node, cfg):
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
        cm = node_exec(spod, "cat", "/host/var/lib/model4/cpu-map.json")
        try:
            facts["cpu_map"] = json.loads(cm) if cm.strip() else None
        except json.JSONDecodeError:
            facts["cpu_map"] = None
    return facts


def host_cell_dir(cfg, tb, cell):
    base = cfg["storage"]["host_path"]
    return f"/host{base}/{tb}/{cell['arm_dir']}/{cell['scale_dir']}/U{m4.u_label(cell['u'])}"


# --------------------------------------------------------------------------- #
def start_irq_source(cfg, irq_load, node, dry):
    """Apply the iperf3 UDP generator (server + client) at --irq-load. The client
    targets the node's InternalIP, which the hostNetwork server binds — so both pods
    can be applied in ONE shot (no deploy-then-read-IP dance)."""
    spec = m4.irq_source_spec(cfg, irq_load)
    if not spec["enabled"] or dry:
        return None
    names = _render.irq_source_names(irq_load)
    sip = node_internal_ip(node) or "127.0.0.1"
    kubectl("apply", "-f", "-", input_text=_render.render_irq_source(cfg, irq_load, sip))
    wait_ready(names["server"], 120)
    wait_ready(names["client"], 60)
    log(f"IRQ source started (load={irq_load} server_ip={sip})")
    return {"names": names, "server_ip": sip, "spec": spec}


# --------------------------------------------------------------------------- #
def do_cell(cfg, cell, tb, outdir, spod, ipod, facts, attempts, settle, dry,
            max_cell_seconds, steerable_regex, force_lowirq, min_delta):
    rt_name = cell["rt_name"]
    log(f"=== {cell['arm'].upper()} {cell['cell_id']} P={cell['period_us']}us U={cell['u']} "
        f"Q={cell['q_us']} K={cell['K']} C_baseline={cell['c_baseline_us']} ===")

    rt_env, placed = {}, dry
    if dry:
        log("DRY-RUN RT render:\n" + _render.render_rt_cell(cfg, cell, tb)[:400])
    else:
        for att in range(1, attempts + 1):
            delete_objects([rt_name]); time.sleep(settle)
            kubectl("apply", "-f", "-", input_text=_render.render_rt_cell(cfg, cell, tb))
            if not wait_ready(rt_name, 120):
                log(f"{rt_name}: attempt {att}/{attempts} not Ready; retry"); continue
            rt_env = pod_rt_env(rt_name)
            if not parse_cpuset(rt_env.get("RT_CPUSET", "")):
                log(f"{rt_name}: attempt {att}/{attempts} no RT_CPUSET; retry"); continue
            log(f"{cell['cell_id']} RT_CPUSET={rt_env.get('RT_CPUSET')}")
            placed = True; break
    if not placed:
        delete_objects([rt_name])
        return {"cell": cell["cell_id"], "arm": cell["arm"], "stop_reason": "no_placement"}, True

    rt_cpu = first_cpu(rt_env.get("RT_CPUSET", ""))
    other_cpu = other_core_cpu(facts.get("cpu_map"), rt_cpu)
    irq_map, steer_txt, preflight = None, "", {}
    if not dry and ipod is not None and other_cpu is not None:
        # baseline IRQ rate on the RT core BEFORE steering (for the preflight delta)
        base_rate = irq_rate_on_cpu(ipod, rt_cpu, cfg["irq_control"].get("preflight_seconds", 3))
        irq_map, steer_txt = steer(ipod, cell["arm"], rt_cpu, other_cpu, steerable_regex)
        time.sleep(cfg["execution"].get("irq_settle_seconds", 3))
        after_rate = irq_rate_on_cpu(ipod, rt_cpu, cfg["irq_control"].get("preflight_seconds", 3))
        delta = (after_rate - base_rate) if (base_rate is not None and after_rate is not None) else None
        preflight = {"rt_cpu": rt_cpu, "other_cpu": other_cpu, "irq_rate_before": base_rate,
                     "irq_rate_after": after_rate, "irq_rate_delta_per_s": delta,
                     "steered_count": (irq_map or {}).get("steered_count")}
        log(f"{cell['cell_id']} IRQ preflight: rt_cpu={rt_cpu} before={base_rate}/s after={after_rate}/s "
            f"delta={delta}/s steered={(irq_map or {}).get('steered_count')}")
        if cell["arm"] == "on" and (delta is None or delta < min_delta):
            if not force_lowirq:
                log("!! STOP: the `on` arm did NOT raise the RT core's IRQ rate by "
                    f">= {min_delta}/s (delta={delta}). In an Azure guest few lines are "
                    "steerable. Options: enable/raise the IRQ source (--irq-load heavy), or "
                    "re-run with --force-lowirq to proceed anyway (records a possible null).")
                delete_objects([rt_name])
                return {"cell": cell["cell_id"], "arm": cell["arm"],
                        "stop_reason": "irq_preflight_null", "preflight": preflight}, False
            log("WARN proceeding despite low IRQ delta (--force-lowirq).")

    irq_before = irq_snapshot(ipod, rt_cpu) if (not dry and ipod and rt_cpu is not None) else None
    stop_reason, elapsed = ("dry-run", 0.0) if dry else wait_completed(
        rt_name, cell["period_us"], cell["n_jobs"], cfg, max_cell_seconds)
    irq_after = irq_snapshot(ipod, rt_cpu) if (not dry and ipod and rt_cpu is not None) else None
    log(f"{cell['cell_id']} {stop_reason} after {elapsed:.0f}s")

    n = 0
    if not dry and spod:
        if node_cat_to_file(spod, f"{host_cell_dir(cfg, tb, cell)}/jobs.csv", outdir / "jobs.csv"):
            n = count_jobs(outdir / "jobs.csv")
    log(f"{cell['cell_id']} collected {n} job-rows")

    meta = {
        "arm": cell["arm"], "cell_id": cell["cell_id"], "scale": cell["scale"],
        "P_us": cell["period_us"], "U": cell["u"], "Q_us": cell["q_us"], "m": cell["m"],
        "K": cell["K"], "matrix_M": cell["matrix_M"], "c_baseline_us": cell["c_baseline_us"],
        "reservation": {"runtime": cell["reservation_runtime"],
                        "period": cell["reservation_period"], "count": cell["reservation_count"]},
        # placements block matches common.rtmetrics.covariates.join_percell (single
        # reservation -> jobs.csv on the RT cpu -> per-job irq_us attribution).
        "placements": {"rt_cpuset": rt_env.get("RT_CPUSET"), "rt_cpu": rt_cpu,
                       "target": {"file": "jobs.csv", "obj": rt_name,
                                  "rt_cpuset": rt_env.get("RT_CPUSET"), "cpu": rt_cpu}},
        "rt_cpuset": rt_env.get("RT_CPUSET"), "cpu_used": rt_cpu, "other_cpu": other_cpu,
        "irq_map": irq_map, "irq_preflight": preflight,
        "irq_top_lines_before": irq_before, "irq_top_lines_after": irq_after,
        "n_jobs": cell["n_jobs"], "warmup": cell["warmup"],
        "stop_reason": stop_reason, "elapsed_s": round(elapsed, 1), "timeblock": tb,
        "node": facts.get("node"), "kernel": facts.get("kernel"),
        "sched_rt_runtime_us": facts.get("sched_rt_runtime_us"),
        "sched_rt_period_us": facts.get("sched_rt_period_us"),
        "cpu_map": facts.get("cpu_map"), "lscpu": facts.get("lscpu"),
    }
    (outdir / cfg["results"]["cell_metadata_json"]).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not dry:
        delete_objects([rt_name])
    return {"cell": cell["cell_id"], "arm": cell["arm"], "n": n, "rt_cpu": rt_cpu,
            "other_cpu": other_cpu, "steered": (irq_map or {}).get("steered_count"),
            "stop_reason": stop_reason}, True


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Model 4 sweep orchestrator (IRQ steering)")
    ap.add_argument("--arm", required=True, choices=["off", "on"])
    ap.add_argument("--irq-load", default=None, choices=["off", "light", "medium", "heavy"],
                    help="IRQ-source intensity (default from config)")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--scales", nargs="*", default=["tight", "soft"], choices=["tight", "soft"])
    ap.add_argument("--only-u", nargs="*", type=float, default=None)
    ap.add_argument("--n-jobs", type=int, default=None, help="override N_jobs (deepen tail cells)")
    ap.add_argument("--max-cell-seconds", type=float, default=None)
    ap.add_argument("--force-lowirq", action="store_true",
                    help="proceed even if the on-arm IRQ preflight shows no effect")
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = m4.load_config(args.config)
    if args.n_jobs:
        cfg["stopping_rule"]["n_jobs"] = args.n_jobs
    results_root = Path(args.results_root) if args.results_root else HERE / cfg["results"]["root"]

    ktab = m4.load_source_ktable(cfg)
    if not ktab and not args.dry_run:
        log(f"ERROR: reused calibration table missing: {m4.source_table_path(cfg)}")
        log("Build it once in Model 1_1:  python ../model1_1/calibration/calibrate.py")
        return 1

    irq_load = args.irq_load or cfg["irq_source"].get("default_irq_load", "medium")
    node = resolve_node(cfg)
    if not node:
        log(f"WARN no node labelled {cfg['node']['node_label']}")
    spod = pod_by_label("app=model4-sampler", node)
    ipod = pod_by_label("app=model4-irq-control", node)
    facts = node_facts(spod, ipod, node, cfg) if not args.dry_run else {"node": node, "cpu_map": None}
    log(f"arm={args.arm} irq_load={irq_load} node={node} sampler={spod} irq_control={ipod} "
        f"kernel={facts.get('kernel')}")
    if ipod is None and not args.dry_run:
        log("WARN irq-control pod not found; steering disabled (apply irq-control/apply.sh)")

    steerable_regex = "|".join(cfg["irq_control"]["steerable_patterns"])
    min_delta = int(cfg["irq_control"].get("min_effective_irq_delta_per_s", 200))
    settle = cfg["execution"]["inter_cell_settle_seconds"]
    attempts = int(cfg["execution"]["placement_max_attempts"])

    src = start_irq_source(cfg, irq_load, node, args.dry_run)
    summary = []
    try:
        for cell in m4.iter_cells(cfg, args.arm, ktab):
            if cell["scale"] not in args.scales:
                continue
            if args.only_u is not None and cell["u"] not in args.only_u:
                continue
            outdir = (results_root / args.timeblock / cell["arm_dir"] / cell["scale_dir"]
                      / f"U{m4.u_label(cell['u'])}")
            outdir.mkdir(parents=True, exist_ok=True)
            res, cont = do_cell(cfg, cell, args.timeblock, outdir, spod, ipod, facts, attempts,
                                settle, args.dry_run, args.max_cell_seconds, steerable_regex,
                                args.force_lowirq, min_delta)
            summary.append(res)
            log(f"{cell['cell_id']} done: {res}")
            if not cont:
                log("aborting sweep on preflight null (use --force-lowirq or raise --irq-load)")
                break
            if not args.dry_run and settle > 0:
                time.sleep(settle)
    finally:
        # ALWAYS restore IRQ affinity + irqbalance and tear down the IRQ source
        if not args.dry_run and ipod is not None:
            log("restoring IRQ affinity + irqbalance")
            restore_irq(ipod)
        if src is not None:
            delete_objects([src["names"]["client"], src["names"]["server"]], include_claims=False)

    if not args.dry_run and spod:
        dest = results_root / args.timeblock / "samples"
        dest.mkdir(parents=True, exist_ok=True)
        for nm in ("cpu.csv", "tasks.csv", "server.csv"):
            if node_cat_to_file(spod, f"/host/var/lib/model4/samples/{nm}", dest / nm):
                log(f"saved sampler stream {nm}")
            else:
                log(f"WARN sampler stream {nm} unavailable")

    tbdir = results_root / args.timeblock
    tbdir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.arm}-{irq_load}"
    (tbdir / f"summary-{tag}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log(f"=== {args.arm.upper()} SWEEP SUMMARY (irq_load={irq_load}) ===")
    for s in summary:
        log(json.dumps(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
