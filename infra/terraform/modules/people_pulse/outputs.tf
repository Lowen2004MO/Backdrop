output "application_url" {
  description = "Public HTTPS Lambda Function URL."
  value       = aws_lambda_function_url.application.function_url
}

output "ecr_repository_url" {
  description = "ECR repository used by the deployment script."
  value       = aws_ecr_repository.application.repository_url
}

output "database_secret_arn" {
  description = "ARN of the RDS-managed database credentials."
  value       = aws_db_instance.database.master_user_secret[0].secret_arn
}

output "demo_password_secret_arn" {
  description = "ARN of the generated demo password, or null when demo accounts are disabled."
  value       = var.enable_demo_accounts ? aws_secretsmanager_secret.demo_password[0].arn : null
}
