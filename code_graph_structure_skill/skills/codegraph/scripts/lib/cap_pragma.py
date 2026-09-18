#!/usr/bin/env python3
"""Cap exemptions declared in source: `# codegraph:exempt <metrics> -- <reason>`.

An exemption is a SEAM, not an escape hatch, and the difference is enforced here:

  * it must name every metric it suppresses — there is no exempt-everything form, so a pragma
    written for one reason cannot silently start hiding a different defect later;
  * it must carry a reason after `--`, and a pragma without one is itself reported as the
    `exempt_without_reason` finding;
  * every exemption that fires is COUNTED and emitted as a record of its own, so the report says
    "3 findings suppressed, here is why" instead of quietly showing a clean scan.

The intended use is a published algorithm whose shape is the citation — Tarjan 1972, Brandes
2001 — where decomposing to the house nesting limit makes the code harder to check against the
paper. That is a real reason. "This function is hard to fix" is not, and the reason text is where
a reviewer sees which one they are looking at.

This module knows nothing about Python or the AST: it reads text and returns line numbers, so it
serves every language scanner and can be tested with a three-line string.
"""
from __future__ import annotations

from collections import namedtuple

MARK = "# codegraph:exempt"
REASON_SEP = "--"

Exemption = namedtuple("Exemption", "metrics reason line")


def parse(text: str, line: int) -> Exemption:
    """One pragma line into an Exemption. Metrics may be comma- or space-separated."""
    body = text.split(MARK, 1)[1]
    head, _, reason = body.partition(REASON_SEP)
    metrics = {m.strip() for m in head.replace(" ", ",").split(",") if m.strip()}
    return Exemption(metrics, reason.strip(), line)


class _Walk:
    """The two things reading a file line by line needs to remember: what has been attached, and
    which pragma is still waiting for a declaration to attach to. A class rather than four
    parameters threaded through a helper, which is the shape this skill asks for elsewhere."""

    def __init__(self) -> None:
        self.found: dict[int, Exemption] = {}
        self.pending: Exemption | None = None

    def feed(self, number: int, raw: str) -> None:
        line = raw.strip()
        if line.startswith(MARK):
            self.pending = parse(line, number)
            return
        if not line or line.startswith("#"):
            return                          # blanks and prose comments do not consume a pragma
        if self.pending:
            self.found[number] = self.pending
        self.pending = None


def collect(text: str) -> dict[int, Exemption]:
    """{line number of the declaration it guards -> Exemption}.

    A pragma attaches to the next line of CODE below it, skipping blanks and other comments, so
    it may sit above a decorator and still guard the function the decorator belongs to.
    """
    walk = _Walk()
    for number, raw in enumerate(text.splitlines(), 1):
        walk.feed(number, raw)
    return walk.found


def covers(exemption: Exemption | None, metric: str) -> bool:
    """Does this exemption suppress this metric? A reasonless pragma suppresses NOTHING — it is
    reported instead, so writing `# codegraph:exempt nesting` with no justification makes the
    scan louder rather than quieter."""
    if exemption is None or not exemption.reason:
        return False
    return metric in exemption.metrics


def unjustified(exemptions: dict[int, Exemption]) -> list[Exemption]:
    """Every pragma that named metrics but gave no reason, in line order."""
    bad = [e for e in exemptions.values() if e.metrics and not e.reason]
    return sorted(bad, key=lambda e: e.line)
