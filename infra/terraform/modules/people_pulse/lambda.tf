resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

locals {
  lambda_environment = merge(
    {
      AWS_LWA_ASYNC_INIT           = "true"
      AWS_LWA_PORT                 = "8000"
      AWS_LWA_READINESS_CHECK_PATH = "/health/"
      DB_HOST                      = aws_db_instance.database.address
      DB_NAME                      = "peoplepulse"
      DB_PORT                      = tostring(aws_db_instance.database.port)
      DB_SECRET_ARN                = aws_db_instance.database.master_user_secret[0].secret_arn
      DJANGO_ALLOWED_HOSTS         = ".lambda-url.${var.aws_region}.on.aws,127.0.0.1"
      DJANGO_CSRF_TRUSTED_ORIGINS  = "https://*.lambda-url.${var.aws_region}.on.aws"
      DJANGO_HTTPS                 = "true"
      DJANGO_SECRET_KEY_SECRET_ARN = aws_secretsmanager_secret.django_secret.arn
      DJANGO_SETTINGS_MODULE       = "people_pulse.settings.production"
      GUNICORN_THREADS             = "2"
      GUNICORN_WORKERS             = "1"
      PEOPLE_PULSE_RUNTIME         = "lambda"
    },
    var.enable_demo_accounts ? {
      PEOPLE_PULSE_DEMO_PASSWORD_SECRET_ARN = aws_secretsmanager_secret.demo_password[0].arn
    } : {},
  )
}

resource "aws_lambda_function" "application" {
  function_name = local.name
  description   = "People Pulse Django demonstration"
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.application.repository_url}:${var.image_tag}"
  role          = aws_iam_role.lambda.arn
  architectures = ["x86_64"]

  memory_size                    = var.lambda_memory_size
  timeout                        = var.lambda_timeout_seconds
  reserved_concurrent_executions = var.lambda_reserved_concurrency

  environment {
    variables = local.lambda_environment
  }

  vpc_config {
    subnet_ids         = [for subnet in aws_subnet.connector : subnet.id]
    security_group_ids = [aws_security_group.app_runner.id]
  }

  depends_on = [
    aws_cloudwatch_log_group.application,
    aws_iam_role_policy_attachment.lambda_vpc_execution,
    aws_iam_role_policy.lambda_secrets,
    aws_vpc_endpoint.secretsmanager,
  ]

  tags = local.common_tags
}

resource "aws_lambda_function_url" "application" {
  function_name      = aws_lambda_function.application.function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"
}

resource "aws_lambda_permission" "public_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.application.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "public_invoke" {
  statement_id             = "AllowPublicInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.application.function_name
  principal                = "*"
  invoked_via_function_url = true
}
