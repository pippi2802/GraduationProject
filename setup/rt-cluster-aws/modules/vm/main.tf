# ---------------------------------------------------------------------------
# Pool of identical Linux EC2 instances (control plane or worker) with optional
# NLB target-group attachment and round-robin AZ spread across subnets.
# Mirrors modules/vm.bicep:
#   Azure NIC + VM           -> AWS EC2 instance
#   zone round-robin         -> subnet (AZ) round-robin
#   SSH key / password auth  -> key pair / cloud-init password
#   LB backend pool          -> target group attachment
# ---------------------------------------------------------------------------

locals {
  use_password = var.admin_password != ""

  # Optional cloud-init to enable password auth for the admin user, matching the
  # Bicep behaviour where a password is used only when no SSH key is provided.
  user_data = local.use_password ? <<-CLOUD_INIT
    #cloud-config
    users:
      - name: ${var.admin_username}
        groups: sudo
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
        lock_passwd: false
    chpasswd:
      expire: false
      list:
        - ${var.admin_username}:${var.admin_password}
    ssh_pwauth: true
  CLOUD_INIT
  : null
}

resource "aws_instance" "this" {
  count                  = var.instance_count
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = element(var.subnet_ids, count.index)
  vpc_security_group_ids = var.security_group_ids
  key_name               = var.key_name != "" ? var.key_name : null
  user_data              = local.user_data

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = var.root_volume_type
    encrypted   = true
  }

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-${count.index}" })
}

# Register every instance with each supplied target group (API server LB).
resource "aws_lb_target_group_attachment" "this" {
  count            = length(var.target_group_arns) * var.instance_count
  target_group_arn = var.target_group_arns[floor(count.index / var.instance_count)]
  target_id        = aws_instance.this[count.index % var.instance_count].id
  port             = 6443
}
