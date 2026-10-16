ephemeral "random_password" "django_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "django_secret" {
  name                    = "${var.env_name}/people-pulse/django-secret-key"
  description             = "Generated Django secret key for ${var.env_name}"
  recovery_window_in_days = var.secret_recovery_window_days
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "django_secret" {
  secret_id                = aws_secretsmanager_secret.django_secret.id
  secret_string_wo         = ephemeral.random_password.django_secret.result
  secret_string_wo_version = var.secret_value_version
}

ephemeral "random_password" "demo_password" {
  count = var.enable_demo_accounts ? 1 : 0

  length  = 24
  special = false
}

resource "aws_secretsmanager_secret" "demo_password" {
  count = var.enable_demo_accounts ? 1 : 0

  name                    = "${var.env_name}/people-pulse/demo-password"
  description             = "Generated password for demonstration accounts in ${var.env_name}"
  recovery_window_in_days = var.secret_recovery_window_days
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "demo_password" {
  count = var.enable_demo_accounts ? 1 : 0

  secret_id                = aws_secretsmanager_secret.demo_password[0].id
  secret_string_wo         = ephemeral.random_password.demo_password[0].result
  secret_string_wo_version = var.secret_value_version
}
