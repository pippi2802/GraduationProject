# RT-DRA Observability — Session Handoff (Prometheus + Grafana)

> Purpose of next session: build a Prometheus exporter + Grafana dashboard that
> visualizes the **resource utilization of the NodeAllocationState (NAS)** and other
> RT-DRA parameters, producing a clean dashboard for the thesis.

---

## 1. The big picture (what this cluster is)

A self-managed **kubeadm** cluster on Azure used to validate **KubeDeadline / rt-DRA**
(real-time Dynamic Resource Allocation using SCHED_DEADLINE / HCBS).

- **k8s** 1.28.0, **cgroup v2** (cgroup2fs).
- **Control plane**: `rt-cluster-cp-0` (10.0.1.4). kubectl runs here (as `azureuser`,
  NOT root — root has no kubeconfig).
- **Worker**: `rt-cluster-worker-0` (10.0.2.4, D4s_v5, **4 vCPU**, 16 GB), HCBS RT kernel
  `6.16.0-rc4+`. Reached via Bastion SSH.
- **CNI**: Calico via the **Tigera operator** → pods live in namespace **`calico-system`**
  (NOT kube-system). Reinstall = `tigera-operator.yaml v3.28.0` + Installation CRD
  (cidr `192.168.0.0/16`, VXLANCrossSubnet) + APIServer.
- **Runtime**: RT-patched containerd `/usr/local/bin/containerd` + RT runc fork
  `/usr/local/sbin/runc`. `enable_cdi=true`, `SystemdCgroup=true`.

## 2. The rt-DRA driver (where the metrics come from)

- Image `pippina2/dra-rt-driver:v0.1.1`, Helm release `dra-rt-driver` in ns
  `dra-rt-driver`. Two pods: **controller** (on CP, does allocation) +
  **kubeletplugin** (on worker, does NodePrepareResources / CDI / cgroup writes).
- DRA plugin name `rt.resource.example.com`; **ResourceClass** `rt.example.com`.
- **The data source for the dashboard is the `NodeAllocationState` (NAS) CRD** — one per
  node. It is the single object that holds allocatable + allocated RT-CPU state.

### NAS CRD shape (the metrics model) — `dra-rt-driver/api/.../nas/v1alpha1/nas.go`
```go
NodeAllocationStateSpec {
  AllocatableCpuset  []AllocatableCpuset           // per-CPU capacity (ID, Util)
  AllocatedClaims    map[string]AllocatedCpuset    // claimUID -> allocated CPUs
  PreparedClaims     map[string]PreparedCpuset     // claimUID -> prepared CPUs
  AllocatedUtilToCpu AllocatedUtilset              // { Cpus: map[cpuID]->{Util} }
}

AllocatableCpu   { ID int; Util int }                       // capacity per CPU
AllocatedCpu     { ID int; Runtime int; Period int }        // per claim, per CPU
AllocatedRtCpu   { Cpuset []AllocatedCpu; CgroupUID string }
AllocatedUtil    { Util int }                               // utilisation value
MappedUtil       = map[string]AllocatedUtil                 // cpuID(string) -> util
```

**Key metrics to export (per node, per CPU, per claim):**
| Metric idea | Source field | Notes |
|---|---|---|
| `rtdra_cpu_capacity_util` | `AllocatableCpuset[i].Util` | total assignable util per CPU |
| `rtdra_cpu_allocated_util` | `AllocatedUtilToCpu.Cpus[cpuID].Util` | currently used util per CPU |
| `rtdra_cpu_free_util` | capacity − allocated | derived |
| `rtdra_claim_runtime_us` | `AllocatedClaims[uid].RtCpu.Cpuset[].Runtime` | per claim |
| `rtdra_claim_period_us` | `AllocatedClaims[uid].RtCpu.Cpuset[].Period` | per claim |
| `rtdra_claim_cpu` | `AllocatedClaims[uid].RtCpu.Cpuset[].ID` | which CPU(s) a claim got |
| `rtdra_claims_total` | len(AllocatedClaims) | active claims per node |
| `rtdra_node_util_ratio` | sum(allocated)/sum(capacity) | headline gauge |

> Observed live example (from controller logs): allocate picked **worst-fit** CPU 1 for a
> claim `{cpu:1, runtime:100, period:1000}`; `AllocatedUtilToCpu` became
> `map[0:{0} 1:{100} 2:{0} 3:{0}]`. So util is an **integer 0–100 per CPU** (percent-like).

## 3. How to read the NAS live (for prototyping the exporter)

```bash
# list NAS objects (one per node), in the driver namespace
kubectl get nas -A
kubectl -n dra-rt-driver get nas rt-cluster-worker-0 -o yaml   # full spec
kubectl -n dra-rt-driver get nas rt-cluster-worker-0 -o jsonpath='{.spec.allocatedUtilToCpu}'
```
The CRD is `nodeallocationstates.nas.resource.example.com` (singular `nas`). The exporter
will **watch/poll this CRD** and translate `spec` into Prometheus gauges.

## 4. Where to build (existing scaffolding)

- `rt-grafana-extension/` exists with an **empty** `prometheus-client/` dir and a
  `.gitignore`. This is the home for the new work.
- **Recommended architecture:**
  1. **Exporter** (Go preferred — reuse the driver's typed client in
     `dra-rt-driver/api/.../nas/v1alpha1/client/client.go`; or Python with `kubernetes`
     client) that lists/watches NAS objects and serves `/metrics`.
  2. Deploy as a small Deployment + Service + ServiceMonitor (or a Prometheus scrape
     annotation) in the cluster.
  3. **Grafana** dashboard JSON with: per-CPU utilization heatmap, node util gauge,
     per-claim runtime/period table, claims-over-time, free vs allocated stacked bars.
- Decide early: **Go exporter** (type-safe, reuses CRD structs, best fit) vs **Python**
  (faster to prototype). Go is the stronger thesis artifact and avoids re-modeling the CRD.

## 5. IMPORTANT context: enforcement is NOT yet working (doesn't block the dashboard)

The dashboard visualizes the **driver's allocation bookkeeping (NAS)**, which works fully.
But know the current state so you don't conflate "allocated" with "enforced":

- ✅ **Working**: DRA allocation (controller worst-fit), CDI env injection
  (`RT_CPUSET`, `RT_RUNTIME_PERIOD`), cpuset pinning, and the **NAS util accounting**.
- ❌ **Not working**: actual kernel RT budget in the container cgroup
  (`cpu.rt_multi_runtime_us = 0 0 0 0` → `chrt -f` denied / `SCHED_OTHER only`).
- **Root cause (confirmed with HCBS team)**: original rt-DRA was validated on
  **cgroup v1 + an older kernel**. Our env is **cgroup v2 + kernel 6.16.0-rc4+** → two
  mismatches. The driver's parent-slice seeder `UpdateParentCgroup` is commented out and
  uses v1 paths (`/sys/fs/cgroup/cpu,cpuacct/...`). RT-runc leaf write no-ops on the
  newer/v2 kernel.
- **Decision pending** (separate track): reproduce on Nasim's exact kernel+v1 first, then
  port to v2. **This does not affect the dashboard** — NAS util data is populated by the
  controller regardless of kernel enforcement.

> For the dashboard you can therefore demonstrate **allocation/utilization behavior**
> (worst-fit packing, per-CPU util, claim params) even though kernel enforcement is still
> being sorted out. Good to note this caveat in the thesis: "dashboard reflects the
> scheduler's allocation decisions; enforcement validation is tracked separately."

## 6. The verification workload (reference / demo data generator)

`rt-dra-verify/` (committed) creates RT claims to exercise the driver:
- `rt-verify.yaml` — Namespace `rt-verify`, **RtClaimParameters** `{count:1, runtime:100,
  period:1000}`, ResourceClaimTemplate `rt.example.com`, Pod `rt-verify`.
- `apply.sh` — builds ConfigMap from `verify.sh` and applies everything.
- Use this (or scale it up to multiple claims) to **generate allocation activity** so the
  dashboard has interesting data (multiple CPUs filling up, worst-fit packing visible).

## 7. First steps for the next session
1. `kubectl -n dra-rt-driver get nas rt-cluster-worker-0 -o yaml` — eyeball the real data.
2. Choose exporter language (recommend Go, reuse NAS client).
3. Scaffold exporter in `rt-grafana-extension/prometheus-client/` → expose the metrics in
   the table in §2.
4. Deploy exporter + (kube-prometheus-stack or existing Prometheus) + Grafana.
5. Build dashboard panels: per-CPU util heatmap, node util gauge, claim table, claims/time.
6. Drive load with `rt-dra-verify` (scale claim count) to populate panels.

## 8. Gotchas learned this session (save time)
- kubectl as **root fails** (`localhost:8080`) — run as `azureuser`, no `sudo`.
- Calico is in **`calico-system`**, not kube-system (Tigera operator install).
- First `NodePrepareResources` attempt can race (`rtCDIDevices: []`) then succeed on
  retry — the error is swallowed because it's commented out in `driver.go`. Harmless.
- Util values are **integers 0–100 per CPU** (treat as percent).
- The repo root is `GraduationProject` (one git repo); remember to **`git push`** —
  commits don't appear on GitHub until pushed.
- `kubectl get nodes` shows `containerd://Unknown` for the RT containerd build — cosmetic.
