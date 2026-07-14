variable "name_prefix" {
  description = "Name prefix for instances (e.g. \"rt-cluster-cp\" or \"rt-cluster-worker\")."
  type        = string
}

variable "instance_count" {
  description = "Number of EC2 instances to create."
  type        = number

  validation {
    condition     = var.instance_count >= 1
    error_message = "instance_count must be at least 1."
  }
}

variable "instance_type" {
  description = "EC2 instance type, e.g. m6i.xlarge."
  type        = string
}

variable "ami_id" {
  description = "AMI ID to launch (custom RT image or an Ubuntu AMI)."
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs (one per AZ). Instances are round-robin spread across them."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security group IDs to attach to each instance."
  type        = list(string)
}

variable "admin_username" {
  description = "Admin/login username created via cloud-init when a password is set."
  type        = string
  default     = "ubuntu"
}

variable "admin_password" {
  description = "Optional admin password (set via cloud-init). Used only when ssh_public_key is empty."
  type        = string
  default     = ""
  sensitive   = true
}

variable "key_name" {
  description = "Name of an existing EC2 key pair to inject. Empty => no key pair."
  type        = string
  default     = ""
}

variable "root_volume_size" {
  description = "Root EBS volume size in GB."
  type        = number
  default     = 128
}

variable "root_volume_type" {
  description = "Root EBS volume type."
  type        = string
  default     = "gp3"
}

variable "target_group_arns" {
  description = "Target group ARNs to register the instances with. Empty => not attached to any LB."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
