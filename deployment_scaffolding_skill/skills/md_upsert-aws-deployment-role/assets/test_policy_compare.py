"""
Tests for policy_compare.py — diffing a generated IAM document against the live
one on AWS. Pure/AWS-free.

Run:  python3 -m pytest commands/assets/createDeploymentRole/test_policy_compare.py -q
"""

import pytest

import policy_compare as pc


def test_new_document_when_nothing_live():
    gen = {"Statement": [{"Sid": "A", "Action": ["s3:GetObject"]}]}
    diff = pc.diff_documents(None, gen)
    assert diff.exists is False
    assert diff.changed is True
    assert "s3:GetObject" in diff.added_actions


def test_unchanged_when_action_sets_match():
    doc = {"Statement": [{"Sid": "A", "Action": ["s3:GetObject", "s3:PutObject"]}]}
    # Same actions, different order / whitespace shouldn't matter.
    other = {"Statement": [{"Sid": "A", "Action": ["s3:PutObject", "s3:GetObject"]}]}
    diff = pc.diff_documents(doc, other)
    assert diff.changed is False


def test_added_and_removed_actions():
    live = {"Statement": [{"Sid": "A", "Action": ["s3:GetObject", "s3:PutObject"]}]}
    gen = {"Statement": [{"Sid": "A", "Action": ["s3:GetObject", "s3:DeleteObject"]}]}
    diff = pc.diff_documents(live, gen)
    assert diff.added_actions == ["s3:DeleteObject"]
    assert diff.removed_actions == ["s3:PutObject"]


def test_sid_delta_detected():
    live = {"Statement": [{"Sid": "A", "Action": ["s3:GetObject"]}]}
    gen = {"Statement": [{"Sid": "A", "Action": ["s3:GetObject"]},
                         {"Sid": "B", "Action": ["ec2:DescribeInstances"]}]}
    diff = pc.diff_documents(live, gen)
    assert diff.added_sids == ["B"]
    assert diff.changed is True


def test_notaction_is_counted():
    live = {"Statement": [{"Sid": "Deny", "NotAction": ["s3:*"]}]}
    gen = {"Statement": [{"Sid": "Deny", "NotAction": ["s3:*", "cloudfront:*"]}]}
    diff = pc.diff_documents(live, gen)
    assert "cloudfront:*" in diff.added_actions


# --------------------------------------------------------------------------- #
# parse_live_document
# --------------------------------------------------------------------------- #
def test_parse_empty_means_no_live_document():
    assert pc.parse_live_document("") is None
    assert pc.parse_live_document("   ") is None


def test_parse_non_policy_json_is_none():
    assert pc.parse_live_document('{"foo": 1}') is None
    assert pc.parse_live_document("not json") is None


def test_parse_valid_policy():
    doc = pc.parse_live_document('{"Statement": [{"Sid": "A", "Action": "s3:GetObject"}]}')
    assert doc is not None and doc["Statement"][0]["Sid"] == "A"


def test_render_new_and_unchanged_and_changed():
    assert "NEW" in pc.render_diff("x", pc.diff_documents(None, {"Statement": []}))
    same = {"Statement": [{"Sid": "A", "Action": ["s3:GetObject"]}]}
    assert "unchanged" in pc.render_diff("x", pc.diff_documents(same, same))
    live = {"Statement": [{"Sid": "A", "Action": ["s3:GetObject"]}]}
    gen = {"Statement": [{"Sid": "A", "Action": ["s3:PutObject"]}]}
    assert "CHANGED" in pc.render_diff("x", pc.diff_documents(live, gen))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
