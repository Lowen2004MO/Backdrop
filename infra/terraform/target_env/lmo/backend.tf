terraform {
  backend "s3" {
    key          = "people-pulse/lmo/terraform.tfstate"
    region       = "eu-west-2"
    encrypt      = true
    use_lockfile = true
  }
}
