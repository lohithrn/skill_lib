#!/usr/bin/env python3
"""Exact cap measurement for Python, via the AST. Reads a file list on stdin, emits JSONL.

No heuristic matches an AST, so caps.sh prefers this and marks Python `degraded` without it.
Every number here is a measurement: node line spans and node counts, nothing inferred.

This file is held to the caps it measures, and that is not decoration — an enforcer that cannot
obey its own rule is evidence the rule is wrong. Two shapes carry the weight: a `Threshold` object
so the graduated warn/hard comparison exists once, and a `Finding` value object so no function
needs six parameters to describe one result. Both are the standard fixes the doctrine asks for.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import traceback
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cap_pragma                                                        # noqa: E402
from ast_measure import (FUNC, LOOP, SKIP, body_span, count_params,      # noqa: E402
                         declaration_line, deepest)

CAPS = {
    "method": int(os.environ.get("CG_CAP_METHOD", 25)),
    "method_warn": int(os.environ.get("CG_CAP_METHOD_WARN", 15)),
    "nesting": int(os.environ.get("CG_CAP_NESTING", 1)),
    "loop_body": int(os.environ.get("CG_CAP_LOOP_BODY", 8)),
    "params": int(os.environ.get("CG_CAP_PARAMS", 4)),
    "params_warn": int(os.environ.get("CG_CAP_PARAMS_WARN", 3)),
    "public": int(os.environ.get("CG_CAP_PUBLIC", 7)),
    "public_warn": int(os.environ.get("CG_CAP_PUBLIC_WARN", 5)),
}
ROOT = os.environ.get("CG_ROOT", "")

Finding = namedtuple("Finding", "metric line value cap severity name")
# What was measured, before any cap is applied. It exists so `check` takes one argument instead of
# four — the same Introduce Parameter Object move this scanner asks of the code it reads.
Measure = namedtuple("Measure", "metric value line name")


class Threshold:
    """One cap. `warn=None` means hard-only, which is what nesting and loop bodies are: there is
    no such thing as almost nesting twice."""

    def __init__(self, hard: int, warn: int | None = None) -> None:
        self.hard = hard
        self.warn = warn

    def check(self, measure: Measure) -> Finding | None:
        if measure.value > self.hard:
            return self._finding(measure, self.hard, "major")
        if self.warn is not None and measure.value > self.warn:
            return self._finding(measure, self.warn, "minor")
        return None

    def _finding(self, measure: Measure, cap: int, severity: str) -> Finding:
        return Finding(measure.metric, measure.line, measure.value, cap, severity, measure.name)


METHOD = Threshold(CAPS["method"], CAPS["method_warn"])
NESTING = Threshold(CAPS["nesting"])
LOOP_BODY = Threshold(CAPS["loop_body"])
PARAMS = Threshold(CAPS["params"], CAPS["params_warn"])
PUBLIC = Threshold(CAPS["public"], CAPS["public_warn"])


def write(rel: str, finding: Finding) -> None:
    sys.stdout.write(json.dumps({
        "file": rel, "line": finding.line, "metric": finding.metric, "value": finding.value,
        "cap": finding.cap, "severity": finding.severity, "name": finding.name,
    }, separators=(",", ":")) + "\n")


class Report:
    """Findings sink for ONE file. It carries the path and that file's exemptions together, so no
    scanning function has to be handed both — and so suppression happens in exactly one place."""

    def __init__(self, rel: str, exemptions: dict) -> None:
        self.rel = rel
        self.exemptions = exemptions

    def add(self, finding: Finding | None, decl_line: int = 0) -> None:
        """Emit one finding, or emit it as `exempt` when a pragma above `decl_line` covers it.
        A suppressed finding is still PRINTED, with severity `exempt`: the report says what it
        chose not to count, because an invisible exemption is indistinguishable from a bug."""
        if finding is None:
            return
        if cap_pragma.covers(self.exemptions.get(decl_line), finding.metric):
            write(self.rel, finding._replace(severity="exempt"))
            return
        write(self.rel, finding)

    def extend(self, findings: list, decl_line: int = 0) -> None:
        for finding in findings:
            self.add(finding, decl_line)


def loop_findings(fn: ast.AST, qual: str) -> list:
    loops = [n for n in ast.walk(fn) if isinstance(n, LOOP)]
    return [LOOP_BODY.check(Measure("loop_body", body_span(n), n.lineno, qual)) for n in loops]


def else_findings(fn: ast.AST, qual: str) -> list:
    """Every `else`/`elif`, plus the obscure loop/try `else`. The cap is 0: the doctrine replaces
    the branch with a resolver chosen by a registry, so the branch becomes a lookup."""
    branches = [n for n in ast.walk(fn) if isinstance(n, ast.If) and n.orelse]
    exotic = [n for n in ast.walk(fn)
              if isinstance(n, LOOP + (ast.Try,)) and getattr(n, "orelse", None)]
    return [_branch_finding(n, qual) for n in branches] + [
        Finding("else", n.orelse[0].lineno, 1, 0, "minor", f"{qual} (loop/try else)")
        for n in exotic]


def _branch_finding(node: ast.If, qual: str) -> Finding:
    solo_if = len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
    kind = "elif" if solo_if else "else"
    return Finding("else", node.orelse[0].lineno, 1, 0, "major", f"{qual} ({kind})")


def scan_function(report: Report, fn: ast.AST, qual: str) -> None:
    decl = declaration_line(fn)
    depth, at = deepest(fn)
    report.add(METHOD.check(Measure("method_lines", body_span(fn), fn.lineno, qual)), decl)
    report.add(NESTING.check(Measure("nesting", depth, at, qual)), decl)
    report.add(PARAMS.check(Measure("params", count_params(fn), fn.lineno, qual)), decl)
    report.extend(loop_findings(fn, qual), decl)
    report.extend(else_findings(fn, qual), decl)


def scan_class(report: Report, cls: ast.ClassDef) -> None:
    public = [n for n in cls.body if isinstance(n, FUNC) and not n.name.startswith("_")]
    report.add(PUBLIC.check(Measure("public_members", len(public), cls.lineno, cls.name)),
               cls.lineno)
    bases = [b for b in cls.bases if isinstance(b, ast.Name)]
    if len(bases) > 1:
        report.add(Finding("multiple_inheritance", cls.lineno, len(bases), 1, "minor", cls.name),
                   cls.lineno)


def walk_definitions(report: Report, tree: ast.AST) -> None:
    """Every class and function with its qualified name, iteratively."""
    work = [(child, "") for child in ast.iter_child_nodes(tree)]
    while work:
        _visit_definition(report, work)


def _visit_definition(report: Report, work: list) -> None:
    node, prefix = work.pop()
    if isinstance(node, ast.ClassDef):
        scan_class(report, node)
    if isinstance(node, FUNC):
        scan_function(report, node, f"{prefix}{node.name}")
    if not isinstance(node, SKIP):
        return
    work.extend((child, f"{prefix}{node.name}.") for child in ast.iter_child_nodes(node))


def read_source(path: str, rel: str) -> str | None:
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8", "replace")
    except OSError as exc:
        write(rel, Finding("unparseable", 1, 1, 0, "minor", type(exc).__name__))
        return None


def parse_tree(text: str, path: str, report: Report) -> ast.AST | None:
    try:
        return ast.parse(text, filename=path)
    except (SyntaxError, ValueError) as exc:
        at = getattr(exc, "lineno", 1) or 1
        report.add(Finding("unparseable", at, 1, 0, "minor", str(getattr(exc, "msg", exc))))
        return None


def pragma_findings(exemptions: dict) -> list:
    """A pragma that names metrics but gives no reason suppresses nothing and is reported."""
    return [Finding("exempt_without_reason", e.line, 1, 0, "major", ",".join(sorted(e.metrics)))
            for e in cap_pragma.unjustified(exemptions)]


def scan_file(path: str) -> None:
    rel = os.path.relpath(path, ROOT) if ROOT else path
    text = read_source(path, rel)
    if text is None:
        return
    report = Report(rel, cap_pragma.collect(text))
    report.extend(pragma_findings(report.exemptions))
    tree = parse_tree(text, path, report)
    if tree is None:
        return
    walk_definitions(report, tree)


def main() -> int:
    """Error boundary. One unscannable file must not degrade a whole language, so each failure
    is reported with its traceback and the scan continues. Exit stays 0: caps.sh reads a
    non-zero exit as "the scanner is unusable" and drops Python to file-length-only."""
    for line in sys.stdin:
        _scan_one(line.strip())
    return 0


def _scan_one(path: str) -> None:
    if not path:
        return
    try:
        scan_file(path)
    except RecursionError:
        # A file deep enough to blow the stack is itself the finding.
        rel = os.path.relpath(path, ROOT) if ROOT else path
        write(rel, Finding("unparseable", 1, 1, 0, "minor", "RecursionError: AST too deep"))
    except Exception:                               # noqa: BLE001 - boundary: log and continue
        traceback.print_exc()                       # full stack, per error-handling.md §1
        print(f"scan_python: giving up on {path}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
