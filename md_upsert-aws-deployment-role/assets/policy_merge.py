#!/usr/bin/env python3
"""
policy_merge.py
==============

Additive-by-default merge of a generated IAM document onto what is LIVE on AWS.
The rule: applying must NEVER silently shrink an existing role's permissions. We
union the live actions with the generated ones (so we only ever ADD), and we
report exactly what a non-additive apply WOULD remove, so the caller can require
explicit confirmation before any reduction.

Pure/AWS-free (works on dicts), so it is unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MergeResult:
    """Outcome of merging generated onto live."""
    merged: dict                                   # the additive union to apply
    added_actions: list[str] = field(default_factory=list)     # new, from generated
    removed_actions: list[str] = field(default_factory=list)   # in live, dropped by generated
    had_live: bool = False                         # was there a live document?

    @property
    def would_remove(self) -> bool:
        return bool(self.removed_actions)


def _statement_actions(statement: dict) -> tuple[str, list[str]]:
    """Return (key, actions) where key is 'Action' or 'NotAction'."""
    for key in ("Action", "NotAction"):
        value = statement.get(key)
        if value is None:
            continue
        return key, ([value] if isinstance(value, str) else list(value))
    return "Action", []


def _all_actions(document: dict | None) -> set[str]:
    actions: set[str] = set()
    for statement in (document or {}).get("Statement", []):
        _key, values = _statement_actions(statement)
        actions.update(values)
    return actions


def additive_merge(live: dict | None, generated: dict) -> MergeResult:
    """
    Union `live` into `generated` so the applied document is a SUPERSET of both —
    permissions are only ever added, never dropped. Reports which live actions the
    generated doc omitted (what a destructive replace would have removed).

    The merged document keeps the generated document's statement structure and
    folds any live-only actions into a dedicated PreservedFromExistingPolicy
    statement, so nothing the role already had is lost.
    """
    if live is None:
        return MergeResult(merged=generated, had_live=False,
                           added_actions=sorted(_all_actions(generated)))

    live_actions = _all_actions(live)
    gen_actions = _all_actions(generated)
    live_only = sorted(live_actions - gen_actions)
    return MergeResult(
        merged=_with_preserved(generated, live_only), had_live=True,
        added_actions=sorted(gen_actions - live_actions), removed_actions=live_only)


def _with_preserved(generated: dict, live_only: list[str]) -> dict:
    """Copy `generated`, appending a statement that keeps any live-only actions."""
    merged = {"Version": generated.get("Version", "2012-10-17"),
              "Statement": list(generated.get("Statement", []))}
    if live_only:
        merged["Statement"].append({
            "Sid": "PreservedFromExistingPolicy",
            "Effect": "Allow",
            "Action": live_only,
            "Resource": "*",
        })
    return merged


def replace_result(live: dict | None, generated: dict) -> MergeResult:
    """
    The DESTRUCTIVE alternative: apply `generated` verbatim (may shrink). Used
    only after the user has explicitly confirmed a reduction. Still reports the
    removed actions for the audit trail.
    """
    live_actions = _all_actions(live)
    gen_actions = _all_actions(generated)
    return MergeResult(
        merged=generated, had_live=live is not None,
        added_actions=sorted(gen_actions - live_actions),
        removed_actions=sorted(live_actions - gen_actions))
