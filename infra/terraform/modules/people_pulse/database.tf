resource "aws_db_subnet_group" "database" {
  name       = "${local.name}-database"
  subnet_ids = [for subnet in aws_subnet.data : subnet.id]

  tags = merge(local.common_tags, {
    Name = "${local.name}-database"
  })
}

resource "aws_db_instance" "database" {
  identifier = "${local.name}-db"

  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = var.db_instance_class
  allocated_storage           = 20
  max_allocated_storage       = 100
  storage_type                = "gp3"
  storage_encrypted           = true
  db_name                     = "peoplepulse"
  username                    = "people_pulse_admin"
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.database.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  backup_retention_period   = var.backup_retention_days
  copy_tags_to_snapshot     = true
  delete_automated_backups  = false
  deletion_protection       = var.db_deletion_protection
  skip_final_snapshot       = var.db_skip_final_snapshot
  final_snapshot_identifier = var.db_skip_final_snapshot ? null : "${local.name}-final"

  enabled_cloudwatch_logs_exports = ["postgresql"]
  auto_minor_version_upgrade      = true
  apply_immediately               = false

  tags = merge(local.common_tags, {
    Name = "${local.name}-db"
  })
}
