"""
python_structure_checks.py
==========================

The Python-specific, AST-based checks: method/function length (rule 4), loop-body
length (rule 5), single-member enums (rule 7A), vague method names (rule 7F), and
module-level mutable state (rule 21). Everything here needs a parsed syntax tree,
so it is kept apart from the language-agnostic line/name checks.
"""

from __future__ import annotations

import ast
from pathlib import Path

from lint_model import (
    Finding, MAX_LOOP_BODY_LINES, MAX_METHOD_LINES, VAGUE_METHOD_NAMES,
)


class PythonStructureVisitor(ast.NodeVisitor):
    """Collects method-length, loop-body, enum, and naming findings for one file."""

    def __init__(self, path: str):
        self.path = path
        self.findings: list[Finding] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._check_loop(node)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._check_loop(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._check_single_member_enum(node)
        self.generic_visit(node)

    def _check_function(self, node) -> None:
        length = body_span(node.body)
        if length > MAX_METHOD_LINES:
            self.findings.append(Finding(
                self.path, node.lineno, "method-too-long", "warning",
                f"'{node.name}' spans {length} lines (> {MAX_METHOD_LINES}). "
                "Extract a named private method (SKILL.md rule 4).",
            ))
        if node.name in VAGUE_METHOD_NAMES:
            self.findings.append(Finding(
                self.path, node.lineno, "vague-method-name", "info",
                f"Method '{node.name}' is a bare verb. Use verb+noun like "
                "'find_entities' (SKILL.md rule 7F).",
            ))

    def _check_loop(self, node) -> None:
        length = body_span(node.body)
        if length > MAX_LOOP_BODY_LINES:
            self.findings.append(Finding(
                self.path, node.lineno, "loop-body-too-long", "info",
                f"Loop body is {length} lines (> {MAX_LOOP_BODY_LINES}). "
                "Extract the per-item work into a method (SKILL.md rule 5).",
            ))

    def _check_single_member_enum(self, node: ast.ClassDef) -> None:
        if not is_enum(node):
            return
        members = [n for n in node.body if is_enum_member(n)]
        if len(members) == 1:
            self.findings.append(Finding(
                self.path, node.lineno, "single-member-enum", "info",
                f"Enum '{node.name}' has one member — ceremony. Use a named "
                "constant + direct method instead (SKILL.md rule 7A).",
            ))


def body_span(body: list[ast.stmt]) -> int:
    """Line count of a statement body, from its first line to its last."""
    if not body:
        return 0
    start = body[0].lineno
    end = max(getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno for stmt in body)
    return end - start + 1


def is_enum(node: ast.ClassDef) -> bool:
    names = {b.id for b in node.bases if isinstance(b, ast.Name)}
    names |= {b.attr for b in node.bases if isinstance(b, ast.Attribute)}
    return bool(names & {"Enum", "IntEnum", "StrEnum"})


def is_enum_member(stmt: ast.stmt) -> bool:
    """A `NAME = value` assignment — an enum member, not a method or docstring."""
    if isinstance(stmt, ast.Assign):
        return all(isinstance(t, ast.Name) for t in stmt.targets)
    return isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)


def assigns_mutable_lowercase(stmt: ast.Assign) -> bool:
    """`items = []` / `cache = {}` at module scope — a lowercase mutable, not a CONSTANT."""
    if not isinstance(stmt.value, (ast.List, ast.Dict, ast.Set)):
        return False
    return any(isinstance(t, ast.Name) and not t.id.isupper() for t in stmt.targets)


def check_module_globals(tree: ast.Module, path: str) -> list[Finding]:
    """Flag module-level mutable assignments (non-constant globals; SKILL.md rule 21)."""
    findings: list[Finding] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and assigns_mutable_lowercase(stmt):
            findings.append(Finding(
                path, stmt.lineno, "module-level-state", "info",
                "Module-level mutable value. Pass through a constructor or DI "
                "instead of global state (SKILL.md rule 21).",
            ))
    return findings


def check_python_module(path: Path, source: str, on_parse_error) -> list[Finding]:
    """Parse `source` and return all Python structural findings for `path`."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        on_parse_error(f"Could not parse {path} ({error}); only line rules applied.")
        return []
    visitor = PythonStructureVisitor(str(path))
    visitor.visit(tree)
    findings = list(visitor.findings)
    findings.extend(check_module_globals(tree, str(path)))
    return findings
