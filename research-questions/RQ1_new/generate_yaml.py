#!/usr/bin/env python3
"""
generate_yaml.py <model> — stamp the sweep manifests from a readable base.

Like kuberay's generate_yaml.py: load the base manifest (models/<model>/job.yaml),
substitute the per-cell values, write one file per cell. Here the base is a token
template (@@NAME@@ @@RUNTIME@@=Q @@PERIOD@@=P @@K@@ @@SUB@@) and the K comes from
models/<model>/k_table.json (calibrate.py). Co-runners declared in config.yaml
(neighbours / interferer) are appended.

    python generate_yaml.py model2
    -> models/model2/generated/<scale>/U<u>.yaml   (kubectl create -f these; run_job.sh does it)
"""
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MODELS = HERE / "models"


def ulabel(u):
    return "%g" % u


def uint(u):
    return int(round(u * 100))


NEIGHBOUR = """---
apiVersion: rt.resource.example.com/v1alpha1
kind: RtClaimParameters
metadata: {{ namespace: {ns}, name: "{name}-nb{i}-params" }}
spec: {{ count: 1, runtime: {nbq}, period: {p} }}
---
apiVersion: resource.k8s.io/v1alpha2
kind: ResourceClaimTemplate
metadata: {{ namespace: {ns}, name: "{name}-nb{i}-claim" }}
spec:
  spec:
    resourceClassName: rt.example.com
    parametersRef: {{ apiGroup: rt.resource.example.com, kind: RtClaimParameters, name: "{name}-nb{i}-params" }}
---
apiVersion: v1
kind: Pod
metadata:
  namespace: {ns}
  name: "{name}-nb{i}"
  labels: {{ app: {model}, role: neighbour }}
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
          # runs until the cell is torn down (after the TARGET completes), so it
          # contends for the target's WHOLE run instead of finishing early.
          exec $PIN /usr/local/bin/matmul --M 48 --K {nbk} --period-us {p} \\
            --n-jobs 100000000 --warmup 200 --priority 90 --seed 20260713 $CPU --logfile /results/jobs.csv
      securityContext: {{ capabilities: {{ add: ["SYS_NICE","IPC_LOCK"] }} }}
      resources: {{ claims: [{{ name: rtcpu }}] }}
      volumeMounts: [{{ name: results, mountPath: /results }}]
  resourceClaims:
    - {{ name: rtcpu, source: {{ resourceClaimTemplateName: "{name}-nb{i}-claim" }} }}
  volumes:
    - name: results
      hostPath: {{ path: {host}/{sub}/nb{i}, type: DirectoryOrCreate }}
"""

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
          # UNRESERVED (CFS) matmul pinned to the SMT sibling; priority 0.
          exec taskset -c {cpu} /usr/local/bin/matmul --M 48 --K {k} --period-us {p} \\
            --n-jobs 6000 --warmup 200 --priority 0 --cpu {cpu} --seed 20260713 --logfile /results/jobs.csv
      volumeMounts: [{{ name: results, mountPath: /results }}]
  volumes:
    - name: results
      hostPath: {{ path: {host}/{sub}/intf, type: DirectoryOrCreate }}
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: generate_yaml.py <model>"); return 2
    model = sys.argv[1]
    cfg = yaml.safe_load((MODELS / model / "config.yaml").read_text(encoding="utf-8"))
    base = (MODELS / model / "job.yaml").read_text(encoding="utf-8")
    ktab_path = MODELS / model / "k_table.json"
    ktab = json.loads(ktab_path.read_text(encoding="utf-8")) if ktab_path.exists() else {}
    cr = cfg.get("co_runners") or {}
    lk, _, lv = cfg["node_label"].partition("=")
    ns, image, host = cfg["namespace"], cfg["image"], cfg["host_path"]
    out_root = MODELS / model / "generated"

    n = 0
    for scale, P in cfg["scales"].items():
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
                       .replace("@@SUB@@", sub))

            nb = cr.get("neighbours")
            if nb:
                nb_u = float(nb.get("u", 0.1)); nb_Q = int(round(nb_u * P))
                nb_K = (ktab.get(f"{scale}-U{ulabel(nb_u)}") or {}).get("K") or K
                for i in range(int(nb.get("count", 0))):
                    doc += NEIGHBOUR.format(ns=ns, name=name, i=i, nbq=nb_Q, p=P, nbk=nb_K,
                                            model=model, lk=lk, lv=lv, image=image,
                                            host=host, sub=sub)
            intf = cr.get("interferer")
            if intf:
                doc += INTERFERER.format(ns=ns, name=name, model=model, lk=lk, lv=lv,
                                         image=image, cpu=intf.get("cpu", "1"), k=K, p=P,
                                         host=host, sub=sub)

            fp = out_root / scale / f"U{ulabel(u)}.yaml"
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(doc, encoding="utf-8")
            n += 1
    print(f"[gen] wrote {n} manifest(s) under {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
