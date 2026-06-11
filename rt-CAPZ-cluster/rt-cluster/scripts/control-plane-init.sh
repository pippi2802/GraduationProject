#!/bin/bash
# -----------------------------------------------------------------------------
# control-plane-init.sh
#
# Phase 4a: bring up the kubeadm control plane and install:
#   * the Kubernetes API + control plane (kubeadm init with DRA alpha gates)
#   * the Calico CNI (operator install, pod CIDR 192.168.0.0/16)
#   * the dra-rt-driver (Helm chart from the cloned repo)
#
# Also:
#   * (best-effort) mounts /dev/sdc1 at /var/lib/etcddisk if the disk exists
#     (Azure data disk for etcd separation)
#   * captures the worker join command at /var/lib/kubeadm-join.sh
#     (perms 0600) so you can SSH and copy it to each worker manually
#
# Assumes prereq-common.sh and common.sh have run.
# Idempotent via /var/lib/rt-stack/markers/control-plane-init.done.
#
# Tunables (via env vars):
#   RT_API_ENDPOINT   override controlPlaneEndpoint (default: <node-ip>:6443)
#   RT_POD_CIDR       pod subnet (default: 192.168.0.0/16 -- Calico's default)
#   RT_UNTAINT_CP     "true" to allow pods on the CP (single-node testing)
#   RT_SKIP_DRA       "true" to skip Helm-installing dra-rt-driver
# -----------------------------------------------------------------------------
set -Eeuo pipefail

# shellcheck source=lib/common-functions.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common-functions.sh"

rt_strict_mode
rt_setup_logging control-plane-init
rt_skip_if_done   control-plane-init

if ! rt_already_done prereq-common; then echo "[error] run prereq-common.sh first" >&2; exit 1; fi
if ! rt_already_done common;         then echo "[error] run common.sh first"         >&2; exit 1; fi

export PATH=/usr/local/go/bin:/usr/local/bin:/usr/local/sbin:$PATH

# -----------------------------------------------------------------------------
# 1. Optional etcd data-disk setup (Azure-attached /dev/sdc, label etcd_disk)
# -----------------------------------------------------------------------------
DISK="/dev/sdc"; PART="${DISK}1"; MOUNTPOINT="/var/lib/etcddisk"; LABEL="etcd_disk"
if [[ -b "$DISK" ]]; then
    echo "[etcd-disk] $DISK present, configuring"
    if ! lsblk -no NAME "$PART" >/dev/null 2>&1; then
        parted -s "$DISK" mklabel gpt mkpart primary 0% 100%
        sleep 2
    fi
    blkid | grep -q "$LABEL" || mkfs.ext4 -F -L "$LABEL" "$PART"
    install -d -m 0755 "$MOUNTPOINT"
    grep -q "$LABEL" /etc/fstab || \
        echo "LABEL=$LABEL $MOUNTPOINT ext4 defaults 0 2" >> /etc/fstab
    mount | grep -q "$MOUNTPOINT" || mount "$MOUNTPOINT"
else
    echo "[etcd-disk] $DISK not present, skipping"
fi

# -----------------------------------------------------------------------------
# 2. Clone dra-rt-driver (needed for the Helm chart and the kubeadm-config.yaml
#    that some forks ship). Best-effort -- we generate our own kubeadm-config.
# -----------------------------------------------------------------------------
DRA_SRC="${RT_WORKDIR}/dra-rt-driver"
rt_git_clone https://github.com/nasim-samimi/dra-rt-driver.git "$DRA_SRC"

# -----------------------------------------------------------------------------
# 3. Generate a kubeadm config that enables DRA on every component.
# -----------------------------------------------------------------------------
NODE_IP="$(ip -4 -o route get 1 | awk '{print $7; exit}')"
APISERVER_ENDPOINT="${RT_API_ENDPOINT:-${NODE_IP}:6443}"
POD_CIDR="${RT_POD_CIDR:-192.168.0.0/16}"
KUBEADM_CFG="${RT_WORKDIR}/kubeadm-config.yaml"

cat >"$KUBEADM_CFG" <<EOF
apiVersion: kubeadm.k8s.io/v1beta3
kind: InitConfiguration
localAPIEndpoint:
  advertiseAddress: "${NODE_IP}"
  bindPort: 6443
nodeRegistration:
  criSocket: unix:///run/containerd/containerd.sock
  kubeletExtraArgs:
    feature-gates: "DynamicResourceAllocation=true"
---
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
kubernetesVersion: v1.28.0
controlPlaneEndpoint: "${APISERVER_ENDPOINT}"
networking:
  podSubnet: "${POD_CIDR}"
  serviceSubnet: "10.96.0.0/12"
featureGates:
  DynamicResourceAllocation: true
apiServer:
  extraArgs:
    feature-gates: "DynamicResourceAllocation=true"
    runtime-config: "resource.k8s.io/v1alpha2=true"
controllerManager:
  extraArgs:
    feature-gates: "DynamicResourceAllocation=true"
scheduler:
  extraArgs:
    feature-gates: "DynamicResourceAllocation=true"
---
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
cgroupDriver: systemd
featureGates:
  DynamicResourceAllocation: true
EOF

echo "[kubeadm] config:"
cat "$KUBEADM_CFG"

# -----------------------------------------------------------------------------
# 4. kubeadm init (skip if already initialised)
# -----------------------------------------------------------------------------
if [[ -f /etc/kubernetes/admin.conf ]]; then
    echo "[kubeadm] /etc/kubernetes/admin.conf exists, skipping init"
else
    echo "[kubeadm] running init"
    kubeadm init --config="$KUBEADM_CFG" --upload-certs
fi

# -----------------------------------------------------------------------------
# 5. kubeconfig for root and for the login user (azureuser by default)
# -----------------------------------------------------------------------------
install -d -m 0755 /root/.kube
cp -f /etc/kubernetes/admin.conf /root/.kube/config
chown root:root /root/.kube/config

LOGIN_USER="${SUDO_USER:-azureuser}"
if id "$LOGIN_USER" &>/dev/null; then
    LOGIN_HOME="$(getent passwd "$LOGIN_USER" | cut -d: -f6)"
    install -d -m 0755 -o "$LOGIN_USER" -g "$LOGIN_USER" "$LOGIN_HOME/.kube"
    cp -f /etc/kubernetes/admin.conf "$LOGIN_HOME/.kube/config"
    chown "$LOGIN_USER":"$LOGIN_USER" "$LOGIN_HOME/.kube/config"
fi

export KUBECONFIG=/etc/kubernetes/admin.conf

# -----------------------------------------------------------------------------
# 6. Wait for the API server, then install Calico
# -----------------------------------------------------------------------------
echo "[wait] kube-apiserver to respond"
for _ in $(seq 1 60); do
    kubectl get --raw=/readyz >/dev/null 2>&1 && break
    sleep 5
done

CALICO_VERSION="v3.28.0"
if ! kubectl get ns tigera-operator >/dev/null 2>&1; then
    echo "[calico] installing operator $CALICO_VERSION"
    kubectl create -f "https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VERSION}/manifests/tigera-operator.yaml"
fi

# Wait for the operator CRDs to exist before applying the Installation resource.
for _ in $(seq 1 60); do
    kubectl get crd installations.operator.tigera.io >/dev/null 2>&1 && break
    sleep 5
done

cat <<EOF | kubectl apply -f -
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    ipPools:
    - name: default-ipv4-ippool
      blockSize: 26
      cidr: ${POD_CIDR}
      encapsulation: VXLANCrossSubnet
      natOutgoing: Enabled
      nodeSelector: all()
---
apiVersion: operator.tigera.io/v1
kind: APIServer
metadata:
  name: default
spec: {}
EOF

# -----------------------------------------------------------------------------
# 7. Single-node convenience: optionally untaint the CP
# -----------------------------------------------------------------------------
if [[ "${RT_UNTAINT_CP:-false}" == "true" ]]; then
    echo "[cp] removing NoSchedule taint (single-node mode)"
    kubectl taint nodes --all node-role.kubernetes.io/control-plane:NoSchedule- 2>/dev/null || true
fi

# -----------------------------------------------------------------------------
# 8. Persist the worker join command (manual distribution)
# -----------------------------------------------------------------------------
JOIN_FILE="/var/lib/kubeadm-join.sh"
echo "[join] regenerating worker join command -> $JOIN_FILE"
{
    echo "#!/bin/bash"
    echo "# kubeadm join command generated $(date -u +%FT%TZ) on $(hostname)"
    kubeadm token create --print-join-command --ttl 0
} > "$JOIN_FILE"
chmod 0600 "$JOIN_FILE"
echo "[join] saved (chmod 600). scp this file to each worker as root:"
echo "       scp $JOIN_FILE worker:/tmp/kubeadm-join.sh && ssh worker 'sudo bash /tmp/kubeadm-join.sh'"

# -----------------------------------------------------------------------------
# 9. Wait for Calico to come up, then install dra-rt-driver
# -----------------------------------------------------------------------------
echo "[wait] Calico apiserver/operator"
kubectl -n calico-system   rollout status ds/calico-node --timeout=10m || true
kubectl -n calico-system   rollout status deploy/calico-kube-controllers --timeout=10m || true

if [[ "${RT_SKIP_DRA:-false}" != "true" ]]; then
    CHART_DIR="$(find "$DRA_SRC" -type f -name Chart.yaml -path '*dra-rt-driver*' 2>/dev/null | head -n1 | xargs -r dirname)"
    if [[ -n "$CHART_DIR" && -d "$CHART_DIR" ]]; then
        echo "[dra] installing chart from $CHART_DIR"
        helm upgrade --install dra-rt-driver "$CHART_DIR" \
            --namespace dra-rt-driver --create-namespace
    else
        echo "[dra] WARNING: no Helm chart found under $DRA_SRC; install dra-rt-driver manually"
    fi
fi

# -----------------------------------------------------------------------------
# 10. Final sanity
# -----------------------------------------------------------------------------
kubectl get nodes -o wide || true
kubectl get pods -A      || true

rt_mark_done control-plane-init
