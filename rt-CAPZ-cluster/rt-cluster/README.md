# Simple Kubernetes Cluster on Azure - Bicep

A minimal Bicep template to deploy VMs for a Kubernetes cluster on Azure. No scripts, no production setup—just VMs, VNet, and NSG.

## What Gets Deployed

- **Virtual Network** (10.0.0.0/16) with 2 subnets
  - Control plane subnet (10.0.1.0/24)
  - Worker node subnet (10.0.2.0/24)
- **Network Security Group** with rules for SSH and Kubernetes API
- **Control Plane VMs** (configurable count, default: 1)
- **Worker Node VMs** (configurable count, default: 1)
- Uses your rtUbuntu24.04 shared gallery image

## Prerequisites

```bash
# 1. Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# 2. Install Bicep
az bicep install

# 3. Login to Azure
az login
```

## Parameters

Edit `parameters.biceparam` to customize:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resourceGroupName` | string | - | **REQUIRED** - Your resource group |
| `location` | string | swedencentral | Azure region |
| `clusterName` | string | rt-cluster | Cluster name |
| `controlPlaneCount` | int | 1 | Number of control plane VMs |
| `workerNodeCount` | int | 1 | Number of worker VMs |
| `vmSize` | string | Standard_D4ds_v5 | VM size (Standard_D4ds_v5, Standard_D2ds_v5, etc.) |
| `sshPublicKey` | string | "" | SSH public key for VM access |
| `environment` | string | test | Environment tag |

Image parameters (already set to your gallery):
- `imageSubscriptionId`: d06f8f89-f7d3-46b3-b7a8-649244fb54c6
- `imageResourceGroup`: rg-rtAKS
- `imageGallery`: rtUbuntu
- `imageName`: rtUbuntu24.04
- `imageVersion`: 1.0.2

## Quick Deploy

### Step 1: Update parameters.biceparam

```bash
nano parameters.biceparam
```

Change at minimum:
```
param resourceGroupName = 'my-rg'  # Your actual resource group
param controlPlaneCount = 1
param workerNodeCount = 1
param vmSize = 'Standard_D4ds_v5'
```

### Step 2: Deploy

```bash
az deployment group create \
  --resource-group "my-rg" \
  --template-file main.bicep \
  --parameters parameters.biceparam
```

### Step 3: Get VM Details

```bash
# List VMs created
az vm list --resource-group "my-rg" --query "[].{Name:name, IP:publicIps}"

# Get private IPs
az vm list-ip-addresses --resource-group "my-rg"
```

## Advanced: Custom Parameters via CLI

```bash
az deployment group create \
  --resource-group "my-rg" \
  --template-file main.bicep \
  --parameters \
    resourceGroupName="my-rg" \
    clusterName="my-cluster" \
    controlPlaneCount=1 \
    workerNodeCount=2 \
    vmSize="Standard_D2ds_v5" \
    location="swedencentral"
```

## Outputs

The deployment returns:
- `clusterName` - Name of your cluster
- `vnetId` - Virtual Network ID
- `controlPlaneVMIds` - List of control plane VM IDs
- `workerVMIds` - List of worker VM IDs
- `nsgId` - Network Security Group ID

View outputs after deployment:

```bash
az deployment group show \
  --resource-group "my-rg" \
  --name main \
  --query properties.outputs
```

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "environment": { "value": "dev" },
    "location": { "value": "swedencentral" },
    "clusterName": { "value": "capi-dev" },
    "controlPlaneCount": { "value": 1 },
    "workerNodeCount": { "value": 2 },
    "tenantId": { "value": "cb5b3c56-8331-4862-8e2c-369b8684fdc0" },
    "servicePrincipalClientId": { "value": "5796b248-d3e7-45de-b98c-880aa403b2cb" },
    "servicePrincipalClientSecret": { "value": "your-secret" }
  }
}
```

Deploy:

```bash
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file main.bicep \
  --parameters @parameters.json
```

### Step 5: Monitor Deployment

```bash
# Watch deployment progress
az deployment group list \
  --resource-group "$RESOURCE_GROUP" \
  --output table

# Get deployment details
az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name main
```

## Post-Deployment Steps

### 1. Get VM Information

```bash
# List all VMs in the cluster
az vm list \
  --resource-group "$RESOURCE_GROUP" \
  --query "[].{Name:name, Status:powerState}" \
  -o table

# Get IP addresses
az vm list-ip-addresses \
  --resource-group "$RESOURCE_GROUP" \
  --output table
```

### 2. Connect to Control Plane Node

```bash
# Get the public IP of the first control plane node
CONTROL_PLANE_IP=$(az vm list-ip-addresses \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?contains(virtualMachine.name, 'cp-0')].virtualMachine.network.publicIpAddresses[0].ipAddress" \
  -o tsv)

# SSH into control plane
ssh -i ~/.ssh/azure_rsa azureuser@$CONTROL_PLANE_IP
```

### 3. Initialize Kubernetes Cluster (On Control Plane)

```bash
# SSH into control plane node
ssh -i ~/.ssh/azure_rsa azureuser@$CONTROL_PLANE_IP

# Initialize Kubernetes with kubeadm
sudo kubeadm init \
  --pod-network-cidr=192.168.0.0/16 \
  --kubernetes-version=v1.35.0 \
  --control-plane-endpoint=$CONTROL_PLANE_IP

# Setup kubeconfig
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Verify cluster
kubectl cluster-info
kubectl get nodes
```

### 4. Install Container Network Interface (CNI)

Choose your preferred CNI plugin. Example with Calico:

```bash
# On the control plane node
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml

kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/custom-resources.yaml
```

### 5. Join Worker Nodes to Cluster

```bash
# On control plane, get the join command
sudo kubeadm token create --print-join-command

# On each worker node, run the join command (with sudo)
sudo kubeadm join <control-plane-ip>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>
```

### 6. Verify Cluster

```bash
# From control plane
kubectl get nodes
kubectl get pods --all-namespaces
```

## Customization Examples

### Example 1: Deploy with 3 Control Plane Nodes and 5 Worker Nodes

```bash
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters \
    controlPlaneCount=3 \
    workerNodeCount=5 \
    servicePrincipalClientSecret="$CLIENT_SECRET"
```

### Example 2: Use Larger VM Sizes

```bash
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters \
    controlPlaneVmSize="Standard_D8ds_v5" \
    workerVmSize="Standard_E4ds_v5" \
    servicePrincipalClientSecret="$CLIENT_SECRET"
```

### Example 3: Different Environment (Production)

```bash
az deployment group create \
  --resource-group "capi-prod" \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters \
    environment=prod \
    location="eastus" \
    resourceGroupName="capi-prod" \
    clusterName="capi-prod" \
    controlPlaneCount=3 \
    workerNodeCount=10 \
    servicePrincipalClientSecret="$CLIENT_SECRET"
```

## Modifying Parameters

### Via Command Line
Use the `--parameters` flag with space-separated `key=value` pairs.

### Via parameters.biceparam File
Edit `parameters.biceparam` and modify the parameter values:

```biceparam
param clusterName = 'my-cluster'
param controlPlaneCount = 3
param workerNodeCount = 5
param location = 'eastus'
```

## Cleanup

To delete all resources:

```bash
# Delete the entire resource group
az group delete \
  --name "$RESOURCE_GROUP" \
  --yes --no-wait

# Check deletion status
az group show --name "$RESOURCE_GROUP" 2>/dev/null || echo "Resource group deleted"
```

## Troubleshooting

### Issue: VMs don't have internet access
**Solution:** Check Network Security Group rules and ensure outbound traffic is allowed.

```bash
az network nsg rule list \
  --resource-group "$RESOURCE_GROUP" \
  --nsg-name "control-plane-subnet-nsg" \
  -o table
```

### Issue: Kubeadm init fails with image pull errors
**Solution:** Ensure containerd is properly configured on the VMs.

```bash
# SSH into the VM and check containerd status
sudo systemctl status containerd
sudo systemctl restart containerd
```

### Issue: Service Principal authentication fails
**Solution:** Verify the service principal credentials and ensure it has proper RBAC roles.

```bash
az ad sp show --id $CLIENT_ID
```

### Issue: SSH Connection denied
**Solution:** Ensure SSH public key is added to the parameters and the private key permissions are set correctly.

```bash
# Fix SSH key permissions
chmod 600 ~/.ssh/azure_rsa
chmod 644 ~/.ssh/azure_rsa.pub
```

## Deployment Optimization

### Validation Before Deployment
```bash
# Validate the bicep template
az deployment group validate \
  --resource-group "$RESOURCE_GROUP" \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters servicePrincipalClientSecret="$CLIENT_SECRET"
```

### Dry Run / What-If
```bash
# See what would be created without deploying
az deployment group what-if \
  --resource-group "$RESOURCE_GROUP" \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters servicePrincipalClientSecret="$CLIENT_SECRET"
```

## Performance Considerations

1. **VM Sizing**: Use `Standard_D4ds_v5` or larger for production workloads
2. **Storage**: Premium_LRS is used for all managed disks for better performance
3. **Network**: NSG rules are optimized to allow inter-node communication
4. **Scaling**: Easily scale by changing `controlPlaneCount` and `workerNodeCount`

## Security Best Practices

1. **SSH Keys**: Store private keys securely and never commit them
2. **Service Principal**: Use separate service principals for different environments
3. **Network Security**: Review and restrict NSG rules as needed
4. **RBAC**: Implement proper Azure RBAC roles for cluster access
5. **Secrets**: Never hardcode secrets in parameter files; use Azure Key Vault instead

### Using Azure Key Vault for Secrets

```bash
# Store secret in Azure Key Vault
az keyvault secret set \
  --vault-name my-keyvault \
  --name client-secret \
  --value "$CLIENT_SECRET"

# Retrieve during deployment
CLIENT_SECRET=$(az keyvault secret show \
  --vault-name my-keyvault \
  --name client-secret \
  --query value -o tsv)
```

## Additional Resources

- [Bicep Documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- [Kubernetes on Azure](https://learn.microsoft.com/en-us/azure/aks/)
- [kubeadm Installation](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/)
- [Cluster API for Azure (CAPZ)](https://github.com/kubernetes-sigs/cluster-api-provider-azure)

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review Azure deployment logs: `az deployment group show --resource-group $RESOURCE_GROUP --name main`
3. SSH into VMs and check system logs: `journalctl -xe`
4. Review Kubernetes logs: `kubectl logs -n kube-system`

## License

This Bicep infrastructure template is provided as-is for educational and development purposes.

---

**Last Updated**: June 2026
**Bicep Version**: 0.27+
**Kubernetes Version**: v1.35.0
**Azure CLI Version**: 2.50+
