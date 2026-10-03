# alpha_drift

Two baseline runs (100000 jobs each, no stress), single-core then multi-core,
on the VM you name. Run it once per VM to measure how much the baselines drift
between VM types (e.g. `worker6` and `worker0`), and against the baselines of
the main four-condition campaign (`workload/run_campaign.sh`).

```bash
# detached, from research-questions/RQ2 (needs a machine with a real kubeconfig)
nohup alpha_drift/run_alpha_drift.sh worker6 > /dev/null 2>&1 &
tail -f alpha_drift/results/worker6/alpha_drift.log
# the other VM, at the same time or later:
nohup alpha_drift/run_alpha_drift.sh worker0 > /dev/null 2>&1 &
```

Takes about 2.3 h per VM (about 70 min per run). The two VMs can run at the
same time: each invocation suffixes its pod, claim and claim-parameters names
with `-<vm-label>`, so they never share a name. The script still aborts if a
pod of its own name already exists, for example from a second invocation for
the same VM.

## How the VM is chosen

`<vm-label>` is the suffix of the VM's node-prep namespace
`rq2-node-prep-<vm-label>` (override with `NODE_PREP_NS`). The node that
namespace's agent pod runs on is the node the workload is pinned to. The
script writes a copy of each pod spec with its `nodeSelector` replaced by
`{ experiment-model: rq2, kubernetes.io/hostname: <that node> }`, so both
models can run on any VM whatever its `rq2-role` label says. The specs in
`workload/pods/` are not edited, so the runs stay comparable to the main
campaign. The exact applied specs are saved in
`results/<vm>/manifests/`.

The node must carry `experiment-model=rq2`. If it does not, the script stops
and prints the command; it never labels nodes itself:

```bash
kubectl label node <node-name> experiment-model=rq2
```

Things the script cannot check for a new VM: that cpu1 (and cpu2 for
multi-core) are isolated RT cores there, and that the node's seeded RT budget
is at least `runtime / period` of the pod specs (`runtime: 39100` of
`period: 41667`). See the header comment of `workload/pods/single_core_pod.yaml`.

## Stress runs (Route 2 transfer test)

```bash
nohup alpha_drift/run_alpha_drift.sh worker0 memory > /dev/null 2>&1 &
```

The optional second argument is the condition: `baseline` (default), `memory`
or `cache`. With a stress condition the script starts the enemy the way
`workload/run_campaign.sh` does (memory 2662400 KB, cache 266240 KB, stride 64;
cpus `2,3,0` for single-core and `3,0` for multi-core, the same as session 1,
override with `ENEMY_CPUS`), confirms every enemy is really burning cpu,
deploys the pod, pulls the data, and stops the enemy with a polled
confirmation. An exit trap stops the enemy if the script dies or is
interrupted. The enemy start/stop scripts come from `stress1/` (or `stress/`,
or `STRESS_DIR`).

Before the first stress run on a VM, install the enemy binary on its node
(`/usr/local/bin/rq2-enemy`, step 1 of `analysis/execution_commands.txt`),
check there are at least 3 GB free for the memory enemy, and re-seed the RT
budget if the node was rebooted.

Data goes to `alpha_drift/results/<vm>/<model>/<condition>/`, next to the
baseline runs.

## Per run

Checks no `rq2-enemy` is running on the node and no old pod exists, applies
the pinned pod, waits for it to finish, pulls the CSV and `meta.json` via the
node-prep agent, checks the data (row count equals jobs, mlockall/sched_fifo/
affinity ok), and deletes the pod. A failed run is retried once, then recorded
as FAILED while the next run goes on.

## Output (git-ignored)

```
alpha_drift/results/<vm>/single_core/<condition>/instance0.{csv,meta.json}
alpha_drift/results/<vm>/multi_core/<condition>/instance{0,1}.{csv,meta.json}
alpha_drift/results/<vm>/manifests/{single_core,multi_core}.yaml
alpha_drift/results/<vm>/alpha_drift.log
```

Resume after a crash without redoing a finished run:

```bash
START_FROM=multi_core alpha_drift/run_alpha_drift.sh worker6
```

Environment overrides: `NODE_PREP_NS`, `WORKLOAD_NS`, `JOBS` (row-count check
only; must match the pod specs), `ATTEMPTS`, `SETTLE_S`, `START_FROM`,
`ENEMY_CPUS`, `STRESS_DIR`, `MEMORY_SIZE_KB`, `CACHE_SIZE_KB`, `STRIDE_BYTES`.
