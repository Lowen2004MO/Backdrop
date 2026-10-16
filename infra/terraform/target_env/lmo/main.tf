module "people_pulse" {
  source = "../../modules/people_pulse"

  env_name                     = var.env_name
  aws_region                   = var.aws_region
  vpc_cidr                     = var.vpc_cidr
  db_instance_class            = var.db_instance_class
  db_multi_az                  = var.db_multi_az
  db_deletion_protection       = var.db_deletion_protection
  db_skip_final_snapshot       = var.db_skip_final_snapshot
  backup_retention_days        = var.backup_retention_days
  image_tag                    = var.image_tag
  iam_role_name_prefix         = var.iam_role_name_prefix
  iam_permissions_boundary_arn = var.iam_permissions_boundary_arn
  enable_demo_accounts         = var.enable_demo_accounts
  secret_value_version         = var.secret_value_version
  secret_recovery_window_days  = var.secret_recovery_window_days
}

output "application_url" {
  value = module.people_pulse.application_url
}

output "ecr_repository_url" {
  value = module.people_pulse.ecr_repository_url
}

output "demo_password_secret_arn" {
  value = module.people_pulse.demo_password_secret_arn
}
