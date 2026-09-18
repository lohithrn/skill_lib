"""
Tests for repo_source.py — resolving a repo from a remote URL or a local folder.
Network/git are not exercised here; the URL-vs-path classification and local
resolution are pure.

Run:  python3 -m pytest commands/assets/createDeploymentRole/test_repo_source.py -q
"""

from pathlib import Path

import pytest

import repo_source


def test_classifies_github_urls_as_remote():
    assert repo_source.looks_like_repo_url("https://github.com/org/repo")
    assert repo_source.looks_like_repo_url("https://github.com/org/repo.git")
    assert repo_source.looks_like_repo_url("git@github.com:org/repo.git")
    assert repo_source.looks_like_repo_url("ssh://git@github.com/org/repo")


def test_classifies_local_paths_as_not_remote():
    assert not repo_source.looks_like_repo_url("/Users/x/project")
    assert not repo_source.looks_like_repo_url("./relative/dir")
    assert not repo_source.looks_like_repo_url("~/code/thing")


def test_parse_repo_url_extracts_org_and_repo():
    assert repo_source.parse_repo_url("https://github.com/acme/webapp.git") == \
        ("acme", "webapp")
    assert repo_source.parse_repo_url("git@github.com:org/repo") == ("org", "repo")


def test_parse_repo_url_rejects_non_github():
    with pytest.raises(ValueError):
        repo_source.parse_repo_url("not-a-url")


def test_resolve_local_folder_returns_it(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert repo_source.resolve_repo_source(str(repo)) == repo.resolve()


def test_resolve_missing_local_folder_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        repo_source.resolve_repo_source(str(tmp_path / "nope"))


def test_github_auth_gate_raises_when_gh_missing(monkeypatch):
    monkeypatch.setattr(repo_source.shutil, "which", lambda _: None)
    with pytest.raises(repo_source.GitHubAuthError):
        repo_source.ensure_github_auth()


def test_github_auth_gate_raises_when_logged_out(monkeypatch):
    monkeypatch.setattr(repo_source.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(repo_source.subprocess, "run",
                        lambda *a, **k: type("R", (), {"returncode": 1})())
    with pytest.raises(repo_source.GitHubAuthError):
        repo_source.ensure_github_auth()


def test_remote_clone_checks_auth_before_cloning(monkeypatch, tmp_path):
    # A URL source must hit the auth gate; if gh is logged out we must fail there,
    # NOT attempt a clone.
    monkeypatch.setattr(repo_source.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(repo_source.subprocess, "run",
                        lambda *a, **k: type("R", (), {"returncode": 1})())
    cloned = []
    monkeypatch.setattr(repo_source, "clone_repo", lambda *a: cloned.append(a))
    with pytest.raises(repo_source.GitHubAuthError):
        repo_source.resolve_repo_source("https://github.com/org/repo")
    assert not cloned, "must not clone when auth check fails"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
