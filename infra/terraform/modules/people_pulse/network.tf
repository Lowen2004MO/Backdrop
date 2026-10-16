data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "application" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${local.name}-vpc"
  })
}

resource "aws_subnet" "connector" {
  for_each = local.connector_subnets

  vpc_id                  = aws_vpc.application.id
  cidr_block              = each.value.cidr_block
  availability_zone       = each.value.availability_zone
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "${local.name}-connector-${each.key}"
    Tier = "connector"
  })
}

resource "aws_subnet" "data" {
  for_each = local.data_subnets

  vpc_id                  = aws_vpc.application.id
  cidr_block              = each.value.cidr_block
  availability_zone       = each.value.availability_zone
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "${local.name}-data-${each.key}"
    Tier = "data"
  })
}

resource "aws_route_table" "connector" {
  vpc_id = aws_vpc.application.id

  tags = merge(local.common_tags, {
    Name = "${local.name}-connector"
  })
}

resource "aws_route_table_association" "connector" {
  for_each = aws_subnet.connector

  subnet_id      = each.value.id
  route_table_id = aws_route_table.connector.id
}

resource "aws_route_table" "data" {
  vpc_id = aws_vpc.application.id

  tags = merge(local.common_tags, {
    Name = "${local.name}-data"
  })
}

resource "aws_route_table_association" "data" {
  for_each = aws_subnet.data

  subnet_id      = each.value.id
  route_table_id = aws_route_table.data.id
}

resource "aws_security_group" "app_runner" {
  # Retain the original physical name so switching compute does not replace the
  # security group attached to the partially deployed database.
  name        = "${local.name}-app-runner"
  description = "App Runner egress to the private People Pulse database"
  vpc_id      = aws_vpc.application.id

  egress {
    description = "Application outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name}-app-runner"
  })
}

resource "aws_security_group" "database" {
  name        = "${local.name}-database"
  description = "PostgreSQL access from App Runner only"
  vpc_id      = aws_vpc.application.id

  ingress {
    description     = "PostgreSQL from application compute"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_runner.id]
  }

  egress {
    description = "AWS-managed database egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name}-database"
  })
}

resource "aws_security_group" "secrets_endpoint" {
  name        = "${local.name}-secrets-endpoint"
  description = "HTTPS access to the private Secrets Manager endpoint"
  vpc_id      = aws_vpc.application.id

  ingress {
    description     = "HTTPS from application compute"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.app_runner.id]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name}-secrets-endpoint"
  })
}

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.application.id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = [for subnet in aws_subnet.connector : subnet.id]
  security_group_ids = [aws_security_group.secrets_endpoint.id]

  tags = merge(local.common_tags, {
    Name = "${local.name}-secrets-manager"
  })
}
