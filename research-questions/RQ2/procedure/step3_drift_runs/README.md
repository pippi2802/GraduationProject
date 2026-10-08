# Step 3: drift between runs: other VMs, other times, and one stressed run

The bound C_p of the same workload changes a little from run to run, on one VM and between VMs of the same type. alpha_drift measures it as the spread
of the baseline bounds, so step 4 needs more baseline runs than the two of step 2: **at least one extra baseline** (the two of step 2 plus one make three, the minimum for the
spread and its leave-one-out check to mean anything; more is better), taken on another VM of the same type or at another time. One further **stressed run**, with the memory enemy,
checks that the budgets cover a run that was not used to derive them.

The arguments are those of step 2 (same workload contract, same pod YAML as in step 2). The label is yours (the VM, the day ...). `--jobs N` sets the number of jobs of the run with the same YAML (for example 30000 here while step 2 used 50000); the run must then have exactly N rows.
```bash
./run_extra.sh baseline --label vm2 --scenario single_core --pod-yaml ../../workload/pods/single_core_pod.yaml \
    --node rt-k8s-worker-7 --agent-ns rq2-node-prep-worker7 --node-dir /var/lib/rq2/results/single_core --prefix single_core --instances 1
./run_extra.sh baseline --label vm3 ... (another VM or another day)
./run_extra.sh stress --paired-with vm2 --scenario single_core --pod-yaml ... --node rt-k8s-worker-7 ... --enemy-cpus 2,3,0     # --enemy memory (default) or cache
```
`--paired-with` names the baseline measured next to the stressed run (same node, close in time): step 4 divides the stressed run's bound by that baseline's for the
stress ratio on that run and the rule for m. It is written to `results/<scenario>/stress_run/paired_with.txt`; without it that part of step 4 is skipped with a note.

Results: `results/<scenario>/extra_baselines/<label>/instance<N>.csv` and `results/<scenario>/stress_run/instance<N>.csv`. The enemy start and stop scripts are copies of
`../../stress1/`; install the enemy on the node first (`../step2_profiling/install_enemy.sh`). The StartError note of step 2 applies here as well.
