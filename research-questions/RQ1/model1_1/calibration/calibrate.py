#!/usr/bin/env python3
"""
calibrate.py — per-cell K calibration for Model 1_1.

For each (scale, U) cell: find the repetition count K so the MEDIAN per-job
execution time C (CLOCK_THREAD_CPUTIME_ID) ~= target Q = round(U*P), on an
ISOLATED physical core, and record C's coefficient of variation (CV). A clean,
low-CV C is a precondition for delay attribution, so we WARN/FAIL if CV exceeds
config kernel.cv_threshold.

C is LINEAR in K (K reps of the same fixed matmul), so instead of a blind binary
search we solve K ~= Q / (C/K) and refine in 2-3 probes — far fewer pod execs.

Modes:
  (default) cluster: deploy a calibration pod (kernel image, `sleep infinity`) on
            the experiment-model=model1 node, `kubectl exec` matmul with each K,
            read the per-job CSV from stdout. Measures C on the REAL experiment CPU.
  --local : run the native ./matmul binary here (build it with `make -C ../../common/kernel`).

Outputs (paths from config.calibration): k_table.json, cv_report.json, k_curve.csv.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import model1lib as m1  # noqa: E402

NS = "model1-1"
CALIB_POD = "model1-1-calib"


def run(cmd, check=False, input_text=None):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, input=input_text, check=check)


def kubectl(*args, check=False, input_text=None):
    return run(["kubectl", *args], check=check, input_text=input_text)


def log(m):
    print(f"[calibrate] {m}", flush=True)


def resolve_node(cfg) -> str | None:
    label = cfg["node"]["node_label"]
    r = kubectl("get", "nodes", "-l", label, "-o",
                "jsonpath={.items[0].metadata.name}")
    return (r.stdout or "").strip() or None


# --------------------------------------------------------------------------- #
# probe: run matmul with a given K, return (median_C_us, cv, n)
# --------------------------------------------------------------------------- #
def parse_C(csv_text: str):
    C = []
    for line in csv_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("job_index"):
            continue
        parts = line.split(",")
        if len(parts) < 5:
            continue
        try:
            C.append(float(parts[4]))   # C_cputime_us is column index 4
        except ValueError:
            pass
    if not C:
        return None
    med = statistics.median(C)
    cv = (statistics.pstdev(C) / med) if med > 0 else float("inf")
    return med, cv, len(C)


class Runner:
    """Runs matmul either in the calib pod (cluster) or natively (--local)."""

    def __init__(self, cfg, local: bool, rt_cpu: int):
        self.cfg = cfg
        self.local = local
        self.rt_cpu = rt_cpu
        self.bin = str(ROOT.parent / "common" / "kernel" / "matmul")

    def measure(self, M, K, probe_jobs, warmup):
        args = ["--M", str(M), "--K", str(K), "--period-us", "0",
                "--n-jobs", str(probe_jobs), "--warmup", str(warmup),
                "--priority", "90", "--cpu", str(self.rt_cpu)]
        if self.local:
            r = run([self.bin, *args])
            return parse_C(r.stdout or "")
        # cluster: taskset pin + matmul inside the calib pod, capture stdout
        cmd = f"taskset -c {self.rt_cpu} /usr/local/bin/matmul " + " ".join(args)
        r = kubectl("exec", "-n", NS, CALIB_POD, "--", "bash", "-c", cmd)
        return parse_C(r.stdout or "")


def solve_K(runner: Runner, M, Q_us, cfg, curve_rows, cell_id):
    cal = cfg["calibration"]
    tol = float(cal["tolerance_frac"])
    probe = int(cal["probe_jobs"])
    warm = int(cal["warmup_jobs"])
    kmin, kmax = int(cal["k_min"]), int(cal["k_max"])

    # seed: raise K until C is measurable (>= 200 us) to get a stable slope
    K = max(kmin, 1)
    res = runner.measure(M, K, probe, warm)
    if not res:
        raise RuntimeError(f"{cell_id}: no C samples (matmul failed?)")
    med, cv, _ = res
    while med < 200.0 and K < kmax:
        K = min(kmax, max(K * 4, K + 1))
        res = runner.measure(M, K, probe, warm)
        if not res:
            raise RuntimeError(f"{cell_id}: no C samples at K={K}")
        med, cv, _ = res
    curve_rows.append((cell_id, K, med, cv))

    # linear refine: C ~= K * c1  =>  K_target = Q / (C/K)
    for _ in range(8):
        if med > 0 and abs(med - Q_us) <= tol * Q_us:
            break
        c1 = med / K
        Knew = max(kmin, min(kmax, int(round(Q_us / c1))))
        if Knew == K:
            break
        K = Knew
        res = runner.measure(M, K, probe, warm)
        if not res:
            raise RuntimeError(f"{cell_id}: no C samples at K={K}")
        med, cv, _ = res
        curve_rows.append((cell_id, K, med, cv))
    return K, med, cv


def ensure_calib_pod(cfg, node, local):
    if local:
        return
    img = cfg["image"]["full_ref"]
    r = kubectl("get", "pod", "-n", NS, CALIB_POD)
    if r.returncode == 0:
        log("calib pod already running")
        return
    manifest = f"""
apiVersion: v1
kind: Namespace
metadata: {{ name: {NS} }}
---
apiVersion: v1
kind: Pod
metadata: {{ name: {CALIB_POD}, namespace: {NS}, labels: {{ app: model1-1-calib }} }}
spec:
  restartPolicy: Never
  nodeSelector: {{ {cfg['node']['node_label'].split('=')[0]}: "{cfg['node']['node_label'].split('=')[1]}" }}
  tolerations: [{{ operator: Exists }}]
  containers:
    - name: calib
      image: {img}
      imagePullPolicy: {cfg['image']['pull_policy']}
      command: ["sleep", "infinity"]
      securityContext:
        capabilities: {{ add: ["SYS_NICE", "IPC_LOCK"] }}
"""
    log("deploying calib pod")
    kubectl("apply", "-f", "-", input_text=manifest, check=True)
    kubectl("wait", "-n", NS, f"pod/{CALIB_POD}", "--for=condition=Ready",
            "--timeout=180s")


def main() -> int:
    ap = argparse.ArgumentParser(description="Model 1_1 K calibration")
    ap.add_argument("--config", default=None)
    ap.add_argument("--local", action="store_true",
                    help="run native ../../common/kernel/matmul instead of a cluster pod")
    ap.add_argument("--rt-cpu", type=int, default=None,
                    help="isolated CPU to calibrate on (default cpu_assignment.rt_core_logical)")
    ap.add_argument("--force", action="store_true", help="recalibrate even cells already in the table")
    args = ap.parse_args()

    cfg = m1.load_config(args.config)
    rt_cpu = args.rt_cpu if args.rt_cpu is not None else int(cfg["cpu_assignment"]["rt_core_logical"])
    M = int(cfg["kernel"]["matrix_M"])
    cv_thr = float(cfg["kernel"]["cv_threshold"])

    node = None
    if not args.local:
        node = resolve_node(cfg)
        if not node:
            log(f"ERROR: no node labelled {cfg['node']['node_label']}")
            return 1
        ensure_calib_pod(cfg, node, args.local)

    runner = Runner(cfg, args.local, rt_cpu)
    ktab = m1.load_k_table(cfg)
    cv_report = {}
    curve_rows = []
    failed_cv = []

    # cells to calibrate: all grid cells + the canary's cell
    cells = list(m1.iter_cells(cfg, ktab)) + [m1.canary_cell(cfg, ktab)]
    seen = set()
    for c in cells:
        cid = c["cell_id"]
        key = (c["scale"], c["u"])
        if key in seen:
            continue
        seen.add(key)
        if not args.force and cid in ktab and ktab[cid].get("K"):
            log(f"{cid}: already calibrated (K={ktab[cid]['K']}); skip")
            continue
        Q = c["q_us"]
        log(f"{cid}: solving K for Q={Q}us (M={M}) on cpu{rt_cpu} ...")
        K, med, cv = solve_K(runner, M, Q, cfg, curve_rows, cid)
        entry = {"K": K, "median_C_us": round(med, 1), "cv": round(cv, 4),
                 "M": M, "Q_us": Q, "scale": c["scale"], "u": c["u"]}
        ktab[cid] = entry
        cv_report[cid] = {"cv": round(cv, 4), "threshold": cv_thr,
                          "ok": cv <= cv_thr, "median_C_us": round(med, 1), "Q_us": Q}
        flag = "OK" if cv <= cv_thr else "HIGH-CV!!"
        log(f"{cid}: K={K} median_C={med:.0f}us (Q={Q}) cv={cv:.4f} [{flag}]")
        if cv > cv_thr:
            failed_cv.append(cid)

    # write outputs
    m1.k_table_path(cfg).parent.mkdir(parents=True, exist_ok=True)
    m1.k_table_path(cfg).write_text(json.dumps(ktab, indent=2), encoding="utf-8")
    (ROOT / cfg["calibration"]["cv_report_file"]).write_text(
        json.dumps(cv_report, indent=2), encoding="utf-8")
    curve_p = ROOT / cfg["calibration"]["curve_file"]
    with open(curve_p, "w", encoding="utf-8") as fh:
        fh.write("cell_id,K,median_C_us,cv\n")
        for r in curve_rows:
            fh.write(f"{r[0]},{r[1]},{r[2]:.1f},{r[3]:.4f}\n")
    log(f"wrote {m1.k_table_path(cfg)}")
    log(f"wrote {ROOT / cfg['calibration']['cv_report_file']}")
    log(f"wrote {curve_p}")

    if not args.local:
        kubectl("delete", "pod", "-n", NS, CALIB_POD, "--ignore-not-found", "--wait=false")

    if failed_cv:
        log(f"WARNING: {len(failed_cv)} cell(s) exceeded CV threshold {cv_thr}: "
            f"{', '.join(failed_cv)} — clean-C precondition NOT met; investigate "
            f"(sibling activity? not isolated? DVFS?) before trusting delay attribution.")
        return 3
    log("all cells calibrated within CV threshold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
