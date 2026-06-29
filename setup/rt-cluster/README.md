# rt-cluster — Self-managed Kubernetes on Azure (Bicep)

Minimal, modular Bicep template that deploys the **infrastructure** for a self-managed Kubernetes cluster on Azure: a VNet with a NAT Gateway for outbound internet, a configurable number of control-plane and worker VMs (optionally spread across availability zones), and — when there is more than one control plane — an internal Standard Load Balancer fronting the Kubernetes API server.

> This template only deploys VMs and networking. The actual `kubeadm`/`kubelet` bootstrap is left to the scripts under [`scripts/`](scripts/), which are wired up separately (e.g. via `cloud-init`, `az vm run-command`, or by hand) once you’ve validated them.

## What gets deployed

| Component | Always | Notes |
|---|---|---|
| Virtual Network (`10.0.0.0/16` by default) | ✅ | 2 subnets: control-plane + workers |
| Network Security Group | ✅ | Locked down: only intra-VNet SSH/6443 + `AzureLoadBalancer`. **No public ingress.** |
| Public IP + NAT Gateway | ✅ | Stable outbound IP for every VM. No VM has its own public IP. |
| Control-plane VMs | ✅ | Count is configurable (`controlPlaneCount`). |
| Worker VMs | ✅ | Count is configurable (`workerNodeCount`). |
| Internal Standard Load Balancer (port 6443) | when `controlPlaneCount > 1` | Private frontend in the control-plane subnet. |
| Availability-zone spread | when `zones` is non-empty | Round-robin over the zones you pass. |

Because VMs have no public IPs, you access them either through **Azure Bastion** (deploy it separately into the same VNet by adding an `AzureBastionSubnet`) or with **`az ssh vm`** from a jumpbox.

## Repository layout

```
rt-cluster/
├── main.bicep                  # orchestrator
├── modules/
│   ├── network.bicep           # VNet, NSG, NAT Gateway
│   ├── loadbalancer.bicep      # Internal LB for the K8s API server
│   └── vm.bicep                # Generic pool of identical Linux VMs
├── parameters.bicepparam       # main parameter file (recommended)
├── parameters.json             # JSON variant (legacy tooling)
├── scripts/                    # VM bootstrap scripts (not invoked by the template)
└── README.md
```

## Prerequisites

```bash
# Azure CLI 2.50+ and Bicep
az --version
az bicep upgrade

az login
az account set --subscription "<your-subscription-id>"
```

## Quick start

The template ships with two parameter files. Pick **one**:

- `parameters.bicepparam` — recommended. Reads secrets from environment variables (`ADMIN_PASSWORD`, `SSH_PUBLIC_KEY`). **Cannot be mixed** with inline `--parameters key=value` overrides on the CLI; edit the file or set env vars instead.
- `parameters.json` — legacy/portable. Supports inline `--parameters key=value` overrides on the CLI.

### Using `parameters.bicepparam` (recommended)

```bash
RG=rt-cluster-rg
LOC=swedencentral

az group create -n "$RG" -l "$LOC"

# Secrets come from the environment - never commit them.
export ADMIN_PASSWORD='ChangeMe-Now-12345!'
export SSH_PUBLIC_KEY="$(cat ~/.ssh/id_rsa.pub 2>/dev/null)"   # optional

az deployment group create \
  --resource-group "$RG" \
  --template-file main.bicep \
  --parameters parameters.bicepparam
```

To change sizing/region/image, edit `parameters.bicepparam` directly (it's a real Bicep file, you get IntelliSense).

### Using `parameters.json` (with inline overrides)

```bash
RG=rt-cluster-rg
LOC=swedencentral

az group create -n "$RG" -l "$LOC"

az deployment group create \
  --resource-group "$RG" \
  --template-file main.bicep \
  --parameters parameters.json \
  --parameters adminPassword='ChangeMe-Now-12345!'
```

Override any other parameter the same way:

```bash
az deployment group create \
  --resource-group "$RG" \
  --template-file main.bicep \
  --parameters parameters.json \
  --parameters \
      controlPlaneCount=3 \
      workerNodeCount=5 \
      workerVmSize=Standard_D8ds_v5 \
      zones='[1,2,3]' \
      imageType=ubuntu2404 \
      adminPassword='ChangeMe-Now-12345!'
```

### Validate / dry-run

```bash
az deployment group validate \
  --resource-group "$RG" --template-file main.bicep \
  --parameters parameters.json --parameters adminPassword='ChangeMe-Now-12345!'

az deployment group what-if \
  --resource-group "$RG" --template-file main.bicep \
  --parameters parameters.json --parameters adminPassword='ChangeMe-Now-12345!'
```

## Parameters

All parameters live in [main.bicep](main.bicep). The most useful ones:

| Parameter | Default | Description |
|---|---|---|
| `location` | resource-group location | Azure region. |
| `clusterName` | `rt-cluster` | Prefix used in every resource name. |
| `environment` | `dev` | Tag value (`dev`/`test`/`prod`/…). |
| `controlPlaneCount` | `1` | Number of control-plane VMs. **LB is auto-deployed when > 1.** |
| `workerNodeCount` | `2` | Number of worker VMs. |
| `controlPlaneVmSize` | `Standard_D4ds_v5` | SKU for control-plane VMs. |
| `workerVmSize` | `Standard_D4ds_v5` | SKU for worker VMs. |
| `zones` | `[1,2,3]` | Availability zones; VMs are round-robin spread. Pass `[]` for non-zonal. |
| `adminUsername` | `azureuser` | Linux admin user. |
| `adminPassword` | *(required, `@secure`)* | Used only when `sshPublicKey` is empty. With `parameters.bicepparam` it comes from `$ADMIN_PASSWORD`; with `parameters.json` pass it via `--parameters adminPassword=...`. |
| `sshPublicKey` | `''` | When non-empty, password auth is disabled. |
| `imageType` | `custom` | `custom` ⇒ Shared Image Gallery; `ubuntu2404` ⇒ Canonical marketplace image. |
| `imageSubscriptionId` / `imageResourceGroup` / `imageGallery` / `imageName` / `imageVersion` | — | Used only when `imageType=custom`. |
| `vnetAddressPrefix` / `controlPlaneSubnetPrefix` / `workerSubnetPrefix` | `10.0.0.0/16` / `.1.0/24` / `.2.0/24` | Override only if they collide with an existing peered VNet. |

### Choosing the image

```bicep
// Canonical Ubuntu 24.04 LTS from the marketplace - no other params needed:
param imageType = 'ubuntu2404'

// …or your own Shared Image Gallery image:
param imageType            = 'custom'
param imageSubscriptionId  = '<sub-id>'
param imageResourceGroup   = 'rg-rtAKS'
param imageGallery         = 'rtUbuntu'
param imageName            = 'rtUbuntu24.04'
param imageVersion         = '1.0.2'
```

### Choosing authentication

- **SSH key (recommended).** Set `sshPublicKey` to the contents of `~/.ssh/id_rsa.pub`. Password auth is then disabled. `adminPassword` still has to be supplied because of the `@secure()`/`@minLength(12)` constraint, but Azure won’t use it.
- **Password.** Leave `sshPublicKey` empty and pass `adminPassword` via the CLI or a Key Vault reference. Never commit it.

```bash
# SSH key with the JSON parameter file:
az deployment group create ... \
  --parameters parameters.json \
  --parameters sshPublicKey="$(cat ~/.ssh/id_rsa.pub)" \
               adminPassword='ChangeMe-Now-12345!'
```

## Outputs

```bash
az deployment group show -g "$RG" -n main --query properties.outputs
```

| Output | What it is |
|---|---|
| `clusterName`, `location` | echo |
| `vnetId` | resource ID of the VNet |
| `natEgressIp` | the public IP all VMs egress through |
| `controlPlaneVmNames` / `controlPlanePrivateIps` | per-VM lists |
| `workerVmNames` / `workerPrivateIps` | per-VM lists |
| `apiServerEndpoint` | LB private IP if multi-CP, else the single CP’s private IP |
| `apiLoadBalancerDeployed` | `true` iff the LB module ran |

## Connecting to the cluster

Because no VM has a public IP, pick one of:

```bash
# Option A: Azure Bastion (requires you to add an AzureBastionSubnet + bastion host to the VNet)
az network bastion ssh \
  --name <bastion-name> --resource-group "$RG" \
  --target-resource-id <vm-id> --auth-type ssh-key --username azureuser \
  --ssh-key ~/.ssh/id_rsa

# Option B: az ssh vm via the AAD-Login extension (requires private connectivity from your machine)
az ssh vm --resource-group "$RG" --vm-name rt-cluster-cp-0
```

Once on a control-plane VM, run your bootstrap scripts from [`scripts/`](scripts/) (`docker-install.sh`, `control-plane-init.sh`, `worker-init.sh`, …).

## Cleanup

```bash
az group delete --name "$RG" --yes --no-wait
```

## Notes & limitations

- The template intentionally does **not** install Kubernetes. That’s the job of the scripts in [`scripts/`](scripts/), which you’ll wire up via `cloud-init`, `customData`, `az vm run-command`, or VM extensions once they’re validated.
- The Standard LB frontend is **private**. If you want `kubectl` access from outside Azure, either add a Bastion/jumpbox or change the LB module to use a public frontend.
- TrustedLaunch + vTPM is enabled; secure boot is off (kept off because some Kubernetes node setups need to load unsigned kernel modules). Turn it on in [modules/vm.bicep](modules/vm.bicep) if your image supports it.
- Accelerated networking is enabled by default; the chosen VM size must support it (D4ds_v5 does).
