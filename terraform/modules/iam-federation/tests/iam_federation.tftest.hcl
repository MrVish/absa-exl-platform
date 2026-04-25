# Plan-only test fixture — uses mock_provider so the AWS provider can
# initialise without real AWS access. Real apply uses the caller's provider.
mock_provider "aws" {}

variables {
  env                                    = "dev"
  absa_identity_center_saml_provider_arn = "arn:aws:iam::000000000000:saml-provider/AWSSSO_test_DO_NOT_DELETE"
  permissions_boundary_arn               = "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary"
  github_org_slash_repo                  = "absa-group/absa-exl-platform"
  allowed_github_branches_for_apply      = ["main"]
  tags = {
    cost_center = "ml-platform"
  }
}

run "all_workload_roles_attach_permissions_boundary" {
  command = plan

  assert {
    condition = (
      aws_iam_role.platform_engineer.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary" &&
      aws_iam_role.platform_operator.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary" &&
      aws_iam_role.platform_readonly.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary" &&
      aws_iam_role.break_glass.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary" &&
      aws_iam_role.ci_deploy.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary"
    )
    error_message = "All five roles must attach the env-scoped permissions boundary"
  }
}

run "break_glass_trust_policy_requires_mfa" {
  command = plan

  assert {
    condition     = strcontains(aws_iam_role.break_glass.assume_role_policy, "MultiFactorAuthPresent")
    error_message = "Break-glass trust policy must require MFA"
  }
}

run "ci_deploy_sub_condition_includes_branch" {
  # 'apply' (not plan) — under mock_provider, aws_iam_role.assume_role_policy
  # is computed-unknown at plan time. Apply produces the populated string.
  command = apply

  assert {
    condition = strcontains(
      aws_iam_role.ci_deploy.assume_role_policy,
      "repo:absa-group/absa-exl-platform:ref:refs/heads/main",
    )
    error_message = "ci-deploy trust policy sub condition must include the configured branch"
  }
}

run "ci_deploy_inline_policy_denies_credential_mutation" {
  # 'apply' for the same mock_provider/computed-attr reason as above.
  command = apply

  assert {
    condition = (
      strcontains(aws_iam_role_policy.ci_deploy.policy, "iam:CreateUser") &&
      strcontains(aws_iam_role_policy.ci_deploy.policy, "iam:CreateAccessKey") &&
      strcontains(aws_iam_role_policy.ci_deploy.policy, "kms:ScheduleKeyDeletion") &&
      strcontains(aws_iam_role_policy.ci_deploy.policy, "cloudtrail:StopLogging")
    )
    error_message = "ci-deploy inline policy must explicitly deny credential mutation, key deletion, and audit-evasion actions"
  }
}

run "oidc_provider_uses_sts_client_id" {
  command = plan

  assert {
    # client_id_list is typed as a set, not a list — index access is invalid.
    condition     = contains(aws_iam_openid_connect_provider.github.client_id_list, "sts.amazonaws.com")
    error_message = "GitHub OIDC provider client_id_list must include sts.amazonaws.com"
  }
}

run "session_durations_match_role_purpose" {
  command = plan

  assert {
    condition = (
      aws_iam_role.platform_engineer.max_session_duration == 28800 &&
      aws_iam_role.platform_operator.max_session_duration == 14400 &&
      aws_iam_role.platform_readonly.max_session_duration == 28800 &&
      aws_iam_role.break_glass.max_session_duration == 3600 &&
      aws_iam_role.ci_deploy.max_session_duration == 3600
    )
    error_message = "Session durations: engineer/readonly 8h, operator 4h, break-glass/ci-deploy 1h"
  }
}

run "env_validation_rejects_unknown_value" {
  command = plan

  variables {
    env = "qa"
  }

  expect_failures = [
    var.env,
  ]
}

run "n_branches_produce_n_sub_conditions" {
  # 'apply' for the same mock_provider/computed-attr reason as above.
  command = apply

  variables {
    allowed_github_branches_for_apply = ["main", "release", "hotfix"]
  }

  assert {
    condition = alltrue([
      strcontains(aws_iam_role.ci_deploy.assume_role_policy, "repo:absa-group/absa-exl-platform:ref:refs/heads/main"),
      strcontains(aws_iam_role.ci_deploy.assume_role_policy, "repo:absa-group/absa-exl-platform:ref:refs/heads/release"),
      strcontains(aws_iam_role.ci_deploy.assume_role_policy, "repo:absa-group/absa-exl-platform:ref:refs/heads/hotfix"),
    ])
    error_message = "When N branches are configured, the ci-deploy trust policy must contain N corresponding sub conditions"
  }
}
