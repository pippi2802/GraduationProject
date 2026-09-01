#!/usr/bin/env python3
"""Compare two sriov-probe result directories (accel_off vs accel_on).

Usage: compare.py <off_dir> <on_dir>
"""
import json
import re
import sys
import statistics as stats


def parse_ping(path):
    times = []
    pat = re.compile(r"time=([0-9.]+) ms")
    with open(path) as f:
        for line in f:
            m = pat.search(line)
            if m:
                times.append(float(m.group(1)))
    if not times:
        raise ValueError(f"no RTT samples parsed from {path}")
    times.sort()
    n = len(times)
    return {
        "n": n,
        "mean": stats.mean(times),
        "p50": times[int(n * 0.50)],
        "p95": times[min(int(n * 0.95), n - 1)],
        "p99": times[min(int(n * 0.99), n - 1)],
        "max": times[-1],
    }


def parse_iperf_udp(path):
    with open(path) as f:
        data = json.load(f)
    s = data["end"]["sum"]
    return {
        "jitter_ms": s.get("jitter_ms"),
        "lost_percent": s.get("lost_percent"),
        "bits_per_second": s.get("bits_per_second"),
    }


def parse_iperf_tcp(path):
    with open(path) as f:
        data = json.load(f)
    s = data["end"]["sum_received"]
    return {"bits_per_second": s.get("bits_per_second")}


def pct_change(off, on):
    if off == 0:
        return float("nan")
    return (on - off) / off * 100.0


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    off_dir, on_dir = sys.argv[1], sys.argv[2]

    off_ping = parse_ping(f"{off_dir}/ping.log")
    on_ping = parse_ping(f"{on_dir}/ping.log")
    off_udp = parse_iperf_udp(f"{off_dir}/iperf_udp.json")
    on_udp = parse_iperf_udp(f"{on_dir}/iperf_udp.json")
    off_tcp = parse_iperf_tcp(f"{off_dir}/iperf_tcp.json")
    on_tcp = parse_iperf_tcp(f"{on_dir}/iperf_tcp.json")

    print(f"{'metric':<20}{'accel_off':>15}{'accel_on':>15}{'change':>12}")
    rows = [
        ("ping p50 (ms)", off_ping["p50"], on_ping["p50"]),
        ("ping p95 (ms)", off_ping["p95"], on_ping["p95"]),
        ("ping p99 (ms)", off_ping["p99"], on_ping["p99"]),
        ("ping max (ms)", off_ping["max"], on_ping["max"]),
        ("udp jitter (ms)", off_udp["jitter_ms"], on_udp["jitter_ms"]),
        ("udp loss (%)", off_udp["lost_percent"], on_udp["lost_percent"]),
        ("tcp throughput (Gbps)", off_tcp["bits_per_second"] / 1e9, on_tcp["bits_per_second"] / 1e9),
    ]
    important = []
    for name, off_v, on_v in rows:
        change = pct_change(off_v, on_v)
        print(f"{name:<20}{off_v:>15.3f}{on_v:>15.3f}{change:>11.1f}%")
        if "throughput" not in name and abs(change) >= 50:
            important.append(name)

    print()
    if important:
        print(f"DECISION RULE MET (>=50% change) on: {', '.join(important)}")
        print("-> worth re-checking calendar before building a real experiment.")
    else:
        print("DECISION RULE NOT MET (<50% change on all latency/jitter metrics).")
        print("-> drop it, keep as future-work paragraph only.")


if __name__ == "__main__":
    main()
