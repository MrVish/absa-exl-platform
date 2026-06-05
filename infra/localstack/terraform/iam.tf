# Demo-only IAM role the producer chain assumes.
#
# In production the producer assumes pipeline-factory-signer (created by
# the signing-foundation module) via GitHub Actions OIDC. The demo chain
# isn't running in GHA, so we add a separate role that any LocalStack
# caller in the EXL account can assume via static creds.
#
# LocalStack accepts any role with a matching name and doesn't actually
# enforce the trust policy beyond syntactic validation. The principal
# below is the EXL account root.

resource "aws_iam_role" "demo_signer" {
  name = "exl-demo-signer-${var.env_name}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.exl_account_id}:root" }
        Action    = "sts:AssumeRole"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "demo_signer_admin" {
  role = aws_iam_role.demo_signer.name
  # LocalStack-only: AdministratorAccess simplifies the demo wiring.
  # The real producer chain uses the pipeline-factory-signer role
  # (signing-foundation module) with scoped kms:Sign + s3:PutObject perms.
  # NEVER attach AdministratorAccess to a producer role in production.
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
