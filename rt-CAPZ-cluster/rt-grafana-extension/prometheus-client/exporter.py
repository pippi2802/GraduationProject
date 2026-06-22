#!/usr/bin/env python3
"""
rt-DRA NodeAllocationState (NAS) Prometheus exporter.

Watches the NodeAllocationState CRD published by the rt-DRA driver
(KubeDeadline) and exposes the per-node / per-CPU / per-claim real-time
allocation state as Prometheus metrics on /metrics.

CRD:    nodeallocationstates.nas.rt.resource.example.com (v1alpha1, namespaced)
Source: dra-rt-driver/api/example.com/resource/rt/nas/v1alpha1/nas.go

Utilisation scale (matches the driver's SetUtilisation):
    claimUtil = runtime * 1000 / period
So a {runtime:100, period:1000} reservation (10% of a CPU) is stored as
util=100. A fully reserved CPU is util=1000. The exporter therefore also
exposes a *_fraction = util / 1000.0 (0..1) for convenience.
"""

import os
import time
import logging

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from prometheus_client import start_http_server, REGISTRY
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily

# ---------------------------------------------------------------------------
# Configuration (env-overridable so the same image works in/out of cluster)
# ---------------------------------------------------------------------------
GROUP = os.getenv("NAS_GROUP", "nas.rt.resource.example.com")
VERSION = os.getenv("NAS_VERSION", "v1alpha1")
PLURAL = os.getenv("NAS_PLURAL", "nodeallocationstates")
# Empty => watch all namespaces. Defaults to the driver's namespace.
NAMESPACE = os.getenv("NAS_NAMESPACE", "dra-rt-driver")
PORT = int(os.getenv("EXPORTER_PORT", "9101"))
# Driver stores util as runtime*1000/period, so a full CPU == 1000.
UTIL_FULL_SCALE = float(os.getenv("UTIL_FULL_SCALE", "1000"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("rtdra-exporter")


def _load_kube_config():
    """In-cluster service-account first, fall back to local kubeconfig."""
    try:
        config.load_incluster_config()
        log.info("loaded in-cluster kube config")
    except config.ConfigException:
        config.load_kube_config()
        log.info("loaded local kube config")


class NASCollector:
    """A prometheus_client custom collector.

    collect() is called on every scrape. It re-queries the NAS CRD and yields
    fresh metric families, so claim/CPU label sets that disappear do not leave
    stale series behind (which a plain Gauge.labels() cache would).
    """

    def __init__(self, custom_api):
        self.api = custom_api

    # -- helpers ---------------------------------------------------------
    def _list_nas(self):
        if NAMESPACE:
            resp = self.api.list_namespaced_custom_object(
                GROUP, VERSION, NAMESPACE, PLURAL
            )
        else:
            resp = self.api.list_cluster_custom_object(GROUP, VERSION, PLURAL)
        return resp.get("items", [])

    # -- the collector ---------------------------------------------------
    def collect(self):
        # Metric families (re-created each scrape).
        cpu_capacity = GaugeMetricFamily(
            "rtdra_cpu_capacity_util",
            "Assignable real-time utilisation capacity per CPU "
            "(driver units, full CPU = %d)." % UTIL_FULL_SCALE,
            labels=["node", "cpu"],
        )
        cpu_allocated = GaugeMetricFamily(
            "rtdra_cpu_allocated_util",
            "Currently allocated real-time utilisation per CPU "
            "(driver units, full CPU = %d)." % UTIL_FULL_SCALE,
            labels=["node", "cpu"],
        )
        cpu_free = GaugeMetricFamily(
            "rtdra_cpu_free_util",
            "Free real-time utilisation per CPU (capacity - allocated).",
            labels=["node", "cpu"],
        )
        cpu_alloc_frac = GaugeMetricFamily(
            "rtdra_cpu_allocated_fraction",
            "Allocated real-time utilisation per CPU as a 0..1 fraction.",
            labels=["node", "cpu"],
        )
        node_capacity = GaugeMetricFamily(
            "rtdra_node_capacity_util",
            "Total assignable RT utilisation across all CPUs on the node.",
            labels=["node"],
        )
        node_allocated = GaugeMetricFamily(
            "rtdra_node_allocated_util",
            "Total allocated RT utilisation across all CPUs on the node.",
            labels=["node"],
        )
        node_ratio = GaugeMetricFamily(
            "rtdra_node_util_ratio",
            "Node RT utilisation ratio (allocated / capacity), 0..1.",
            labels=["node"],
        )
        node_cpus = GaugeMetricFamily(
            "rtdra_node_cpus_total",
            "Number of allocatable CPUs known to the node allocation state.",
            labels=["node"],
        )
        claims_total = GaugeMetricFamily(
            "rtdra_claims_total",
            "Number of allocated RT claims on the node.",
            labels=["node"],
        )
        prepared_total = GaugeMetricFamily(
            "rtdra_prepared_claims_total",
            "Number of prepared RT claims on the node.",
            labels=["node"],
        )
        claim_runtime = GaugeMetricFamily(
            "rtdra_claim_runtime_us",
            "Per-claim, per-CPU SCHED_DEADLINE runtime budget (microseconds).",
            labels=["node", "claim", "cpu"],
        )
        claim_period = GaugeMetricFamily(
            "rtdra_claim_period_us",
            "Per-claim, per-CPU SCHED_DEADLINE period (microseconds).",
            labels=["node", "claim", "cpu"],
        )
        claim_util = GaugeMetricFamily(
            "rtdra_claim_util",
            "Per-claim, per-CPU utilisation (runtime*1000/period, driver units).",
            labels=["node", "claim", "cpu"],
        )
        claim_cpu_count = GaugeMetricFamily(
            "rtdra_claim_cpu_count",
            "Number of CPUs assigned to a claim.",
            labels=["node", "claim"],
        )
        nas_ready = GaugeMetricFamily(
            "rtdra_node_ready",
            "1 if the NodeAllocationState status is Ready, else 0.",
            labels=["node"],
        )
        scrape_ok = GaugeMetricFamily(
            "rtdra_scrape_success",
            "1 if the last NAS scrape succeeded, else 0.",
        )
        scrape_duration = GaugeMetricFamily(
            "rtdra_scrape_duration_seconds",
            "Duration of the last NAS scrape in seconds.",
        )
        scrape_errors = CounterMetricFamily(
            "rtdra_scrape_errors_total",
            "Total number of failed NAS scrapes since exporter start.",
        )

        start = time.time()
        try:
            items = self._list_nas()
            self._errors = getattr(self, "_errors", 0)
        except (ApiException, Exception) as exc:  # noqa: BLE001
            self._errors = getattr(self, "_errors", 0) + 1
            log.error("NAS scrape failed: %s", exc)
            scrape_ok.add_metric([], 0.0)
            scrape_duration.add_metric([], time.time() - start)
            scrape_errors.add_metric([], float(self._errors))
            yield scrape_ok
            yield scrape_duration
            yield scrape_errors
            return

        for item in items:
            node = (item.get("metadata") or {}).get("name", "unknown")
            spec = item.get("spec") or {}
            status = item.get("status", "")

            nas_ready.add_metric([node], 1.0 if status == "Ready" else 0.0)

            # --- per-CPU capacity (AllocatableCpuset[].rtcpu{id,util}) -----
            cap_by_cpu = {}
            allocatable = spec.get("allocatableCpuset") or []
            for entry in allocatable:
                rtcpu = (entry or {}).get("rtcpu") or {}
                if "id" not in rtcpu:
                    continue
                cpu_id = str(rtcpu["id"])
                util = float(rtcpu.get("util", 0))
                cap_by_cpu[cpu_id] = util
                cpu_capacity.add_metric([node, cpu_id], util)
            node_cpus.add_metric([node], float(len(cap_by_cpu)))

            # --- per-CPU allocated (allocatedUtilToCpu.cpus[id].util) ------
            alloc_by_cpu = {}
            cpus_map = (spec.get("allocatedUtilToCpu") or {}).get("cpus") or {}
            for cpu_id, val in cpus_map.items():
                util = float((val or {}).get("util", 0))
                alloc_by_cpu[cpu_id] = util

            total_cap = 0.0
            total_alloc = 0.0
            all_cpu_ids = set(cap_by_cpu) | set(alloc_by_cpu)
            for cpu_id in sorted(all_cpu_ids, key=lambda x: int(x) if x.isdigit() else x):
                cap = cap_by_cpu.get(cpu_id, 0.0)
                alloc = alloc_by_cpu.get(cpu_id, 0.0)
                cpu_allocated.add_metric([node, cpu_id], alloc)
                cpu_free.add_metric([node, cpu_id], max(cap - alloc, 0.0))
                cpu_alloc_frac.add_metric(
                    [node, cpu_id], alloc / UTIL_FULL_SCALE if UTIL_FULL_SCALE else 0.0
                )
                total_cap += cap
                total_alloc += alloc

            node_capacity.add_metric([node], total_cap)
            node_allocated.add_metric([node], total_alloc)
            node_ratio.add_metric(
                [node], (total_alloc / total_cap) if total_cap > 0 else 0.0
            )

            # --- per-claim (allocatedClaims[uid].rtcpu.cpuset[]) -----------
            allocated_claims = spec.get("allocatedClaims") or {}
            claims_total.add_metric([node], float(len(allocated_claims)))
            for claim_uid, alloc_set in allocated_claims.items():
                rtcpu = (alloc_set or {}).get("rtcpu") or {}
                cpuset = rtcpu.get("cpuset") or []
                claim_cpu_count.add_metric([node, claim_uid], float(len(cpuset)))
                for cpu in cpuset:
                    cpu_id = str(cpu.get("id", "?"))
                    runtime = float(cpu.get("runtime", 0))
                    period = float(cpu.get("period", 0))
                    claim_runtime.add_metric([node, claim_uid, cpu_id], runtime)
                    claim_period.add_metric([node, claim_uid, cpu_id], period)
                    util = (runtime * 1000.0 / period) if period else 0.0
                    claim_util.add_metric([node, claim_uid, cpu_id], util)

            prepared_claims = spec.get("preparedClaims") or {}
            prepared_total.add_metric([node], float(len(prepared_claims)))

        scrape_ok.add_metric([], 1.0)
        scrape_duration.add_metric([], time.time() - start)
        scrape_errors.add_metric([], float(getattr(self, "_errors", 0)))

        yield from (
            cpu_capacity,
            cpu_allocated,
            cpu_free,
            cpu_alloc_frac,
            node_capacity,
            node_allocated,
            node_ratio,
            node_cpus,
            claims_total,
            prepared_total,
            claim_runtime,
            claim_period,
            claim_util,
            claim_cpu_count,
            nas_ready,
            scrape_ok,
            scrape_duration,
            scrape_errors,
        )


def main():
    _load_kube_config()
    custom_api = client.CustomObjectsApi()

    REGISTRY.register(NASCollector(custom_api))
    start_http_server(PORT)
    log.info(
        "rt-DRA NAS exporter listening on :%d/metrics "
        "(group=%s version=%s plural=%s namespace=%s)",
        PORT, GROUP, VERSION, PLURAL, NAMESPACE or "<all>",
    )
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
