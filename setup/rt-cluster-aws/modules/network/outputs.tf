output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "control_plane_subnet_ids" {
  description = "Private control-plane subnet IDs, one per AZ."
  value       = aws_subnet.control_plane[*].id
}

output "worker_subnet_ids" {
  description = "Private worker subnet IDs, one per AZ."
  value       = aws_subnet.worker[*].id
}

output "security_group_id" {
  description = "ID of the cluster security group."
  value       = aws_security_group.cluster.id
}

output "nat_gateway_id" {
  description = "ID of the NAT Gateway."
  value       = aws_nat_gateway.this.id
}

output "nat_public_ip" {
  description = "Stable public IP that every VM egresses through."
  value       = aws_eip.nat.public_ip
}

output "availability_zones" {
  description = "Availability zones the subnets were spread across."
  value       = local.azs
}
