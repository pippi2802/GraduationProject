output "load_balancer_arn" {
  description = "ARN of the internal API NLB."
  value       = aws_lb.api.arn
}

output "target_group_arn" {
  description = "ARN of the API server target group (attach instances here)."
  value       = aws_lb_target_group.api.arn
}

output "api_server_endpoint" {
  description = "Private DNS name of the internal API NLB."
  value       = aws_lb.api.dns_name
}
