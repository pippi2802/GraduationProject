# Raspberry Pi as a Kubernetes worker — contended periodic workload

This experiment is the **third** point in the comparison:

1. [`ContendedAKS_experiment/`](../ContendedAKS_experiment) — cloud K8s (AKS).
2. [`RaspberryPi_experiment/`](../RaspberryPi_experiment) — bare metal Pi, no K8s.
3. **This folder** — same Pi, but joined to a Kubernetes cluster as a
   worker / "edge" node and running the workload as a Pod.

Together the three runs isolate the contribution of each layer:

| Run | Hardware | OS scheduler | Container runtime | K8s control plane |
|-----|----------|--------------|-------------------|--------------------|
| AKS contended | Azure VM (`Standard_D2ps_v6`, 2 vCPU ARM, hypervisor) | CFS | containerd | AKS managed |
| Pi bare metal | Raspberry Pi 4/5 | CFS | none | none |
| **Pi + K8s**  | Raspberry Pi 4/5 | CFS | containerd (k3s) | k3s on the Pi (or remote) |

Any extra jitter / miss rate in run 3 vs run 2 is attributable to **the
container + Kubernetes layer alone**, since the hardware and kernel are
identical.

## Files

- [`rt_multi_periodic.c`](rt_multi_periodic.c) — same periodic workload as
  the other two experiments.
- [`Dockerfile`](Dockerfile) — builds for `linux/arm64`. Works natively on
  the Pi or cross-built from x86 via `docker buildx`.
- [`scripts/build_image.sh`](scripts/build_image.sh) — convenience builder
  (native or cross).
- [`scripts/run_workload.sh`](scripts/run_workload.sh) — container
  entrypoint (workload + `/proc/stat` sampler + hold).
- [`k8s/workload-contended.yaml`](k8s/workload-contended.yaml) — Pod with
  two containers, pinned to the Pi via `nodeSelector`.
- [`scripts/run_experiment.sh`](scripts/run_experiment.sh) — deploys the
  pod, waits, `kubectl cp`s CSVs out, deletes the pod.
- [`analyze.py`](analyze.py) — same analyzer (only the plot title
  differs).

## Cluster topology

There are two reasonable setups; pick one.

### A) Single-node k3s **on the Pi** (recommended — simplest)

Control plane + worker on the Pi itself. Lightweight, one command to set
up. Closest to what you'd deploy on a real edge gateway.

On the Pi:

```bash
# Required cgroup flags for k3s on Raspberry Pi OS / Ubuntu:
#   in /boot/firmware/cmdline.txt (Pi OS) or /boot/cmdline.txt, append:
#     cgroup_memory=1 cgroup_enable=memory
#   then reboot.

curl -sfL https://get.k3s.io | sh -
sudo kubectl get nodes      # the Pi shows up as control-plane,worker

# Make kubectl usable without sudo (optional):
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown "$USER":"$USER" ~/.kube/config
```

### B) External control plane (laptop / VM) + the Pi joined as a worker

Useful if you already have a kubeadm / k3s cluster elsewhere and want the
Pi to be just one node in it.

On the **server** (control plane, e.g. a laptop or VM, arm64 or x86):

```bash
curl -sfL https://get.k3s.io | sh -
sudo cat /var/lib/rancher/k3s/server/node-token       # copy the token
ip route get 1 | awk '{print $7; exit}'               # server IP
```

On the **Pi** (worker):

```bash
# Same cgroup tweak as in (A) if not already done.
K3S_URL=https://<server-ip>:6443 \
K3S_TOKEN=<token-from-server> \
sh -c 'curl -sfL https://get.k3s.io | sh -'
```

On the **server**, confirm the Pi joined:

```bash
kubectl get nodes -o wide
# NAME          STATUS   ROLES                  ...  INTERNAL-IP   ...
# server        Ready    control-plane,master   ...
# raspberrypi   Ready    <none>                 ...  192.168.x.y
```

Mark the Pi as the edge worker (optional but useful for `nodeSelector`):

```bash
kubectl label node raspberrypi node-role.kubernetes.io/edge=true
kubectl label node raspberrypi role=edge
```

## Pre-run tuning on the Pi

Same as in [`RaspberryPi_experiment/`](../RaspberryPi_experiment) — pin
the CPU governor so the Pi doesn't ramp frequency between invocations:

```bash
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # -> performance

# Optional: silence background daemons
sudo systemctl stop snapd cron unattended-upgrades 2>/dev/null || true
```

## Build the image

Pick **one** of the three:

**(1) Build on the Pi (native arm64), import directly into k3s**
— no registry needed:

```bash
# on the Pi
cd RaspberryPiK8s_experiment
docker build -t rt-contended-pi:0.1 .
# k3s uses containerd, not docker, so import the image into it:
docker save rt-contended-pi:0.1 | sudo k3s ctr images import -
sudo k3s ctr images ls | grep rt-contended-pi
```

If you don't have docker on the Pi, install `buildah` or just build with
`nerdctl` against k3s's containerd:

```bash
sudo nerdctl --namespace k8s.io build -t rt-contended-pi:0.1 .
```

**(2) Cross-build on an x86 dev machine, push to a registry**

```bash
# one-time:
docker buildx create --use
docker run --privileged --rm tonistiigi/binfmt --install all
# build & push:
PUSH=1 ./scripts/build_image.sh <registry>/rt-contended-pi:0.1
```

Then the Pi (and k3s) will pull from that registry.

**(3) Cross-build on x86, save tarball, copy to Pi, import**

```bash
LOAD=1 ./scripts/build_image.sh rt-contended-pi:0.1
docker save rt-contended-pi:0.1 -o rt-contended-pi.tar
scp rt-contended-pi.tar pi@<pi-ip>:/tmp/
ssh pi@<pi-ip> 'sudo k3s ctr images import /tmp/rt-contended-pi.tar'
```

## Run the experiment

```bash
chmod +x scripts/*.sh
kubectl get nodes        # note the Pi hostname (e.g. "raspberrypi")
./scripts/run_experiment.sh rt-contended-pi:0.1 raspberrypi
```

This will:

1. Render `k8s/workload-contended.yaml` (substituting the image and
   `nodeSelector` hostname).
2. `kubectl apply` it.
3. Wait until both containers print `[cA] done` / `[cB] done`.
4. `kubectl cp` the 8 CSVs (`cA_task0..2`, `cB_task0..2`,
   `cA_proc_stat`, `cB_proc_stat`) into `results/<timestamp>/`.
5. Delete the pod.

Then analyze:

```bash
python3 analyze.py results/<timestamp>/
```

## Comparing the three runs

Place the three `summary.txt` next to each other:

```text
ContendedAKS_experiment/results/run1/summary.txt
RaspberryPi_experiment/results/<ts>/summary.txt
RaspberryPiK8s_experiment/results/<ts>/summary.txt
```

What to look for:

- `exec_var` should still be tiny everywhere (the busy loop is
  deterministic) — if it's not on the Pi+K8s run, the container/cgroup
  layer is the culprit.
- `resp_var`, `p99(resp)`, `max(resp)`, `miss_rate` — increasing from
  bare-metal Pi → Pi+K8s tells you how much **K8s + containerd alone**
  cost you. Increasing further from Pi+K8s → AKS tells you how much the
  **cloud platform** (hypervisor, noisy neighbours, AKS DaemonSets) adds
  on top.
- `cA_proc_stat.csv` / `cB_proc_stat.csv` deltas: any non-zero `steal`
  column on AKS that's zero on the Pi confirms hypervisor preemption.

## Notes / gotchas

- The default `nodeSelector` uses `kubernetes.io/hostname: NODE_NAME`,
  which is the most portable label. If you instead want to target the
  `node-role.kubernetes.io/edge` label set above, edit
  [`k8s/workload-contended.yaml`](k8s/workload-contended.yaml).
- The pod is `restartPolicy: Never` and sleeps 10 h after the run; this
  is required so `kubectl cp` can still read the emptyDir before the pod
  is GC'd. The driver deletes the pod at the end.
- If you want **hard CPU pinning** (mirroring `taskset -c 0,1` from the
  bare-metal run), enable the kubelet's `static` CPU manager and request
  exactly `cpu: "2"` (integer, requests==limits) so the pod gets
  Guaranteed QoS. With k3s, edit `/etc/rancher/k3s/config.yaml`:
  ```yaml
  kubelet-arg:
    - "cpu-manager-policy=static"
    - "kube-reserved=cpu=500m"
    - "system-reserved=cpu=500m"
  ```
  then restart k3s. Otherwise the workload load-balances across all 4 Pi
  cores under CFS, which is the more realistic "edge K8s" scenario and is
  what the default manifest does.
