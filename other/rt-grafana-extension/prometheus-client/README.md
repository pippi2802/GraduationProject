# rt-DRA NAS Exporter + Grafana Dashboard

A Prometheus exporter and Grafana dashboard that visualize the **real-time
resource allocation** managed by the rt-DRA driver (KubeDeadline). It reads the
`NodeAllocationState` (NAS) CRD — the single object that holds the allocatable
and allocated RT-CPU state per node — and exposes it as Prometheus metrics.

```
NodeAllocationState CRD  ──watch──▶  exporter (/metrics)  ──scrape──▶  Prometheus  ──▶  Grafana dashboard
 (nas.rt.resource.example.com)        :9101                              :9090            :3000
```

> The dashboard reflects the **scheduler's allocation decisions** (worst-fit
> packing, per-CPU utilisation, per-claim runtime/period). Kernel RT *enforcement*
> on this cgroup-v2 / 6.16-rc kernel is tracked separately and does not affect
> this allocation/utilisation view.

---

## Contents

| Path | What |
|---|---|
| `exporter.py` | The exporter (Python, custom Prometheus collector). |
| `Dockerfile`, `requirements.txt` | Build the exporter image. |
| `build.sh` | Build + push the image. |
| `deploy.sh` | Apply RBAC + Deployment + (optional) ServiceMonitor. |
| `deploy/rbac.yaml` | ServiceAccount + read-only ClusterRole on NAS. |
| `deploy/deployment.yaml` | Exporter Deployment + Service (+ scrape annotations). |
| `deploy/servicemonitor.yaml` | ServiceMonitor for kube-prometheus-stack. |
| `monitoring/prometheus.yaml` | Standalone demo Prometheus (annotation scraping). |
| `monitoring/grafana.yaml` | Standalone demo Grafana (datasource + dashboard pre-provisioned). |
| `monitoring/install.sh` | Install the demo stack + load the dashboard. |
| `dashboards/rtdra-nas-dashboard.json` | The Grafana dashboard. |

---

## Metrics

Util uses the driver's units: `util = runtime * 1000 / period`, so a full CPU is
`1000` (a `{runtime:100, period:1000}` 10% reservation is stored as `100`).
`*_fraction` metrics divide by 1000 to give 0..1.

| Metric | Labels | Meaning |
|---|---|---|
| `rtdra_cpu_capacity_util` | node, cpu | Assignable RT util capacity per CPU. |
| `rtdra_cpu_allocated_util` | node, cpu | Currently allocated RT util per CPU. |
| `rtdra_cpu_free_util` | node, cpu | capacity − allocated. |
| `rtdra_cpu_allocated_fraction` | node, cpu | allocated / 1000 (0..1). |
| `rtdra_node_capacity_util` | node | Σ capacity over CPUs. |
| `rtdra_node_allocated_util` | node | Σ allocated over CPUs. |
| `rtdra_node_util_ratio` | node | allocated / capacity (0..1). |
| `rtdra_node_cpus_total` | node | Allocatable CPU count. |
| `rtdra_claims_total` | node | Active allocated claims. |
| `rtdra_prepared_claims_total` | node | Prepared claims. |
| `rtdra_claim_runtime_us` | node, claim, cpu | Per-claim, per-CPU runtime (µs). |
| `rtdra_claim_period_us` | node, claim, cpu | Per-claim, per-CPU period (µs). |
| `rtdra_claim_util` | node, claim, cpu | runtime*1000/period. |
| `rtdra_claim_cpu_count` | node, claim | CPUs assigned to a claim. |
| `rtdra_node_ready` | node | 1 if NAS status Ready. |
| `rtdra_scrape_success` | — | 1 if last scrape OK. |
| `rtdra_scrape_duration_seconds` | — | Last scrape duration. |
| `rtdra_scrape_errors_total` | — | Cumulative scrape errors. |

---

## Quick start (cluster — run as `azureuser` on the control plane)

```bash
cd rt-grafana-extension/prometheus-client

# 1. Build + push the exporter image (registry defaults to pippina2)
./build.sh                      # REGISTRY=... TAG=... to override

# 2. Deploy the exporter (RBAC + Deployment + Service, ServiceMonitor if operator present)
./deploy.sh

# 3a. Already have Prometheus/Grafana? Point them at the exporter and import
#     dashboards/rtdra-nas-dashboard.json.
#
# 3b. Or stand up the bundled demo stack (Prometheus + Grafana, dashboard pre-loaded):
cd monitoring && ./install.sh
```

Access the UIs (port-forward on the control plane, then tunnel via the bastion):

```bash
kubectl -n rt-monitoring port-forward svc/grafana 3000:3000      # admin / admin
kubectl -n rt-monitoring port-forward svc/prometheus 9090:9090
```

The dashboard lands in Grafana under the **rt-DRA** folder
("rt-DRA — Real-Time Resource Allocation (NAS)").

---

## Generate activity for the dashboard

Use the verification workload to create RT claims so CPUs fill up and worst-fit
packing becomes visible:

```bash
cd ../../rt-dra-verify && ./apply.sh
# scale the claim count in rt-verify.yaml (RtClaimParameters.count) for more load
```

---

## Using kube-prometheus-stack instead of the demo stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
# apply the ServiceMonitor (its `release: monitoring` label must match the Helm release)
kubectl apply -f deploy/servicemonitor.yaml
# import dashboards/rtdra-nas-dashboard.json in Grafana, or add it as a
# sidecar-discovered ConfigMap labelled grafana_dashboard=1.
```

---

## Run locally (out of cluster) for development

Uses your kubeconfig automatically when not in a pod:

```bash
pip install -r requirements.txt
NAS_NAMESPACE=dra-rt-driver python exporter.py
curl -s localhost:9101/metrics | grep rtdra_
```

### Configuration (env vars)

| Var | Default | Purpose |
|---|---|---|
| `NAS_NAMESPACE` | `dra-rt-driver` | Namespace to watch (empty = all). |
| `NAS_GROUP` | `nas.rt.resource.example.com` | CRD group. |
| `NAS_VERSION` | `v1alpha1` | CRD version. |
| `NAS_PLURAL` | `nodeallocationstates` | CRD plural. |
| `EXPORTER_PORT` | `9101` | Metrics port. |
| `UTIL_FULL_SCALE` | `1000` | Driver util value for a full CPU. |
| `LOG_LEVEL` | `INFO` | Log verbosity. |

---

## How it works

`exporter.py` registers a custom `prometheus_client` collector. On every scrape
it re-lists the NAS objects via the Kubernetes `CustomObjectsApi` and yields
fresh metric families, so claim/CPU label sets that disappear don't leave stale
series behind. It uses the in-cluster ServiceAccount token when running in a pod,
or your local kubeconfig otherwise.
