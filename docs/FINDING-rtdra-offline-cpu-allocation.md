# FINDING — RT-DRA allocates offline CPUs unless the kubelet-plugin re-enumerates

**Context:** Model 1 (clean-baseline RQ1 experiment) on the self-managed kubeadm
cluster (`rt-cluster-cp-0` + `rt-cluster-worker-0`, Standard_D4s_v5 = 4 vCPU / 2
physical cores), using the KubeDeadline **RT-DRA** driver (`dra-rt-driver`,
`rt-v0.1.1`).

**Status:** RESOLVED. Fix = offline the hyper-thread siblings **first**, then
`rollout restart` the RT-DRA kubelet-plugin so its NAS `allocatableCpuset` is
rebuilt from the *online* CPU set.

---

## Symptom

With the two hyper-thread siblings offlined by node-prep (cpu1, cpu3 → online=0,
leaving cpu0/cpu2 as whole physical cores), the RT pods crashed at startup:

```
taskset: failed to set pid 1's affinity: Invalid argument
[rtapp] cell=tight-u20 RT_CPUSET=3
```

`RT_CPUSET=3` — the driver had allocated **cpu3, which is offline** — so pinning
(`taskset -c 3`) failed and the container exited (canary → CrashLoopBackOff, RT
cell → Error). Earlier pods landed on cpu0 (worked) and cpu3 (failed),
apparently at random.

## Root cause

Two facts combined:

1. **`count` = number of cores, not a CPU index.** The RT-DRA
   `RtClaimParameters` field `count` is the number of cores `m` (KubeDeadline
   paper, ECRTS 2025, §3.3 and Fig. 4b: *"count … denote the number of cores
   mᵢ"*). The **driver** chooses *which* CPUs via an admission test
   (`find_by_admission_test(n, bw, count)`, Algorithm 1) using a worst-fit /
   best-fit strategy. The user cannot pin a specific CPU from the claim.
   - Empirical confirmation: three pods all had `count: 1` yet were placed on
     cpu0, cpu3, and (crashed) — inconsistent with "count = index", consistent
     with "1 core, driver spreads via worst-fit".

2. **The driver's core pool (`NAS.allocatableCpuset`) is built once, at
   kubelet-plugin startup, and did not reflect the later offlining.** The NAS
   `NodeAllocationState/rt-cluster-worker-0` listed all four CPUs:

   ```yaml
   allocatableCpuset:
   - rtcpu: { id: 0, util: 0 }
   - rtcpu: { id: 1, util: 0 }
   - rtcpu: { id: 2, util: 0 }
   - rtcpu: { id: 3, util: 0 }
   ```

   The kubelet-plugin (`dra-rt-driver-kubeletplugin`) had last restarted **before**
   node-prep offlined cpu1/cpu3, so its enumeration still included the (now
   offline) siblings. The worst-fit admission test therefore happily handed out
   cpu3.

Net: node-prep and the driver disagreed about which CPUs exist, and the driver
won (it writes `RT_CPUSET` / cgroup `cpu.rt_multi_runtime_us`).

## Fix

Make the driver's allocatable pool match the online CPU set by re-enumerating
**after** the siblings are offline:

```bash
# 1. siblings already offline via node-prep (cpu1, cpu3 online=0; cpu0, cpu2 online)
kubectl -n model1 logs -l app=model1-node-prep --tail=20   # confirms offline set

# 2. rebuild the driver's NAS pool from the ONLINE CPUs
kubectl -n dra-rt-driver rollout restart daemonset dra-rt-driver-kubeletplugin
kubectl -n dra-rt-driver rollout status  daemonset dra-rt-driver-kubeletplugin
```

Result — `allocatableCpuset` now contains only the online cores:

```yaml
allocatableCpuset:
- rtcpu: { id: 0, util: 0 }
- rtcpu: { id: 2, util: 0 }
```

The driver can no longer allocate offline CPUs; every RT cell / canary now gets
`RT_CPUSET ∈ {0, 2}` and `taskset` succeeds.

## Why this works

The kubelet-plugin enumerates the node's CPUs at startup to populate
`NAS.allocatableCpuset`. A CPU taken offline (`/sys/devices/system/cpu/cpuN/online
= 0`) is dropped from the runtime-visible online set, so a **fresh** enumeration
excludes it. Restarting the DaemonSet forces that fresh enumeration. (A restart
that happens *before* offlining, as originally, keeps the stale 4-CPU pool.)

## Operational procedure (ordering matters)

For Model 1 the order is **offline → re-enumerate**:

1. `node-prep/apply.sh` offlines the hyper-thread siblings and writes
   `/var/lib/model1/cpu-map.json` (rt_cpu=0, canary_cpu=2, offline=[1,3]).
2. `kubectl -n dra-rt-driver rollout restart daemonset dra-rt-driver-kubeletplugin`.
3. Verify `allocatableCpuset == {0,2}` before starting the sweep.

**On every node reboot** the CPUs come back online and the plugin re-enumerates 4
CPUs at boot → repeat steps 1–3 (node-prep DaemonSet re-offlines on boot; then
restart the plugin again). Do this before any Model 1 run after a reboot.

## Verification

```bash
kubectl apply -f workloads/model1/manifests/rendered/soft-u40.yaml
kubectl -n model1 exec soft-u40 -- printenv RT_CPUSET      # expect 0 or 2
kubectl -n model1 exec soft-u40 -- bash -c 'wc -l /results/*.log; sleep 3; wc -l /results/*.log'  # growing
kubectl -n model1 delete -f workloads/model1/manifests/rendered/soft-u40.yaml
```

## Approaches considered and rejected

- **`count` as a CPU index** — contradicts the paper (`count` = cores) and the
  observed placements; `count: 0` would request zero cores. Rejected.
- **Editing `NAS.allocatableCpuset` by hand** — works but is fragile (the driver
  may re-derive it) and must be redone each reboot; the plugin restart achieves
  the same result cleanly.
- **Kubernetes CPU Manager (static policy)** — does not solve it: CPU Manager is
  an independent allocator the RT-DRA driver never consults, so it can't
  constrain the driver's core choice; and it would fight KubeDeadline's own
  cpuset + `cpu.rt_multi_runtime_us` pinning (two writers of `cpuset.cpus`),
  potentially detaching the SCHED_FIFO task from its RT budget. KubeDeadline is
  the pinner by design; CPU Manager stays off.

## Implications for the harness

- `run_model1.py` records the real `RT_CPUSET` and `RT_RUNTIME_PERIOD` per cell
  in `cell.json`, so analysis always knows the actual core used.
- Because the driver (not node-prep) decides between cpu0 and cpu2, the sampler's
  `rt` vs `canary` labelling (currently keyed on the cpu-map) should eventually
  be keyed on the pod cgroup instead; for now the canary starts first and holds
  one core while cells take the other, and `cell.json` disambiguates.
