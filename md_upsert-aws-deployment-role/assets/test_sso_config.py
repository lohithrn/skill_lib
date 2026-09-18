"""
Tests for sso_config.py — deriving the per-repo SSO profile name and SSO settings
with NO company defaults. Pure/AWS-free (the profile lookup is injected).

Run:  python3 -m pytest commands/assets/createDeploymentRole/test_sso_config.py -q
"""

from pathlib import Path

import re

import pytest

import sso_config as s


def test_profile_name_is_sanitized_repo_name():
    assert s.profile_name_for_repo("webapp") == "webapp"
    assert s.profile_name_for_repo("World-Wide.Web") == "world-wide-web"
    assert s.profile_name_for_repo("  ") == "aws-deploy"


def test_settings_taken_from_existing_profile_first():
    def lookup(key):
        if key.endswith("sso_start_url"):
            return "https://acme.awsapps.com/start"
        if key.endswith("sso_region"):
            return "us-east-1"
        return None
    got = s.resolve_sso_settings(Path("/nonexistent"), "acme", lookup)
    assert got.complete
    assert got.start_url == "https://acme.awsapps.com/start"
    assert got.sso_region == "us-east-1"


def test_settings_derived_from_repo_scripts_when_profile_missing(tmp_path):
    (tmp_path / "deploy.sh").write_text(
        'aws sso login\n# sso_region = us-west-2\n'
        'START=https://myorg.awsapps.com/start\n')
    got = s.resolve_sso_settings(tmp_path, "myorg", lambda _k: None)
    assert got.start_url == "https://myorg.awsapps.com/start"
    assert got.sso_region == "us-west-2"


def test_incomplete_when_nothing_found(tmp_path):
    # No profile config, no hints in the repo -> caller must ask the user.
    got = s.resolve_sso_settings(tmp_path, "x", lambda _k: None)
    assert not got.complete
    assert got.start_url is None


def test_no_company_defaults_anywhere():
    # Regression: this module used to carry one org's start URL and account id as
    # defaults, so every repo silently inherited them. The check is written by
    # SHAPE, not by any particular org's name: a concrete start URL (a literal
    # subdomain before .awsapps.com) and any 12-digit account id are both banned.
    # The generic regex that MATCHES such a URL is fine — its subdomain is a
    # character class, not a literal.
    src = Path(__file__).with_name("sso_config.py").read_text()
    assert re.search(r"https://[a-z0-9][a-z0-9-]*\.awsapps\.com", src) is None
    assert re.search(r"(?<!\d)\d{12}(?!\d)", src) is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
