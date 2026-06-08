#!/bin/bash
set -e

cd ../dra-rt-driver
# Disable swap
swapoff -a
sed -i '/ swap / s/^/#/' /etc/fstab

# Start kubeadm init
echo "Starting kubeadm init..."
if [ ! -f /etc/kubernetes/admin.conf ]; then
    echo "Running kubeadm init..."
    kubeadm init --config=kubeadm-config.yaml
else
    echo "kubeadm already initialized, skipping."
fi
sudo systemctl daemon-reload
sudo systemctl restart containerd
sudo systemctl restart kubelet

# Important to run: create kubeconfig on the control-plane node
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Checks
kubectl get nodes
