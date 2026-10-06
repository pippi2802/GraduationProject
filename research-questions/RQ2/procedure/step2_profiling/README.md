# Step 2: profile your workload, baseline1, cache, memory, baseline2

One node, unattended, in this order: baseline (no stress), cache enemy, memory enemy, baseline again. The enemy cores are the m of the platform factor.

## The workload contract
- a pod YAML with ONE Pod; its `nodeSelector` is a one-line flow mapping (`nodeSelector: { key: value }`), the script adds the node.
- the pod writes `/results/<prefix>_instance<N>.csv` and `.meta.json` (N = 0, 1, ...) to a hostPath directory of the node.
- columns of the CSV: `job_id, skipped, warmup, cpu_ns, release_ns, response_ns` (CPU time of the job, release time, response time); `start_ns, end_ns, frame_idx` for the platform-event check of step 4. The meta file may hold `sched_fifo_ok`, `affinity_ok`, `mlockall_ok`: the script rejects a run where one is false.
- the number of jobs is set in the pod YAML (at least 50000 for p = 1e-3; the profiling of the thesis used 100000).
- prerequisites: kubectl on this machine, a node-prep agent pod (label `app=rq1-agent`) on the node (as in `setup/`), the enemy installed on the node once:
  `./install_enemy.sh <agent-namespace> <node>`.

## Run
```bash
./run_profiling.sh --scenario single_core --pod-yaml ../../workload/pods/single_core_pod.yaml \
    --node rt-k8s-worker-6 --agent-ns rq2-node-prep-worker6 --node-dir /var/lib/rq2/results/single_core --prefix single_core \
    --instances 1 --enemy-cpus 2,3,0
./run_profiling.sh --scenario multi_core --pod-yaml ../../workload/pods/multi_core_pod.yaml \
    --node rt-k8s-worker-7 --agent-ns rq2-node-prep-worker7 --node-dir /var/lib/rq2/results/multi_core --prefix multi_core \
    --instances 2 --enemy-cpus 3,0
```
Another workload (audio, segmentation, your own): the same command with its pod YAML, e.g. `../../workload3/pods/single_core_pod.yaml`.
The two commands above run on different nodes, so you can start both. Detach long runs: `nohup ./run_profiling.sh ... > profiling.log 2>&1 &`, stop with
`pkill -TERM -f "[r]un_profiling.sh"` (it also stops the enemies).
`./run_profiling.sh` without arguments prints all options (`--only cache,memory` reruns single runs, `--cache-kb`, `--memory-kb`, `--attempts`).

## What it checks
Each run is retried once. A failed pod is seen at once and its state and logs are printed. A file that is missing or empty on the node (wrong node, no output),
fewer than 1000 rows, or a false real-time flag in the meta file, fails the run. Enemies are confirmed to burn CPU before the run and confirmed gone after it,
also when the script is interrupted.

## Results
`results/<scenario>/{baseline1,cache,memory,baseline2}/instance<N>.csv` and `results/<scenario>/profiling.json` (the node and the enemy cores m). Step 4 reads them.

## When a pod ends in StartError
The kernel refused the pod's real-time reservation. Pods of workloads with a different server period leave their period in the node's
`kubepods-besteffort.slice`, and a two-core pod cannot regrow it. Read the message first (`kubectl -n <ns> get pod <pod> -o jsonpath='{.status.containerStatuses[0].state}'`),
and if it mentions `cpu.rt_runtime_us ... invalid argument`, reset the slice on that node (no pod may be running) and run again:
```bash
kubectl -n <agent-ns> exec -i <agent> -- nsenter --target 1 --mount --pid -- bash -c \
  'd=/sys/fs/cgroup/kubepods.slice/kubepods-besteffort.slice; echo 0 > $d/cpu.rt_runtime_us && echo <period us of your pod> > $d/cpu.rt_period_us'
```
