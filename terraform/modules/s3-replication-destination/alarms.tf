resource "aws_sns_topic" "replication_alerts" {
  name              = "${var.env}-s3-replication-alerts"
  kms_master_key_id = "alias/aws/sns"

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "replication_latency" {
  alarm_name          = "${var.env}-s3-replication-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ReplicationLatency"
  namespace           = "AWS/S3"
  period              = 60
  statistic           = "Maximum"
  threshold           = var.alarm_threshold_seconds
  alarm_description   = "Replication latency exceeded RTC SLA for ${var.env}"
  treat_missing_data  = "notBreaching"

  dimensions = {
    SourceBucket      = "absa-model-handoff-${var.env}"
    DestinationBucket = aws_s3_bucket.this.id
    RuleId            = "${var.env}-replicate-model-ready"
  }

  alarm_actions = [aws_sns_topic.replication_alerts.arn]
  ok_actions    = [aws_sns_topic.replication_alerts.arn]

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "failed_replication" {
  alarm_name          = "${var.env}-s3-replication-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "OperationsFailedReplication"
  namespace           = "AWS/S3"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Any replication failure for ${var.env} should page immediately"
  treat_missing_data  = "notBreaching"

  dimensions = {
    SourceBucket      = "absa-model-handoff-${var.env}"
    DestinationBucket = aws_s3_bucket.this.id
    RuleId            = "${var.env}-replicate-model-ready"
  }

  alarm_actions = [aws_sns_topic.replication_alerts.arn]

  tags = local.common_tags
}
