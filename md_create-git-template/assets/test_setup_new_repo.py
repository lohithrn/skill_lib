import subprocess
from pathlib import Path
from types import SimpleNamespace

import setup_new_repo


def test_accepts_local_folder_and_branch():
    args = setup_new_repo.parse_args([
        "--repo-path", "/tmp/example", "--branch", "feature/infra", "--type", "frontend"
    ])
    assert args.repo_path == "/tmp/example"
    assert args.repo_url is None
    assert args.branch == "feature/infra"


def test_accepts_explicit_named_aws_profile():
    args = setup_new_repo.parse_args(["--repo-path", "/tmp/example", "--aws-profile", "team-admin"])
    assert args.aws_profile == "team-admin"
    assert args.account is None


def test_aws_identity_is_verified_with_selected_profile(monkeypatch):
    calls = []
    monkeypatch.setattr(setup_new_repo.shutil, "which", lambda _: "/usr/bin/aws")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "must-not-leak")

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("env", {})))
        return SimpleNamespace(returncode=0, stdout="123456789012\n")

    monkeypatch.setattr(setup_new_repo, "run", fake_run)
    account = setup_new_repo.ensure_aws_auth("team-admin")
    assert account == "123456789012"
    assert calls[0][0] == [
        "aws", "sts", "get-caller-identity", "--profile", "team-admin",
        "--query", "Account", "--output", "text",
    ]
    assert calls[0][1]["AWS_PROFILE"] == "team-admin"
    assert "AWS_ACCESS_KEY_ID" not in calls[0][1]


def test_template_command_has_no_deployment_role_switch():
    args = setup_new_repo.parse_args(["--repo-path", "/tmp/example"])
    assert not hasattr(args, "run_deploy_role")


def test_copy_template_strips_tmpl_suffix_and_skips_tokens_doc(tmp_path: Path):
    template = tmp_path / "tpl"
    (template / "infra").mkdir(parents=True)
    (template / "TOKENS.md.tmpl").write_text("token docs\n")
    (template / "infra" / "provider_login.sh.tmpl").write_text("echo __PROJECT_NAME__\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    written = setup_new_repo.copy_template(template, repo, {"__PROJECT_NAME__": "webapp"})
    assert written == ["infra/provider_login.sh"]
    out = repo / "infra" / "provider_login.sh"
    assert out.read_text() == "echo webapp\n"
    assert out.stat().st_mode & 0o111  # the .sh executable bit survives the strip
    assert not (repo / "TOKENS.md").exists()


def test_no_default_sso_start_url(tmp_path: Path):
    # A baked-in start URL would point a scaffolded repo at one organisation.
    args = setup_new_repo.parse_args(["--repo-path", "/tmp/example"])
    assert args.sso_start_url == ""
    subs = setup_new_repo.build_substitutions(
        setup_new_repo.parse_args(["--repo-path", "/tmp/example", "--account", "123456789012"]),
        "acme", "webapp", "webapp", set(), "frontend",
    )
    assert "__SSO_START_URL__" not in subs


def test_checkout_branch_creates_and_selects_branch(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    setup_new_repo.checkout_branch(repo, "feature/infra")
    current = subprocess.run(
        ["git", "branch", "--show-current"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert current == "feature/infra"
