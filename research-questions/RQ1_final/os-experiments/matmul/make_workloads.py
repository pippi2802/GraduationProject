#!/usr/bin/env python3
"""Stamp the matmul workload directories from the sieve ones of os-experiments, with the SAME names and structure:
  workloads/model1, model5-phys, 01-model1 .. 08-model1, 01-model5 .. 08-model5
(the pinned/other variants are not copied). Only these things change relative to ../workloads/<name>:
  * namespace, node label, host path get an "mm-" prefix (so nothing collides with the sieve runs on the nodes); pod label `app: <model>` unchanged
  * image: the matmul image (build.sh); `--sieve-n @@SIEVE_N@@` -> `--matrix-n @@MATRIX_N@@`; scales use matrix_n (soft N=256, tight N=64)
  * multi-core claim: requestedCpus [1,3] -> [1,2] (cores 1 and 2 only; single-core stays on cpu 2)
  * utilizations: [0.1, 0.5, 0.7, 0.94]; no k_table.json (calibrate with calibrate.py, then use_full_isolation_k.sh)
MM_N_SOFT (default 256) / MM_N_TIGHT (default 64): matrix dimensions per scale, see README.
Run: python3 make_workloads.py
"""
import os, pathlib, re

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / "workloads"
IMAGE = os.environ.get("IMG", "pippina2/rq1final-matmul:v1")
N_SOFT, N_TIGHT = int(os.environ.get("MM_N_SOFT", 256)), int(os.environ.get("MM_N_TIGHT", 64))
NAMES = ["model1", "model5-phys"] + [f"{c:02d}-model{p}" for c in range(1, 9) for p in (1, 5)]

n = 0
for name in sorted(NAMES):
    cfg = (SRC / name / "config.yaml").read_text()
    job = (SRC / name / "job.yaml").read_text()
    ns = re.search(r"^namespace: (\S+)", cfg, re.M).group(1)
    host = re.search(r"^host_path: /var/lib/rq1final/(\S+)", cfg, re.M).group(1)

    cfg = re.sub(r"^namespace: \S+", f"namespace: mm-{ns}", cfg, flags=re.M)
    cfg = re.sub(r"^node_label: experiment-model=\S+", f"node_label: experiment-model=mm-{ns}", cfg, flags=re.M)
    cfg = re.sub(r"^host_path: \S+", f"host_path: /var/lib/rq1final/mm-{host}", cfg, flags=re.M)
    cfg = re.sub(r"^image: \S+", f"image: {IMAGE}", cfg, flags=re.M)
    cfg = re.sub(r"^utilizations: .*$", "utilizations: [0.1, 0.5, 0.7, 0.94]", cfg, flags=re.M)
    cfg = re.sub(r"^  soft: \{.*\}$", f"  soft: {{ period_us: 100000, matrix_n: {N_SOFT} }}", cfg, flags=re.M)
    cfg = re.sub(r"^  tight: \{.*\}$", f"  tight: {{ period_us: 10000, matrix_n: {N_TIGHT} }}", cfg, flags=re.M)
    cfg = cfg.replace("requested_cpus: [1, 3]", "requested_cpus: [1, 2]")
    cfg = f"# MATMUL copy of ../../workloads/{name} (make_workloads.py): same structure, matrix kernel, namespace/label/host path prefixed mm-, cores 1 and 2.\n" + cfg

    job = job.replace(f"namespace: {ns}", f"namespace: mm-{ns}").replace(f"experiment-model: {ns} ", f"experiment-model: mm-{ns} ")
    job = job.replace(f"/var/lib/rq1final/{host}/", f"/var/lib/rq1final/mm-{host}/")
    job = job.replace("image: pippina2/rq1final-probe:v1", f"image: {IMAGE}")
    job = job.replace("--sieve-n @@SIEVE_N@@", "--matrix-n @@MATRIX_N@@").replace("@@SIEVE_N@@", "@@MATRIX_N@@")
    job = job.replace("requestedCpus: [1,3]", "requestedCpus: [1,2]")
    assert "sieve" not in job.lower().split("---", 1)[1], name

    d = HERE / "workloads" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(cfg)
    (d / "job.yaml").write_text(job)
    n += 1
print(f"wrote {n} workload dirs (soft N={N_SOFT}, tight N={N_TIGHT}); K tables: python3 calibrate.py model1 --rt-cpu 2 ; python3 calibrate.py model5-phys --rt-cpu 2 ; ./use_full_isolation_k.sh")
