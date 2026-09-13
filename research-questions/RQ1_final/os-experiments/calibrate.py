#!/usr/bin/env python3
"""
calibrate.py <model> -- find K so median C ~= headroom * Q.

Run with frequency pinned (node-prep/apply.sh first). C is CPU-time, linear
in K, so we solve K ~= target / (C/K). Calibration always measures the probe
SOLO (no co-runner/generator present) regardless of model -- see
models/model1/config.yaml's comment for why per-model (really per-NODE)
calibration still matters even so (different physical hosts can genuinely
differ; sharing a K table blindly across nodes risks the same class of bug
as the 2026-08 round3 K-mismatch incident, just introduced deliberately).

    python calibrate.py model1 --local        # native ./workload on an isolated core
    python calibrate.py model1                # exec inside a calib pod on the node

Writes models/<model>/k_table.json  {scale-U: {K, median_C_us, cv}}.
"""
import argparse
import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BIN = HERE / "workload"
CV_THRESHOLD = 0.02
PROBE_JOBS, PROBE_WARMUP = 400, 100


def run(cmd, input_text=None):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, input=input_text)


def median_cv(csv_text):
    C = []
    for line in csv_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("job_index"):
            continue
        p = line.split(",")
        if len(p) >= 5:
            try:
                C.append(float(p[4]))
            except ValueError:
                pass
    if not C:
        return None
    m = statistics.median(C)
    return m, (statistics.pstdev(C) / m if m else float("inf"))


def measure(K, sieve_n, local, rt_cpu, ns, pod):
    args = ["--K", str(K), "--sieve-n", str(sieve_n), "--period-us", "0",
            "--n-jobs", str(PROBE_JOBS), "--warmup", str(PROBE_WARMUP),
            "--priority", "90", "--cpu", str(rt_cpu)]
    if local:
        proc = run([str(BIN), *args])
    else:
        cmd = f"taskset -c {rt_cpu} /usr/local/bin/workload " + " ".join(args)
        proc = run(["kubectl", "exec", "-n", ns, pod, "--", "bash", "-c", cmd])
    res = median_cv(proc.stdout or "")
    if res is None:
        err = (proc.stderr or "").strip()
        print(f"[calib] measure(K={K}) produced no samples"
              + (f" -- probe stderr: {err}" if err else " -- no stderr captured"))
    return res


def solve_K(target, sieve_n, local, rt_cpu, ns, pod):
    K = 1
    res = measure(K, sieve_n, local, rt_cpu, ns, pod)
    if not res:
        raise RuntimeError("no C samples (probe failed?)")
    med, cv = res
    while med < 200.0 and K < 10**8:
        K = max(K * 4, K + 1)
        res = measure(K, sieve_n, local, rt_cpu, ns, pod)
        if not res:
            raise RuntimeError(f"no C samples at K={K} (probe failed? see stderr above)")
        med, cv = res
    for _ in range(8):
        if med > 0 and abs(med - target) <= 0.03 * target:
            break
        Knew = max(1, int(round(target / (med / K))))
        if Knew == K:
            # K=1 (or whatever we're stuck at) doesn't hit target -- e.g. a
            # single sieve pass already costs more than this cell's budget.
            # Not an error: keep it, using the real measured med/cv as-is
            # (deliberate choice -- see models/model1/config.yaml's comment).
            break
        K = Knew
        res = measure(K, sieve_n, local, rt_cpu, ns, pod)
        if not res:
            raise RuntimeError(f"no C samples at K={K} (probe failed? see stderr above)")
        med, cv = res
    return K, med, cv


def ensure_pod(cfg, ns, pod):
    if run(["kubectl", "get", "pod", "-n", ns, pod]).returncode == 0:
        return
    lk, _, lv = cfg["node_label"].partition("=")
    m = f"""apiVersion: v1
kind: Namespace
metadata: {{ name: {ns} }}
---
apiVersion: v1
kind: Pod
metadata: {{ name: {pod}, namespace: {ns} }}
spec:
  restartPolicy: Never
  nodeSelector: {{ {lk}: {lv} }}
  tolerations: [{{ operator: Exists }}]
  containers:
    - name: calib
      image: {cfg['image']}
      command: ["sleep","infinity"]
      securityContext: {{ capabilities: {{ add: ["SYS_NICE","IPC_LOCK"] }} }}
"""
    run(["kubectl", "apply", "-f", "-"], input_text=m)
    run(["kubectl", "wait", "-n", ns, f"pod/{pod}", "--for=condition=Ready", "--timeout=180s"])


def main() -> int:
    ap = argparse.ArgumentParser(description="RQ1_final K calibration (freq-pinned)")
    ap.add_argument("model")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--rt-cpu", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    model_dir = HERE / "workloads" / args.model
    cfg = yaml.safe_load((model_dir / "config.yaml").read_text())
    ns, pod = cfg["namespace"], f"{args.model}-calib"
    if not args.local:
        ensure_pod(cfg, ns, pod)

    tab_path = model_dir / "k_table.json"
    table = json.loads(tab_path.read_text()) if tab_path.exists() else {}
    failed = []
    imprecise = []
    for scale, scale_cfg in cfg["scales"].items():
        P = scale_cfg["period_us"]
        sieve_n = scale_cfg["sieve_n"]
        for u in cfg["utilizations"]:
            key = f"{scale}-U{'%g' % u}"
            if not args.force and table.get(key, {}).get("K"):
                print(f"[calib] {key}: cached K={table[key]['K']}; skip"); continue
            Q = int(round(u * P))
            target = int(round(cfg["headroom_frac"] * Q))
            K, med, cv = solve_K(target, sieve_n, args.local, args.rt_cpu, ns, pod)
            effective_u = med / P   # the utilization this cell ACTUALLY runs at
            off_target = med > 0 and abs(med - target) > 0.03 * target
            table[key] = {"K": K, "median_C_us": round(med, 1), "cv": round(cv, 4),
                          "target_us": target, "Q_us": Q, "scale": scale, "u": u,
                          "sieve_n": sieve_n, "effective_u": round(effective_u, 4),
                          "off_target": off_target,
                          "calibrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            print(f"[calib] {key}: K={K} medC={med:.0f} (target {target}) cv={cv:.4f} "
                  f"[{'OK' if cv <= CV_THRESHOLD else 'HIGH-CV'}]"
                  + (f" -- OFF TARGET: effective U={effective_u:.3f}, not nominal {u}" if off_target else ""))
            if cv > CV_THRESHOLD:
                failed.append(key)
            if off_target:
                imprecise.append(key)
            tab_path.write_text(json.dumps(table, indent=2), encoding="utf-8")
    print(f"[calib] wrote {tab_path}")
    if not args.local:
        run(["kubectl", "delete", "pod", "-n", ns, pod, "--ignore-not-found", "--wait=false"])
    if imprecise:
        print(f"[calib] NOTE off-target (kept deliberately, K=1 floor exceeds/undershoots "
              f"target -- use effective_u from k_table.json, not the nominal label): {imprecise}")
    if failed:
        print(f"[calib] WARNING high CV (freq not pinned / core not isolated?): {failed}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
