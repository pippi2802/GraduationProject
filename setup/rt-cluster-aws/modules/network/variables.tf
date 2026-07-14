variable "cluster_name" {
  description = "Base name used to derive resource names."
  type        = string
}

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

variable "availability_zones" {
  description = "Availability zones to spread subnets across. Empty => first 3 in the region."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
