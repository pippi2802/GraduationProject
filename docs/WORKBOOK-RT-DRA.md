# RT-DRA — Installation, Requirements & Troubleshooting Workbook

> Scope: the full **RT Dynamic Resource Allocation** stack — RT-containerd, RT-runc,
> kubeadm cluster with the DRA feature, Calico CNI, and the `dra-rt-driver` Helm chart —
> plus how to verify and debug it.
>
> Prerequisite: the worker must already run the **HCBS RT kernel** with
> `CONFIG_RT_GROUP_SCHED=y` (see `WORKBOOK-HCBS-kernel.md`).

---

## 0. Architecture at a glance

```
Control plane (rt-cluster-cp-0, 10.0.1.4)        Worker (rt-cluster-worker-0, 10.0.2.4)
  kube-apiserver / scheduler / controller          RT kernel 6.16.0-rc4+ (cgroup v2)
  dra-rt-driver-controller  (does allocation)       RT-containerd /usr/local/bin/containerd
  kubectl (run as azureuser, NOT root)              RT-runc /usr/local/sbin/runc
  Calico via Tigera operator (calico-system ns)     dra-rt-driver-kubeletplugin
                                                     (NodePrepareResources + CDI + cgroup)
```

**Flow:** Pod with a ResourceClaim → scheduler asks driver if node is suitable →
controller allocates a CPU (worst-fit) and writes it into the node's
**NodeAllocationState (NAS)** CRD → kubeletplugin on the worker reads the allocation,
writes a **CDI spec** (injects `RT_CPUSET`, `RT_RUNTIME_PERIOD` env) → **RT-runc** writes
the RT budget into the container cgroup at container start.

---

## 1. Requirements

| Component | Version / note |
|---|---|
| Kubernetes (kubeadm/kubelet/kubectl) | **1.28.0** (pinned) |
| Container runtime | **RT-containerd** (fork, branch `rt`) — NOT stock containerd |
| Low-level runtime | **RT-runc** (fork, branch `rt`) at `/usr/local/sbin/runc` |
| Go | 1.22.5 (to build the runtimes) |
| Helm | v3.7+ |
| CNI | Calico (Tigera operator), pod CIDR `192.168.0.0/16` |
| Kernel | HCBS RT, `CONFIG_RT_GROUP_SCHED=y`, cgroup v2 |
| DRA feature gate | enabled at `kubeadm init` via config file |
| Driver image | `pippina2/dra-rt-driver:v0.1.1` |

DRA API specifics:
- API group `resource.k8s.io/v1alpha2` (claims need a nested `source:`).
- DRA plugin / driver name: `rt.resource.example.com`.
- ResourceClass: `rt.example.com`.
- Claim params CRD `rt.resource.example.com/v1alpha1` → `RtClaimParameters{count, runtime, period}`
  (defaults count 1, runtime 10, period 100).

---

## 2. Install — node prerequisites (every node)

The repo automates this in `rt-cluster/scripts/`. Order matters:
```
run-worker.sh  ->  prereq-common.sh  ->  common.sh  ->  worker-init.sh
run-cp.sh      ->  prereq-common.sh  ->  common.sh  ->  control-plane-init.sh
```

`prereq-common.sh` (Phase 0/1/3, runs on EVERY node) does:
- apt base packages + `build-essential pkg-config libseccomp-dev jq git`
- **disables swap** (now + `/etc/fstab`)
- loads `overlay` + `br_netfilter`, writes k8s sysctl
- installs **Go 1.22.5** to `/usr/local/go` (to build RT runtimes)
- installs **Helm 3**
- installs **kubeadm/kubelet/kubectl 1.28.0** from pkgs.k8s.io
- does **NOT** install Docker (it would shadow RT-containerd — see Troubleshooting)

> Manual equivalent of the key bits:
> ```bash
> sudo swapoff -a
> sudo modprobe overlay br_netfilter
> # sysctl: net.bridge.bridge-nf-call-iptables=1, ip_forward=1
> ```

---

## 3. Install — RT container runtimes (worker)

### RT-containerd
```bash
git clone -b rt https://github.com/nasim-samimi/containerd.git
cd containerd
make
sudo make install                 # installs to /usr/local/bin/containerd
containerd config default | sudo tee /etc/containerd/config.toml
```
Edit `/etc/containerd/config.toml` and set **all** of:
```toml
# under [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
SystemdCgroup = true
BinaryName    = "/usr/local/sbin/runc"
# under [plugins."io.containerd.grpc.v1.cri"]
enable_cdi    = true               # REQUIRED for DRA/CDI env injection
```

### RT-runc
```bash
sudo apt install -y libseccomp-dev
git clone -b rt https://github.com/nasim-samimi/runc.git
cd runc
make
sudo install -D -m0755 runc /usr/local/sbin/runc
```

### Restart and verify the RIGHT runtime is active
```bash
sudo systemctl daemon-reload
sudo systemctl restart containerd
sudo systemctl restart kubelet

# verify RT builds are the ones in use
sudo readlink -f /proc/$(pgrep -x containerd)/exe   # /usr/local/bin/containerd
which runc                                          # /usr/local/sbin/runc
sudo crictl info | grep -E 'BinaryName|SystemdCgroup|enableCDI'
```

---

## 4. Install — Kubernetes cluster

### Control plane
```bash
sudo kubeadm init --config=kubeadm-config.yaml     # enables DRA, podSubnet 192.168.0.0/16
mkdir -p $HOME/.kube && sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

### Calico CNI (Tigera operator) — pods live in `calico-system`
```bash
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/tigera-operator.yaml
until kubectl get crd installations.operator.tigera.io >/dev/null 2>&1; do sleep 3; done
cat <<'EOF' | kubectl apply -f -
apiVersion: operator.tigera.io/v1
kind: Installation
metadata: { name: default }
spec:
  calicoNetwork:
    ipPools:
    - name: default-ipv4-ippool
      blockSize: 26
      cidr: 192.168.0.0/16
      encapsulation: VXLANCrossSubnet
      natOutgoing: Enabled
      nodeSelector: all()
---
apiVersion: operator.tigera.io/v1
kind: APIServer
metadata: { name: default }
spec: {}
EOF
watch kubectl get pods -n calico-system -o wide
```

### Join the worker
```bash
# on CP:
kubeadm token create --print-join-command
# on worker (or via the repo's worker-init.sh which auto-runs /tmp/kubeadm-join.sh):
sudo kubeadm join --config=worker-config.yaml
```

---

## 5. Install — the RT-DRA driver (control plane)
```bash
helm upgrade -i \
  --create-namespace --namespace dra-rt-driver \
  dra-rt-driver \
  ./dra-rt-driver/deployments/helm/dra-rt-driver \
  --set image.repository=pippina2/dra-rt-driver \
  --set image.tag=v0.1.1 \
  --set pullPolicy=Always

kubectl -n dra-rt-driver get pods -o wide      # controller (CP) + kubeletplugin (worker)
kubectl get resourceclasses                    # rt.example.com
kubectl get nas -A                             # NodeAllocationState per node
```

---

## 6. Verify end-to-end (the rt-dra-verify workload)

`rt-dra-verify/` (in repo) creates a real RT claim and probes the result.
```bash
cd rt-dra-verify
./apply.sh                                      # run as azureuser, NOT sudo
kubectl -n rt-verify get pod -w                 # wait for Running
kubectl -n rt-verify logs rt-verify
```
Read the SUMMARY:
- ✅ correct: `SCHED_FIFO (RT) [matches paper]` + non-zero `cpu.rt_multi_runtime_us`.
- ❌ current state: `SCHED_OTHER only [RT NOT enforced]`, `cpu.rt_multi_runtime_us = 0 0 0 0`
  (see Known Issue §8).

What a healthy allocation looks like in the driver logs:
```
allocate, claimUID: ...  worstFitCpus: [1]
writecgrouptocdi, rtcdidevices: [runtime-100.period-1000 1]
prepared CDI devices: [runtime-100.period-1000/CPUSET=1]
```

---

## 7. Troubleshooting matrix

| Symptom | Cause | Fix |
|---|---|---|
| `kubectl ... localhost:8080 connection refused` | run as **root** (no kubeconfig) | run as `azureuser`, no `sudo`; or `KUBECONFIG=$HOME/.kube/config` |
| Worker `NotReady`, `/etc/cni/net.d` empty | Calico missing (e.g. after re-image) | reinstall Calico operator (§4) |
| `daemonsets calico-node not found` in kube-system | Calico is in **calico-system** (operator) | `kubectl -n calico-system get/rollout ds calico-node` |
| `FailedPrepareDynamicResources: rtCDIDevices is nil or incomplete: []` | first prepare attempt raced before NAS allocation written | usually self-heals on kubelet retry; the driver swallows the real error (commented out in `driver.go`) |
| Pod stuck `Pending`, `waiting for resource driver to allocate` | kubeletplugin not running / NAS not updated | `kubectl -n dra-rt-driver get pods -o wide`; check plugin logs |
| `containerd://Unknown` in `kubectl get nodes` | RT-containerd CRI version string not parsed | cosmetic; ignore |
| Pods cycle / sandbox recreated every ~6 min | **stock** containerd shadowing RT build | ensure `/proc/$(pgrep -x containerd)/exe` = `/usr/local/bin/containerd`; remove docker.io/containerd.io |
| `SystemdCgroup` mismatch, containers reaped | config.toml `SystemdCgroup=false` vs kubelet systemd | set `SystemdCgroup=true`, restart containerd |
| CDI env not injected into pod | `enable_cdi=false` in config.toml | set `enable_cdi=true`, restart containerd |
| `chrt -f` Operation not permitted | no RT budget in cgroup (and/or missing CAP_SYS_NICE) | add `securityContext.capabilities.add:[SYS_NICE]`; fix RT budget (§8) |

### Stock-containerd-shadowing check (a real bug hit before)
```bash
sudo readlink -f /proc/$(pgrep -x containerd)/exe   # MUST be /usr/local/bin/containerd
systemctl cat containerd | grep ExecStart           # MUST point at /usr/local/bin/containerd
# if docker.io/containerd.io got installed it drops /usr/bin/containerd and a unit that
# shadows the RT build -> remove it and restore the RT unit.
```

---

## 8. KNOWN OPEN ISSUE — RT enforcement not yet active

Everything **up to allocation** works (DRA allocate, CDI inject, cpuset pin, NAS util
accounting). The **kernel RT budget never lands in the container cgroup**, so SCHED_FIFO is
denied.

- **Confirmed root cause with the HCBS/rt-DRA authors:** original validation was on
  **cgroup v1 + an older kernel**. We run **cgroup v2 + 6.16.0-rc4+** → two mismatches.
- The driver's parent-slice seeder **`UpdateParentCgroup`** is **commented out** in
  `cmd/dra-rt-kubeletplugin/driver.go` and uses **v1 paths**
  (`/sys/fs/cgroup/cpu,cpuacct/kubepods.slice`). On v2 the path is
  `/sys/fs/cgroup/kubepods.slice` (no `cpu,cpuacct`).
- RT bandwidth is **hierarchical**: the container leaf can only get budget if every parent
  (`kubepods.slice` → `kubepods-besteffort.slice` → pod slice) is seeded first.

**Two resolution paths (decision pending):**
1. **Reproduce** on the authors' exact kernel + cgroup **v1** → green baseline first.
2. **Port** the driver (`UpdateParentCgroup` → v2 paths) + verify RT-runc leaf write against
   the newer kernel's `cpu.rt_multi_runtime_us` semantics.

**Questions for the authors:** exact validated kernel version + HCBS patch commit; is there
a cgroup-v2 branch of driver/RT-runc; expected write format/values for the parent slices.

---

## 9. Quick reference — key paths & names
```
RT containerd : /usr/local/bin/containerd   (systemd unit "containerd (RT build)")
RT runc       : /usr/local/sbin/runc
containerd cfg: /etc/containerd/config.toml (SystemdCgroup=true, BinaryName, enable_cdi=true)
driver ns     : dra-rt-driver        image pippina2/dra-rt-driver:v0.1.1
plugin name   : rt.resource.example.com
ResourceClass : rt.example.com
NAS CRD       : nodeallocationstates (singular: nas)
verify        : rt-dra-verify/ (apply.sh, rt-verify.yaml, verify.sh)
Calico ns     : calico-system  (Tigera operator, calico v3.28.0)
pod CIDR      : 192.168.0.0/16
```
