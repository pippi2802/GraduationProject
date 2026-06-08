# Azure Bicep Kubernetes Cluster - Quick Start Guide

This quick start will get you deployed in under 15 minutes!

## Prerequisites (5 minutes)

### 1. Install Azure CLI
```bash
# For Ubuntu/Debian
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# For macOS
brew install azure-cli

# For Windows (via winget)
winget install Microsoft.AzureCLI
```

### 2. Install Bicep (Automatic)
Bicep is installed automatically with recent Azure CLI versions, but you can manually update:
```bash
az bicep install
```

### 3. Login to Azure
```bash
az login --use-device-code
```

### 4. Generate SSH Key (Optional, but recommended)
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/azure_rsa -N ""
```

## Quick Deploy (5 minutes)

### Option A: Using the Deploy Script (Easiest)

```bash
# Make script executable
chmod +x deploy.sh

# Run with defaults (1 control plane, 2 workers)
./deploy.sh

# Or specify your own values
./deploy.sh -e dev -l swedencentral -p 3 -w 5
```

### Option B: Manual Deployment

```bash
# Set up environment
export RESOURCE_GROUP="capi-dev"
export LOCATION="swedencentral"
export SUBSCRIPTION_ID="d06f8f89-f7d3-46b3-b7a8-649244fb54c6"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Deploy using your parameters
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters servicePrincipalClientSecret="your-secret-here"
```

## Customize Your Deployment

### Example 1: High Availability Setup (3 Control Planes, 10 Workers)

Using deploy script:
```bash
./deploy.sh -e prod -p 3 -w 10
```

Or manual:
```bash
az deployment group create \
  --resource-group capi-prod \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters \
    environment=prod \
    controlPlaneCount=3 \
    workerNodeCount=10 \
    servicePrincipalClientSecret="your-secret"
```

### Example 2: Development Environment (Minimal)

```bash
./deploy.sh -e dev -p 1 -w 1
```

### Example 3: Different Region

```bash
./deploy.sh -l eastus -c my-cluster
```

## Post-Deployment Steps (5 minutes)

### 1. Get VM Details
```bash
# List all VMs
az vm list --resource-group capi-dev -o table

# Get IP addresses
CONTROL_PLANE_IP=$(az vm list-ip-addresses \
  --resource-group capi-dev \
  --query "[?contains(virtualMachine.name, 'cp-0')].virtualMachine.network.publicIpAddresses[0].ipAddress" \
  -o tsv)

echo "Control Plane IP: $CONTROL_PLANE_IP"
```

### 2. SSH into Control Plane
```bash
ssh -i ~/.ssh/azure_rsa azureuser@$CONTROL_PLANE_IP
```

### 3. Initialize Kubernetes
```bash
# On the control plane VM
sudo kubeadm init \
  --pod-network-cidr=192.168.0.0/16 \
  --kubernetes-version=v1.35.0

# Copy kubeconfig
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Verify
kubectl cluster-info
kubectl get nodes
```

### 4. Install CNI (Container Network Interface)

Calico example:
```bash
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/custom-resources.yaml
```

### 5. Join Worker Nodes

Get join command from control plane:
```bash
# On control plane
sudo kubeadm token create --print-join-command
```

On each worker node:
```bash
# SSH into each worker
ssh -i ~/.ssh/azure_rsa azureuser@$WORKER_IP

# Run the join command
sudo kubeadm join <control-plane-ip>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>
```

Verify cluster:
```bash
# Back on control plane
kubectl get nodes
kubectl get pods --all-namespaces
```

## Troubleshooting

### Can't SSH into VM?
```bash
# Check security group allows SSH
az network nsg rule list \
  --resource-group capi-dev \
  --nsg-name control-plane-subnet-nsg \
  -o table

# Verify SSH key permissions
chmod 600 ~/.ssh/azure_rsa
chmod 644 ~/.ssh/azure_rsa.pub
```

### kubeadm init fails?
```bash
# SSH into the node and check logs
journalctl -xe
sudo systemctl status kubelet
docker version  # or containerd --version
```

### Pods not starting?
```bash
# Check if CNI is installed
kubectl get daemonsets -A
kubectl get pods -A --field-selector status.phase=Pending
```

## Common Parameters Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `environment` | dev | Environment name (dev/staging/prod) |
| `location` | swedencentral | Azure region |
| `clusterName` | capi-dev | Cluster name |
| `controlPlaneCount` | 1 | Number of control plane nodes |
| `workerNodeCount` | 2 | Number of worker nodes |
| `controlPlaneVmSize` | Standard_D4ds_v5 | Control plane VM size |
| `workerVmSize` | Standard_D4ds_v5 | Worker node VM size |
| `kubernetesVersion` | v1.35.0 | Kubernetes version |

## Cost Estimation

**Default Setup (1 CP + 2 Workers):**
- 3x Standard_D4ds_v5 VMs: ~$420/month
- Storage & networking: ~$50/month
- **Total: ~$470/month**

**HA Setup (3 CP + 10 Workers):**
- 13x Standard_D4ds_v5 VMs: ~$1,820/month
- Storage & networking: ~$100/month
- **Total: ~$1,920/month**

## Clean Up

```bash
# Delete all resources
az group delete --name capi-dev --yes --no-wait
```

## Next Steps

1. Deploy your applications to the cluster
2. Setup ingress controller (e.g., NGINX)
3. Configure persistent storage
4. Setup monitoring and logging (e.g., Prometheus, ELK)
5. Implement CI/CD pipeline

## Additional Resources

- [Full README.md](./README.md) - Comprehensive documentation
- [Kubernetes Official Docs](https://kubernetes.io/docs/)
- [Azure Bicep](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [kubeadm Setup](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/)

---

**Happy clustering! 🚀**
