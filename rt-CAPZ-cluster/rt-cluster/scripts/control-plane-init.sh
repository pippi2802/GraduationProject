#!/bin/bash
set -e

echo "Starting control plane initialization..."

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

# Setup disk for etcd
echo "Partitioning and formatting disk for etcd..."
DISK="/dev/sdc"
if [ -b "$DISK" ]; then
    # Create partition
    parted -s "$DISK" mklabel gpt mkpart primary 0% 100%
    
    # Wait for partition to appear
    sleep 2
    
    # Format partition
    mkfs.ext4 "${DISK}1" -F -L etcd_disk
    
    # Create mount directory
    mkdir -p /var/lib/etcddisk
    
    # Add to fstab
    echo "LABEL=etcd_disk /var/lib/etcddisk ext4 defaults 0 2" >> /etc/fstab
    
    # Mount
    mount /var/lib/etcddisk
fi

KUBEADM_VERSION="1.28.0"
KUBELET_VERSION="1.28.0"
KUBECTL_VERSION="1.28.0"

KUBEADM_CURRENT_VERSION=$(kubeadm version -o short 2>/dev/null || echo "none")

if [ "$KUBEADM_CURRENT_VERSION" != "$KUBEADM_VERSION" ]; then
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

else
    echo "kubeadm is already at the desired version $KUBEADM_VERSION"
fi

# Install go
echo "installing Go..."
wget https://go.dev/dl/go1.22.5.linux-amd64.tar.gz
rm -rf /usr/local/go
tar -C /usr/local -xzf go1.22.5.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
go version

# Create tmp dir
mkdir -p tmp

# Retrive RT-DRA repo
echo "Cloning RT-DRA repository..."
git clone https://github.com/nasim-samimi/dra-rt-driver.git


# Install container runtime (RT-containerd)
echo "Installing RT-containerd..."
git clone -b rt https://github.com/nasim-samimi/containerd.git tmp/containerd
cd tmp/containerd
make
make install
echo "RT-containerd installed successfully."
echo "Creating the config file for RT-containerd..."
cd ..
mkdir -p /etc/containerd
# containerd config default > /etc/containerd/config.toml or
containerd config default | sudo tee /etc/containerd/config.toml > /dev/null
echo "Config file created"

# Installing CNI
echo "Installing CNI plugins..."
mkdir -p /opt/cni/bin
curl -LO https://github.com/containernetworking/plugins/releases/download/v1.4.1/cni-plugins-linux-amd64-v1.4.1.tgz
tar -C /opt/cni/bin -xzf cni-plugins-linux-amd64-v1.4.1.tgz
mkdir -p /etc/cni/net.d
cat <<EOF | tee /etc/cni/net.d/10-containerd-bridge.conf > /dev/null
{
  "cniVersion": "0.4.0",
  "name": "bridge",
  "type": "bridge",
  "bridge": "cni0",
  "isGateway": true,
  "ipMasq": true,
  "ipam": {
    "type": "host-local",
    "ranges": [[{ "subnet": "10.244.0.0/16" }]],
    "routes": [{ "dst": "0.0.0.0/0" }]
  }
}
EOF



# Install rt-runc
echo "Installing rt-runc..."
git clone -b rt https://github.com/nasim-samimi/runc.git tmp/runc
cd tmp/runc
make
install -D -m0755 runc /usr/local/sbin/runc
cd ~/dra-rt-driver   # or wherever kubeadm-config.yaml is


# Disable swap
swapoff -a
sed -i '/ swap / s/^/#/' /etc/fstab

# Start kubeadm init
echo "Starting kubeadm init..."
systemctl daemon-reload
systemctl restart containerd
systemctl restart kubelet
kubeadm init --config=kubeadm-config.yaml


# systemctl restart containerd

# Installing RT-DRA
echo "Installing RT-DRA..."
cd ../../dra-rt-driver
kubectl get pod -A
helm upgrade -i \
  --create-namespace \
  --namespace dra-rt-driver \
  dra-rt-driver \
  deployments/helm/dra-rt-driver
kubectl get pod -n dra-rt-driver




# # Configure kernel modules
# cat << EOF > /etc/modules-load.d/k8s.conf
# overlay
# br_netfilter
# EOF

# modprobe overlay
# modprobe br_netfilter

# # Configure kernel parameters
# cat << EOF > /etc/sysctl.d/k8s.conf
# net.bridge.bridge-nf-call-iptables = 1
# net.bridge.bridge-nf-call-ip6tables = 1
# net.ipv4.ip_forward = 1
# EOF

# sysctl --system

# # Install kubeadm, kubelet, kubectl
# echo "Installing Kubernetes tools..."
# curl -fsSLo /usr/share/keyrings/kubernetes-archive-keyring.gpg https://dl.k8s.io/apt/doc/apt-key.gpg

# echo "deb [signed-by=/usr/share/keyrings/kubernetes-archive-keyring.gpg] https://apt.kubernetes.io/ kubernetes-xenial main" | tee /etc/apt/sources.list.d/kubernetes.list

# apt-get update
# apt-get install -y kubelet kubeadm kubectl

# # Hold versions to prevent auto-upgrade
# apt-mark hold kubelet kubeadm kubectl

# # Enable and start kubelet
# systemctl daemon-reload
# systemctl enable kubelet

# echo "Control plane initialization completed successfully!"
# echo "Ready for kubeadm init..."
