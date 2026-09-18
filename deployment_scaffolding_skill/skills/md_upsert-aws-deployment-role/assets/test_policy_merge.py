"""
Tests for policy_merge.py — additive-by-default merge of generated onto live.
Pure/AWS-free.

Run:  python3 -m pytest commands/assets/createDeploymentRole/test_policy_merge.py -q
"""

import pytest

import policy_merge as pm


def _actions(doc):
    out = set()
    for s in doc["Statement"]:
        v = s.get("Action") or s.get("NotAction") or []
        out.update([v] if isinstance(v, str) else v)
    return out


def test_no_live_returns_generated_unchanged():
    gen = {"Statement": [{"Sid": "A", "Action": ["s3:GetObject"]}]}
    r = pm.additive_merge(None, gen)
    assert r.had_live is False
    assert r.merged is gen
    assert r.would_remove is False


def test_merge_is_additive_never_shrinks():
    # Live has a broad action the generated doc omits — it must be PRESERVED.
    live = {"Statement": [{"Sid": "L", "Action": ["s3:GetObject", "ec2:DescribeInstances"]}]}
    gen = {"Statement": [{"Sid": "G", "Action": ["s3:GetObject", "s3:PutObject"]}]}
    r = pm.additive_merge(live, gen)
    merged = _actions(r.merged)
    # Union: nothing lost, new added.
    assert "ec2:DescribeInstances" in merged   # preserved from live
    assert "s3:PutObject" in merged            # added from generated
    assert r.would_remove is True              # generated omitted ec2:DescribeInstances
    assert r.removed_actions == ["ec2:DescribeInstances"]
    assert r.added_actions == ["s3:PutObject"]
    # A dedicated preservation statement carries the live-only action.
    assert any(s.get("Sid") == "PreservedFromExistingPolicy" for s in r.merged["Statement"])


def test_no_removal_when_generated_is_superset():
    live = {"Statement": [{"Sid": "L", "Action": ["s3:GetObject"]}]}
    gen = {"Statement": [{"Sid": "G", "Action": ["s3:GetObject", "s3:PutObject"]}]}
    r = pm.additive_merge(live, gen)
    assert r.would_remove is False
    assert not any(s.get("Sid") == "PreservedFromExistingPolicy" for s in r.merged["Statement"])


def test_replace_result_is_destructive_but_reports_removed():
    live = {"Statement": [{"Sid": "L", "Action": ["s3:GetObject", "ec2:DescribeInstances"]}]}
    gen = {"Statement": [{"Sid": "G", "Action": ["s3:GetObject"]}]}
    r = pm.replace_result(live, gen)
    assert r.merged is gen                       # verbatim generated (shrinks)
    assert r.removed_actions == ["ec2:DescribeInstances"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
