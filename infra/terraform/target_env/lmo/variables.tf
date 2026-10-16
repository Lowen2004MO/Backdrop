variable "aws_region" {
  type    = string
  default = "eu-west-2"
}
variable "env_name" {
  type    = string
  default = "lmo"
}
variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}
variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}
variable "db_multi_az" {
  type    = bool
  default = false
}
variable "db_deletion_protection" {
  type    = bool
  default = false
}
variable "db_skip_final_snapshot" {
  type    = bool
  default = false
}
variable "backup_retention_days" {
  type    = number
  default = 7
}
variable "image_tag" {
  type    = string
  default = "latest"
}
variable "iam_role_name_prefix" {
  type    = string
  default = "bounded-lmo-people-pulse"
}
variable "iam_permissions_boundary_arn" {
  type    = string
  default = "arn:aws:iam::010067763291:policy/PermissionBoundary"
}
variable "enable_demo_accounts" {
  type    = bool
  default = true
}
variable "secret_recovery_window_days" {
  type    = number
  default = 0
}
variable "secret_value_version" {
  type    = number
  default = 1
}
