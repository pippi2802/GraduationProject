#!/bin/bash
# -----------------------------------------------------------------------------
# prereq-common.sh
#
# Phase 0+1+3:  base OS prep + build toolchain + Kubernetes packages.
# Runs on EVERY node (control plane and workers).
#
# Idempotent: safe to re-run; exits early once /var/lib/rt-stack/markers/
# prereq-common.done exists.
#
# What it does:
#   * waits for cloud-init/apt locks, sets noninteractive front-end
#   * installs build deps, jq, git, etc.
#   * disables swap (now and in /etc/fstab)
#   * loads br_netfilter + overlay and writes sysctl rules for Kubernetes
#   * installs Go 1.22.5 to /usr/local/go (needed to build RT-containerd & RT-runc)
#   * installs Helm 3 (used by the CP to install dra-rt-driver)
#   * installs kubeadm/kubelet/kubectl pinned to 1.28.0 from pkgs.k8s.io,
#     guarded so it does NOT fail on a brand-new VM where kubelet is absent.
#
# What it does NOT do:
#   * does not install Docker (replaced by RT-containerd built from source)
#   * does not start kubelet (kubeadm init/join will do that)
# -----------------------------------------------------------------------------
set -Eeuo pipefail

# shellcheck source=lib/common-functions.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common-functions.sh"

rt_strict_mode
rt_setup_logging prereq-common
rt_skip_if_done   prereq-common

CODENAME="$(rt_codename)"
ARCH="$(rt_arch)"
echo "[info] Ubuntu codename=$CODENAME arch=$ARCH"

# -----------------------------------------------------------------------------
# 1. OS update + base packages
# -----------------------------------------------------------------------------
rt_apt_update
rt_wait_apt
apt-get upgrade -y

rt_apt_install \
    curl wget ca-certificates gnupg lsb-release \
    apt-transport-https software-properties-common \
    jq git parted \
    build-essential pkg-config libseccomp-dev

# -----------------------------------------------------------------------------
# 2. Disable swap (kubelet refuses to start otherwise on 1.28)
# -----------------------------------------------------------------------------
swapoff -a || true
sed -i.bak '/[[:space:]]swap[[:space:]]/ s/^\([^#]\)/#\1/' /etc/fstab

# -----------------------------------------------------------------------------
# 3. Kernel modules + sysctl (required by kubeadm preflight on CP & workers)
# -----------------------------------------------------------------------------
cat >/etc/modules-load.d/k8s.conf <<EOF
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter

cat >/etc/sysctl.d/99-k8s.conf <<EOF
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sysctl --system >/dev/null

# -----------------------------------------------------------------------------
# 4. Go 1.22.5
# -----------------------------------------------------------------------------
GO_VERSION="1.22.5"
if /usr/local/go/bin/go version 2>/dev/null | grep -q "go${GO_VERSION} "; then
    echo "[go] $GO_VERSION already installed"
else
    echo "[go] installing $GO_VERSION"
    GO_TGZ="/tmp/go${GO_VERSION}.linux-${ARCH}.tar.gz"
    curl -fsSL -o "$GO_TGZ" "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz"
    rm -rf /usr/local/go
    tar -C /usr/local -xzf "$GO_TGZ"
    rm -f "$GO_TGZ"
fi
# Make Go available to every login shell AND to non-interactive cloud-init scripts.
cat >/etc/profile.d/go.sh <<'EOF'
export PATH=/usr/local/go/bin:$PATH
EOF
chmod 0755 /etc/profile.d/go.sh
export PATH=/usr/local/go/bin:$PATH

# -----------------------------------------------------------------------------
# 5. Helm 3
# -----------------------------------------------------------------------------
if ! have_cmd helm; then
    echo "[helm] installing Helm 3"
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 -o /tmp/get-helm-3.sh
    chmod 700 /tmp/get-helm-3.sh
    /tmp/get-helm-3.sh
    rm -f /tmp/get-helm-3.sh
else
    echo "[helm] already installed: $(helm version --short)"
fi

# -----------------------------------------------------------------------------
# 6. Kubernetes packages (kubeadm/kubelet/kubectl @ 1.28.0)
#    Guarded so it does not blow up on a fresh OS (the bug you hit before).
# -----------------------------------------------------------------------------
K8S_MINOR="v1.28"
K8S_PKG_VERSION="1.28.0-1.1"
KEYRING="/etc/apt/keyrings/kubernetes-${K8S_MINOR//./-}.gpg"
APT_LIST="/etc/apt/sources.list.d/kubernetes-${K8S_MINOR//./-}.list"

install -d -m 0755 /etc/apt/keyrings
if [[ ! -f "$KEYRING" ]]; then
    curl -fsSL "https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/Release.key" \
        | gpg --dearmor -o "$KEYRING"
fi
if [[ ! -f "$APT_LIST" ]]; then
    echo "deb [signed-by=${KEYRING}] https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/ /" \
        > "$APT_LIST"
fi
rt_apt_update

# Stop & remove only if currently present -- skip cleanly on first-time installs.
systemctl stop kubelet 2>/dev/null || true
apt-mark unhold kubeadm kubelet kubectl 2>/dev/null || true
for pkg in kubeadm kubelet kubectl; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
        apt-get remove -y "$pkg" || true
    fi
done

rt_apt_install \
    kubeadm="${K8S_PKG_VERSION}" \
    kubelet="${K8S_PKG_VERSION}" \
    kubectl="${K8S_PKG_VERSION}"
apt-mark hold kubeadm kubelet kubectl

systemctl daemon-reload
systemctl enable kubelet   # do NOT start; kubeadm init/join will.

echo "[k8s] installed: $(kubeadm version -o short)"

rt_mark_done prereq-common
