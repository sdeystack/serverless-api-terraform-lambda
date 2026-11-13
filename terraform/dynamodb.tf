resource "aws_dynamodb_table" "items" {
  name         = "${local.name_prefix}-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  # Lab table: allow Terraform to delete it with `terraform destroy`.
  # A production table would usually set deletion_protection_enabled = true.
  deletion_protection_enabled = false

  point_in_time_recovery {
    enabled = false
  }
}
