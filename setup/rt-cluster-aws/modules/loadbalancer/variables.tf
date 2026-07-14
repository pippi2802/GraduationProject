variable "cluster_name" {
  description = "Base name used to derive resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC the internal NLB lives in."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs for the internal NLB frontend (control-plane subnets)."
  type        = list(string)
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
