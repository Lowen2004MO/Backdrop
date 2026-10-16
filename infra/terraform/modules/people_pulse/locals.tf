locals {
  name = "${var.env_name}-people-pulse"
  iam_role_name_prefix = coalesce(
    var.iam_role_name_prefix,
    "${var.env_name}-people-pulse",
  )

  common_tags = {
    Application = "people-pulse"
    Environment = var.env_name
    ManagedBy   = "terraform"
  }

  connector_subnets = {
    a = {
      availability_zone = data.aws_availability_zones.available.names[0]
      cidr_block        = cidrsubnet(var.vpc_cidr, 8, 0)
    }
    b = {
      availability_zone = data.aws_availability_zones.available.names[1]
      cidr_block        = cidrsubnet(var.vpc_cidr, 8, 1)
    }
  }

  data_subnets = {
    a = {
      availability_zone = data.aws_availability_zones.available.names[0]
      cidr_block        = cidrsubnet(var.vpc_cidr, 8, 10)
    }
    b = {
      availability_zone = data.aws_availability_zones.available.names[1]
      cidr_block        = cidrsubnet(var.vpc_cidr, 8, 11)
    }
  }
}
