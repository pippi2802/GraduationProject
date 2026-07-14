output "instance_ids" {
  description = "IDs of the created instances."
  value       = aws_instance.this[*].id
}

output "instance_names" {
  description = "Name tags of the created instances."
  value       = [for i in aws_instance.this : i.tags["Name"]]
}

output "private_ips" {
  description = "Private IP addresses of the created instances."
  value       = aws_instance.this[*].private_ip
}
