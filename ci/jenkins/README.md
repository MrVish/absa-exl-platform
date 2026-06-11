# `ci/jenkins/` — Jenkins shared library + Jenkinsfile examples

This directory holds the **Jenkins shared library** ("absa-ci") that the
platform's Jenkinsfiles consume, plus example Jenkinsfile ports of the
six GHA workflows under `.github/workflows/`.

See [ADR-0011](../../docs/adr/0011-ci-platform-jenkins.md) for the
decision context.

## Layout

```
ci/jenkins/
├── README.md                          (this file)
├── vars/                              # shared library global "steps"
│   ├── setupUv.groovy                 # install + sync uv
│   ├── awsLogin.groovy                # assume role (no-op under IRSA)
│   ├── publishStatus.groovy           # POST commit status to GitHub
│   └── postPrComment.groovy           # find-or-create PR comment
├── src/com/absa/ci/                   # supporting Groovy classes
│   └── BuildContext.groovy            # context fields shared across steps
├── resources/                         # static resources (none yet)
└── examples/
    ├── python-validate.Jenkinsfile        # PR-only, no AWS
    └── pipeline-factory.Jenkinsfile       # drift gate + sign + register (AWS)
```

## Wiring this library into Jenkins

1. **Register the library** in Jenkins → Manage Jenkins → System →
   Global Pipeline Libraries:
   - Name: `absa-ci`
   - Default version: `main` (or a tag once stabilized)
   - Retrieval method: Modern SCM → Git → this repo URL
   - Library path: `ci/jenkins/`
2. **Per-Jenkinsfile** add at the top:
   ```groovy
   @Library('absa-ci@main') _
   ```
   (Pin to a tag like `absa-ci@v1.0.0` in production.)

## Pre-requisites on the agent

The library assumes a Linux agent (Docker capability for the LocalStack
demo; CPython 3.12 not required because uv installs its own toolchain)
with:

- `git`, `curl`, `bash`
- `docker` (for the LocalStack demo only)
- `aws` CLI v2 (for the AWS-touching steps)
- Network reachability to:
  - GitHub (for commit-status + PR-comment APIs)
  - AWS STS / KMS / S3 in `eu-west-1`
  - Registry API endpoint (post-Phase-4)

## Credentials Jenkins must hold

| ID (Jenkins credentials) | Type | Used by |
|---|---|---|
| `aws-signer-role-arn` | Secret text | `pipeline-factory.Jenkinsfile`, `publish-signing-key.Jenkinsfile` |
| `aws-registrar-role-arn` | Secret text | `pipeline-factory.Jenkinsfile` |
| `aws-kms-signing-key-arn` | Secret text | `pipeline-factory.Jenkinsfile`, `publish-signing-key.Jenkinsfile` |
| `aws-signed-manifests-bucket` | Secret text | `pipeline-factory.Jenkinsfile` |
| `aws-public-keys-bucket` | Secret text | `publish-signing-key.Jenkinsfile` |
| `registry-api-endpoint` | Secret text | `pipeline-factory.Jenkinsfile` |
| `github-bot-token` | Username + password (PAT) **OR** GitHub App credentials | `pipeline-factory.Jenkinsfile` (drift-gate commit-back), all status-reporting |

Production setup: back these with **AWS Secrets Manager** via the
Jenkins AWS Secrets Manager Credentials Provider plugin so rotation is
managed centrally.

## Migration map (GHA → Jenkins)

| `.github/workflows/...` | `ci/jenkins/examples/...` | AWS auth | Notes |
|---|---|---|---|
| `python-validate.yml` | `python-validate.Jenkinsfile` | none | Lowest-risk port — proves library wiring |
| `code-intake.yml` | `code-intake.Jenkinsfile` (TODO) | none | Same shape as `python-validate` |
| `terraform-validate.yml` | `terraform-validate.Jenkinsfile` (TODO) | dummy creds | Uses `postPrComment` step |
| `pipeline-factory.yml` | `pipeline-factory.Jenkinsfile` | IRSA / assume-role | 3-stage; drift gate commits back |
| `publish-signing-key.yml` | `publish-signing-key.Jenkinsfile` (TODO) | IRSA / assume-role | Manual trigger from runbook |
| `localstack-demo.yml` | `localstack-demo.Jenkinsfile` (TODO) | none | Needs docker on agent |

The two examples checked in here cover both patterns (no-AWS and
AWS-touching). The remaining four follow the same templates.
