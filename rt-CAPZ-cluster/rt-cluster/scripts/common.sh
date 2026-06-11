#!/bin/bash
# -----------------------------------------------------------------------------
# common.sh
#
# Phase 2:  build & install the RT container runtime stack on EVERY node.
#
#   RT-containerd ->  /usr/local/bin/containerd
#   RT-runc       ->  /usr/local/sbin/runc
#   systemd unit  ->  /etc/systemd/system/containerd.service
#                     (ExecStart=/usr/local/bin/containerd, so no stale Docker
#                     /usr/bin/containerd can ever shadow it)
#   config.toml   ->  /etc/containerd/config.toml
#                     with CDI enabled, SystemdCgroup=true, BinaryName pointing
#                     at /usr/local/sbin/runc.
#
# Assumes prereq-common.sh has run (Go + build tools present).
# Idempotent via /var/lib/rt-stack/markers/common.done.
# -----------------------------------------------------------------------------
set -Eeuo pipefail

# shellcheck source=lib/common-functions.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common-functions.sh"

rt_strict_mode
rt_setup_logging common
rt_skip_if_done   common

# Hard requirement: phase 1 must have run.
if ! rt_already_done prereq-common; then
    echo "[error] prereq-common phase has not completed; run prereq-common.sh first" >&2
    exit 1
fi

export PATH=/usr/local/go/bin:$PATH

# -----------------------------------------------------------------------------
# 1. Purge any stock Docker / containerd packages that would shadow the RT
#    binaries via /usr/bin/containerd or /usr/sbin/runc. We want exactly one
#    containerd and one runc on the system.
# -----------------------------------------------------------------------------
echo "[purge] removing stock docker/containerd/runc packages if present"
systemctl stop containerd 2>/dev/null || true
systemctl stop docker     2>/dev/null || true
for pkg in containerd containerd.io docker.io docker-ce docker-ce-cli \
           docker-buildx-plugin docker-compose-plugin runc; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
        apt-get remove -y --purge "$pkg" || true
    fi
done
apt-get autoremove -y || true
# Belt & braces: drop stale binaries that may survive a partial purge.
rm -f /usr/bin/containerd /usr/bin/containerd-shim* /usr/sbin/runc

# -----------------------------------------------------------------------------
# 2. Build & install RT-containerd
# -----------------------------------------------------------------------------
CONTAINERD_SRC="${RT_WORKDIR}/containerd"
rt_git_clone https://github.com/nasim-samimi/containerd.git "$CONTAINERD_SRC" rt
(
    cd "$CONTAINERD_SRC"
    echo "[build] containerd $(git rev-parse --short HEAD)"
    make
    make install                            # installs to /usr/local/bin
)
echo "[verify] containerd --version: $(/usr/local/bin/containerd --version)"

# -----------------------------------------------------------------------------
# 3. Build & install RT-runc
# -----------------------------------------------------------------------------
RUNC_SRC="${RT_WORKDIR}/runc"
rt_git_clone https://github.com/nasim-samimi/runc.git "$RUNC_SRC" rt
(
    cd "$RUNC_SRC"
    echo "[build] runc $(git rev-parse --short HEAD)"
    make
    install -D -m 0755 runc /usr/local/sbin/runc
)
echo "[verify] runc --version: $(/usr/local/sbin/runc --version | head -n1)"

# -----------------------------------------------------------------------------
# 4. systemd unit for the RT containerd (upstream make install does NOT ship one)
# -----------------------------------------------------------------------------
cat >/etc/systemd/system/containerd.service <<'EOF'
[Unit]
Description=containerd container runtime (RT build)
Documentation=https://containerd.io
After=network.target local-fs.target

[Service]
ExecStartPre=-/sbin/modprobe overlay
ExecStart=/usr/local/bin/containerd
Type=notify
Delegate=yes
KillMode=process
Restart=always
RestartSec=5
LimitNPROC=infinity
LimitCORE=infinity
LimitNOFILE=1048576
TasksMax=infinity
OOMScoreAdjust=-999

[Install]
WantedBy=multi-user.target
EOF

# -----------------------------------------------------------------------------
# 5. /etc/containerd/config.toml -- generated then patched for CDI + RT-runc.
# -----------------------------------------------------------------------------
install -d -m 0755 /etc/containerd
/usr/local/bin/containerd config default >/etc/containerd/config.toml

# 5a. cgroup driver -> systemd (required: kubelet defaults to systemd since 1.22)
sed -i 's|SystemdCgroup = false|SystemdCgroup = true|' /etc/containerd/config.toml

# 5b. force the runc binary to our RT build (don't trust $PATH)
sed -i 's|BinaryName = ""|BinaryName = "/usr/local/sbin/runc"|' /etc/containerd/config.toml

# 5c. Enable CDI under [plugins."io.containerd.grpc.v1.cri"] (required for DRA
#     to inject RT parameters via CDI specs). Only inject the keys once.
if ! grep -q 'enable_cdi' /etc/containerd/config.toml; then
    python3 - <<'PY'
import re, pathlib
p = pathlib.Path("/etc/containerd/config.toml")
text = p.read_text()
hdr = '[plugins."io.containerd.grpc.v1.cri"]'
ins = ('\n    enable_cdi = true'
       '\n    cdi_spec_dirs = ["/etc/cdi", "/var/run/cdi"]')
if hdr in text and "enable_cdi" not in text:
    text = text.replace(hdr, hdr + ins, 1)
    p.write_text(text)
PY
fi

# 5d. crictl pointed at our containerd socket (handy for debugging).
cat >/etc/crictl.yaml <<EOF
runtime-endpoint: unix:///run/containerd/containerd.sock
image-endpoint: unix:///run/containerd/containerd.sock
timeout: 10
EOF

# -----------------------------------------------------------------------------
# 6. CNI plugin binaries (the network plugin -- Calico -- is installed by the
#    CP script; here we just need the CNI binary tree to exist for kubelet).
# -----------------------------------------------------------------------------
CNI_VERSION="v1.4.1"
CNI_DIR="/opt/cni/bin"
if [[ ! -x "${CNI_DIR}/bridge" ]]; then
    echo "[cni] installing plugins ${CNI_VERSION}"
    install -d -m 0755 "$CNI_DIR"
    curl -fsSL -o /tmp/cni.tgz \
        "https://github.com/containernetworking/plugins/releases/download/${CNI_VERSION}/cni-plugins-linux-$(rt_arch)-${CNI_VERSION}.tgz"
    tar -C "$CNI_DIR" -xzf /tmp/cni.tgz
    rm -f /tmp/cni.tgz
fi

# IMPORTANT: do NOT drop a 10-containerd-bridge.conf in /etc/cni/net.d here.
# Calico (installed by control-plane-init.sh) will own that directory, and any
# pre-existing conf that sorts before Calico's will silently break pod
# networking on this node.
install -d -m 0755 /etc/cni/net.d
rm -f /etc/cni/net.d/10-containerd-bridge.conf

# -----------------------------------------------------------------------------
# 7. Bring containerd up
# -----------------------------------------------------------------------------
systemctl daemon-reload
systemctl enable --now containerd

# Sanity check: are we actually talking to /usr/local/bin/containerd?
sleep 2
echo "[verify] running binary: $(readlink -f /proc/$(pidof -s containerd)/exe || echo unknown)"
echo "[verify] containerd status:"
systemctl is-active containerd
crictl info --output go-template --template '{{.config.containerd.defaultRuntimeName}} / runc: {{(index .config.containerd.runtimes "runc").options.BinaryName}}' || true

rt_mark_done common
