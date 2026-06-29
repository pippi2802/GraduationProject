# rt-cluster bootstrap scripts

These scripts turn a fresh Ubuntu VM (24.04 or 22.04 — codename auto-detected)
provisioned by the Bicep template into a kubeadm-managed Kubernetes 1.28
cluster with **RT-containerd**, **RT-runc**, **CDI** and the **DRA alpha
feature** enabled, ready for the `dra-rt-driver`.

> The Bicep template is **not** modified by these scripts. Run them via
> cloud-init `customData`, `az vm run-command`, or by hand.

## Layout

```
scripts/
├── lib/
│   └── common-functions.sh   # sourced helpers (logging, markers, apt locks)
├── prereq-common.sh          # phase 0+1+3: OS + toolchain + kube packages
├── common.sh                 # phase 2:     RT-containerd + RT-runc + CDI
├── control-plane-init.sh     # phase 4a:    kubeadm init + Calico + dra-rt-driver
├── worker-init.sh            # phase 4b:    waits or runs /tmp/kubeadm-join.sh
├── run-cp.sh                 # one-shot orchestrator for CP VMs
├── run-worker.sh             # one-shot orchestrator for worker VMs
└── docker-install.sh         # LEGACY -- not used by the RT pipeline
```

## Execution pipeline

```
┌────────────────────────┐        ┌────────────────────────┐
│ control plane VM       │        │ worker VM              │
│                        │        │                        │
│ run-cp.sh:             │        │ run-worker.sh:         │
│   prereq-common.sh     │        │   prereq-common.sh     │
│   common.sh            │        │   common.sh            │
│   control-plane-init.sh│        │   worker-init.sh       │
│                        │        │   (waits for join cmd) │
│   -> /var/lib/         │        │                        │
│      kubeadm-join.sh   │──scp──▶│   /tmp/kubeadm-join.sh │
└────────────────────────┘        └────────────────────────┘
```

Each phase is **idempotent**: it writes
`/var/lib/rt-stack/markers/<phase>.done` on success and exits 0 immediately
if that marker exists. Per-phase logs go to `/var/log/rt-stack/<phase>.log`.

### Manual run

```bash
# on every CP VM:
sudo bash scripts/run-cp.sh

# on every worker VM:
sudo bash scripts/run-worker.sh

# after run-cp.sh finishes, from your workstation or a jumpbox:
scp azureuser@<cp-ip>:/var/lib/kubeadm-join.sh /tmp/join.sh
scp /tmp/join.sh azureuser@<worker-ip>:/tmp/kubeadm-join.sh
ssh azureuser@<worker-ip> 'sudo bash /tmp/kubeadm-join.sh'
# or simply re-run sudo bash scripts/run-worker.sh once the file is in place
```

### cloud-init delivery (recommended)

Drop one of the `run-*.sh` scripts into the VM as `customData` (Bicep
`osProfile.customData` -> base64-encoded shell script with a `#!/bin/bash`
shebang), and ship `scripts/` somewhere on the image (custom Packer image is
the cleanest path; otherwise `git clone` inside the cloud-init script).

## Phase reference

| Phase | Script | Marker | What it owns |
|---|---|---|---|
| 0+1+3 | `prereq-common.sh` | `prereq-common.done` | apt, swap, sysctl, modules, Go, Helm, kubeadm/kubelet/kubectl |
| 2 | `common.sh` | `common.done` | purge Docker, build & install RT-containerd + RT-runc, systemd unit, `/etc/containerd/config.toml` with `enable_cdi=true`, `SystemdCgroup=true`, `BinaryName=/usr/local/sbin/runc`, CNI plugin binaries |
| 4a | `control-plane-init.sh` | `control-plane-init.done` | etcd disk (if `/dev/sdc` present), kubeadm-config.yaml (DRA gates), `kubeadm init`, kubeconfig for `azureuser`, Calico, dra-rt-driver Helm chart, `/var/lib/kubeadm-join.sh` |
| 4b | `worker-init.sh` | `worker-init.done` (only after join) | runs `/tmp/kubeadm-join.sh` if present |

## Tunables (env vars)

| Var | Default | Effect |
|---|---|---|
| `RT_WORKDIR` | `/opt/rt-stack` | where source repos are cloned & built |
| `RT_API_ENDPOINT` | `<node-ip>:6443` | `controlPlaneEndpoint` in kubeadm config (set this to the LB IP for HA) |
| `RT_POD_CIDR` | `192.168.0.0/16` | Pod subnet (Calico default) |
| `RT_UNTAINT_CP` | `false` | Set `true` for single-node clusters (lets pods run on the CP) |
| `RT_SKIP_DRA` | `false` | Skip the dra-rt-driver Helm install |
| `RT_JOIN_FILE` | `/tmp/kubeadm-join.sh` | Worker reads the join command from here |

## Why no Docker

`docker-ce` pulls in the `containerd.io` and `runc` packages, which install
`/usr/bin/containerd` and `/usr/sbin/runc`. These would silently shadow the
RT builds (`/usr/local/bin/containerd` and `/usr/local/sbin/runc`) at runtime,
and `SCHED_DEADLINE` would not be enforced. `common.sh` therefore explicitly
purges those packages before installing the RT runtime. `docker-install.sh`
is kept in the tree as a reference only — it is **not** part of the pipeline.

## Validation checklist

After `run-cp.sh` finishes on the CP and at least one worker has joined:

```bash
# 1. RT runtime really is the one running:
readlink -f /proc/$(pidof -s containerd)/exe   # -> /usr/local/bin/containerd
crictl info | grep -E '(enable_cdi|BinaryName|SystemdCgroup)'

# 2. DRA API is registered:
kubectl api-resources | grep resource.k8s.io

# 3. Cluster + dra-rt-driver:
kubectl get nodes -o wide
kubectl -n dra-rt-driver get pods
kubectl get resourceclasses

# 4. End-to-end: apply a RT ResourceClaim + Pod from dra-rt-driver/demo/
```
