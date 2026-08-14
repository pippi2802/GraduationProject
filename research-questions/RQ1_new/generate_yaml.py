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
import os
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
spec: {{ count: 1, runtime: {nbq}, period: {p}, requestedCpus: [@@REQUESTED_CPUS@@] }}
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
          # UNRESERVED (CFS) matmul pinned to whatever cpu run_job.sh resolves at
          # placement time (the target's spare/sibling cpu); priority 0. Runs
          # until the cell is torn down (same rationale as model2's neighbour
          # and the reserved competitor) -- it's created ONCE per scale and
          # must persist across every cell in it, not just one.
          exec taskset -c {cpu} /usr/local/bin/matmul --M 48 --K {k} --period-us {p} \\
            --n-jobs 100000000 --warmup 200 --priority 0 --cpu {cpu} --seed 20260713 --logfile /results/jobs.csv
      securityContext: {{ capabilities: {{ add: ["SYS_NICE","IPC_LOCK"] }} }}
      volumeMounts: [{{ name: results, mountPath: /results }}]
  volumes:
    - name: results
      hostPath: {{ path: {host}/{sub}/intf, type: DirectoryOrCreate }}
"""

# Reserved competitor (model3, COMPETITOR_TYPE=reserved): its own CBS reservation
# at co_runners.competitor.u, generated as a SEPARATE file (like INTERFERER) since
# it must only be instantiated for the reserved arm. Like the target and
# NEIGHBOUR, it carries an @@REQUESTED_CPUS@@ placeholder (2026-08-14) --
# run_job.sh's place_fixed_competitor substitutes it with a deterministically
# chosen cpu (avoiding KEEP_CPU, with a valid PAIR_TYPE-relative pair partner)
# before creating it, via the dra-rt-driver's RequestedCpus support, instead
# of the old worst-fit + delete/recreate-until-landed retry.
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
          # reserved competitor: runs until the cell is torn down, contending for
          # the target's whole run (same rationale as model2's neighbour).
          exec $PIN /usr/local/bin/matmul --M 48 --K {ck} --period-us {p} \\
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
    cfg = yaml.safe_load((MODELS / model / "config.yaml").read_text(encoding="utf-8"))
    base = (MODELS / model / "job.yaml").read_text(encoding="utf-8")
    # workload selection: WORKLOAD env overrides config; separate k_table per kind.
    workload = (os.environ.get("WORKLOAD") or cfg.get("workload") or "matmul").strip()
    buf_kb = int(os.environ.get("BUF_KB") or cfg.get("buf_kb") or 131072)
    tab_name = "k_table.json" if workload == "matmul" else f"k_table.{workload}.json"
    ktab_path = MODELS / model / tab_name
    ktab = json.loads(ktab_path.read_text(encoding="utf-8")) if ktab_path.exists() else {}
    cr = cfg.get("co_runners") or {}
    lk, _, lv = cfg["node_label"].partition("=")
    ns, image, host = cfg["namespace"], cfg["image"], cfg["host_path"]
    # separate output tree per workload -- generate_yaml.py used to always
    # write to models/<model>/generated/ regardless of WORKLOAD, so switching
    # a model between matmul and ptrchase silently clobbered whichever set of
    # manifests wasn't just regenerated (found 2026-08-06: a matmul rerun
    # overwrote ptrchase's manifests mid-investigation, and vice versa).
    out_root = MODELS / model / ("generated" if workload == "matmul" else f"generated_{workload}")

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

            # model2: the neighbour is generated as a SEPARATE file (not
            # appended to `doc`) so run_job.sh can create and confirm it BEFORE
            # the target even exists -- placing them together and hoping the
            # target doesn't race ahead of the neighbour's own startup/warmup
            # was unreliable in practice (confirmed: cells where the target had
            # no real contention because the neighbour wasn't up yet).
            nb = cr.get("neighbours")
            if nb:
                nb_u = float(nb.get("u", 0.1)); nb_Q = int(round(nb_u * P))
                nb_K = (ktab.get(f"{scale}-U{ulabel(nb_u)}") or {}).get("K") or K
                nb_doc = ""
                for i in range(int(nb.get("count", 0))):
                    nb_doc += NEIGHBOUR.format(ns=ns, name=name, i=i, nbq=nb_Q, p=P, nbk=nb_K,
                                               model=model, lk=lk, lv=lv, image=image,
                                               host=host, sub=sub)
                if workload != "matmul":
                    nb_doc = nb_doc.replace("/usr/local/bin/matmul ",
                                            f"/usr/local/bin/matmul --kind {workload} --buf-kb {buf_kb} ")
                fp_nb = out_root / "_nb" / scale / f"U{ulabel(u)}.yaml"
                fp_nb.parent.mkdir(parents=True, exist_ok=True)
                fp_nb.write_text(nb_doc, encoding="utf-8")

            # model3: BOTH competitor arms are pre-generated as SEPARATE files (not
            # appended to `doc`) since which one gets instantiated is a run_job.sh
            # -time choice (COMPETITOR_TYPE); neither has a driver-independent cpu
            # at generate time.
            #
            # Both arms share ONE reference intensity (co_runners.competitor.u,
            # default 0.3) rather than the unreserved arm scaling with the
            # target's own K: otherwise "reserved vs unreserved" wouldn't be a
            # single-variable comparison -- at low target U the fixed-0.3
            # reserved competitor would be busier than the target-matched
            # unreserved one, and at high target U the reverse, confounding
            # scheduling-class with workload intensity. A fixed shared intensity
            # isolates reserved-vs-unreserved as the only thing that differs.
            comp_cfg = cr.get("competitor") or {}
            comp_u = float(comp_cfg.get("u", 0.3)); comp_Q = int(round(comp_u * P))
            comp_K = (ktab.get(f"{scale}-U{ulabel(comp_u)}") or {}).get("K") or K

            intf = cr.get("interferer")
            if intf is not None:
                # unreserved: taskset-pinned CFS load at the SAME fixed reference
                # intensity as the reserved arm (comp_K, not the target's own K).
                # @@INTF_CPU@@ is filled in by run_job.sh once it knows the
                # target's actual spare/sibling cpu.
                intf_doc = INTERFERER.format(ns=ns, name=name, model=model, lk=lk, lv=lv,
                                             image=image, cpu="@@INTF_CPU@@", k=comp_K, p=P,
                                             host=host, sub=sub)
                if workload != "matmul":
                    intf_doc = intf_doc.replace("/usr/local/bin/matmul ",
                                                f"/usr/local/bin/matmul --kind {workload} --buf-kb {buf_kb} ")
                fp_intf = out_root / "_intf" / scale / f"U{ulabel(u)}.yaml"
                fp_intf.parent.mkdir(parents=True, exist_ok=True)
                fp_intf.write_text(intf_doc, encoding="utf-8")
            comp = cr.get("competitor")
            if comp is not None:
                # reserved: its own CBS reservation; no cpu placeholder needed --
                # like the target, its landing cpu comes from the driver and
                # run_job.sh places it with the same retry-until-landed technique.
                comp_doc = COMPETITOR_RESERVED.format(ns=ns, name=name, model=model, lk=lk, lv=lv,
                                                      image=image, cq=comp_Q, p=P, ck=comp_K,
                                                      host=host, sub=sub)
                if workload != "matmul":
                    comp_doc = comp_doc.replace("/usr/local/bin/matmul ",
                                                f"/usr/local/bin/matmul --kind {workload} --buf-kb {buf_kb} ")
                fp_comp = out_root / "_comp" / scale / f"U{ulabel(u)}.yaml"
                fp_comp.parent.mkdir(parents=True, exist_ok=True)
                fp_comp.write_text(comp_doc, encoding="utf-8")

            # non-matmul workloads: inject the kernel flags into EVERY probe command
            # (target + neighbours + interferer all call /usr/local/bin/matmul).
            if workload != "matmul":
                doc = doc.replace("/usr/local/bin/matmul ",
                                  f"/usr/local/bin/matmul --kind {workload} --buf-kb {buf_kb} ")

            fp = out_root / scale / f"U{ulabel(u)}.yaml"
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(doc, encoding="utf-8")
            n += 1
    print(f"[gen] wrote {n} manifest(s) under {out_root} (workload={workload})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
