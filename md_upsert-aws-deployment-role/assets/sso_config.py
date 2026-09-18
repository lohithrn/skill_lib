#!/usr/bin/env python3
"""
sso_config.py
============

Discover the AWS SSO settings for a repo WITHOUT baking in any company defaults.
The profile name is derived from the repo/folder, and the SSO start URL / region
are DERIVED — never hardcoded — in this order:

  1. an already-configured AWS profile of that name (its sso_start_url/sso_region);
  2. the repo's own deploy scripts (an `https://<org>.awsapps.com/start` literal);
  3. otherwise: unknown → the caller must ASK the user.

The regexes and file scan are pure; the profile lookup is injected as a callback
(so it's testable without the AWS CLI). No `acme`/account-id constants live
here — that was the bug this module removes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# An IAM Identity Center / SSO start URL. No specific org is assumed.
_START_URL_RE = re.compile(r"https://[a-z0-9][a-z0-9-]*\.awsapps\.com/start/?#?/?")
_SSO_REGION_RE = re.compile(
    r"sso[_-]?region\s*[=:]\s*[\"']?((?:us|eu|ap|ca|sa|me|af|il)-[a-z]+-[1-9])")

_SCAN_EXTS = {".sh", ".bash", ".zsh", ".yml", ".yaml", ".tf", ".tfvars", ".env"}


@dataclass
class SsoSettings:
    """What we need to configure/login an SSO profile. Any field may be missing."""
    start_url: str | None = None
    sso_region: str | None = None

    @property
    def complete(self) -> bool:
        return bool(self.start_url and self.sso_region)


def profile_name_for_repo(repo_name: str) -> str:
    """The dedicated per-repo profile name: the sanitized repo/folder name."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", repo_name).strip("-").lower()
    return slug or "crowbar-deploy"


def discover_from_repo(repo_path: Path) -> SsoSettings:
    """Scan the repo's deploy scripts for an SSO start URL / region literal."""
    settings = SsoSettings()
    for f in sorted(repo_path.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in _SCAN_EXTS:
            continue
        if any(p in (".git", ".terraform", "node_modules") for p in f.parts):
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        settings = _merge(settings, text)
        if settings.complete:
            break
    return settings


def _merge(settings: SsoSettings, text: str) -> SsoSettings:
    if not settings.start_url:
        m = _START_URL_RE.search(text)
        if m:
            settings.start_url = m.group(0)
    if not settings.sso_region:
        m = _SSO_REGION_RE.search(text)
        if m:
            settings.sso_region = m.group(1)
    return settings


def resolve_sso_settings(
    repo_path: Path,
    profile_name: str,
    profile_lookup,
) -> SsoSettings:
    """
    Resolve SSO settings by precedence: existing profile config first, then the
    repo's deploy scripts. `profile_lookup(key)` returns a configured profile
    value (e.g. from `aws configure get`), or None. Returns whatever was found;
    an incomplete result signals the caller to ASK the user.
    """
    from_profile = SsoSettings(
        start_url=profile_lookup(f"profile.{profile_name}.sso_start_url"),
        sso_region=profile_lookup(f"profile.{profile_name}.sso_region"))
    if from_profile.complete:
        return from_profile
    from_repo = discover_from_repo(repo_path)
    # Prefer any concrete value we already have from the profile over a repo hit.
    return SsoSettings(
        start_url=from_profile.start_url or from_repo.start_url,
        sso_region=from_profile.sso_region or from_repo.sso_region)
