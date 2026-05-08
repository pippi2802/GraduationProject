# Contended AKS experiment

Goal: show that a time-sensitive periodic workload **misses deadlines** and
exhibits **high execution-time variance** on vanilla AKS, even when the
total CPU utilization is below the available capacity.

## Setup

- AKS nodepool VM: `Standard_D2ps_v6` (2 vCPUs, ARM).
- One Pod with two containers (`rt-a`, `rt-b`), pinned to the same node.
- Each container runs `rt_multi_periodic` with **3 periodic tasks**:

  | Task | Period T | WCET C | U = C/T |
  |------|---------:|-------:|--------:|
  | 0    | 20 ms    | 5 ms   | 0.25    |
  | 1    | 50 ms    | 15 ms  | 0.30    |
  | 2    | 100 ms   | 25 ms  | 0.25    |

  Per-container U = 0.80. Two containers ⇒ total U = **1.60 < 2.0**
  (schedulable in theory). Both containers run on the same 2-vCPU node, so
  the 6 threads contend on the CFS scheduler.

Each invocation logs release / start / finish wall-clock times and the
CPU time spent in the busy loop. A deadline miss is recorded when
`finish > release + period`.

## Files

- [rt_multi_periodic.c](rt_multi_periodic.c) — multi-threaded periodic workload.
- [Dockerfile](Dockerfile) — builds the image.
- [scripts/run_workload.sh](scripts/run_workload.sh) — container entrypoint
  (runs the workload + `/proc/stat` sampler, then sleeps so results can be
  copied out before pod GC).
- [k8s/workload-contended.yaml](k8s/workload-contended.yaml) — Pod with two
  containers; replace `IMAGE` and `NODE_NAME`.
- [scripts/run_experiment.sh](scripts/run_experiment.sh) — deploys the pod,
  waits for both containers to finish, `kubectl cp`s the CSVs out, deletes
  the pod.
- [analyze.py](analyze.py) — per-task mean/variance/percentiles +
  deadline-miss rate; writes `summary.txt` and `cdf.png`.

## Run it

1. Build & push the image (example with ACR):

   ```bash
   az acr build --registry <registry> --image rt-contended:0.1 .
   # or
   docker build -t <registry>/rt-contended:0.1 .
   docker push  <registry>/rt-contended:0.1
   ```

2. Attach the registry to the cluster (one-time):

   ```bash
   az aks update --resource-group <rg> --name <aks> --attach-acr <registry>
   ```

3. Pick a node:

   ```bash
   kubectl get nodes
   ```

4. Run the experiment:

   ```bash
   ./scripts/run_experiment.sh <registry>.azurecr.io/rt-contended:0.1 <node-name>
   ```

   Results land in `results/<timestamp>/`.

5. Analyze:

   ```bash
   python analyze.py results/<timestamp>/
   ```

   Produces `summary.txt` (variance + deadline-miss rate per task) and
   `cdf.png` (per-task response-time CDF).

## Tuning

- To stress the node harder, increase `TASK_*` runtimes in
  [k8s/workload-contended.yaml](k8s/workload-contended.yaml) (keep total
  utilization below 2.0 to keep the set theoretically schedulable).
- To run longer, increase the `iters` field of each TASK spec.
- `HOLD_SEC` keeps the container alive after the run so `kubectl cp` can
  fetch the CSVs.
