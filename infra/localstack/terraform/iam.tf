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

# Placeholder writer policy for the signing-foundation module.
#
# The signing-foundation module requires a writer_policy_arn input that
# it attaches to its registrar role (so the registrar can POST/PATCH the
# registry API). In production this comes from the pipeline-registry
# module's writer_policy_arn output (execute-api:Invoke on POST/PATCH
# routes against the registry's API Gateway).
#
# Here the demo's registrar runs as a local uvicorn process (T9), not
# behind API Gateway, so there is no execute-api policy to attach.
# The demo's producer chain uses AdministratorAccess via the demo_signer
# role above to call the uvicorn endpoint directly. This stub policy
# just satisfies the module's required input with a syntactically valid
# ARN; the registrar role itself is never assumed by the demo.

resource "aws_iam_policy" "registrar_stub" {
  name        = "exl-demo-registrar-stub-${var.env_name}"
  description = "Placeholder writer policy for the signing-foundation module. The demo's registrar runs as uvicorn and uses AdministratorAccess via the demo_signer role instead."
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = aws_dynamodb_table.registry.arn
      },
    ]
  })
}
