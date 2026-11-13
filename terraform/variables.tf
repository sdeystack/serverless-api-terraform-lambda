variable "aws_region" {
  description = "AWS region for all resources. Use one region everywhere and record it in the README."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project name used in resource names and tags."
  type        = string
  default     = "serverless-api"
}

variable "environment" {
  description = "Environment name, for example dev."
  type        = string
  default     = "dev"
}

variable "lambda_memory_mb" {
  description = "Lambda memory in MB. 128 MB is enough for this small handler."
  type        = number
  default     = 128
}

variable "lambda_timeout_seconds" {
  description = "Lambda timeout in seconds. DynamoDB calls here are fast, so 10s leaves headroom without hiding a hung call for long."
  type        = number
  default     = 10
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days for Lambda and API Gateway logs."
  type        = number
  default     = 7
}
