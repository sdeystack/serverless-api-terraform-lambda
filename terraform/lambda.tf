# Package the handler. Only lambda/handler.py is zipped; tests live in tests/
# at the repo root and are not deployed. The handler uses only the Python
# standard library plus boto3, which is included in the Lambda runtime, so no
# dependency packaging step is needed for this project.

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}-handler"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "handler" {
  function_name = "${local.name_prefix}-handler"
  description   = "Items API handler for the serverless API lab project."
  role          = aws_iam_role.lambda.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout_seconds

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.items.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}
