#!/usr/bin/env python3
"""
repo_source.py
=============

Resolve "where is the repo?" for the deployment-role workflow. The user may give
either a **remote GitHub URL** (which we clone) or an **existing local folder**
(which we use in place) — and, for a URL, an optional branch to check out.

Kept as its own small module so the provisioner can accept both forms and so the
URL-vs-path classification is unit-testable without touching git or the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# Temp dirs we cloned into this run, so the caller can clean them up afterward.
# Only clones land here — user-supplied local folders are never tracked/removed.
_cloned_dirs: list[Path] = []


class GitHubAuthError(RuntimeError):
    """Raised when the GitHub CLI is missing or not logged in."""


def cleanup_clones() -> list[Path]:
    """Remove every temp clone made this run. Returns the paths removed."""
    removed: list[Path] = []
    while _cloned_dirs:
        path = _cloned_dirs.pop()
        try:
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path)
        except OSError:
            pass
    return removed

# Matches an https or ssh GitHub URL; the classifier only needs "does this look
# like a remote we should clone" vs "a local folder".
_GITHUB_RE = re.compile(r"github\.com[/:]", re.IGNORECASE)


def looks_like_repo_url(source: str) -> bool:
    """True when the source string is a remote git URL (clone), not a local path."""
    s = source.strip()
    return bool(_GITHUB_RE.search(s)) or s.startswith(("git@", "http://", "https://", "ssh://"))


def parse_repo_url(url: str) -> tuple[str, str]:
    """Return (org, repo) parsed from an https or ssh GitHub URL."""
    cleaned = url.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+)$", cleaned)
    if not match:
        raise ValueError(f"Could not parse a GitHub org/repo from: {url}")
    return match.group(1), match.group(2)


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd).returncode


def ensure_github_auth() -> None:
    """
    Verify the GitHub CLI is installed and authenticated BEFORE any remote clone,
    so a private repo does not fail cloning with a confusing error. Raises
    GitHubAuthError (with the exact fix) if not — the caller runs `gh auth login`.
    """
    if shutil.which("gh") is None:
        raise GitHubAuthError(
            "GitHub CLI 'gh' not found. Install it, then run `gh auth login`.")
    if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode != 0:
        raise GitHubAuthError(
            "Not logged in to GitHub. Run `gh auth login` (in the prompt: "
            "`! gh auth login`), then re-run.")


def clone_repo(url: str, dest: Path) -> None:
    """Clone `url` into `dest`, preferring gh and falling back to plain git."""
    if _run(["gh", "repo", "clone", url, str(dest)]) == 0:
        return
    if _run(["git", "clone", url, str(dest)]) != 0:
        raise RuntimeError(f"Failed to clone {url}")


def checkout_branch(repo_dir: Path, branch: str) -> None:
    """Check out an existing local/remote branch, or leave HEAD as-is if blank."""
    if not branch:
        return
    if _run(["git", "-C", str(repo_dir), "checkout", branch]) == 0:
        return
    if _run(["git", "-C", str(repo_dir), "checkout", "--track", f"origin/{branch}"]) != 0:
        raise RuntimeError(f"Could not check out branch '{branch}' in {repo_dir}")


def resolve_repo_source(source: str, branch: str = "", dest: Path | None = None) -> Path:
    """
    Resolve a URL-or-path source to a local repo directory.

    A remote URL is cloned (into `dest`, or a fresh temp dir) and the branch
    checked out; a local path is expanded and returned as-is. Raises on a missing
    local folder or a failed clone.
    """
    if looks_like_repo_url(source):
        # Verify GitHub auth first — a private repo would otherwise fail the clone
        # with a confusing permission error.
        ensure_github_auth()
        target = dest or Path(tempfile.mkdtemp(prefix="aws-deploy-repo-"))
        if dest is None:
            _cloned_dirs.append(target)  # we own this temp dir; clean it up later
        clone_repo(source, target)
        checkout_branch(target, branch)
        return target
    local = Path(source).expanduser().resolve()
    if not local.is_dir():
        raise NotADirectoryError(f"Local repo folder does not exist: {local}")
    return local
