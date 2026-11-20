#!/usr/bin/env python3
"""Stamp the RQ1_fromdefault workload directories (workloads/dNN-model1, workloads/dNN-model5) and their manifests.

dNN keeps the numbering of RQ1_final's scenarios; here the lever is switched ON from an all-defaults node instead of reverted from full isolation:
  d07 all defaults (reference)   d01 isolcpus   d02 nohz_full   d03 rcu_nocbs   d04 systemd containment   d05 IRQ steering
  d06 boot-params bundle         d08 frequency pinning
Same sources as RQ1_final: job.yaml from the 07 (all defaults) workloads, ONE calibration for everything = K table of the full-isolation runs
(model1 for single-core, model5-phys for multi-core, kubedeadline-experiments/models), same scales / sieve sizes / headroom 0.7.
Run: python3 make_workloads.py && for d in workloads/d*; do python3 generate_yaml.py $(basename $d); done
"""
import json, pathlib, re, shutil
HERE = pathlib.Path(__file__).resolve().parent
RQ1 = HERE.parent / "RQ1_final"
SRC = RQ1 / "os-experiments" / "workloads"
KD = RQ1 / "kubedeadline-experiments" / "models"
UTILS = [0.1, 0.5, 0.7, 0.94]
LEVERS = {"d07": "all defaults (reference)", "d01": "isolcpus", "d02": "nohz_full", "d03": "rcu_nocbs", "d04": "systemd containment",
          "d05": "IRQ steering", "d06": "boot-params bundle", "d08": "frequency pinning"}
PLACE = {"model1": ("07-model1", "model1"), "model5": ("07-model5", "model5-phys")}   # (job.yaml template, K-table source)

for code, name in LEVERS.items():
    for model, (tmpl, ref) in PLACE.items():
        wl = f"{code}-{model}"
        d = HERE / "workloads" / wl
        d.mkdir(parents=True, exist_ok=True)
        job = (SRC / tmpl / "job.yaml").read_text().replace(tmpl, wl)
        (d / "job.yaml").write_text(job)
        shutil.copy(KD / ref / "k_table.json", d / "k_table.json")
        cfg = (SRC / tmpl / "config.yaml").read_text().replace(tmpl, wl)
        cfg = re.sub(r"^utilizations: .*$", f"utilizations: {UTILS}", cfg, flags=re.M)
        cfg = f"# RQ1_fromdefault {wl}: ONLY '{name}' switched on, starting from an all-defaults node (see ../../README.md).\n# K table = full-isolation calibration of RQ1_final ({ref}); U sweep = the four utilizations used in the analysis.\n" + cfg
        (d / "config.yaml").write_text(cfg)
print("wrote", len(LEVERS) * len(PLACE), "workload dirs")
