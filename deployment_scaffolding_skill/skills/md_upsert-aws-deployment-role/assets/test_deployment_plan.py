"""
Tests for deployment_plan.py — the AWS-free planning half of the deployment-role
workflow. Everything here runs with NO AWS calls.

Covered:
  - terraform discovery (known infra dir, script-inferred, *.tf fallback)
  - naming + region parsing
  - build_plan assembly: policy + boundary generation, prod region guardrail,
    boundary ARN wiring, IAM detection
  - the plan is fully produced with only a placeholder account (no AWS)

Run:  python3 -m pytest commands/assets/createDeploymentRole/test_deployment_plan.py -q
"""

from pathlib import Path

import pytest

import deployment_plan


def make_repo(tmp_path: Path, tf_body: str, rel="infra/terraform") -> Path:
    d = tmp_path / rel
    d.mkdir(parents=True)
    (d / "main.tf").write_text(tf_body)
    return tmp_path


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def test_discovers_known_infra_dir(tmp_path):
    repo = make_repo(tmp_path, 'resource "aws_s3_bucket" "b" { bucket = "x" }')
    dirs = deployment_plan.discover_terraform(repo, "prod")
    assert dirs == [repo / "infra" / "terraform"]


def test_discovers_tf_anywhere_as_fallback(tmp_path):
    d = tmp_path / "weird" / "place"
    d.mkdir(parents=True)
    (d / "x.tf").write_text('resource "aws_s3_bucket" "b" {}')
    dirs = deployment_plan.discover_terraform(tmp_path, "beta")
    assert d in dirs


def test_discovery_falls_back_to_repo_when_no_tf(tmp_path):
    assert deployment_plan.discover_terraform(tmp_path, "beta") == [tmp_path]


# --------------------------------------------------------------------------- #
# Naming + regions
# --------------------------------------------------------------------------- #
def test_build_names_parallel_suffixes():
    role, policy, boundary = deployment_plan.build_names("WebApp", "frontend", "prod")
    assert role == "webapp-frontend-prod-deploy-role"
    assert policy == "webapp-frontend-prod-deploy-policy"
    assert boundary == "webapp-frontend-prod-deploy-boundary"


def test_parse_regions_dedupes_and_defaults():
    assert deployment_plan.parse_regions("us-west-2, us-west-2 us-east-1", "x") == ["us-west-2", "us-east-1"]
    assert deployment_plan.parse_regions("", "us-west-2") == ["us-west-2"]


# --------------------------------------------------------------------------- #
# Plan assembly (no AWS)
# --------------------------------------------------------------------------- #
def test_build_plan_generates_policy_and_boundary_without_aws(tmp_path):
    repo = make_repo(
        tmp_path,
        'terraform { backend "s3" {} }\n'
        'resource "aws_cloudfront_distribution" "c" {}\n'
        'resource "aws_s3_bucket" "b" { bucket = "x" }\n',
    )
    plan = deployment_plan.build_plan(
        repo_path=repo, component="frontend", stage="prod", repo_name="wwweb",
        regions=["us-west-1"],
    )
    # Names + ARN use the placeholder account (no AWS was contacted).
    assert plan.role_name == "wwweb-frontend-prod-deploy-role"
    assert deployment_plan.PLACEHOLDER_ACCOUNT in plan.boundary_arn
    # CloudFront implies ACM read + us-east-1 in the prod guardrail.
    allow = {a for s in plan.permissions_policy["Statement"]
             if s["Effect"] == "Allow" for a in (s.get("Action") or [])}
    assert "acm:DescribeCertificate" in allow
    deny = next(s for s in plan.permissions_policy["Statement"] if s["Effect"] == "Deny")
    assert "us-east-1" in deny["Condition"]["StringNotEquals"]["aws:RequestedRegion"]
    # A boundary document is always produced.
    assert plan.boundary_policy["Statement"]


def test_build_plan_beta_has_no_region_guardrail(tmp_path):
    repo = make_repo(tmp_path, 'resource "aws_s3_bucket" "b" { bucket = "x" }')
    plan = deployment_plan.build_plan(
        repo_path=repo, component="frontend", stage="beta", repo_name="wwweb",
        regions=["us-west-2"],
    )
    assert not [s for s in plan.permissions_policy["Statement"] if s["Effect"] == "Deny"]


def test_build_plan_detects_iam_management(tmp_path):
    repo = make_repo(tmp_path, 'resource "aws_iam_role" "r" { name = "x" }')
    plan = deployment_plan.build_plan(
        repo_path=repo, component="backend", stage="prod", repo_name="svc",
        account="123456789012",
    )
    assert plan.creates_iam is True
    gated = [s for s in plan.permissions_policy["Statement"]
             if s.get("Sid") == "IAMCreateOnlyWithBoundary"]
    assert gated and gated[0]["Condition"]["StringEquals"]["iam:PermissionsBoundary"] == plan.boundary_arn


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
