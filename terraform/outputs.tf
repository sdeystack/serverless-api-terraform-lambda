output "api_endpoint" {
  description = "Base URL for the HTTP API. Append /items to call the API."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "lambda_function_name" {
  description = "Lambda function name, for checking logs and metrics."
  value       = aws_lambda_function.handler.function_name
}

output "dynamodb_table_name" {
  description = "DynamoDB table name used by the API."
  value       = aws_dynamodb_table.items.name
}

output "lambda_error_alarm_name" {
  description = "CloudWatch alarm name for Lambda errors."
  value       = aws_cloudwatch_metric_alarm.lambda_errors.alarm_name
}

output "aws_region" {
  description = "Region all resources were deployed to."
  value       = var.aws_region
}
