#!/usr/bin/env python3
"""
policy_compare.py
================

Compare a freshly generated IAM document (policy or boundary) against the one
currently live on AWS, and render the difference. The diff itself is pure and
AWS-free (so it's unit-testable); the actual fetch is a thin callback the caller
supplies (it wraps provider_login.sh's get_role_inline_policy /
get_boundary_document).

The unit of comparison is the **action set per Sid** plus the top-level effect
and condition, which is what actually matters for "did the permissions change" —
key ordering and whitespace are ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class DocumentDiff:
    """The difference between a live document and a generated one."""
    exists: bool                       # was there a live document at all?
    added_actions: list[str] = field(default_factory=list)     # in generated, not live
    removed_actions: list[str] = field(default_factory=list)   # in live, not generated
    added_sids: list[str] = field(default_factory=list)
    removed_sids: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return not self.exists or bool(
            self.added_actions or self.removed_actions
            or self.added_sids or self.removed_sids)


def _actions_of(document: dict | None) -> set[str]:
    """All actions across every statement, as a set (Action or NotAction)."""
    actions: set[str] = set()
    for statement in (document or {}).get("Statement", []):
        for key in ("Action", "NotAction"):
            value = statement.get(key)
            if isinstance(value, str):
                actions.add(value)
            elif isinstance(value, list):
                actions.update(value)
    return actions


def _sids_of(document: dict | None) -> set[str]:
    return {s.get("Sid", "") for s in (document or {}).get("Statement", []) if s.get("Sid")}


def diff_documents(live: dict | None, generated: dict) -> DocumentDiff:
    """
    Compare a live document (or None if the role/policy doesn't exist yet) with
    the generated one. Reports the action and Sid deltas.
    """
    if live is None:
        return DocumentDiff(exists=False, added_actions=sorted(_actions_of(generated)),
                            added_sids=sorted(_sids_of(generated)))
    live_actions, gen_actions = _actions_of(live), _actions_of(generated)
    live_sids, gen_sids = _sids_of(live), _sids_of(generated)
    return DocumentDiff(
        exists=True,
        added_actions=sorted(gen_actions - live_actions),
        removed_actions=sorted(live_actions - gen_actions),
        added_sids=sorted(gen_sids - live_sids),
        removed_sids=sorted(live_sids - gen_sids),
    )


def parse_live_document(raw: str) -> dict | None:
    """
    Turn a provider_login.sh fetch result into a policy dict, or None when the
    role/policy does not exist yet (the helper prints nothing in that case).
    """
    text = (raw or "").strip()
    if not text:
        return None
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) and "Statement" in doc else None


def render_diff(label: str, diff: DocumentDiff) -> str:
    """A short human-readable summary of one document's diff."""
    if not diff.exists:
        return f"{label}: NEW — no live document on AWS; all {len(diff.added_actions)} action(s) will be created."
    if not diff.changed:
        return f"{label}: unchanged — live document already matches the generated one."
    lines = [f"{label}: CHANGED"]
    if diff.added_sids:
        lines.append(f"  + statements: {', '.join(diff.added_sids)}")
    if diff.removed_sids:
        lines.append(f"  - statements: {', '.join(diff.removed_sids)}")
    for action in diff.added_actions:
        lines.append(f"  + {action}")
    for action in diff.removed_actions:
        lines.append(f"  - {action}")
    return "\n".join(lines)
