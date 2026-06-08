#!/bin/bash
set -e

echo "Starting worker node initialization..."

# Update system
apt-get update
apt-get upgrade -y

# Install required packages
apt-get install -y \
    curl \
    wget \
    ca-certificates \
    gnupg \
    lsb-release \
    apt-transport-https \
    software-properties-common \
    jq

# Install container runtime (containerd)
echo "Installing containerd..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y containerd.io

# Configure containerd
mkdir -p /etc/containerd
containerd config default > /etc/containerd/config.toml

# Fix containerd configuration for Kubernetes
sed -i 's/^disabled_plugins = \[\]/disabled_plugins = []/' /etc/containerd/config.toml

systemctl restart containerd

# Disable swap
swapoff -a
sed -i '/ swap / s/^/#/' /etc/fstab

# Configure kernel modules
cat << EOF > /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

modprobe overlay
modprobe br_netfilter

# Configure kernel parameters
cat << EOF > /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF

sysctl --system

# Install kubeadm, kubelet, kubectl
echo "Installing Kubernetes tools..."
curl -fsSLo /usr/share/keyrings/kubernetes-archive-keyring.gpg https://dl.k8s.io/apt/doc/apt-key.gpg

echo "deb [signed-by=/usr/share/keyrings/kubernetes-archive-keyring.gpg] https://apt.kubernetes.io/ kubernetes-xenial main" | tee /etc/apt/sources.list.d/kubernetes.list

apt-get update
apt-get install -y kubelet kubeadm kubectl

# Hold versions to prevent auto-upgrade
apt-mark hold kubelet kubeadm kubectl

# Enable and start kubelet
systemctl daemon-reload
systemctl enable kubelet

echo "Worker node initialization completed successfully!"
echo "Ready to join cluster..."
