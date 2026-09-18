#!/usr/bin/env python3
"""Measurement of one Python AST node: length, nesting depth, parameter count.

A pure sink node — it imports `ast` and nothing else, holds no cap and emits no finding, so it can
be tested by parsing a three-line string and asserting a number. `scan_python.py` decides what
those numbers MEAN; that separation is why a wrong threshold and a wrong measurement can never be
confused for each other.
"""
from __future__ import annotations

import ast

FUNC = (ast.FunctionDef, ast.AsyncFunctionDef)
LOOP = (ast.For, ast.AsyncFor, ast.While)
# Nesting counts CONTROL FLOW only. `with` and `try` are not decisions and do not count;
# counting them would flag correct resource handling as a violation.
NESTS = (ast.If, ast.For, ast.AsyncFor, ast.While)
if hasattr(ast, "Match"):  # 3.10+
    NESTS = NESTS + (ast.Match,)
SKIP = FUNC + (ast.ClassDef,)


def body_span(node: ast.AST) -> int:
    """Lines of actual body, docstring and decorators excluded — what a reader must hold."""
    body = getattr(node, "body", None)
    if not body:
        return 0
    stmts = list(body)
    if is_docstring(stmts[0]):
        stmts = stmts[1:]          # a docstring is documentation, not length
    if not stmts:
        return 0
    end = max(getattr(s, "end_lineno", s.lineno) or s.lineno for s in stmts)
    return end - stmts[0].lineno + 1


def is_docstring(stmt: ast.AST) -> bool:
    if not isinstance(stmt, ast.Expr):
        return False
    value = getattr(stmt, "value", None)
    return isinstance(value, ast.Constant) and isinstance(value.value, str)


def deepest(fn: ast.AST) -> tuple[int, int]:
    """Nesting depth as SKILL.md defines it, and the line where it peaks.

    SKILL.md: "Nesting is measured from the method body, so `for` + `if` is depth 1 and legal; a
    third level is not." So the OUTERMOST control construct is depth 0 and only what is nested
    INSIDE it counts — one `for` is not nesting, a branch within that `for` is one level of it.
    Counting the outer construct itself would flag the shape the spec explicitly permits, and a
    tool that contradicts its own specification gets the specification changed to match the tool
    by whoever hits it next.

    Iterative on an explicit stack rather than a recursive closure: the recursive form needed a
    loop around a branch around a branch, which is the very shape this function exists to report.
    """
    best, line = 0, getattr(fn, "lineno", 1)
    work = [(stmt, 0) for stmt in getattr(fn, "body", [])]
    while work:
        best, line = _descend(work, best, line)
    return max(best - 1, 0), line


def _descend(work: list, best: int, line: int) -> tuple[int, int]:
    """Pop one node, push its children with their depth, return the running maximum."""
    node, depth = work.pop()
    if isinstance(node, SKIP):
        return best, line          # a nested def resets the budget; it is measured on its own
    depth += isinstance(node, NESTS)
    work.extend((child, depth) for child in ast.iter_child_nodes(node))
    return (depth, node.lineno) if depth > best else (best, line)


def count_params(node: ast.AST) -> int:
    args = node.args
    total = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    if args.args and args.args[0].arg in ("self", "cls"):
        return total - 1           # the receiver is not a parameter of the problem
    return total


def declaration_line(fn: ast.AST) -> int:
    """The line a pragma must sit above: the first decorator when there is one, the `def` when
    there is not. Attaching to the `def` alone would make a pragma unusable on a decorated
    function, which is where a justified exemption is most likely to be needed."""
    return min([d.lineno for d in getattr(fn, "decorator_list", [])] + [fn.lineno])
