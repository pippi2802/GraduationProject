# ----------------------------------------------------------------------------
# General
# ----------------------------------------------------------------------------
variable "aws_region" {
  description = "AWS region for every resource."
  type        = string
  default     = "eu-north-1"
}

variable "cluster_name" {
  description = "Base name used as a prefix for all resources."
  type        = string
  default     = "rt-cluster"

  validation {
    condition     = length(var.cluster_name) >= 3 && length(var.cluster_name) <= 24
    error_message = "cluster_name must be between 3 and 24 characters."
  }
}

variable "environment" {
  description = "Environment tag (dev, test, staging, prod, ...)."
  type        = string
  default     = "dev"
}

variable "extra_tags" {
  description = "Free-form tags applied to every resource (merged with built-ins)."
  type        = map(string)
  default     = {}
}

# ----------------------------------------------------------------------------
# Sizing
# ----------------------------------------------------------------------------
variable "control_plane_count" {
  description = "Number of control plane instances. An internal NLB is deployed automatically when this is > 1."
  type        = number
  default     = 1

  validation {
    condition     = var.control_plane_count >= 1
    error_message = "control_plane_count must be at least 1."
  }
}

variable "worker_node_count" {
  description = "Number of worker instances."
  type        = number
  default     = 2

  validation {
    condition     = var.worker_node_count >= 1
    error_message = "worker_node_count must be at least 1."
  }
}

variable "control_plane_instance_type" {
  description = "Instance type for control plane nodes (Azure Standard_D4ds_v5 ~= m6i.xlarge)."
  type        = string
  default     = "m6i.xlarge"
}

variable "worker_instance_type" {
  description = "Instance type for worker nodes (Azure Standard_D4ds_v5 ~= m6i.xlarge)."
  type        = string
  default     = "m6i.xlarge"
}

variable "availability_zones" {
  description = "Availability zones to spread instances across (round-robin). Empty => first 3 in the region."
  type        = list(string)
  default     = []
}

# ----------------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------------
variable "admin_username" {
  description = "Admin username for every instance (used with cloud-init when a password is set)."
  type        = string
  default     = "ubuntu"
}

variable "admin_password" {
  description = "Admin password. Used only when ssh_public_key is empty."
  type        = string
  default     = ""
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key. When non-empty, an EC2 key pair is created and password auth is skipped."
  type        = string
  default     = ""
}

# ----------------------------------------------------------------------------
# Image
# ----------------------------------------------------------------------------
variable "image_type" {
  description = "Which image to use: 'custom' (custom_ami_id) or 'ubuntu2404' (latest Canonical AMI)."
  type        = string
  default     = "custom"

  validation {
    condition     = contains(["custom", "ubuntu2404"], var.image_type)
    error_message = "image_type must be either 'custom' or 'ubuntu2404'."
  }
}

variable "custom_ami_id" {
  description = "AMI ID of the custom RT image (only used when image_type=custom)."
  type        = string
  default     = ""
}

# ----------------------------------------------------------------------------
# Networking
# ----------------------------------------------------------------------------
variable "vpc_cidr" {
  description = "CIDR for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "control_plane_subnet_prefix" {
  description = "CIDR carved into one private control-plane subnet per AZ."
  type        = string
  default     = "10.0.1.0/24"
}

variable "worker_subnet_prefix" {
  description = "CIDR carved into one private worker subnet per AZ."
  type        = string
  default     = "10.0.2.0/24"
}

variable "public_subnet_prefix" {
  description = "CIDR for the public subnet that hosts the NAT Gateway."
  type        = string
  default     = "10.0.0.0/24"
}
