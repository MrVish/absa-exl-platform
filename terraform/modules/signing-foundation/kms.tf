data "aws_caller_identity" "current" {}

resource "aws_kms_key" "manifest_signer" {
  description              = "ABSA x EXL manifest envelope signer (RSA-3072, deterministic RSASSA_PKCS1_V1_5_SHA_256)"
  key_usage                = "SIGN_VERIFY"
  customer_master_key_spec = "RSA_3072"
  deletion_window_in_days  = 30
  enable_key_rotation      = false # asymmetric KMS keys do not support automatic rotation (ADR-0009)
  policy                   = data.aws_iam_policy_document.kms_key.json
  tags = {
    Sprint = "phase-2-sprint-3"
    ADR    = "0009"
    env    = var.env
    region = var.region
  }
}

resource "aws_kms_alias" "manifest_signer" {
  name          = var.kms_alias_name
  target_key_id = aws_kms_key.manifest_signer.id
}

data "aws_iam_policy_document" "kms_key" {
  statement {
    sid       = "EnableRootAccount"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  statement {
    sid = "KeyAdminsManage"
    actions = [
      "kms:Describe*", "kms:Get*", "kms:List*",
      "kms:Update*", "kms:TagResource", "kms:UntagResource",
      "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion",
    ]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = var.key_admin_principals
    }
  }

  statement {
    sid       = "SignerSigns"
    actions   = ["kms:Sign", "kms:GetPublicKey", "kms:DescribeKey"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.signer.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = ["RSASSA_PKCS1_V1_5_SHA_256"]
    }
  }

  dynamic "statement" {
    for_each = length(var.absa_verifier_principals) > 0 ? [1] : []
    content {
      sid       = "AbsaVerifiers"
      actions   = ["kms:Verify", "kms:GetPublicKey", "kms:DescribeKey"]
      resources = ["*"]
      principals {
        type        = "AWS"
        identifiers = var.absa_verifier_principals
      }
    }
  }
}
