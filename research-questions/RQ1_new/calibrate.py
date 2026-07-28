#!/usr/bin/env python3
"""
calibrate.py <model> — find K per (scale, U) so median C ≈ headroom * Q.

RUN WITH THE FREQUENCY PINNED (node-prep/apply.sh <model> first). C is CPU-time, so
it depends on clock speed; calibrating at the pinned base clock the sweep uses is
what makes C reproducible. C is linear in K, so we solve K ≈ target/(C/K).

    python calibrate.py model1 --local        # native ./matmul on an isolated core
    python calibrate.py model1                 # exec inside a calib pod on the node

Writes models/<model>/k_table.json  {scale-U: {K, median_C_us, cv}}. Calibrates
every U in the grid (0.1 covers neighbours too).
"""
import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BIN = HERE / "matmul"
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


def measure(cfg, K, local, rt_cpu, ns, pod):
    args = ["--M", str(cfg["matrix_M"]), "--K", str(K), "--period-us", "0",
            "--n-jobs", str(PROBE_JOBS), "--warmup", str(PROBE_WARMUP),
            "--priority", "90", "--cpu", str(rt_cpu)]
    if local:
        return median_cv(run([str(BIN), *args]).stdout or "")
    cmd = f"taskset -c {rt_cpu} /usr/local/bin/matmul " + " ".join(args)
    return median_cv(run(["kubectl", "exec", "-n", ns, pod, "--", "bash", "-c", cmd]).stdout or "")


def solve_K(cfg, target, local, rt_cpu, ns, pod):
    K = 1
    res = measure(cfg, K, local, rt_cpu, ns, pod)
    if not res:
        raise RuntimeError("no C samples (probe failed?)")
    med, cv = res
    while med < 200.0 and K < 10**8:
        K = max(K * 4, K + 1); med, cv = measure(cfg, K, local, rt_cpu, ns, pod)
    for _ in range(8):
        if med > 0 and abs(med - target) <= 0.03 * target:
            break
        Knew = max(1, int(round(target / (med / K))))
        if Knew == K:
            break
        K = Knew; med, cv = measure(cfg, K, local, rt_cpu, ns, pod)
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
    ap = argparse.ArgumentParser(description="RQ1 K calibration (freq-pinned)")
    ap.add_argument("model")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--rt-cpu", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((HERE / "models" / args.model / "config.yaml").read_text())
    ns, pod = cfg["namespace"], f"{cfg['model']}-calib"
    if not args.local:
        ensure_pod(cfg, ns, pod)

    tab_path = HERE / "models" / args.model / "k_table.json"
    table = json.loads(tab_path.read_text()) if tab_path.exists() else {}
    failed = []
    for scale, P in cfg["scales"].items():
        for u in cfg["utilizations"]:
            key = f"{scale}-U{'%g' % u}"
            if not args.force and table.get(key, {}).get("K"):
                print(f"[calib] {key}: cached K={table[key]['K']}; skip"); continue
            Q = int(round(u * P))
            target = int(round(cfg["headroom_frac"] * Q))
            K, med, cv = solve_K(cfg, target, args.local, args.rt_cpu, ns, pod)
            table[key] = {"K": K, "median_C_us": round(med, 1), "cv": round(cv, 4),
                          "target_us": target, "Q_us": Q, "scale": scale, "u": u}
            print(f"[calib] {key}: K={K} medC={med:.0f} (target {target}) cv={cv:.4f} "
                  f"[{'OK' if cv <= CV_THRESHOLD else 'HIGH-CV'}]")
            if cv > CV_THRESHOLD:
                failed.append(key)
    tab_path.write_text(json.dumps(table, indent=2), encoding="utf-8")
    print(f"[calib] wrote {tab_path}")
    if not args.local:
        run(["kubectl", "delete", "pod", "-n", ns, pod, "--ignore-not-found", "--wait=false"])
    if failed:
        print(f"[calib] WARNING high CV (freq not pinned / core not isolated?): {failed}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
