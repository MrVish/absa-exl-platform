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
  command = plan

  assert {
    condition = strcontains(
      aws_iam_role.ci_deploy.assume_role_policy,
      "repo:absa-group/absa-exl-platform:ref:refs/heads/main",
    )
    error_message = "ci-deploy trust policy sub condition must include the configured branch"
  }
}

run "ci_deploy_inline_policy_denies_credential_mutation" {
  command = plan

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
    condition     = aws_iam_openid_connect_provider.github.client_id_list[0] == "sts.amazonaws.com"
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
