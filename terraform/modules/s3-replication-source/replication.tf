resource "aws_s3_bucket_replication_configuration" "this" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.this.id

  rule {
    id       = "${var.env}-replicate-model-ready"
    status   = "Enabled"
    priority = 0

    filter {
      prefix = var.prefix_filter
    }

    delete_marker_replication {
      status = var.delete_marker_replication ? "Enabled" : "Disabled"
    }

    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }

    destination {
      bucket        = var.destination_bucket_arn
      account       = var.destination_account_id
      storage_class = "STANDARD"

      access_control_translation {
        owner = "Destination"
      }

      encryption_configuration {
        replica_kms_key_id = var.destination_kms_key_arn
      }

      dynamic "replication_time" {
        for_each = var.replication_time_control_enabled ? [1] : []
        content {
          status = "Enabled"
          time {
            minutes = 15
          }
        }
      }

      dynamic "metrics" {
        for_each = var.replication_time_control_enabled ? [1] : []
        content {
          status = "Enabled"
          event_threshold {
            minutes = 15
          }
        }
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}
