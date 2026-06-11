# ADR-0011: CI Platform — Jenkins (replaces GitHub Actions)

| Field | Value |
| --- | --- |
| Status | Proposed |
| Date | 2026-06-11 |
| Deciders | Vishnu S (EXL ML Platform), EXL DevOps Lead |
| Consulted | ABSA Cloud Platform (Jenkins identity model), EXL Security (credential storage) |
| Supersedes-in-part | [ADR-0003](0003-manifest-signing-kms-asymmetric.md) §"Signing trust model", [ADR-0009](0009-signing-foundation-topology.md) §"OIDC provider" |
| Related | [Phase 3 closeout](../phase-3-closeout.md), `.github/workflows/`, `terraform/modules/signing-foundation/` |

## Context

Phase 1-3 used **GitHub Actions** for every CI gate — six workflows (~560 LOC)
covering Python lint/types/tests, the pipeline-factory drift+sign+register chain,
Terraform validate, code-intake validate, the LocalStack end-to-end demo, and the
KMS public-key re-publish job. AWS authentication is via **GitHub OIDC** to two
IAM roles (signer, registrar) wired by `terraform/modules/signing-foundation`.

EXL's enterprise CI standard is **Jenkins**, not GitHub Actions. The platform
must run on EXL infrastructure once real-AWS Phase 4 work begins; GHA was a
build-time convenience that does not survive contact with EXL's production CI
policy. This ADR captures the swap before we wire it into real AWS — re-anchoring
later (after real signing roles are issued) would force a second IAM trust-policy
migration we can avoid by doing this now.

The decision is not whether to switch (it is forced by EXL policy) but **how**
to switch with minimum disruption to the cryptographic chain-of-custody story
and the signed-manifest invariants the platform already enforces.

## Decision

### Adopt Jenkins as the CI orchestration platform

All six GHA workflows are ported to Jenkins. The **business logic** (the Python
CLIs, the canonical-JSON signers, the verifiers, code-intake, pipeline-factory)
is unchanged — only the orchestration layer moves. The byte-stable manifest
guarantee, the sign-then-upload idempotency contract, and the chain-of-custody
digest assertions hold across the migration because the executables are the
same.

### Jenkins identity model: IRSA on EKS (recommended)

The single biggest infrastructure decision. Three candidates were considered:

| Model | Trust mechanism | Verdict |
|---|---|---|
| **IRSA on EKS** | EKS OIDC provider → IAM role per K8s ServiceAccount | **Adopted.** Closest semantic match to GHA OIDC: per-job identity, ephemeral creds, no static keys. |
| **EC2 instance profile + role chaining** | Jenkins controller/agent EC2 IAM role assumes a downstream role per job | Acceptable fallback if EKS is unavailable; loses per-job identity granularity. |
| **Jenkins as OIDC IdP** | Jenkins exposes its own OIDC discovery endpoint, AWS trusts it | Rejected — adds an attack surface, rarely deployed at banking-grade. |

The signing-foundation Terraform module will gain a variable
`identity_provider = "github_actions" | "jenkins_irsa" | "jenkins_instance"`
(default flips to `jenkins_irsa` once the EKS cluster ARN is known). During
cutover both providers can be trusted simultaneously by passing a list.

The trust policy under `jenkins_irsa` looks like:

```hcl
data "aws_iam_policy_document" "jenkins_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.eks_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(var.eks_oidc_issuer_url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(var.eks_oidc_issuer_url, "https://", "")}:sub"
      values = [
        "system:serviceaccount:${var.jenkins_namespace}:${var.jenkins_signer_sa}",
      ]
    }
  }
}
```

The `:sub` claim binds the role to a specific K8s ServiceAccount in a specific
namespace — the same granularity GHA gave us via the `repo:org/repo:ref:...`
constraint.

### Shared library for the common pipeline shape

A Groovy shared library `ci/jenkins/` ("absa-ci") provides reusable steps so
each Jenkinsfile stays short (~30-50 lines instead of ~100):

- `setupUv()` — pin uv version, install, prime cache
- `awsLogin([roleArn:..., region:'eu-west-1'])` — no-op under IRSA, explicit
  `sts:AssumeRole` if an ARN is passed (for the legacy/chained model)
- `publishStatus(context, state, [description, targetUrl])` — POST commit
  status back to GitHub via the Branch Source plugin
- `postPrComment(body)` — find-or-create a PR comment (matches the
  `actions/github-script` behaviour `terraform-validate.yml` uses today)

The library lives in this repo under `ci/jenkins/` and is loaded by Jenkins as
a Global Pipeline Library named `absa-ci`. Per-Jenkinsfile import:

```groovy
@Library('absa-ci@main') _
```

### Branch protection: Jenkins → GitHub commit statuses

GitHub branch protection rules continue to gate merges. Jenkins reports a
**named commit status per job** via the GitHub plugin. Branch protection's
"required status checks" list will be re-pointed from GHA job names to Jenkins
status contexts (e.g. `ci/python-validate`, `ci/pipeline-factory/sign`).

### Secrets: Jenkins credentials → AWS Secrets Manager

The seven GHA secrets (`AWS_OIDC_SIGNER_ROLE_ARN`, `AWS_KMS_SIGNING_KEY_ARN`,
`AWS_SIGNED_MANIFESTS_BUCKET`, `AWS_OIDC_REGISTRAR_ROLE_ARN`,
`AWS_PUBLIC_KEYS_BUCKET`, `REGISTRY_API_ENDPOINT`, plus the bot PAT for
commit-back) move to Jenkins Credentials, ideally backed by **AWS Secrets
Manager** via the Jenkins AWS Secrets Manager Credentials Provider plugin.

Rotation policy:
- Role ARNs / bucket names: rotated only on infra change (rare).
- KMS key ARN: rotated per [`docs/runbooks/kms-key-rotation.md`](../runbooks/kms-key-rotation.md).
- Bot PAT: 90-day rotation, automated via the rotation Lambda already proposed
  for Phase 4.

### Drift-gate commit-back uses a bot identity

The `pipeline-factory.yml` job today uses `${{ secrets.GITHUB_TOKEN }}` to push
regenerated manifests back to the branch. Jenkins replaces this with a
**dedicated GitHub App** (preferred) or a long-lived bot PAT stored in Secrets
Manager. The App route is preferred because it produces auditable per-action
identities and is revocable without touching a user account.

## Migration phasing (3 sprints, ~4 weeks)

### Sprint M1 — Foundation (1 week)

1. This ADR merged (proposed → accepted after EKS decision).
2. Shared library `ci/jenkins/` skeleton committed.
3. Pick identity model with ABSA — IRSA on EKS unless blocked.
4. Port `python-validate` (no AWS, lowest risk) — verify shared library wiring
   end-to-end. **This Jenkinsfile is the proving ground.**

### Sprint M2 — AWS-touching workflows (1-2 weeks)

1. Re-jig `signing-foundation` module to support
   `identity_provider = "github_actions" | "jenkins_irsa" | "both"`.
2. Port `publish-signing-key`, `pipeline-factory` (drift + sign + register),
   `code-intake`.
3. Run **GHA + Jenkins in parallel** for one week. Compare:
   - Manifest digests byte-identical
   - Signatures verifiable by both flows' published PEMs
   - `make demo` (LocalStack) passes after each Jenkins build

### Sprint M3 — LocalStack + Terraform + cutover (1 week)

1. Port `localstack-demo`, `terraform-validate` (the PR-comment step is the
   only piece needing care).
2. Flip branch protection required-checks list to Jenkins contexts.
3. Retire GHA: rename files to `*.disabled.yml` for one release as rollback
   safety, then delete.
4. Sweep docs: ADR-0003, ADR-0009, compliance matrix, runbooks,
   technical-overview, CLAUDE_CODE_BRIEF, Phase 3 closeout.
5. Stamp `Status: Accepted` on this ADR.

## Consequences

### Positive

- Single source of truth for CI policy aligns with EXL standards; no policy
  carve-out for this platform.
- IRSA is functionally equivalent to GHA OIDC — keeps the per-job ephemeral
  credential property the security story depends on.
- Shared-library extraction makes the next CI swap cheaper (the surface area
  is concentrated in `ci/jenkins/vars/`).
- Forces a single ADR-0011 to capture every CI cross-cutting concern;
  scattered references in ADR-0003 / ADR-0009 get re-anchored.

### Negative

- Throws away ~560 LOC of working GHA YAML. The signing/registration logic
  is preserved in the Python CLIs but the orchestration YAML must be rewritten.
- IRSA on EKS requires the EKS cluster ARN, ServiceAccount names, and namespace
  to be known before the trust policy can be written. Blocks Sprint M2 if ABSA
  hasn't agreed the cluster topology.
- The drift-gate commit-back loses GHA's first-party token (`GITHUB_TOKEN`,
  auto-issued, auto-rotated). A GitHub App or bot PAT is operationally heavier.
- Compliance matrix evidence URLs change shape (GHA run URLs → Jenkins build
  URLs). Auditors will need a mapping note for any pre-cutover runs.
- During Sprint M2 the platform briefly runs two CI providers — operational
  cost in dashboards, alerts, and incident triage doubles for ~1 week.

### Neutral

- Path-filtered triggers (`paths:` in GHA, `when { changeset 'path/**' }` in
  Jenkins) map 1:1. No behaviour change.
- Concurrency control (`concurrency:` in GHA, `lock(resource:...)` in Jenkins)
  maps 1:1. Same singleton-signer guarantee.
- LocalStack demo workflow ports trivially — docker-compose runs anywhere
  Docker runs.

## Open questions

1. **Does ABSA Cloud Platform run Jenkins on EKS?** Drives IRSA vs instance
   profile choice. Locks the trust-policy shape.
2. **GitHub App or bot PAT for drift-gate commit-back?** Recommend GitHub App
   for revocability; bot PAT acceptable as MVP.
3. **Secrets backend: AWS Secrets Manager or HashiCorp Vault?** Either works
   with the AWS Credentials Provider plugin or Vault plugin respectively;
   need ABSA preference for audit-log integration.
4. **Do we keep `GITHUB_TOKEN`-equivalent semantics across PR forks?** Jenkins
   multibranch with the GitHub Branch Source plugin can do this but requires
   "Build PRs from forks" to be enabled with the appropriate guard
   (review-then-build). Recommend matching GHA's existing behaviour: do not
   build fork PRs without explicit reviewer approval.
