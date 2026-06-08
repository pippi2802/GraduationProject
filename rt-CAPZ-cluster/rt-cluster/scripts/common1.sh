#!/bin/bash
set -e

echo "Starting control plane initialization..."

# Update system
# Wait for apt to be free
while sudo fuser /var/lib/apt/lists/lock >/dev/null 2>&1 ; do
    echo "Waiting for apt to be free..."
    sleep 5
done
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

apt-get install -y pkg-config libseccomp-dev build-essential


# Setup disk for etcd
echo "Setting up etcd disk..."
DISK="/dev/sdc"
PART="${DISK}1"
MOUNTPOINT="/var/lib/etcddisk"
LABEL="etcd_disk"

# Only proceed if disk exists
if [ -b "$DISK" ]; then

    # 1. Create partition only if it doesn't exist
    if ! lsblk -no NAME "$PART" >/dev/null 2>&1; then
        echo "Creating partition on $DISK..."
        parted -s "$DISK" mklabel gpt mkpart primary 0% 100%
        sleep 2
    else
        echo "Partition already exists, skipping."
    fi

    # 2. Create filesystem only if not already formatted
    if ! blkid | grep -q "$LABEL"; then
        echo "Formatting $PART with ext4..."
        mkfs.ext4 "$PART" -F -L "$LABEL"
    else
        echo "Filesystem already exists, skipping format."
    fi

    # 3. Create mountpoint if missing
    mkdir -p "$MOUNTPOINT"

    # 4. Add to fstab only if not already present
    if ! grep -q "$LABEL" /etc/fstab; then
        echo "Adding $LABEL to /etc/fstab..."
        echo "LABEL=$LABEL $MOUNTPOINT ext4 defaults 0 2" >> /etc/fstab
    else
        echo "fstab entry already exists, skipping."
    fi

    # 5. Mount only if not already mounted
    if ! mount | grep -q "$MOUNTPOINT"; then
        echo "Mounting $MOUNTPOINT..."
        mount "$MOUNTPOINT"
    else
        echo "Disk already mounted, skipping."
    fi

else
    echo "Disk $DISK not found, skipping etcd disk setup."
fi


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



# Install go

echo "Installing Go 1.22.5..."
wget https://go.dev/dl/go1.22.5.linux-amd64.tar.gz
rm -rf /usr/local/go
tar -C /usr/local -xzf go1.22.5.linux-amd64.tar.gz
sudo tee /etc/profile.d/go.sh >/dev/null <<EOF
export PATH=/usr/local/go/bin:\$PATH
EOF
sudo chmod +x /etc/profile.d/go.sh

source /etc/profile.d/go.sh


#Install Helm
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh

# Create tmp dir
mkdir -p tmp

# Retrive RT-DRA repository

git clone https://github.com/nasim-samimi/dra-rt-driver.git



# Install container runtime (RT-containerd)

git clone -b rt https://github.com/nasim-samimi/containerd.git tmp/containerd

cd tmp/containerd
make
make install
cd -

mkdir -p /etc/containerd
containerd config default | tee /etc/containerd/config.toml >/dev/null



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


echo "Installing rt-runc..."
git clone -b rt https://github.com/nasim-samimi/runc.git tmp/runc
cd tmp/runc
make
install -D -m0755 runc /usr/local/sbin/runc
