# ============================================================================
# Self-managed Kubernetes cluster on AWS - VPC + NAT + (optional) internal API
# NLB + EC2 instances. Terraform port of setup/rt-cluster (Azure Bicep).
# ============================================================================

locals {
  common_tags = merge({
    cluster     = var.cluster_name
    environment = var.environment
    managedBy   = "terraform"
  }, var.extra_tags)

  deploy_api_lb = var.control_plane_count > 1
  use_ssh_key   = var.ssh_public_key != ""
}

# ----------------------------------------------------------------------------
# Image resolution: custom AMI or latest Canonical Ubuntu 24.04 LTS.
# ----------------------------------------------------------------------------
data "aws_ami" "ubuntu" {
  count       = var.image_type == "ubuntu2404" ? 1 : 0
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

locals {
  ami_id = var.image_type == "custom" ? var.custom_ami_id : data.aws_ami.ubuntu[0].id
}

# ----------------------------------------------------------------------------
# Optional EC2 key pair from the supplied SSH public key.
# ----------------------------------------------------------------------------
resource "aws_key_pair" "this" {
  count      = local.use_ssh_key ? 1 : 0
  key_name   = "${var.cluster_name}-key"
  public_key = var.ssh_public_key
  tags       = local.common_tags
}

# ----------------------------------------------------------------------------
# Modules
# ----------------------------------------------------------------------------
module "network" {
  source = "./modules/network"

  cluster_name                = var.cluster_name
  vpc_cidr                    = var.vpc_cidr
  control_plane_subnet_prefix = var.control_plane_subnet_prefix
  worker_subnet_prefix        = var.worker_subnet_prefix
  public_subnet_prefix        = var.public_subnet_prefix
  availability_zones          = var.availability_zones
  tags                        = local.common_tags
}

module "api_load_balancer" {
  source = "./modules/loadbalancer"
  count  = local.deploy_api_lb ? 1 : 0

  cluster_name = var.cluster_name
  vpc_id       = module.network.vpc_id
  subnet_ids   = module.network.control_plane_subnet_ids
  tags         = local.common_tags
}

module "control_plane" {
  source = "./modules/vm"

  name_prefix        = "${var.cluster_name}-cp"
  instance_count     = var.control_plane_count
  instance_type      = var.control_plane_instance_type
  ami_id             = local.ami_id
  subnet_ids         = module.network.control_plane_subnet_ids
  security_group_ids = [module.network.security_group_id]
  admin_username     = var.admin_username
  admin_password     = local.use_ssh_key ? "" : var.admin_password
  key_name           = local.use_ssh_key ? aws_key_pair.this[0].key_name : ""
  target_group_arns  = local.deploy_api_lb ? [module.api_load_balancer[0].target_group_arn] : []
  tags               = merge(local.common_tags, { role = "control-plane" })
}

module "workers" {
  source = "./modules/vm"

  name_prefix        = "${var.cluster_name}-worker"
  instance_count     = var.worker_node_count
  instance_type      = var.worker_instance_type
  ami_id             = local.ami_id
  subnet_ids         = module.network.worker_subnet_ids
  security_group_ids = [module.network.security_group_id]
  admin_username     = var.admin_username
  admin_password     = local.use_ssh_key ? "" : var.admin_password
  key_name           = local.use_ssh_key ? aws_key_pair.this[0].key_name : ""
  tags               = merge(local.common_tags, { role = "worker" })
}
