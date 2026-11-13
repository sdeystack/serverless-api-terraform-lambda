# Shared naming. The random suffix avoids DynamoDB / log-group name clashes if
# the same account deploys this lab more than once. It does not change the
# architecture; the table name is exported as an output and passed to Lambda
# through the TABLE_NAME environment variable.

resource "random_pet" "suffix" {
  length    = 2
  separator = "-"
}

locals {
  name_prefix = "${var.project_name}-${var.environment}-${random_pet.suffix.id}"
}
