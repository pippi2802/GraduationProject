#!/bin/bash
set -e

# =============================================================================
# WARNING -- DO NOT RUN THIS ON RT CLUSTER NODES (control-plane or workers).
#
# This installs the stock `containerd.io` package, which drops
# /usr/bin/containerd + /lib/systemd/system/containerd.service and SHADOWS the
# RT-patched containerd installed by common.sh at /usr/local/bin/containerd.
# The result is a node running stock containerd with SystemdCgroup=false, which
# fights the kubelet's systemd cgroup driver and makes every pod on the node
# crash-loop every ~74s. See scripts/TROUBLESHOOTING-containerd.md.
#
# This script is LEGACY and intended ONLY for a separate image-BUILD VM that
# needs Docker/Buildx to build container images -- never a cluster node.
# =============================================================================
if [[ -x /usr/local/bin/containerd ]]; then
    echo "[abort] /usr/local/bin/containerd (RT build) is present: this looks like" >&2
    echo "        an RT cluster node. Installing Docker here would shadow it." >&2
    echo "        Refusing to continue. See TROUBLESHOOTING-containerd.md." >&2
    echo "        Set ALLOW_DOCKER_ON_RT_NODE=1 to override (NOT recommended)." >&2
    [[ "${ALLOW_DOCKER_ON_RT_NODE:-0}" == "1" ]] || exit 1
fi

# Install Docker with Buildx and CDI
sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc | cut -f1)

# Add Docker's official GPG key:
echo "Adding Docker's official GPG key..."
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
echo "Installing Docker with Buildx and CDI..."
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin