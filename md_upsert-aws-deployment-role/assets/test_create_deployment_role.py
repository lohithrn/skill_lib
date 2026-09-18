import json
from pathlib import Path
from types import SimpleNamespace

import create_deployment_role


def test_profile_is_required_without_default_account():
    args = create_deployment_role.parse_args([])
    assert args.sso_profile is None
    assert args.account is None
    assert not hasattr(args, "cleanup_profile")


def test_preview_only_writes_json_and_makes_no_aws_calls(tmp_path, monkeypatch, capsys):
    # --no-read-aws is a PREVIEW: produce the policy + boundary JSON without ever
    # touching AWS, and say loudly that the result is unverified.
    repo = tmp_path / "repo" / "infra" / "terraform"
    repo.mkdir(parents=True)
    (repo / "main.tf").write_text('resource "aws_s3_bucket" "b" { bucket = "x" }')
    out = tmp_path / "plan"

    # Any AWS call would go through subprocess.run — make it explode if reached.
    def explode(*a, **k):
        raise AssertionError("preview (--no-read-aws) must not call AWS / subprocess")
    monkeypatch.setattr(create_deployment_role.subprocess, "run", explode)

    monkeypatch.setattr("sys.argv", [
        "create_deployment_role.py", "--dry-run", "--no-read-aws",
        "--component", "frontend", "--stage", "prod", "--repo-name", "wwweb",
        "--repo-path", str(tmp_path / "repo"), "--out-dir", str(out),
        "--user-name", "CI_USER", "--yes",
    ])
    create_deployment_role.main()

    policy = out / "wwweb-frontend-prod-deploy-role-policy.json"
    boundary = out / "wwweb-frontend-prod-deploy-boundary.json"
    assert policy.is_file() and boundary.is_file()
    doc = json.loads(policy.read_text())
    assert doc["Statement"], "policy should have statements"
    assert "PREVIEW ONLY" in capsys.readouterr().out


def test_dry_run_reads_live_aws_then_stops_without_applying(tmp_path, monkeypatch, capsys):
    # A real dry run authenticates, compares against the live role, and stops at
    # the apply gate (default NO under --yes -> apply_default False) with no writes.
    repo = tmp_path / "repo" / "infra" / "terraform"
    repo.mkdir(parents=True)
    (repo / "main.tf").write_text('resource "aws_s3_bucket" "b" { bucket = "x" }')
    out = tmp_path / "plan"

    monkeypatch.setattr(create_deployment_role, "admin_login",
                        lambda *a, **k: ("123456789012", "arn:aws:iam::123456789012:role/Admin"))
    compared = {"called": False}
    def fake_compare(plan):
        compared["called"] = True
    monkeypatch.setattr(create_deployment_role, "compare_with_aws", fake_compare)
    # provision must never run in a dry run that stops at the gate.
    def no_provision(*a, **k):
        raise AssertionError("dry run must not provision")
    monkeypatch.setattr(create_deployment_role, "provision", no_provision)

    monkeypatch.setattr("sys.argv", [
        "create_deployment_role.py", "--dry-run",
        "--component", "frontend", "--stage", "prod", "--repo-name", "wwweb",
        "--repo-path", str(tmp_path / "repo"), "--out-dir", str(out),
        "--user-name", "CI_USER", "--sso-profile", "wwweb", "--yes",
    ])
    create_deployment_role.main()

    assert compared["called"], "dry run must read/compare the live role"
    assert "No AWS changes were made" in capsys.readouterr().out


def test_admin_login_verifies_only_selected_profile(monkeypatch):
    calls = []
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "must-not-leak")

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("env", {})))
        return SimpleNamespace(
            returncode=0,
            stdout="123456789012\tarn:aws:sts::123456789012:assumed-role/Admin/alice\n")

    monkeypatch.setattr(create_deployment_role.subprocess, "run", fake_run)
    account, caller_arn = create_deployment_role.admin_login("team-admin", None, "us-west-2")
    assert account == "123456789012"
    assert caller_arn == "arn:aws:sts::123456789012:assumed-role/Admin/alice"
    assert calls[0][0] == [
        "aws", "sts", "get-caller-identity", "--profile", "team-admin",
        "--query", "[Account,Arn]", "--output", "text",
    ]
    assert calls[0][1]["AWS_PROFILE"] == "team-admin"
    assert "AWS_ACCESS_KEY_ID" not in calls[0][1]
    assert "AWS_ACCESS_KEY_ID" not in create_deployment_role.os.environ
