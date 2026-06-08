# Deployment Troubleshooting Guide

This guide covers common issues and their solutions when deploying the Kubernetes cluster on Azure using Bicep.

## Table of Contents
1. [Pre-Deployment Issues](#pre-deployment-issues)
2. [Deployment Issues](#deployment-issues)
3. [Post-Deployment Issues](#post-deployment-issues)
4. [Cluster Issues](#cluster-issues)
5. [Network Issues](#network-issues)
6. [SSH and Access Issues](#ssh-and-access-issues)
7. [Performance Issues](#performance-issues)

---

## Pre-Deployment Issues

### Issue: "Azure CLI is not installed"

**Error Message:**
```
Azure CLI is not installed
```

**Solution:**
```bash
# For Ubuntu/Debian
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# For macOS
brew install azure-cli

# For Windows (via winget)
winget install Microsoft.AzureCLI

# Verify installation
az --version
```

---

### Issue: "Not logged in to Azure"

**Error Message:**
```
ERROR: Please run 'az login' to setup account.
```

**Solution:**
```bash
# Login with device code (works from CLI/Remote)
az login --use-device-code

# Or traditional browser login
az login

# Verify you're logged in
az account show

# Set correct subscription
az account set --subscription "d06f8f89-f7d3-46b3-b7a8-649244fb54c6"
```

---

### Issue: "Bicep CLI not found"

**Error Message:**
```
bicep: command not found
```

**Solution:**
```bash
# Install/Update Bicep
az bicep install

# Verify installation
az bicep version

# If still failing, try
az upgrade
az bicep install --upgrade
```

---

### Issue: "Invalid subscription ID"

**Error Message:**
```
ERROR: The subscription of '...' doesn't exist in tenants
```

**Solution:**
```bash
# List your subscriptions
az account list --output table

# Identify correct subscription and set it
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Verify
az account show
```

---

## Deployment Issues

### Issue: "InsufficientQuotaForVm" Error

**Error Message:**
```
ERROR: Code=InsufficientQuotaForVm
Message: Deployment failed with multiple errors: ...
```

**Causes:**
- Your Azure subscription has reached VM quota limits
- Region-specific quota limits

**Solutions:**

```bash
# Check current quota for your region
az compute vm list-usage --location swedencentral --output table

# For Standard_D4ds_v5 quota, you need to request an increase
# Go to Azure Portal -> Help + Support -> Service Limit Increase

# Alternatively, use smaller VM sizes temporarily
./deploy.sh --parameters controlPlaneVmSize="Standard_D2ds_v5" --parameters workerVmSize="Standard_D2ds_v5"

# Or use a different region with available quota
./deploy.sh --location "eastus"
```

---

### Issue: "ResourceGroupNotFound"

**Error Message:**
```
ERROR: Resource group 'capi-dev' could not be found.
```

**Solution:**
```bash
# Create the resource group first
az group create --name "capi-dev" --location "swedencentral"

# Then deploy
./deploy.sh

# Or let the deploy script create it for you
```

---

### Issue: "AuthorizationFailed" Error

**Error Message:**
```
ERROR: Authorization failed for template resource deployment
```

**Causes:**
- User doesn't have permissions to create resources
- Service principal has insufficient permissions

**Solutions:**

```bash
# Check current user/service principal permissions
az role assignment list --assignee $(az account show --query user.name -o tsv)

# Need to request more permissions or use an admin account
# Ask your Azure admin to grant you:
# - Contributor role on the subscription or resource group
# - Owner role for more comprehensive access
```

---

### Issue: "Image not found" Error

**Error Message:**
```
ERROR: Code=InvalidImageId
Message: The image ... could not be found
```

**Causes:**
- The shared gallery image doesn't exist
- Wrong subscription or resource group
- Image version doesn't exist

**Solutions:**

```bash
# List available images in the gallery
az image list --resource-group "rg-rtAKS"

# List gallery images
az sig image-definition list \
  --resource-group "rg-rtAKS" \
  --gallery-name "rtUbuntu"

# List specific image versions
az sig image-version list \
  --resource-group "rg-rtAKS" \
  --gallery-name "rtUbuntu" \
  --gallery-image-definition "rtUbuntu24.04"

# Update parameters with correct image details
# Edit parameters.biceparam with the correct:
# - imageResourceGroup
# - imageGalleryName
# - imageName
# - imageVersion
```

---

### Issue: "Invalid Bicep Template" Error

**Error Message:**
```
ERROR: Template validation failed: ...
```

**Solutions:**

```bash
# Validate the template
az deployment group validate \
  --resource-group "capi-dev" \
  --template-file main.bicep \
  --parameters parameters.biceparam

# Check Bicep syntax
az bicep build main.bicep

# If syntax error, review main.bicep for typos
```

---

## Post-Deployment Issues

### Issue: "VMs Created but Not Starting"

**Symptoms:**
- VMs appear in Azure Portal but have PowerState = "Deallocated"
- VMs not responding to SSH

**Solutions:**

```bash
# Start the VMs
az vm start --resource-group "capi-dev" --name "capi-dev-cp-0"

# Start all VMs in resource group
az vm start --resource-group "capi-dev" --ids $(az vm list --resource-group "capi-dev" --query "[].id" -o tsv)

# Check VM status
az vm get-instance-view --resource-group "capi-dev" --name "capi-dev-cp-0" \
  --query "instanceView.statuses" --output table
```

---

### Issue: "Custom Script Extension Failed"

**Symptoms:**
- VMs started but initialization scripts didn't run
- Kubernetes tools not installed

**Solutions:**

```bash
# SSH into the VM and run initialization manually
ssh -i ~/.ssh/azure_rsa azureuser@<VM_IP>

# Run initialization scripts manually
sudo bash /tmp/control-plane-init.sh

# Or reinstall packages
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl

# Check script extension status
az vm extension show \
  --resource-group "capi-dev" \
  --vm-name "capi-dev-cp-0" \
  --name "CustomScript"
```

---

### Issue: "Cost Higher Than Expected"

**Solutions:**

```bash
# Check current resource usage
az resource list --resource-group "capi-dev" --output table

# List all VMs and their sizes
az vm list --resource-group "capi-dev" \
  --query "[].{Name:name, Size:hardwareProfile.vmSize}" \
  -o table

# Reduce VM sizes
az deployment group create \
  --resource-group "capi-dev" \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters \
    controlPlaneVmSize="Standard_D2ds_v5" \
    workerVmSize="Standard_D2ds_v5"

# Or reduce number of nodes
az deployment group create \
  --resource-group "capi-dev" \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters \
    controlPlaneCount=1 \
    workerNodeCount=2
```

---

## Cluster Issues

### Issue: "kubeadm init Fails"

**Error Message:**
```
[init] Using Kubernetes version: v1.35.0
[preflight] Running pre-flight checks
...ERROR...
```

**Causes:**
- Containerd not properly configured
- Kernel modules not loaded
- Swap not disabled

**Solutions:**

```bash
# SSH into control plane
ssh -i ~/.ssh/azure_rsa azureuser@<CP_IP>

# Check if containerd is running
sudo systemctl status containerd

# Restart containerd
sudo systemctl restart containerd

# Check system requirements
grep -i memory /proc/meminfo
lsmod | grep overlay
lsmod | grep br_netfilter

# Disable swap if still enabled
sudo swapoff -a

# Verify swap is off
free -h

# Then retry kubeadm init
sudo kubeadm init --pod-network-cidr=192.168.0.0/16
```

---

### Issue: "Worker Nodes Stuck in NotReady State"

**Symptoms:**
```bash
$ kubectl get nodes
NAME                  STATUS     ROLES    ...
capi-dev-cp-0         Ready      master   ...
capi-dev-worker-0     NotReady   <none>   ...
capi-dev-worker-1     NotReady   <none>   ...
```

**Solutions:**

```bash
# Check kubelet status on worker
ssh -i ~/.ssh/azure_rsa azureuser@<WORKER_IP>
sudo systemctl status kubelet

# Check kubelet logs
sudo journalctl -u kubelet -n 50

# Check if pods are pending
kubectl get pods --all-namespaces

# Install CNI plugin (required for Ready state)
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml

# Check CNI pod status
kubectl get pods -n calico-system
```

---

### Issue: "Pods Stay in Pending State"

**Solutions:**

```bash
# Describe the pod for events
kubectl describe pod <POD_NAME> -n <NAMESPACE>

# Common causes: not enough resources or CNI not installed
# Check node resources
kubectl top nodes

# Install CNI plugin
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml

# Wait for CNI pods to be ready
kubectl wait --for=condition=Ready pod -l app=calico-node -n calico-system --timeout=300s
```

---

## Network Issues

### Issue: "No Outbound Internet from VMs"

**Symptoms:**
- `apt-get` fails with connection timeout
- Cannot pull container images

**Solutions:**

```bash
# Check NSG rules allow outbound traffic
az network nsg rule list \
  --resource-group "capi-dev" \
  --nsg-name "control-plane-subnet-nsg" \
  --output table

# Add outbound rule if missing
az network nsg rule create \
  --resource-group "capi-dev" \
  --nsg-name "control-plane-subnet-nsg" \
  --name "AllowInternetOutbound" \
  --priority 200 \
  --direction Outbound \
  --access Allow \
  --protocol "*" \
  --source-address-prefixes "*" \
  --destination-address-prefixes "*"

# Or check NAT Gateway / routing table
az network vnet subnet show \
  --resource-group "capi-dev" \
  --vnet-name "capi-dev-vnet" \
  --name "control-plane-subnet"
```

---

### Issue: "Pods Cannot Communicate Between Nodes"

**Symptoms:**
- Pod on Node1 cannot ping Pod on Node2
- Service discovery fails

**Solutions:**

```bash
# Verify CNI is installed
kubectl get daemonsets --all-namespaces

# Check pod network connectivity
kubectl run -it --image=busybox --rm debug -- sh
# Inside pod:
nslookup kubernetes.default

# Check node-to-node connectivity
kubectl get nodes -o wide

# SSH to node and test connectivity
ssh -i ~/.ssh/azure_rsa azureuser@<NODE_IP>
ping <OTHER_NODE_IP>

# Verify network plugin (Calico, Flannel, etc.)
kubectl get cni
```

---

## SSH and Access Issues

### Issue: "Permission Denied (publickey)"

**Error Message:**
```
Permission denied (publickey).
```

**Causes:**
- SSH key not properly configured
- Key permissions incorrect
- Wrong username

**Solutions:**

```bash
# Fix SSH key permissions
chmod 600 ~/.ssh/azure_rsa
chmod 644 ~/.ssh/azure_rsa.pub

# Verify key matches what's in the VM
ssh -i ~/.ssh/azure_rsa azureuser@<VM_IP> -vvv

# If you need to add SSH key after deployment
# Redeploy with correct SSH key in parameters

# Or add key manually:
ssh -i ~/.ssh/azure_rsa azureuser@<VM_IP>
echo "ssh-rsa AAAA..." >> ~/.ssh/authorized_keys
```

---

### Issue: "Connection Timeout to VM"

**Error Message:**
```
ssh: connect to host X.X.X.X port 22: Connection timed out
```

**Causes:**
- VM still starting
- Security group blocks SSH (port 22)
- Public IP not assigned

**Solutions:**

```bash
# Check if VM is running
az vm get-instance-view --resource-group "capi-dev" --name "capi-dev-cp-0" \
  --query "instanceView.statuses" --output table

# Check if public IP is assigned
az vm list-ip-addresses --resource-group "capi-dev" --output table

# Check NSG SSH rule
az network nsg rule show \
  --resource-group "capi-dev" \
  --nsg-name "control-plane-subnet-nsg" \
  --name "AllowSSH"

# Wait for VM to fully start
sleep 30
ssh -i ~/.ssh/azure_rsa azureuser@<VM_IP>
```

---

### Issue: "Kubeconfig Access Issues"

**Symptoms:**
```bash
$ kubectl cluster-info
The connection to the server localhost:8080 was refused
```

**Solutions:**

```bash
# SSH into control plane
ssh -i ~/.ssh/azure_rsa azureuser@<CP_IP>

# Copy kubeconfig
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Verify
kubectl cluster-info

# To access from local machine, copy config:
scp -i ~/.ssh/azure_rsa azureuser@<CP_IP>:~/.kube/config ~/capi-dev-config
export KUBECONFIG=~/capi-dev-config
kubectl cluster-info
```

---

## Performance Issues

### Issue: "Slow Pod Startup Times"

**Symptoms:**
- Pods take 30+ seconds to reach Running state
- Image pulls timeout

**Solutions:**

```bash
# Check network performance
kubectl run perf-test --image=nicolaka/netshoot --rm -it -- \
  bash -c "time wget -O /dev/null https://www.google.com"

# Check disk I/O
ssh -i ~/.ssh/azure_rsa azureuser@<NODE_IP>
iostat -x 1 5

# Increase VM disk size if bottleneck
# Edit parameters and redeploy with larger disk sizes
```

---

### Issue: "High CPU/Memory Usage"

**Solutions:**

```bash
# Check resource usage
kubectl top nodes
kubectl top pods --all-namespaces

# Identify heavy pods
kubectl get pods --all-namespaces --sort-by=.spec.containers[0].resources.requests.memory

# Scale up workers if needed
az deployment group create \
  --resource-group "capi-dev" \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters workerNodeCount=5

# Or use larger VM sizes
az deployment group create \
  --resource-group "capi-dev" \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters workerVmSize="Standard_D8ds_v5"
```

---

## Getting Help

If your issue isn't covered here:

1. **Check Azure Logs:**
   ```bash
   # Get deployment logs
   az deployment group show --resource-group "capi-dev" --name main --query "properties.outputs"
   
   # Get VM boot diagnostics
   az vm boot-diagnostics get-boot-log --resource-group "capi-dev" --name "capi-dev-cp-0"
   ```

2. **Check System Logs:**
   ```bash
   # SSH to VM and check logs
   ssh -i ~/.ssh/azure_rsa azureuser@<VM_IP>
   journalctl -xe
   sudo dmesg | tail -50
   ```

3. **Check Kubernetes Logs:**
   ```bash
   # Get cluster events
   kubectl get events --all-namespaces
   
   # Get pod logs
   kubectl logs -n kube-system <POD_NAME>
   
   # Get pod details
   kubectl describe pod -n kube-system <POD_NAME>
   ```

4. **Community Resources:**
   - [Kubernetes Slack Community](https://kubernetes.slack.com/)
   - [Azure Support](https://azure.microsoft.com/en-us/support/)
   - [CAPZ GitHub Issues](https://github.com/kubernetes-sigs/cluster-api-provider-azure/issues)

---

**Last Updated:** June 2026

For additional support, check the main [README.md](README.md) file.
