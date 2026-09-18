#!/usr/bin/env python3
"""
trust_policy.py
==============

Who is allowed to assume the deployment role, as a pure (AWS-free) function of a
few identities. Kept separate so the trust document can be built and tested
without any IAM calls.

The trust policy is deliberately **multi-principal**: CI must assume the role,
but a human debugging a broken deploy must be able to as well — without handing
out a long-lived access key. So we trust, when available:

  - the **CI user** (`arn:aws:iam::<acct>:user/<user>`) — the automation path;
  - the **human caller's role** — resolved from their current session so an
    engineer running this command can immediately `aws sts assume-role` to
    reproduce what CI does (the debugging leeway);
  - optionally the **account root** (`arn:aws:iam::<acct>:root`) — the broadest
    escape hatch, gated behind an explicit opt-in, never on by default.

It stays hack-proof by only ever trusting principals *inside this same account*
(assembled from the verified account id) and by making root opt-in, while still
being loose enough to debug.
"""

from __future__ import annotations

import re

# An SSO/assumed-role session ARN looks like:
#   arn:aws:sts::<acct>:assumed-role/<RoleName>/<session>
# The underlying role a human can re-assume is:
#   arn:aws:iam::<acct>:role/<RoleName>   (or the SSO-reserved path)
_ASSUMED_ROLE_RE = re.compile(
    r"^arn:aws:sts::(?P<acct>\d{12}):assumed-role/(?P<role>[^/]+)/")


def caller_role_arn(caller_arn: str) -> str | None:
    """
    Resolve a caller identity ARN to a role ARN a human can assume, or None if it
    isn't a role session (e.g. a plain IAM user or the root account).

    An `assumed-role` session ARN carries the role NAME but not its full path, so
    we cannot always reconstruct the exact SSO-reserved path
    (`role/aws-reserved/sso.amazonaws.com/<region>/AWSReservedSSO_...`). When the
    role name starts with `AWSReservedSSO_` we emit the reserved prefix so the
    common SSO case resolves; otherwise a plain `role/<name>`.
    """
    match = _ASSUMED_ROLE_RE.match(caller_arn or "")
    if not match:
        return None
    account, role = match.group("acct"), match.group("role")
    if role.startswith("AWSReservedSSO_"):
        return f"arn:aws:iam::{account}:role/aws-reserved/sso.amazonaws.com/{role}"
    return f"arn:aws:iam::{account}:role/{role}"


def trusted_principals(
    account: str,
    ci_user_name: str,
    caller_arn: str | None = None,
    include_root: bool = False,
) -> list[str]:
    """
    The ordered, de-duped principal ARNs allowed to assume the role: CI user
    always, the human caller's role when it resolves (debug leeway), and the
    account root only when `include_root` is set. All within `account`.
    """
    principals: list[str] = [f"arn:aws:iam::{account}:user/{ci_user_name}"]
    resolved = caller_role_arn(caller_arn) if caller_arn else None
    if resolved:
        principals.append(resolved)
    if include_root:
        principals.append(f"arn:aws:iam::{account}:root")
    seen: set[str] = set()
    return [p for p in principals if not (p in seen or seen.add(p))]


def build_trust_policy(
    account: str,
    ci_user_name: str,
    caller_arn: str | None = None,
    include_root: bool = False,
) -> dict:
    """Assemble the role's multi-principal assume-role trust document."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowTrustedPrincipalsToAssume",
                "Effect": "Allow",
                "Principal": {
                    "AWS": trusted_principals(account, ci_user_name, caller_arn, include_root)},
                "Action": "sts:AssumeRole",
            }
        ],
    }
