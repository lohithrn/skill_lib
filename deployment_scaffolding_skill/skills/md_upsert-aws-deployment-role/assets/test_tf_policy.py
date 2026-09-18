"""
Tests for tf_policy.py — the deterministic Terraform -> IAM policy generator.

Covered:
  - resource / data-source -> IAM action mapping (explicit + service:* fallback)
  - S3 remote-state backend detection
  - region detection from terraform (provider/var-default/tfvars) and scripts
  - the prod region guardrail: global-service carve-out (NotAction) and the
    regional-only fallback (Action "*"), plus that beta (no regions) adds no Deny

Run:  python3 -m pytest setup_new_aws/setup_deployment_roles/test_tf_policy.py -q
"""

from pathlib import Path

import pytest

import tf_policy


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def write_tf(tmp_path: Path, name: str, body: str) -> Path:
    d = tmp_path / "terraform"
    d.mkdir(exist_ok=True)
    (d / name).write_text(body)
    return d


def deny_stmt(policy: dict) -> dict | None:
    denies = [s for s in policy["Statement"] if s["Effect"] == "Deny"]
    return denies[0] if denies else None


def allow_actions(policy: dict) -> set[str]:
    actions: set[str] = set()
    for s in policy["Statement"]:
        if s["Effect"] == "Allow":
            actions.update(s.get("Action", []))
    return actions


# --------------------------------------------------------------------------- #
# Resource / data-source mapping
# --------------------------------------------------------------------------- #
def test_known_resource_maps_to_explicit_actions(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_s3_bucket" "b" { bucket = "x" }')
    policy = tf_policy.generate_policy_from_dirs([d])
    actions = allow_actions(policy)
    assert "s3:CreateBucket" in actions
    assert "s3:DeleteBucket" in actions
    # No wildcard for a fully-mapped type.
    assert "s3:*" not in actions


def test_unknown_resource_falls_back_to_service_wildcard(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_elasticache_cluster" "c" { cluster_id = "x" }')
    warnings = []
    policy = tf_policy.generate_policy_from_dirs([d], warn=warnings.append)
    actions = allow_actions(policy)
    assert "elasticache:*" in actions
    assert any("elasticache" in w for w in warnings)


def test_data_source_gets_read_only_actions(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'data "aws_caller_identity" "me" {}')
    actions = allow_actions(tf_policy.generate_policy_from_dirs([d]))
    assert actions == {"sts:GetCallerIdentity"}


def test_s3_backend_adds_state_statement(tmp_path):
    d = write_tf(
        tmp_path,
        "main.tf",
        'terraform { backend "s3" {} }\nresource "aws_s3_bucket" "b" { bucket = "x" }',
    )
    policy = tf_policy.generate_policy_from_dirs([d])
    sids = [s.get("Sid") for s in policy["Statement"]]
    assert "TerraformStateBackend" in sids
    backend = next(s for s in policy["Statement"] if s.get("Sid") == "TerraformStateBackend")
    assert "dynamodb:PutItem" in backend["Action"]


def test_no_backend_no_state_statement(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_s3_bucket" "b" { bucket = "x" }')
    policy = tf_policy.generate_policy_from_dirs([d])
    assert "TerraformStateBackend" not in [s.get("Sid") for s in policy["Statement"]]


# --------------------------------------------------------------------------- #
# Region guardrail
# --------------------------------------------------------------------------- #
def test_no_regions_means_no_deny(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_s3_bucket" "b" { bucket = "x" }')
    policy = tf_policy.generate_policy_from_dirs([d], regions=None)
    assert deny_stmt(policy) is None


def test_guardrail_exempts_only_present_global_services(tmp_path):
    # A CloudFront distribution implies ACM read (cert validation in us-east-1),
    # so acm:* is granted and therefore exempted even with no aws_acm_certificate
    # in the TF. sts is present (caller_identity); route53/iam are not.
    d = write_tf(
        tmp_path,
        "main.tf",
        'resource "aws_cloudfront_distribution" "c" {}\n'
        'resource "aws_s3_bucket" "b" { bucket = "x" }\n'
        'data "aws_caller_identity" "me" {}',
    )
    policy = tf_policy.generate_policy_from_dirs([d], regions=["us-west-2", "us-east-1"])
    deny = deny_stmt(policy)
    assert deny is not None
    assert set(deny["NotAction"]) == {"cloudfront:*", "acm:*", "sts:*"}  # present globals
    assert "Action" not in deny  # NotAction form, not Action form
    assert deny["Condition"]["StringNotEquals"]["aws:RequestedRegion"] == ["us-west-2", "us-east-1"]


def test_cloudfront_implies_acm_read_even_without_acm_resource(tmp_path):
    # Regression: a CloudFront distro whose viewer cert is a raw ARN (no
    # aws_acm_certificate resource/data) still needs ACM read, or CreateDistribution
    # fails with the misleading InvalidViewerCertificate error.
    d = write_tf(tmp_path, "main.tf", 'resource "aws_cloudfront_distribution" "c" {}')
    policy = tf_policy.generate_policy_from_dirs([d])
    allow_actions = {
        a for s in policy["Statement"] if s["Effect"] == "Allow"
        for a in (s.get("Action") or [])
    }
    assert "acm:DescribeCertificate" in allow_actions
    assert "acm:ListCertificates" in allow_actions


def test_cloudfront_forces_us_east_1_into_region_guardrail(tmp_path):
    # Even when the stage region is us-west-1 only, a CloudFront distro must add
    # us-east-1 to the allowed regions (that's where cert validation runs).
    d = write_tf(tmp_path, "main.tf", 'resource "aws_cloudfront_distribution" "c" {}')
    policy = tf_policy.generate_policy_from_dirs([d], regions=["us-west-1"])
    deny = deny_stmt(policy)
    assert deny is not None
    assert set(deny["Condition"]["StringNotEquals"]["aws:RequestedRegion"]) == {"us-west-1", "us-east-1"}


def test_guardrail_regional_only_falls_back_to_action_star(tmp_path):
    d = write_tf(
        tmp_path,
        "main.tf",
        'resource "aws_s3_bucket" "b" { bucket = "x" }\n'
        'resource "aws_dynamodb_table" "t" { name = "y" }',
    )
    policy = tf_policy.generate_policy_from_dirs([d], regions=["us-west-2"])
    deny = deny_stmt(policy)
    assert deny is not None
    assert deny["Action"] == "*"  # no global services -> Action "*"
    assert "NotAction" not in deny


# --------------------------------------------------------------------------- #
# Region detection
# --------------------------------------------------------------------------- #
def test_detect_region_from_provider_literal(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'provider "aws" { region = "eu-west-1" }')
    assert tf_policy.detect_regions([d]) == ["eu-west-1"]


def test_detect_region_from_variable_default(tmp_path):
    d = write_tf(
        tmp_path,
        "variables.tf",
        'variable "aws_region" {\n  type = string\n  default = "ap-south-1"\n}',
    )
    assert tf_policy.detect_regions([d]) == ["ap-south-1"]


def test_detect_region_from_shell_default_form(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'provider "aws" { region = var.aws_region }')
    (tmp_path / "deploy.sh").write_text('AWS_REGION="${AWS_REGION:-us-west-2}"\naws s3 ls\n')
    # tf alone finds nothing; repo scan finds the script hint.
    assert tf_policy.detect_regions([d]) == []
    assert tf_policy.detect_regions([d], repo=tmp_path) == ["us-west-2"]


def test_detect_ignores_dot_terraform_cache(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'provider "aws" { region = "us-west-2" }')
    cache = d / ".terraform"
    cache.mkdir()
    (cache / "terraform.tfvars").write_text('aws_region = "eu-central-1"')
    # The cached eu-central-1 must not leak in.
    assert tf_policy.detect_regions([d], repo=tmp_path) == ["us-west-2"]


def test_detect_orders_by_citation_count(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'provider "aws" { region = "us-west-2" }')
    # us-east-1 cited once (script), us-west-2 cited via provider (weight 3).
    (tmp_path / "ci.sh").write_text("aws configure --region us-east-1\n")
    ordered = tf_policy.detect_regions([d], repo=tmp_path)
    assert ordered[0] == "us-west-2"
    assert set(ordered) == {"us-west-2", "us-east-1"}


# --------------------------------------------------------------------------- #
# IAM management + permissions boundary (Option B)
# --------------------------------------------------------------------------- #
BARN = "arn:aws:iam::123456789012:policy/demo-deploy-boundary"


def test_non_iam_stack_needs_no_boundary(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_s3_bucket" "b" { bucket = "x" }')
    assert tf_policy.needs_boundary([d]) is False


def test_iam_stack_detected(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_iam_role" "r" { name = "x" }')
    assert tf_policy.needs_boundary([d]) is True


def test_iam_creation_is_gated_on_boundary(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_iam_role" "r" { name = "x" }')
    policy = tf_policy.generate_policy_from_dirs([d], boundary_arn=BARN)
    gated = [s for s in policy["Statement"] if s.get("Sid") == "IAMCreateOnlyWithBoundary"]
    assert gated, "expected a boundary-gated IAM creation statement"
    assert gated[0]["Condition"]["StringEquals"]["iam:PermissionsBoundary"] == BARN
    assert "iam:CreateRole" in gated[0]["Action"]
    # The ungated grant must NOT contain the creation actions.
    ungated = [s for s in policy["Statement"] if s.get("Sid") == "TerraformManagedResources"]
    if ungated:
        assert "iam:CreateRole" not in ungated[0]["Action"]


def test_iam_creation_ungated_without_boundary_warns(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_iam_role" "r" { name = "x" }')
    warnings = []
    policy = tf_policy.generate_policy_from_dirs([d], warn=warnings.append)  # no boundary
    # No gated statement; create actions fall into the plain grant, with a warning.
    assert not [s for s in policy["Statement"] if s.get("Sid") == "IAMCreateOnlyWithBoundary"]
    assert "iam:CreateRole" in allow_actions(policy)
    assert any("UNGATED" in w or "escalation" in w for w in warnings)


def test_boundary_doc_is_self_referential_and_denies_escalation(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_iam_role" "r" { name = "x" }')
    boundary = tf_policy.generate_boundary_from_dirs([d], BARN)
    sids = {s["Sid"]: s for s in boundary["Statement"]}
    # Self-referential: created roles may only create roles carrying THIS boundary.
    prop = sids["BoundarySelfPropagatingIAM"]
    assert prop["Condition"]["StringEquals"]["iam:PermissionsBoundary"] == BARN
    # Escalation actions are explicitly denied.
    deny = sids["BoundaryDenyEscalation"]
    assert deny["Effect"] == "Deny"
    assert "iam:CreateUser" in deny["Action"]
    assert "iam:CreateAccessKey" in deny["Action"]
    assert "organizations:*" in deny["Action"]


# --------------------------------------------------------------------------- #
# Read / describe leeway (debugging room without widening writes)
# --------------------------------------------------------------------------- #
def test_policy_grants_read_leeway_for_touched_services(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_s3_bucket" "b" { bucket = "x" }')
    policy = tf_policy.generate_policy_from_dirs([d])
    leeway = next((s for s in policy["Statement"] if s.get("Sid") == "ReadDescribeLeeway"), None)
    assert leeway is not None
    assert "s3:Describe*" in leeway["Action"]
    assert "s3:List*" in leeway["Action"]
    assert "s3:Get*" in leeway["Action"]


def test_boundary_allows_read_everywhere_but_denies_escalation(tmp_path):
    d = write_tf(tmp_path, "main.tf", 'resource "aws_iam_role" "r" { name = "x" }')
    boundary = tf_policy.generate_boundary_from_dirs([d], BARN)
    sids = {s["Sid"]: s for s in boundary["Statement"]}
    read = sids["BoundaryReadEverywhere"]
    assert "ec2:Describe*" in read["Action"]  # a service not even in the stack
    assert read["Effect"] == "Allow"
    # The escalation deny still wins over the broad reads.
    assert sids["BoundaryDenyEscalation"]["Effect"] == "Deny"
    assert "iam:CreateUser" in sids["BoundaryDenyEscalation"]["Action"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
