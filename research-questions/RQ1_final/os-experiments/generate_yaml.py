#!/usr/bin/env python3
"""
generate_yaml.py <model> -- stamp a model's sweep manifests from its job.yaml
+ k_table.json. Ported from RQ1's generate_yaml.py, retargeted at
workload.c's sieve; model3's co-runner templates (INTERFERER, COMPETITOR_RESERVED)
adapted from matmul-specific flags (--M) to workload.c's (--sieve-n).

    python generate_yaml.py model1
    -> models/model1/generated/<scale>/U<u>.yaml
"""
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MODELS = HERE / "workloads"


def ulabel(u):
    return "%g" % u


def uint(u):
    return int(round(u * 100))


# model3 only: unreserved competitor -- CFS sieve, taskset-pinned to a cpu
# run_job.sh resolves at placement time (the target's spare/sibling cpu).
# @@INTF_CPU@@ is filled in by run_job.sh, same convention as RQ1's own model3.
INTERFERER = """---
apiVersion: v1
kind: Pod
metadata:
  namespace: {ns}
  name: "{name}-intf"
  labels: {{ app: {model}, role: interferer }}
spec:
  restartPolicy: Never
  nodeSelector: {{ {lk}: {lv} }}
  tolerations: [{{ operator: Exists }}]
  containers:
    - name: intf
      image: {image}
      command: ["/bin/bash","-c"]
      args:
        - |
          set -e; mkdir -p /results
          exec taskset -c {cpu} /usr/local/bin/workload --K {k} --sieve-n {sieve_n} --period-us {p} \\
            --n-jobs 100000000 --warmup 200 --priority 0 --cpu {cpu} --seed 20260713 --logfile /results/jobs.csv
      securityContext: {{ capabilities: {{ add: ["SYS_NICE","IPC_LOCK"] }} }}
      volumeMounts: [{{ name: results, mountPath: /results }}]
  volumes:
    - name: results
      hostPath: {{ path: {host}/{sub}/intf, type: DirectoryOrCreate }}
"""

# model3 only: reserved competitor, its own CBS reservation. Carries an
# @@REQUESTED_CPUS@@ placeholder (run_job.sh's place_fixed_competitor
# substitutes it with a deterministically-chosen cpu).
COMPETITOR_RESERVED = """---
apiVersion: rt.resource.example.com/v1alpha1
kind: RtClaimParameters
metadata: {{ namespace: {ns}, name: "{name}-comp-params" }}
spec: {{ count: 1, runtime: {cq}, period: {p}, requestedCpus: [@@REQUESTED_CPUS@@] }}
---
apiVersion: resource.k8s.io/v1alpha2
kind: ResourceClaimTemplate
metadata: {{ namespace: {ns}, name: "{name}-comp-claim" }}
spec:
  spec:
    resourceClassName: rt.example.com
    parametersRef: {{ apiGroup: rt.resource.example.com, kind: RtClaimParameters, name: "{name}-comp-params" }}
---
apiVersion: v1
kind: Pod
metadata:
  namespace: {ns}
  name: "{name}-comp"
  labels: {{ app: {model}, role: competitor }}
spec:
  restartPolicy: Never
  nodeSelector: {{ {lk}: {lv} }}
  tolerations: [{{ operator: Exists }}]
  containers:
    - name: probe
      image: {image}
      command: ["/bin/bash","-c"]
      args:
        - |
          set -e; mkdir -p /results
          if [ -n "$RT_CPUSET" ]; then PIN="taskset -c $RT_CPUSET"; CPU="--cpu env"; else PIN=""; CPU=""; fi
          exec $PIN /usr/local/bin/workload --K {ck} --sieve-n {sieve_n} --period-us {p} \\
            --n-jobs 100000000 --warmup 200 --priority 90 --seed 20260713 $CPU --logfile /results/jobs.csv
      securityContext: {{ capabilities: {{ add: ["SYS_NICE","IPC_LOCK"] }} }}
      resources: {{ claims: [{{ name: rtcpu }}] }}
      volumeMounts: [{{ name: results, mountPath: /results }}]
  resourceClaims:
    - {{ name: rtcpu, source: {{ resourceClaimTemplateName: "{name}-comp-claim" }} }}
  volumes:
    - name: results
      hostPath: {{ path: {host}/{sub}/comp, type: DirectoryOrCreate }}
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: generate_yaml.py <model>"); return 2
    model = sys.argv[1]
    model_dir = MODELS / model
    cfg = yaml.safe_load((model_dir / "config.yaml").read_text(encoding="utf-8"))
    base = (model_dir / "job.yaml").read_text(encoding="utf-8")
    ktab_path = model_dir / "k_table.json"
    ktab = json.loads(ktab_path.read_text(encoding="utf-8")) if ktab_path.exists() else {}
    cr = cfg.get("co_runners") or {}
    lk, _, lv = cfg["node_label"].partition("=")
    ns, image, host = cfg["namespace"], cfg["image"], cfg["host_path"]
    out_root = model_dir / "generated"

    n = 0
    for scale, scale_cfg in cfg["scales"].items():
        P = scale_cfg["period_us"]
        sieve_n = scale_cfg["sieve_n"]
        for u in cfg["utilizations"]:
            key = f"{scale}-U{ulabel(u)}"
            K = (ktab.get(key) or {}).get("K")
            if not K:
                print(f"[gen] {key}: not calibrated; skip"); continue
            Q = int(round(u * P))
            name = f"{model}-{scale}-u{uint(u)}"
            sub = f"{scale}/U{ulabel(u)}"
            doc = (base.replace("@@NAME@@", name).replace("@@RUNTIME@@", str(Q))
                       .replace("@@PERIOD@@", str(P)).replace("@@K@@", str(K))
                       .replace("@@SIEVE_N@@", str(sieve_n)).replace("@@SUB@@", sub))

            # model3 only: both competitor arms pre-generated as SEPARATE
            # files (which one gets instantiated is a run_job.sh-time choice,
            # COMPETITOR_TYPE); neither has a driver-independent cpu at
            # generate time. Both arms share ONE reference intensity
            # (co_runners.competitor.u, default 0.4) rather than scaling with
            # the target's own K -- same isolation-of-variable rationale as
            # RQ1's own model3.
            comp_cfg = cr.get("competitor") or {}
            comp_u = float(comp_cfg.get("u", 0.4)); comp_Q = int(round(comp_u * P))
            comp_key = f"{scale}-U{ulabel(comp_u)}"
            comp_K = (ktab.get(comp_key) or {}).get("K") or K

            intf = cr.get("interferer")
            if intf is not None:
                intf_doc = INTERFERER.format(ns=ns, name=name, model=model, lk=lk, lv=lv,
                                             image=image, cpu="@@INTF_CPU@@", k=comp_K, p=P,
                                             sieve_n=sieve_n, host=host, sub=sub)
                fp_intf = out_root / "_intf" / scale / f"U{ulabel(u)}.yaml"
                fp_intf.parent.mkdir(parents=True, exist_ok=True)
                fp_intf.write_text(intf_doc, encoding="utf-8")
            comp = cr.get("competitor")
            if comp is not None:
                comp_doc = COMPETITOR_RESERVED.format(ns=ns, name=name, model=model, lk=lk, lv=lv,
                                                      image=image, cq=comp_Q, p=P, ck=comp_K,
                                                      sieve_n=sieve_n, host=host, sub=sub)
                fp_comp = out_root / "_comp" / scale / f"U{ulabel(u)}.yaml"
                fp_comp.parent.mkdir(parents=True, exist_ok=True)
                fp_comp.write_text(comp_doc, encoding="utf-8")

            fp = out_root / scale / f"U{ulabel(u)}.yaml"
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(doc, encoding="utf-8")
            n += 1
    print(f"[gen] wrote {n} manifest(s) under {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
