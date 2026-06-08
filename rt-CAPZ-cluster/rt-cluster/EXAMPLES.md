# Example Deployments and Configurations

This file contains example configurations for different use cases and scenarios.

## Table of Contents
1. [Development Environment](#development-environment)
2. [Staging Environment](#staging-environment)
3. [Production HA Setup](#production-ha-setup)
4. [Small Cluster](#small-cluster)
5. [Large Scale Deployment](#large-scale-deployment)
6. [Different Region Deployment](#different-region-deployment)

---

## Development Environment

**Use case**: Quick testing, CI/CD pipelines, learning

**Configuration:**
```bash
./deploy.sh -e dev -l swedencentral -p 1 -w 1
```

Or with parameters file:

```biceparam
param environment = 'dev'
param location = 'swedencentral'
param clusterName = 'capi-dev'
param controlPlaneCount = 1
param workerNodeCount = 1
param controlPlaneVmSize = 'Standard_D2ds_v5'  # Smaller VM
param workerVmSize = 'Standard_D2ds_v5'
```

**Cost**: ~$250/month

**Characteristics:**
- Minimal resources
- Single control plane (not HA)
- Perfect for testing and development

---

## Staging Environment

**Use case**: Pre-production testing, load testing, staging deployments

**Configuration:**
```bash
./deploy.sh -e staging -l swedencentral -p 1 -w 3
```

Or with parameters file:

```biceparam
param environment = 'staging'
param location = 'swedencentral'
param clusterName = 'capi-staging'
param controlPlaneCount = 1
param workerNodeCount = 3
param controlPlaneVmSize = 'Standard_D4ds_v5'
param workerVmSize = 'Standard_D4ds_v5'
```

**Cost**: ~$630/month

**Characteristics:**
- More worker capacity for testing
- Single control plane
- Suitable for validating production workloads

---

## Production HA Setup

**Use case**: Production workloads, high availability, critical applications

**Configuration:**
```bash
./deploy.sh -e prod -l swedencentral -p 3 -w 10
```

Or with parameters file:

```biceparam
param environment = 'prod'
param location = 'swedencentral'
param clusterName = 'capi-prod'
param controlPlaneCount = 3          # HA setup with 3 control planes
param workerNodeCount = 10           # 10 worker nodes for workloads
param controlPlaneVmSize = 'Standard_D4ds_v5'
param workerVmSize = 'Standard_D4ds_v5'
param controlPlaneOsDiskSizeGB = 256  # Larger disk for production
param workerOsDiskSizeGB = 256
```

**Cost**: ~$2,100/month

**Characteristics:**
- 3 control plane nodes for HA (survives 1 node failure)
- 10 worker nodes for scaling workloads
- Production-grade disk sizes
- Suitable for mission-critical applications

---

## Small Cluster

**Use case**: Minimal production cluster, edge deployments, resource-constrained scenarios

**Configuration:**
```bash
./deploy.sh -e prod -l swedencentral -p 1 -w 2
```

Parameters:
```biceparam
param environment = 'prod'
param controlPlaneCount = 1
param workerNodeCount = 2
param controlPlaneVmSize = 'Standard_D4ds_v5'
param workerVmSize = 'Standard_D4ds_v5'
```

**Cost**: ~$630/month

**Characteristics:**
- Single control plane (not HA, suitable for non-critical workloads)
- Minimal worker nodes
- Lower cost than HA setup

---

## Large Scale Deployment

**Use case**: Enterprise workloads, ML training, high-traffic applications

**Configuration:**
```bash
./deploy.sh -e prod -l swedencentral -p 5 -w 30
```

Parameters:
```biceparam
param environment = 'prod'
param location = 'swedencentral'
param clusterName = 'capi-enterprise'
param controlPlaneCount = 5          # Extra control planes for high availability
param workerNodeCount = 30           # Significant worker capacity
param controlPlaneVmSize = 'Standard_D8ds_v5'  # Larger control plane VMs
param workerVmSize = 'Standard_E8ds_v5'       # Memory-optimized workers
param controlPlaneOsDiskSizeGB = 512
param workerOsDiskSizeGB = 512
```

**Cost**: ~$7,500/month

**Characteristics:**
- 5 control planes for extreme HA
- 30 worker nodes for horizontal scaling
- Larger VM sizes for more resources
- Suitable for large enterprise deployments

---

## Different Region Deployment

### East US Region

```bash
./deploy.sh -e prod -l eastus -c capi-eastus -p 3 -w 10
```

### Europe West Region

```bash
./deploy.sh -e prod -l westeurope -c capi-eu -p 3 -w 10
```

### Southeast Asia Region

```bash
./deploy.sh -e prod -l southeastasia -c capi-asia -p 3 -w 10
```

---

## Custom VM Size Configurations

### GPU-Enabled Cluster (for ML workloads)

```biceparam
param environment = 'prod'
param clusterName = 'capi-gpu'
param controlPlaneCount = 3
param workerNodeCount = 5
param controlPlaneVmSize = 'Standard_D4ds_v5'
param workerVmSize = 'Standard_NC6s_v3'    # GPU-enabled VM
```

### Memory-Optimized Cluster (for data processing)

```biceparam
param environment = 'prod'
param clusterName = 'capi-memory'
param controlPlaneCount = 3
param workerNodeCount = 8
param controlPlaneVmSize = 'Standard_D4ds_v5'
param workerVmSize = 'Standard_E16ds_v5'   # Memory-optimized VM
```

### Compute-Optimized Cluster (for batch processing)

```biceparam
param environment = 'prod'
param clusterName = 'capi-compute'
param controlPlaneCount = 3
param workerNodeCount = 12
param controlPlaneVmSize = 'Standard_D4ds_v5'
param workerVmSize = 'Standard_F16s_v2'    # Compute-optimized VM
```

---

## Deployment Commands by Scenario

### Quick Demo (Get it up in 5 minutes)
```bash
./deploy.sh  # Uses all defaults
```

### Multi-Region HA Setup

```bash
# Deploy in swedencentral
./deploy.sh -e prod -l swedencentral -c capi-eu-central -p 3 -w 10

# Deploy in eastus for redundancy
./deploy.sh -e prod -l eastus -c capi-us-east -p 3 -w 10
```

### Blue-Green Deployment

```bash
# Deploy Blue cluster
./deploy.sh -e prod -l swedencentral -c capi-blue -p 3 -w 10

# Validate Blue
# ... run tests ...

# Deploy Green cluster
./deploy.sh -e prod -l swedencentral -c capi-green -p 3 -w 10

# Switch traffic to Green
# Delete Blue when ready
```

### Gradual Upgrade Path

```bash
# Start with v1.34
az deployment group create \
  --resource-group capi-dev \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters kubernetesVersion="v1.34.5"

# Test, validate...

# Then upgrade to v1.35
az deployment group create \
  --resource-group capi-dev \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters kubernetesVersion="v1.35.0"
```

---

## Validation Before Deployment

Always validate before deploying to production:

```bash
# Validate template
./deploy.sh --validate -e prod -p 3 -w 10

# Or manually
az deployment group validate \
  --resource-group capi-prod \
  --template-file main.bicep \
  --parameters parameters.biceparam

# See what would be created
az deployment group what-if \
  --resource-group capi-prod \
  --template-file main.bicep \
  --parameters parameters.biceparam
```

---

## Cost Analysis

| Scenario | Setup | Monthly Cost |
|----------|-------|--------------|
| Development | 1 CP + 1 Worker (D2s) | ~$250 |
| Staging | 1 CP + 3 Workers (D4s) | ~$630 |
| Small Prod | 1 CP + 2 Workers (D4s) | ~$630 |
| HA Prod | 3 CP + 10 Workers (D4s) | ~$2,100 |
| Enterprise | 5 CP + 30 Workers (D8s) | ~$7,500 |

---

## Post-Deployment Checklist

For each deployment:

- [ ] Verify all VMs are running: `az vm list --resource-group <RG>`
- [ ] SSH into control plane successfully
- [ ] Run `kubeadm init` on control plane
- [ ] Install CNI plugin
- [ ] Join all worker nodes
- [ ] Verify `kubectl get nodes` shows all nodes as Ready
- [ ] Deploy test workload: `kubectl run nginx --image=nginx`
- [ ] Verify pod is running across nodes

---

## Scaling Examples

### Scale Up After Initial Deployment

```bash
# Increase worker nodes from 2 to 5
az deployment group create \
  --resource-group capi-dev \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters workerNodeCount=5 \
  --parameters servicePrincipalClientSecret="$SECRET"
```

### Scale Down for Cost Savings

```bash
# Reduce worker nodes from 10 to 5
az deployment group create \
  --resource-group capi-prod \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters workerNodeCount=5 \
  --parameters servicePrincipalClientSecret="$SECRET"
```

---

## Network Configuration Examples

### Custom Network CIDR

```biceparam
param vnetAddressPrefix = '172.16.0.0/16'      # Custom VNet
param controlPlaneSubnetPrefix = '172.16.1.0/24'
param workerSubnetPrefix = '172.16.2.0/24'
param podCidr = '10.244.0.0/16'                # Custom pod network
```

### Restricted Access

Modify [network.bicep](modules/network.bicep) NSG rules to restrict SSH to specific IPs:

```bicep
{
  name: 'AllowSSH'
  properties: {
    sourceAddressPrefix: '203.0.113.0/24'  # Your office IP range
    // ... rest of rule ...
  }
}
```

---

## Next Steps

1. Choose the scenario that matches your needs
2. Run the deployment command with appropriate parameters
3. Follow post-deployment steps from README.md
4. Monitor cluster health and scale as needed
5. Implement monitoring, logging, and backup solutions

---

For more details, see [README.md](README.md) and [QUICKSTART.md](QUICKSTART.md)
