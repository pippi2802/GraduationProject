output "cluster_name" {
  description = "Cluster name (echo)."
  value       = var.cluster_name
}

output "aws_region" {
  description = "AWS region (echo)."
  value       = var.aws_region
}

output "vpc_id" {
  description = "ID of the VPC."
  value       = module.network.vpc_id
}

output "nat_egress_ip" {
  description = "Public IP all instances egress through."
  value       = module.network.nat_public_ip
}

output "availability_zones" {
  description = "AZs the subnets/instances were spread across."
  value       = module.network.availability_zones
}

output "control_plane_instance_names" {
  description = "Control-plane instance Name tags."
  value       = module.control_plane.instance_names
}

output "control_plane_private_ips" {
  description = "Control-plane private IPs."
  value       = module.control_plane.private_ips
}

output "worker_instance_names" {
  description = "Worker instance Name tags."
  value       = module.workers.instance_names
}

output "worker_private_ips" {
  description = "Worker private IPs."
  value       = module.workers.private_ips
}

output "api_server_endpoint" {
  description = "NLB DNS name if multi-CP, else the single control plane's private IP."
  value       = local.deploy_api_lb ? module.api_load_balancer[0].api_server_endpoint : module.control_plane.private_ips[0]
}

output "api_load_balancer_deployed" {
  description = "True iff the internal API NLB was deployed (control_plane_count > 1)."
  value       = local.deploy_api_lb
}
