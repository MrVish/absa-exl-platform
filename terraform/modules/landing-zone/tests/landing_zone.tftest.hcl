# Plan-only test fixture — uses mock_provider so the AWS provider's data
# sources (aws_availability_zones, aws_region) don't make real API calls.
# Must only ever be in test files. Real apply uses the caller's provider.
mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["af-south-1a", "af-south-1b", "af-south-1c"]
    }
  }
  mock_data "aws_region" {
    defaults = {
      name = "af-south-1"
    }
  }
}

variables {
  env                = "dev"
  vpc_cidr           = "10.40.0.0/20"
  availability_zones = 3
  transit_gateway_id = "tgw-0123456789abcdef0"
  tags = {
    cost_center = "ml-platform"
    module      = "landing-zone"
  }
}

run "vpc_has_three_subnets_per_tier" {
  command = plan

  assert {
    condition     = length(aws_subnet.public) == 3
    error_message = "Expected 3 public subnets across AZs"
  }

  assert {
    condition     = length(aws_subnet.private) == 3
    error_message = "Expected 3 private subnets across AZs"
  }

  assert {
    condition     = length(aws_subnet.data) == 3
    error_message = "Expected 3 data subnets across AZs"
  }
}

run "non_prod_uses_single_nat_gateway" {
  command = plan

  variables {
    env = "dev"
  }

  assert {
    condition     = length(aws_nat_gateway.this) == 1
    error_message = "Non-prod must use a single NAT gateway for cost"
  }
}

run "prod_uses_one_nat_gateway_per_az" {
  command = plan

  variables {
    env = "prod"
  }

  assert {
    condition     = length(aws_nat_gateway.this) == 3
    error_message = "Prod must use one NAT gateway per AZ"
  }
}

run "flow_logs_are_enabled" {
  command = plan

  assert {
    condition     = aws_flow_log.vpc.traffic_type == "ALL"
    error_message = "VPC flow logs must capture ALL traffic"
  }
}

run "guardduty_detector_exists_when_enabled" {
  command = plan

  variables {
    enable_guardduty = true
  }

  assert {
    condition     = length(aws_guardduty_detector.this) == 1
    error_message = "GuardDuty detector must be created when enable_guardduty=true"
  }
}

run "security_hub_uses_foundational_standard" {
  command = plan

  variables {
    enable_security_hub = true
  }

  assert {
    condition     = length(aws_securityhub_standards_subscription.foundational) == 1
    error_message = "Security Hub Foundational standard must be subscribed"
  }
}

run "env_validation_rejects_unknown_value" {
  command = plan

  variables {
    env = "uat"
  }

  expect_failures = [
    var.env,
  ]
}
