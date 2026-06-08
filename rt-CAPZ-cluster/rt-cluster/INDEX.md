# rt-CAPZ-cluster Bicep Deployment - Complete Guide

Welcome to the rt-CAPZ-cluster Bicep deployment solution! This directory contains everything you need to deploy a production-grade Kubernetes cluster on Azure.

## 📋 Quick Navigation

### 🚀 Getting Started (Read These First)
1. **[QUICKSTART.md](QUICKSTART.md)** - Get up and running in 5 minutes
2. **[README.md](README.md)** - Comprehensive documentation and deployment guide
3. **[EXAMPLES.md](EXAMPLES.md)** - Real-world deployment scenarios

### 🛠️ Deployment
- **[main.bicep](main.bicep)** - Main infrastructure orchestration template
- **[parameters.biceparam](parameters.biceparam)** - Parameter file (Bicep format)
- **[parameters.json](parameters.json)** - Alternative parameter file (JSON format)
- **[deploy.sh](deploy.sh)** - Interactive deployment script (recommended for beginners)

### 📦 Infrastructure Modules
- **[modules/network.bicep](modules/network.bicep)** - Virtual Network, Subnets, and Network Security Groups
- **[modules/controlplane.bicep](modules/controlplane.bicep)** - Control plane VM deployment
- **[modules/worker.bicep](modules/worker.bicep)** - Worker node VM deployment
- **[modules/identity.bicep](modules/identity.bicep)** - Azure identity and security configuration

### 🔧 Initialization Scripts
- **[scripts/control-plane-init.sh](scripts/control-plane-init.sh)** - Control plane node setup script
- **[scripts/worker-init.sh](scripts/worker-init.sh)** - Worker node setup script

### 📚 Documentation
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Problem diagnosis and solutions
- **[INDEX.md](INDEX.md)** - This file (file reference guide)

---

## 📁 Directory Structure

```
rt-cluster/
├── README.md                    # Main documentation
├── QUICKSTART.md               # Quick start guide
├── EXAMPLES.md                 # Example configurations
├── TROUBLESHOOTING.md          # Troubleshooting guide
├── INDEX.md                    # This file
│
├── main.bicep                  # Main Bicep template
├── parameters.biceparam        # Bicep parameters file
├── parameters.json             # JSON parameters file
├── deploy.sh                   # Interactive deployment script
│
├── modules/                    # Bicep modules
│   ├── network.bicep          # Network infrastructure
│   ├── controlplane.bicep     # Control plane VMs
│   ├── worker.bicep           # Worker node VMs
│   └── identity.bicep         # Identity & security
│
└── scripts/                    # Initialization scripts
    ├── control-plane-init.sh  # Control plane setup
    └── worker-init.sh         # Worker node setup
```

---

## 🎯 File Descriptions

### Main Files

#### `main.bicep`
The main orchestration template that:
- Defines all input parameters
- Calls all submodules (network, controlplane, worker, identity)
- Manages deployment flow and dependencies
- Provides outputs (VNet IDs, VM IDs, etc.)

**Key Parameters:**
- `controlPlaneCount` - Number of control plane nodes (modular!)
- `workerNodeCount` - Number of worker nodes (modular!)
- `location` - Azure region
- `clusterName` - Cluster identifier
- All customizable for your needs

#### `parameters.biceparam`
Bicep format parameter file containing:
- Default values for all parameters
- Environment-specific settings
- Easy to read and modify format
- Recommended for Bicep deployments

#### `parameters.json`
JSON format parameter file containing:
- Same parameters as biceparam but in JSON format
- Compatible with ARM template deployments
- Useful for integration with CI/CD systems

#### `deploy.sh`
Interactive bash deployment script featuring:
- Prerequisite checking
- User-friendly prompts
- Validation before deployment
- Progress tracking
- Post-deployment instructions
- Support for `--validate` and `--what-if` flags

**Usage:**
```bash
chmod +x deploy.sh
./deploy.sh -e prod -p 3 -w 10
```

---

### Bicep Modules

#### `modules/network.bicep`
Handles all network infrastructure:
- **Virtual Network** - Creates VNet with custom address space
- **Subnets** - Creates separate subnets for control plane and workers
- **Network Security Groups** - Configures NSGs with appropriate rules:
  - SSH (port 22) - for administration
  - Kubernetes API (port 6443) - for cluster communication
  - Etcd (ports 2379-2380) - for control plane data store
  - Kubelet (port 10250) - for node communication
  - Node ports (30000-32767) - for service traffic

**Outputs:**
- VNet ID
- Subnet IDs
- NSG configurations

#### `modules/controlplane.bicep`
Deploys control plane nodes with:
- **Configurable count** - Deploy 1, 3, 5, or any number
- **VM Configuration**:
  - Uses shared gallery images (rtUbuntu24.04)
  - Premium SSD storage (Premium_LRS)
  - Trusted Launch security
  - System-assigned managed identity
- **Additional disk** - 128GB for etcd persistent storage
- **Custom initialization** - Runs control-plane-init.sh on startup
- **Network setup** - Dynamic private IP assignment

**Features:**
- Supports scaling up/down by changing `controlPlaneCount`
- Each node tagged with role and instance number
- Automatic hostname configuration

#### `modules/worker.bicep`
Deploys worker nodes with:
- **Configurable count** - Deploy 1, 2, 10, or any number
- **VM Configuration**:
  - Uses shared gallery images (rtUbuntu24.04)
  - Premium SSD storage
  - Trusted Launch security
  - System-assigned managed identity
- **Custom initialization** - Runs worker-init.sh on startup
- **Network setup** - Dynamic private IP assignment

**Features:**
- Supports scaling by changing `workerNodeCount`
- Each node tagged with role and instance number
- Ready to join Kubernetes cluster

#### `modules/identity.bicep`
Manages identity and security:
- **User-Assigned Managed Identity** - For cluster-level identity
- **Service Principal Configuration** - For Azure resource integration
- **RBAC Setup** - Foundation for cluster authentication
- **Key Vault Integration** - For secrets management (optional)

---

### Initialization Scripts

#### `scripts/control-plane-init.sh`
Runs on each control plane VM during initialization:
- Updates system packages
- Installs container runtime (containerd)
- Configures container storage
- Installs Kubernetes tools (kubeadm, kubelet, kubectl)
- Prepares etcd disk
- Sets up kernel modules and parameters
- Configures networking for Kubernetes

**Key Actions:**
1. System update and upgrade
2. Containerd installation and configuration
3. Swap disabling
4. Kernel module setup (overlay, br_netfilter)
5. Kubernetes package installation
6. Service enablement

#### `scripts/worker-init.sh`
Runs on each worker node during initialization:
- Same package installations as control plane
- Optimized for worker node tasks
- Ready to join cluster with kubeadm
- Minimal disk configuration (no etcd)

**Key Actions:**
1. System update
2. Container runtime setup
3. Kubernetes tools installation
4. Service enablement

---

## 🚀 Quick Start Workflow

### Scenario 1: First Time User (5 minutes)

```bash
# 1. Read the quick start
cat QUICKSTART.md

# 2. Run the interactive script
chmod +x deploy.sh
./deploy.sh

# 3. Follow the prompts
# - The script guides you through each step
# - Checks for prerequisites
# - Prompts for Azure authentication
# - Confirms configuration before deploying
```

### Scenario 2: Experienced User (Programmatic)

```bash
# 1. Set environment
export SUBSCRIPTION_ID="..."
export CONTROL_PLANES=3
export WORKERS=10

# 2. Deploy directly
az deployment group create \
  --resource-group capi-prod \
  --template-file main.bicep \
  --parameters parameters.biceparam \
  --parameters \
    controlPlaneCount=$CONTROL_PLANES \
    workerNodeCount=$WORKERS
```

### Scenario 3: Infrastructure as Code (CI/CD)

```bash
# 1. Validate template
az deployment group validate \
  --resource-group capi-dev \
  --template-file main.bicep \
  --parameters @parameters.json

# 2. Preview changes
az deployment group what-if \
  --resource-group capi-dev \
  --template-file main.bicep \
  --parameters @parameters.json

# 3. Deploy
az deployment group create \
  --resource-group capi-dev \
  --template-file main.bicep \
  --parameters @parameters.json
```

---

## ⚙️ Key Parameters Explained

### Modular Parameters (The Cool Part!)

These parameters make the infrastructure flexible and scalable:

| Parameter | Default | Type | Purpose |
|-----------|---------|------|---------|
| **controlPlaneCount** | 1 | int | Number of control plane nodes (1, 3, or 5 for HA) |
| **workerNodeCount** | 2 | int | Number of worker nodes |
| **controlPlaneVmSize** | Standard_D4ds_v5 | string | VM size for control plane |
| **workerVmSize** | Standard_D4ds_v5 | string | VM size for workers |

### Environment Parameters

| Parameter | Default | Type | Purpose |
|-----------|---------|------|---------|
| environment | dev | string | dev/staging/prod |
| location | swedencentral | string | Azure region |
| clusterName | capi-dev | string | Cluster name |

### Image Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| imageName | rtUbuntu24.04 | OS image name |
| imageVersion | 1.0.2 | Image version |
| imageGalleryName | rtUbuntu | Shared gallery name |

### Azure AD Parameters

| Parameter | Purpose |
|-----------|---------|
| tenantId | Azure AD tenant |
| servicePrincipalClientId | Service principal ID |
| servicePrincipalClientSecret | Service principal password |

---

## 📊 Example Configurations

### Development Setup
```biceparam
controlPlaneCount = 1
workerNodeCount = 1
controlPlaneVmSize = 'Standard_D2ds_v5'
workerVmSize = 'Standard_D2ds_v5'
```

### Production HA Setup
```biceparam
controlPlaneCount = 3
workerNodeCount = 10
controlPlaneVmSize = 'Standard_D4ds_v5'
workerVmSize = 'Standard_E4ds_v5'
```

### Large Enterprise
```biceparam
controlPlaneCount = 5
workerNodeCount = 30
controlPlaneVmSize = 'Standard_D8ds_v5'
workerVmSize = 'Standard_E16ds_v5'
```

---

## 🔍 When to Use Each File

| Need | File(s) |
|------|---------|
| Get started quickly | QUICKSTART.md + deploy.sh |
| Understand architecture | README.md + main.bicep |
| See examples | EXAMPLES.md |
| Troubleshoot | TROUBLESHOOTING.md |
| Modify parameters | parameters.biceparam or parameters.json |
| Custom deployment | main.bicep + modules/ |
| Automate deployment | deploy.sh with flags or az CLI |
| CI/CD integration | parameters.json |

---

## 💡 Key Features

✅ **Modular** - Easy to scale control planes and worker nodes  
✅ **Parameterized** - Customize everything without editing templates  
✅ **Production-Ready** - HA support, security groups, managed disks  
✅ **Well-Documented** - Multiple guides for different users  
✅ **Easy to Deploy** - Interactive script or one-line CLI commands  
✅ **Real-World Examples** - Dev, staging, and production configurations  
✅ **Comprehensive Help** - Troubleshooting guide included  

---

## 📈 Scaling Examples

### Scale Up Control Planes
```bash
# Change from 1 to 3 control planes for HA
./deploy.sh -p 3 -w 10
```

### Scale Up Workers
```bash
# Add more worker nodes
./deploy.sh -w 20
```

### Scale Down for Cost Savings
```bash
# Reduce to minimal for dev
./deploy.sh -p 1 -w 2 -l eastus
```

---

## 🔐 Security Considerations

1. **SSH Keys** - Store private keys securely, never commit them
2. **Service Principal** - Use Azure Key Vault to store secrets
3. **Network Security Groups** - Review and restrict rules as needed
4. **RBAC** - Implement least-privilege access
5. **Monitoring** - Setup Azure Monitor for resource tracking

See README.md for detailed security best practices.

---

## 📞 Support & Troubleshooting

- **Quick Issues**: Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Deployment Help**: Review [README.md](README.md)
- **Examples**: See [EXAMPLES.md](EXAMPLES.md)
- **Step-by-Step**: Follow [QUICKSTART.md](QUICKSTART.md)

---

## 🎓 Learning Path

1. **Day 1**: Read QUICKSTART.md, run deploy.sh
2. **Day 2**: Study README.md, understand the architecture
3. **Day 3**: Review modules/ to understand Bicep
4. **Day 4**: Customize parameters for your use case
5. **Day 5**: Deploy to production with confidence

---

## 📝 File Statistics

| File | Purpose | Lines |
|------|---------|-------|
| main.bicep | Orchestration | ~150 |
| modules/ | Infrastructure | ~800 |
| scripts/ | Initialization | ~250 |
| Documentation | Guides | ~3000 |

**Total**: ~4,000 lines of production-ready infrastructure code and documentation

---

## 🆘 Checklist Before Deployment

- [ ] Read QUICKSTART.md
- [ ] Have Azure CLI installed
- [ ] Logged into Azure account
- [ ] Know your subscription ID
- [ ] Have service principal credentials
- [ ] Generated SSH key pair
- [ ] Reviewed parameters for your region
- [ ] Checked quota limits for VM sizes

---

## 📚 Additional Resources

- [Kubernetes Official Documentation](https://kubernetes.io/docs/)
- [Azure Bicep Documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- [kubeadm Setup Guide](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/)
- [Container Networking Interface Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/)

---

## 📄 License

This Bicep infrastructure template is provided for educational and development purposes.

---

**Last Updated**: June 2026  
**Version**: 1.0  
**Status**: Production Ready ✅

For detailed information about any file, click on its link above or refer to the specific documentation file.
