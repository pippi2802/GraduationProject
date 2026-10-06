# Online validation of the audio workload

The budgets of `budgets.csv` (from `analysis_template2.ipynb`) given to KubeDeadline as the reservation, the audio task run under them, and the real
misses counted. 28 runs: for each scenario the routes Route 1 and Route 2b at p = 1e-1, 1e-2, 1e-3 and the HWM route (one budget for every p), each without and with the
memory enemy. 50000 jobs of 10 ms per instance (8.3 min); about 10 min a run with the pod start, so about 2.3 h per scenario. Each scenario runs on the node that did
not profile it (multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`), so the two can run at the same time.

```
budgets.csv          scenario, route, p, runtime_us, period_us   <- edit this to change a budget
make_manifests.py    python3 make_manifests.py  (standard library only) writes everything below
pods/<scenario>/<route>/<p>_<none|memory>.yaml    28 self-contained files: RtClaimParameters + ResourceClaimTemplate + Pod; hwm/all_none.yaml, all_memory.yaml
runs.csv             one line per run: pod file, node, enemy cpus, reservation, where the files appear on the node, where to save them
step5_input/budgets.csv   the same budgets in the format step 5's validate.py reads
results/<scenario>/<route>/<p>_<interference>/instance<N>.csv    where to save the results of each run (git-ignored)
```
Reservation: `runtime` = the budget of `budgets.csv` of `period` 10000 us (the task's period), on cpu1 (single-core) or cpu1 and cpu2 (multi-core, one claim for both).
The pod runs `python3 run.py cpus=[..] period_ms=10 jobs=50000 output=/results/<run id>` from image `pippina2/rq2-audio:v2` and writes
`/var/lib/rq2/results/audio_validation/<run id>_instance<N>.csv` on the node. The memory enemy is not in the pod: start it on the node around the runs whose file ends in
`_memory.yaml` (cpus 3,0 for multi-core, 2,3,0 for single-core, memory buffer 2662400 KB, the same as in the profiling).

## Run all of it automatically (on the control plane, from this folder)
```bash
DRY_RUN=1 ./run_validation.sh                                  # the plan: 14 runs per scenario, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &         # both scenarios at the same time, each on its own node: about 2.3 h
tail -f results/single_core/validation.log                     # progress; also results/multi_core/validation.log
./run_validation.sh --scenario single_core --route hwm         # only one scenario, or only one route (route1, route2b, hwm)
pkill -TERM -f "[r]un_validation.sh"                           # stop it (Ctrl-C also works); the enemies are stopped too
```
Order: p = 1e-3 first, then 1e-2, then 1e-1; inside each, route1 then route2b, without then with the memory enemy; HWM last. For every run it starts the
memory enemy when needed (confirmed running), applies the pod of `pods/`, polls it until it ends (a failed pod is seen at once and its state and logs go to the log), pulls
the CSV and meta.json of every instance into `results/`, checks them (row count = jobs; FIFO, affinity and mlock flags true; an empty file is a failure), logs the number of
misses, deletes the pod, stops the enemy (confirmed) and settles 10 s. A failed run is retried once, then recorded as FAILED in `results/<scenario>/summary.tsv` and the rest goes on.
**Safe to restart**: a collected run (`.done` in its folder) is skipped, so after a crash or a stop just start it again.
It refuses to start if a pod of this validation (label `validation=true`) or of the profiling (`rq2-single-instance0`, `rq2-multi`) exists, or an `rq2-enemy` is running on a node.
Before the first run of a scenario it reads the node's `kubepods-besteffort.slice`: if it holds another period than the pods' 10000 us (left by another workload) it resets it
(runtime 0, then the period; no pod is running then) and logs it, because a slice with another period makes a two-core pod fail with StartError. `--no-slice-reset` skips this.
Prerequisites: kubectl, python3, the enemy installed on both nodes (`../../procedure/step2_profiling/install_enemy.sh <agent-ns> <node>`), `../../stress1/campaign_{start,stop}_enemies.sh`.

## One run by hand, if you prefer (from the RQ2 folder)
```bash
F=workload3/validation/pods/single_core/route1/p1e-3_memory.yaml; RUN=rq2-val-aud-single-r1-p1e-3-mem          # both are in runs.csv
NS=rq2-node-prep-worker7; NODE=rt-k8s-worker-7; OUT=workload3/validation/results/single_core/route1/p1e-3_memory; INSTANCES="0"   # multi-core: "0 1"
AGENT=$(kubectl -n $NS get pod -l app=rq1-agent --field-selector spec.nodeName=$NODE -o jsonpath='{.items[0].metadata.name}')
on_node() { kubectl -n $NS exec -i $AGENT -- nsenter --target 1 --mount -- "$@"; }
on_node bash -s -- 2662400 64 2,3,0 < procedure/step3_drift_runs/campaign_start_enemies.sh     # memory runs only; wait for the OK lines
kubectl apply -f $F
until [ "$(kubectl -n rq2 get pod $RUN -o jsonpath='{.status.phase}')" = Succeeded ]; do sleep 30; done     # Failed: kubectl -n rq2 describe pod $RUN
mkdir -p $OUT; for i in $INSTANCES; do for e in csv meta.json; do on_node cat /var/lib/rq2/results/audio_validation/${RUN}_instance$i.$e > $OUT/instance$i.$e; done; done
kubectl -n rq2 delete pod $RUN
on_node bash -s < procedure/step3_drift_runs/campaign_stop_enemies.sh                           # memory runs only
```
Check that the CSVs are not empty (an empty file means a wrong node or no output) and that `meta.json` says `sched_fifo_ok`, `affinity_ok` and `mlockall_ok` true.
Never run two pods of this folder on one node at the same time, and no enemy may be running during a `_none` run. If a pod ends in `StartError`, the node's
`kubepods-besteffort.slice` still holds the period of another workload: see step 2's README (reset it to 10000; `run_validation.sh` does it itself).

## Check the results (step 5)
```bash
cd ../../procedure/step5_online_validation
python3 validate.py check --step4 ../../workload3/validation/step5_input --results ../../workload3/validation/results
```
It prints the verdict per route and tolerance (budget misses against platform stalls), whether jobs are late only above Q*, the stalls, and the over-budgeting; it can be run while
the validation is still going. Without `--step4 .../p_floor.csv` and `burst_check.csv` (those come from running step 4 on this workload) the stall comparison and the online-against-offline table are left out.

## Changing a budget
Edit `budgets.csv`, run `python3 make_manifests.py`, and delete the results of the runs that changed.
