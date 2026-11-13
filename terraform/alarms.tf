# One error alarm, so a failing deploy is visible in CloudWatch without having
# to tail logs. No SNS action is wired up in this lab on purpose: add an
# email/Slack action here for a real service, and record that choice in the
# README. The alarm state can still be checked with:
#   aws cloudwatch describe-alarms --alarm-names "<alarm name from outputs>"

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name_prefix}-lambda-errors"
  alarm_description   = "Lambda Errors > 0 in 5 minutes for the items API handler."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.handler.function_name
  }
}
