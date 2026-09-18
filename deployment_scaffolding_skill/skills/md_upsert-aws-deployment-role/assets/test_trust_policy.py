"""
Tests for trust_policy.py — the multi-principal assume-role trust document.

Covered:
  - resolving an SSO/assumed-role caller ARN to a role ARN a human can assume
  - the reserved-SSO path special case
  - non-role callers (plain user / root / garbage) resolve to None
  - the trust doc always trusts CI, adds the human caller, gates root on opt-in,
    and only ever references principals in the same account (hack-proof)

Run:  python3 -m pytest commands/assets/createDeploymentRole/test_trust_policy.py -q
"""

import pytest

import trust_policy


# --------------------------------------------------------------------------- #
# Caller ARN resolution
# --------------------------------------------------------------------------- #
def test_assumed_role_resolves_to_role_arn():
    caller = "arn:aws:sts::123456789012:assumed-role/AdminRole/alice@corp"
    assert trust_policy.caller_role_arn(caller) == "arn:aws:iam::123456789012:role/AdminRole"


def test_reserved_sso_role_gets_reserved_path():
    caller = "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_Admin_abc123/alice"
    resolved = trust_policy.caller_role_arn(caller)
    assert resolved == ("arn:aws:iam::123456789012:role/aws-reserved/"
                        "sso.amazonaws.com/AWSReservedSSO_Admin_abc123")


def test_non_role_callers_resolve_to_none():
    assert trust_policy.caller_role_arn("arn:aws:iam::123456789012:user/bob") is None
    assert trust_policy.caller_role_arn("arn:aws:iam::123456789012:root") is None
    assert trust_policy.caller_role_arn("") is None
    assert trust_policy.caller_role_arn(None) is None


# --------------------------------------------------------------------------- #
# Trust document assembly
# --------------------------------------------------------------------------- #
def principals(doc):
    return doc["Statement"][0]["Principal"]["AWS"]


def test_ci_user_always_trusted():
    doc = trust_policy.build_trust_policy("123456789012", "CI_USER")
    assert principals(doc) == ["arn:aws:iam::123456789012:user/CI_USER"]
    assert doc["Statement"][0]["Action"] == "sts:AssumeRole"


def test_human_caller_added_for_debugging():
    doc = trust_policy.build_trust_policy(
        "123456789012", "CI_USER",
        caller_arn="arn:aws:sts::123456789012:assumed-role/AdminRole/alice")
    assert "arn:aws:iam::123456789012:user/CI_USER" in principals(doc)
    assert "arn:aws:iam::123456789012:role/AdminRole" in principals(doc)


def test_root_is_opt_in_only():
    without = trust_policy.build_trust_policy("123456789012", "CI_USER")
    assert not any(p.endswith(":root") for p in principals(without))
    with_root = trust_policy.build_trust_policy("123456789012", "CI_USER", include_root=True)
    assert "arn:aws:iam::123456789012:root" in principals(with_root)


def test_all_principals_are_in_the_same_account():
    # Hack-proof: never trust a principal outside the target account.
    doc = trust_policy.build_trust_policy(
        "123456789012", "CI_USER",
        caller_arn="arn:aws:sts::123456789012:assumed-role/AdminRole/alice",
        include_root=True)
    assert all(":123456789012:" in p for p in principals(doc))


def test_no_duplicate_principals():
    # A caller whose resolved role equals nothing special shouldn't duplicate CI.
    doc = trust_policy.build_trust_policy(
        "123456789012", "CI_USER",
        caller_arn="arn:aws:sts::123456789012:assumed-role/AdminRole/alice")
    assert len(principals(doc)) == len(set(principals(doc)))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
