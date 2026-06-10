#!/bin/bash
set -e

# Install Docker and the prerequisites for RT-containerd and CNI plugins

echo "Installing Docker..."
# Install prerequisites

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker's repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package lists
sudo apt-get update

# Define the version you want to install
VERSION_STRING="5:20.10.24~3-0~ubuntu-jammy"

# Install Docker CE and CLI at the specific version, with compatible runtime and plugins
sudo apt-get install -y \
  docker-ce=$VERSION_STRING \
  docker-ce-cli=$VERSION_STRING \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin


echo "Installing goland 1.22.5..."
wget https://go.dev/dl/go1.22.5.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.22.5.linux-amd64.tar.gz

export PATH=$PATH:/usr/local/go/bin
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin

source ~/.bashrc

echo "Installing Helm 3.21.0..."
curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get-helm-3 > get_helm.sh
chmod 700 get_helm.sh
./get_helm.sh

# Kubeadm

KUBEADM_VERSION="v1.28.0"
KUBELET_VERSION="v1.28.0"
KUBECTL_VERSION="v1.28.0"

KUBEADM_CURRENT_VERSION=$(kubeadm version -o short 2>/dev/null || echo "none")


echo "Installing kubeadm $KUBEADM_VERSION..."
echo "Stopping Kubelet..."
systemctl stop kubelet
echo "Stopped Kubelet successfully."
echo "Unholding kubeadm kubelet and kubectl..."
apt-mark unhold kubeadm kubelet kubectl
echo "Removing existing kubeadm, kubelet, kubectl..."
apt remove -y kubeadm kubelet kubectl

echo "Installing kubeadm $KUBEADM_VERSION..."
apt install -y apt-transport-https ca-certificates curl
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.28/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-1-28.gpg
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-1-28.gpg] https://pkgs.k8s.io/core:/stable:/v1.28/deb/ /" | sudo tee /etc/apt/sources.list.d/kubernetes-1-28.list
apt update

apt install -y kubeadm=1.28.0-1.1 kubelet=1.28.0-1.1 kubectl=1.28.0-1.1

apt-mark hold kubeadm kubelet kubectl

systemctl daemon-reload
KUBEADM_CURRENT_VERSION=$(kubeadm version -o short)
echo "Installed kubeadm version: $KUBEADM_CURRENT_VERSION" 
apt-mark hold kubelet kubeadm kubectl
systemctl daemon-reload
systemctl enable kubelet
echo "kubeadm kubectl and kubelet $KUBEADM_VERSION installed successfully. Kubelet not yet running"

