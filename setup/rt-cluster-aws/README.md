# rt-cluster-aws — Self-managed Kubernetes on AWS (Terraform)

Terraform port of [`setup/rt-cluster`](../rt-cluster) (Azure Bicep). It deploys the
**infrastructure** for a self-managed Kubernetes cluster on AWS: a VPC with a NAT
Gateway for outbound internet, a configurable number of control-plane and worker
EC2 instances (spread across availability zones), and — when there is more than one
control plane — an internal Network Load Balancer fronting the Kubernetes API server.

> This template only deploys instances and networking. The actual `kubeadm`/`kubelet`
> bootstrap is left to the scripts under [`../scripts/`](../scripts/), wired up
> separately (e.g. via `user_data`/cloud-init, SSM, or by hand).

## Azure → AWS mapping

| Bicep (Azure) | Terraform (AWS) |
|---|---|
| Resource group | *(implicit — tags + region)* |
| Virtual Network | VPC |
| Subnets (control-plane / worker) | Subnets, one per AZ per role |
| Network Security Group | Security Group |
| Public IP + NAT Gateway | Elastic IP + NAT Gateway (+ IGW + public subnet) |
| Control-plane / worker VMs | EC2 instances |
| Internal Standard Load Balancer (6443) | Internal Network Load Balancer (6443) |
| Availability zones (round-robin) | AZ subnets (round-robin) |
| Shared Image Gallery / Canonical image | Custom AMI / Canonical Ubuntu AMI |

## What gets deployed

| Component | Always | Notes |
|---|---|---|
| VPC (`10.0.0.0/16` by default) | ✅ | Public subnet (NAT) + per-AZ control-plane & worker subnets |
| Security Group | ✅ | Locked down: only intra-VPC SSH/6443/all. **No public ingress.** |
| Elastic IP + NAT Gateway | ✅ | Stable outbound IP for every instance. No instance has a public IP. |
| Control-plane instances | ✅ | Count via `control_plane_count`. |
| Worker instances | ✅ | Count via `worker_node_count`. |
| Internal NLB (port 6443) | when `control_plane_count > 1` | Private frontend in the control-plane subnets. |
| AZ spread | always | Instances round-robin across per-AZ subnets. |

Because instances have no public IPs, connect through **SSM Session Manager** (attach an
instance profile separately) or a **bastion/jumpbox** inside the VPC.

## Repository layout

```
rt-cluster-aws/
├── main.tf                     # orchestrator (module calls, AMI + key pair)
├── variables.tf                # input variables
├── outputs.tf                  # outputs
├── versions.tf                 # provider requirements
├── terraform.tfvars.example    # sample parameter file
├── modules/
│   ├── network/                # VPC, subnets, SG, IGW, NAT Gateway
│   ├── loadbalancer/           # Internal NLB for the K8s API server
│   └── vm/                     # Generic pool of identical EC2 instances
└── README.md
```

## Prerequisites

```bash
terraform -version   # >= 1.5
aws sts get-caller-identity   # credentials configured (env vars, SSO, or profile)
```

## Quick start

```bash
cd setup/rt-cluster-aws

cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: region, counts, image_type/custom_ami_id, ssh_public_key

terraform init
terraform plan
terraform apply
```

Secrets should come from the environment rather than the tfvars file:

```bash
export TF_VAR_ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)"
# or, only if you really need password auth:
export TF_VAR_admin_password='ChangeMe-Now-12345!'

terraform apply
```

## Parameters

Defined in [variables.tf](variables.tf). The most useful ones (Bicep equivalent in parens):

| Variable | Default | Description |
|---|---|---|
| `aws_region` | `eu-north-1` | AWS region (`location`). |
| `cluster_name` | `rt-cluster` | Prefix used in every resource name. |
| `environment` | `dev` | Tag value. |
| `control_plane_count` | `1` | Control-plane instances. **NLB auto-deploys when > 1.** |
| `worker_node_count` | `2` | Worker instances. |
| `control_plane_instance_type` | `m6i.xlarge` | Control-plane size (`controlPlaneVmSize`). |
| `worker_instance_type` | `m6i.xlarge` | Worker size (`workerVmSize`). |
| `availability_zones` | `[]` (first 3) | AZs; instances round-robin spread (`zones`). |
| `admin_username` | `ubuntu` | Login user (used with cloud-init password). |
| `admin_password` | `""` | Used only when `ssh_public_key` is empty. |
| `ssh_public_key` | `""` | When non-empty, an EC2 key pair is created and used. |
| `image_type` | `custom` | `custom` ⇒ `custom_ami_id`; `ubuntu2404` ⇒ Canonical AMI lookup. |
| `custom_ami_id` | `""` | AMI ID for the custom RT image (when `image_type=custom`). |
| `vpc_cidr` / `control_plane_subnet_prefix` / `worker_subnet_prefix` / `public_subnet_prefix` | `10.0.0.0/16` / `.1.0/24` / `.2.0/24` / `.0.0/24` | Override only on CIDR collisions. |

### Choosing the image

```hcl
# Latest Canonical Ubuntu 24.04 LTS (looked up automatically):
image_type = "ubuntu2404"

# ...or your own custom RT AMI:
image_type    = "custom"
custom_ami_id = "ami-0123456789abcdef0"
```

### Choosing authentication

- **SSH key (recommended).** Set `ssh_public_key`; an `aws_key_pair` is created and
  injected. No password is set.
- **Password.** Leave `ssh_public_key` empty and set `admin_password`; cloud-init enables
  password auth for `admin_username`. Never commit it.

## Outputs

```bash
terraform output
```

| Output | What it is |
|---|---|
| `cluster_name`, `aws_region` | echo |
| `vpc_id` | ID of the VPC |
| `nat_egress_ip` | the public IP all instances egress through |
| `control_plane_instance_names` / `control_plane_private_ips` | per-instance lists |
| `worker_instance_names` / `worker_private_ips` | per-instance lists |
| `api_server_endpoint` | NLB DNS name if multi-CP, else the single CP's private IP |
| `api_load_balancer_deployed` | `true` iff the NLB was deployed |

## Connecting to the cluster

Because no instance has a public IP, pick one of:

```bash
# Option A: SSM Session Manager (attach an SSM instance profile to the instances first)
aws ssm start-session --target <instance-id>

# Option B: SSH via a bastion/jumpbox inside the VPC
ssh -J ubuntu@<bastion> ubuntu@<control-plane-private-ip>
```

Once on a control-plane instance, run the bootstrap scripts from
[`../scripts/`](../scripts/) (`docker-install.sh`, `control-plane-init.sh`,
`worker-init.sh`, …).

## Cleanup

```bash
terraform destroy
```
