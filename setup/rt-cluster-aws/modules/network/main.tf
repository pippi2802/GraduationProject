# ---------------------------------------------------------------------------
# VPC, subnets, security group, Internet Gateway and a single NAT Gateway for
# the k8s cluster. Mirrors modules/network.bicep:
#   Azure VNet        -> AWS VPC
#   Azure subnets     -> AWS subnets (one per AZ, per role)
#   Azure NSG         -> AWS security group
#   Azure NAT Gateway -> AWS NAT Gateway (single, stable egress IP)
# Private subnets have no public IPs; egress is via the NAT Gateway only.
# ---------------------------------------------------------------------------

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = length(var.availability_zones) > 0 ? var.availability_zones : slice(data.aws_availability_zones.available.names, 0, 3)

  # One control-plane and one worker subnet per AZ, carved out of the
  # role prefixes (up to 16 AZs => /28 each).
  control_plane_cidrs = [for i, az in local.azs : cidrsubnet(var.control_plane_subnet_prefix, 4, i)]
  worker_cidrs        = [for i, az in local.azs : cidrsubnet(var.worker_subnet_prefix, 4, i)]
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, { Name = "${var.cluster_name}-vpc" })
}

# ---------------------------------------------------------------------------
# Internet Gateway + public subnet + NAT Gateway (single, stable egress IP).
# No cluster VM lives in the public subnet.
# ---------------------------------------------------------------------------
resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.cluster_name}-igw" })
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnet_prefix
  availability_zone       = local.azs[0]
  map_public_ip_on_launch = false

  tags = merge(var.tags, { Name = "${var.cluster_name}-public-subnet" })
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.cluster_name}-nat-eip" })
}

resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id

  tags = merge(var.tags, { Name = "${var.cluster_name}-nat" })

  depends_on = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(var.tags, { Name = "${var.cluster_name}-public-rt" })
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# Private subnets (control plane + workers), one per AZ, all egressing via NAT.
# ---------------------------------------------------------------------------
resource "aws_subnet" "control_plane" {
  count             = length(local.azs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.control_plane_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-control-plane-subnet-${count.index}"
    role = "control-plane"
  })
}

resource "aws_subnet" "worker" {
  count             = length(local.azs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.worker_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-worker-subnet-${count.index}"
    role = "worker"
  })
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }

  tags = merge(var.tags, { Name = "${var.cluster_name}-private-rt" })
}

resource "aws_route_table_association" "control_plane" {
  count          = length(aws_subnet.control_plane)
  subnet_id      = aws_subnet.control_plane[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "worker" {
  count          = length(aws_subnet.worker)
  subnet_id      = aws_subnet.worker[count.index].id
  route_table_id = aws_route_table.private.id
}

# ---------------------------------------------------------------------------
# Security group - only intra-VPC traffic (SSH/6443/all); unrestricted egress.
# No public ingress, mirroring the locked-down Azure NSG.
# ---------------------------------------------------------------------------
resource "aws_security_group" "cluster" {
  name        = "${var.cluster_name}-sg"
  description = "Intra-VPC only ingress for the self-managed k8s cluster."
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "SSH from within the VPC"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "Kubernetes API server from within the VPC"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "All other intra-VPC traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "Unrestricted egress (via NAT Gateway)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.cluster_name}-sg" })
}
