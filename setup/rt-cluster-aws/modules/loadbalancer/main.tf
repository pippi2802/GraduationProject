# ---------------------------------------------------------------------------
# Internal Network Load Balancer for the Kubernetes API server (port 6443).
# Mirrors modules/loadbalancer.bicep (Azure internal Standard LB):
#   Azure internal LB          -> AWS internal NLB
#   frontend IP config         -> NLB (one private IP per subnet/AZ)
#   backend address pool       -> target group
#   health probe (TCP 6443)    -> target group health check
#   load balancing rule        -> listener
# ---------------------------------------------------------------------------

resource "aws_lb" "api" {
  name               = "${var.cluster_name}-api-lb"
  internal           = true
  load_balancer_type = "network"
  subnets            = var.subnet_ids

  tags = merge(var.tags, { Name = "${var.cluster_name}-api-lb" })
}

resource "aws_lb_target_group" "api" {
  name        = "${var.cluster_name}-api-tg"
  port        = 6443
  protocol    = "TCP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    protocol            = "TCP"
    port                = 6443
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  tags = merge(var.tags, { Name = "${var.cluster_name}-api-tg" })
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.api.arn
  port              = 6443
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
