# SNS subscriptions for the prod replication alerts topic.
# Module owns the topic; this stack owns the subscriptions per ADR-0001.
#
# Phase 1: email-only subscription to the platform ops list. PagerDuty /
# Opsgenie integration is added in Phase 2 once the engagement lead
# confirms the paging vendor.
#
# Uncomment when the engagement lead provides the email address.

# resource "aws_sns_topic_subscription" "ops_email" {
#   topic_arn = module.replication_destination.sns_topic_arn
#   protocol  = "email"
#   endpoint  = "exl-platform-ops@example.com" # replace with the real ops list before uncommenting
# }
