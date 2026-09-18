#!/usr/bin/env python3
"""What each non-Python language's syntax says about one file: import targets and type counts.

A pure sink node — it imports `os`, `re`, `collections` and `typing`, touches no filesystem and
reads no environment, so one lexer is testable with a three-line string and a dict. Which record
shape those facts land in is `imports_scan.py`'s decision, not this module's.

The `if lang == "ts" / elif "java" / elif "go"` chain this replaces was one question — "whose
rules read this file?" — with a closed set of answers. Each answer is now a `Lexer`, and
`registry()` is the only place an answer is named, so adding a language is one class plus one
entry and no call site branches on `lang` again.
"""
from __future__ import annotations

import os
import re
from collections import namedtuple
from typing import Protocol

TS_SPEC = re.compile(r"""(?:from\s*|require\s*\(\s*|import\s*\(\s*)['"]([^'"]+)['"]""")
TS_BARE = re.compile(r"""^\s*import\s+['"]([^'"]+)['"]""", re.M)
TS_ALIASES = ("@/", "~/", "#/")              # the common alias-to-source-root convention
JAVA_IMP = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)\s*;", re.M)
JAVA_PKG = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
GO_ONE = re.compile(r"""^\s*import\s+(?:[\w.]+\s+)?["]([^"]+)["]""", re.M)
GO_BLOCK = re.compile(r"^\s*import\s*\(([^)]*)\)", re.M | re.S)
GO_INBLOCK = re.compile(r"""["]([^"]+)["]""")

ABSTRACT_TS = re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(?:interface\s+\w|abstract\s+class\s+\w)", re.M)
CONCRETE_TS = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+\w", re.M)
ABSTRACT_JAVA = re.compile(r"^\s*(?:public\s+|protected\s+)?(?:sealed\s+)?(?:interface\s+\w|abstract\s+(?:sealed\s+)?class\s+\w)", re.M)
CONCRETE_JAVA = re.compile(r"^\s*(?:public\s+|final\s+|static\s+)*(?:class|enum|record)\s+\w", re.M)
ABSTRACT_GO = re.compile(r"^\s*type\s+\w+\s+interface\b", re.M)
CONCRETE_GO = re.compile(r"^\s*type\s+\w+\s+struct\b", re.M)

Source = namedtuple("Source", "rel text")
# One file as a lexer sees it. A value object rather than two parameters, so a lexer that later
# needs the dialect or the byte size gains a field instead of every lexer gaining an argument.

Facts = namedtuple("Facts", "raw extra")
# One lexer's reading: the targets its imports name, plus the fields only that language
# contributes. `extra` is built in the order those keys must appear in the emitted record.


class Lexer(Protocol):
    """Which import targets, and which type counts, does this language's syntax report?"""

    def read(self, src: Source) -> Facts: ...


def type_counts(abstract: re.Pattern, concrete: re.Pattern, text: str) -> dict:
    """`types` counts declarations of both shapes, `abstract` only the first. That rule is the
    same in all three languages, so the pair of patterns is the only thing that varies."""
    found = len(abstract.findall(text))
    return {"types": found + len(concrete.findall(text)), "abstract": found}


def ts_base(spec: str, rel: str) -> str | None:
    """Where a specifier points before extensions are trimmed, or None when it is a package.

    Three answers and only three: a dot-relative specifier resolves against the importing file's
    directory, an aliased one against the source root, and anything else is not a node here.
    """
    if spec.startswith("."):
        return os.path.join(os.path.dirname(rel), spec)
    if spec.startswith(TS_ALIASES):
        return spec[2:]
    return None                                  # a package, not a node in this repo


def ts_resolve(spec: str, rel: str) -> str | None:
    """A relative specifier as a repo-relative, extensionless path. Bare specifiers are external."""
    base = ts_base(spec, rel)
    if base is None:
        return None
    joined = re.sub(r"\.(m|c)?[jt]sx?$", "", os.path.normpath(base))
    return joined[: -len("/index")] if joined.endswith("/index") else joined


class TsLexer:
    """TypeScript/JavaScript: every quoted specifier, resolved against the importing file."""

    def read(self, src: Source) -> Facts:
        specs = set(TS_SPEC.findall(src.text)) | set(TS_BARE.findall(src.text))
        raw = [t for t in (ts_resolve(s, src.rel) for s in specs) if t]
        # `external` is what the bare specifiers cost: counted, never resolved to a node.
        return Facts(raw, {"external": len(specs) - len(raw),
                           **type_counts(ABSTRACT_TS, CONCRETE_TS, src.text)})


class JavaLexer:
    """Java/Kotlin: the `import` lines, minus on-demand wildcards, which name no single type."""

    def read(self, src: Source) -> Facts:
        found = JAVA_PKG.search(src.text)
        return Facts([t for t in JAVA_IMP.findall(src.text) if not t.endswith(".*")],
                     {"pkg": found.group(1) if found else "",
                      **type_counts(ABSTRACT_JAVA, CONCRETE_JAVA, src.text)})


class GoLexer:
    """Go: single imports plus every quoted path inside an `import ( ... )` block.

    Takes the `go list` map by constructor injection rather than reading a module global, so it
    is testable with three lines of source and a two-entry dict.
    """

    def __init__(self, ids: dict[str, str]) -> None:
        self.ids = ids

    def read(self, src: Source) -> Facts:
        blocked = [t for block in GO_BLOCK.findall(src.text) for t in GO_INBLOCK.findall(block)]
        return Facts(GO_ONE.findall(src.text) + blocked,
                     {**type_counts(ABSTRACT_GO, CONCRETE_GO, src.text), **self.own_id(src.rel)})

    def own_id(self, rel: str) -> dict:
        """A Go source import is already a full package path, so a file's own id is the one thing
        its text cannot supply. Keyed on the DIRECTORY, because that is what `go list` names."""
        found = self.ids.get(os.path.dirname(rel))
        return {"id": found} if found else {}


class AbsentLexer:
    """The lexer that makes the set total: a language with no rules yet reports no imports and no
    types instead of raising. Nothing `LANG_BY_EXT` admits lands here today, and that is the
    point — a new extension must not become a traceback before its lexer exists."""

    def read(self, src: Source) -> Facts:
        return Facts([], {})


ABSENT = AbsentLexer()


def registry(go_ids: dict[str, str]) -> dict[str, Lexer]:
    """The lang -> lexer map. Data, not control flow, and the only place an answer is named."""
    return {"ts": TsLexer(), "java": JavaLexer(), "go": GoLexer(go_ids)}
