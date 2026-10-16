variable "env_name" {
  description = "Environment prefix applied to named resources."
  type        = string

  validation {
    condition     = contains(["ci", "dev", "lmo", "prod"], var.env_name)
    error_message = "env_name must be ci, dev, lmo, or prod."
  }
}

variable "aws_region" {
  description = "AWS region used for regional service endpoints."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR range for the isolated application VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_instance_class" {
  description = "RDS PostgreSQL instance class."
  type        = string
}

variable "db_multi_az" {
  description = "Whether RDS uses a standby in another availability zone."
  type        = bool
}

variable "db_deletion_protection" {
  description = "Whether RDS API deletion protection is enabled."
  type        = bool
}

variable "db_skip_final_snapshot" {
  description = "Whether RDS skips its final snapshot when destroyed."
  type        = bool
}

variable "backup_retention_days" {
  description = "Number of days to retain RDS automated backups."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 1 and 35."
  }
}

variable "image_tag" {
  description = "Immutable ECR image tag to deploy to Lambda."
  type        = string
  default     = "latest"
}

variable "iam_role_name_prefix" {
  description = "Optional account-compliant prefix for application IAM role names."
  type        = string
  default     = null
  nullable    = true
}

variable "iam_permissions_boundary_arn" {
  description = "Optional permissions boundary attached to application IAM roles."
  type        = string
  default     = null
  nullable    = true
}

variable "lambda_memory_size" {
  description = "Lambda function memory in MB."
  type        = number
  default     = 1024
}

variable "lambda_timeout_seconds" {
  description = "Maximum Lambda request duration."
  type        = number
  default     = 60
}

variable "lambda_reserved_concurrency" {
  description = "Concurrency cap protecting the small demonstration database."
  type        = number
  default     = 1
}

variable "log_retention_days" {
  description = "CloudWatch application log retention."
  type        = number
  default     = 14
}



variable "enable_demo_accounts" {
  description = "Inject a generated password so startup creates demonstration accounts."
  type        = bool
  default     = true
}

variable "secret_value_version" {
  description = "Increment to rotate the generated Django and demo passwords."
  type        = number
  default     = 1
}

variable "secret_recovery_window_days" {
  description = "Secrets Manager recovery window; zero deletes immediately."
  type        = number
  default     = 0

  validation {
    condition     = var.secret_recovery_window_days == 0 || (var.secret_recovery_window_days >= 7 && var.secret_recovery_window_days <= 30)
    error_message = "secret_recovery_window_days must be zero or between 7 and 30."
  }
}
