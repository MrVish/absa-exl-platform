resource "aws_iam_role" "registrar" {
  name               = "pipeline-factory-registrar"
  description        = "Assumed by GitHub Actions on push to main to POST/PATCH the pipeline registry API."
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
}

resource "aws_iam_role_policy_attachment" "registrar_writer" {
  role       = aws_iam_role.registrar.name
  policy_arn = var.writer_policy_arn
}
