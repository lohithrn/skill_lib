#!/usr/bin/env python3
"""Raw import extraction, one JSON object per file. Reads a file list on stdin.

This scanner RESOLVES nothing against the repo: it only canonicalises what the source text
says, because that needs the file's own path and nothing more. Mapping a target onto a node is
graph_build.py's job, since only it knows the whole node set.

Python goes through the AST and is exact for static imports. Everything else is a regex sweep
over import syntax, which is right for ordinary code and blind to dynamic loading either way —
graph_build.py records that limit as `degraded`, it does not paper over it.

This file owns the Python path and the record shape. Every other language's reading is a `Lexer`
in imports_lexers.py, and `LEXERS` below is this scanner's composition root — the one place a
language is bound to the code that reads it.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import imports_lexers                                                    # noqa: E402
from imports_lexers import Source                                        # noqa: E402

ROOT = os.environ.get("CG_ROOT", "")


def load_go_ids() -> dict[str, str]:
    """`go list` output as {relative dir: import path}. A Go source import is already a full
    package path, so this map is the one thing the source text cannot supply: the package's own
    id. Absent, graph_build falls back to directory paths and resolves by suffix."""
    path = os.environ.get("CG_GO_IDS", "")
    if not path or not os.path.isfile(path):
        return {}
    out: dict[str, str] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 2 or not parts[1]:
                continue
            out[os.path.relpath(parts[0], ROOT) if ROOT else parts[0]] = parts[1]
    return out


GO_IDS = load_go_ids()
LEXERS = imports_lexers.registry(GO_IDS)

LANG_BY_EXT = {
    ".py": "python", ".ts": "ts", ".tsx": "ts", ".js": "ts", ".jsx": "ts",
    ".mjs": "ts", ".cjs": "ts", ".java": "java", ".kt": "java", ".kts": "java", ".go": "go",
}


def dotted(rel: str) -> str:
    """A python file path as the dotted module name the source would import it by."""
    mod = os.path.splitext(rel)[0].replace(os.sep, ".")
    return mod[: -len(".__init__")] if mod.endswith(".__init__") else mod


def package_of(rel: str) -> list[str]:
    """The file's own package, taken from its DIRECTORY.

    Not from its module id: `pkg/__init__.py` has the id `pkg`, so deriving the package by
    dropping the last id component would resolve `from . import x` one level too high and attach
    every relative import in a package's `__init__` to the wrong node.
    """
    directory = os.path.dirname(rel)
    return [p for p in directory.replace(os.sep, ".").split(".") if p]


def absolute_head(node: ast.ImportFrom, pkg: list[str]) -> str:
    """The module a `from ... import` names, made absolute against the importing file's package.

    `node.level` is the dot count: level 1 is the file's own package, so the number of levels
    CLIMBED is `level - 1`. `keep == 0` therefore means "landed exactly on the root", which is
    legal and yields the bare module — it is not the error case.

    Empty when the import climbs PAST the root, because there is no target to record and the
    caller drops it. Returning the bare module there — which is what dropping the package prefix
    while keeping `node.module` does — invents an absolute target out of a relative one:
    `from ....far import y` would be recorded as a plain `far`, and if any node in the tree
    happened to be called `far` the scan would report an edge that no import expresses. An
    invented edge invents a cycle, and a cycle is a blocker.

    KNOWN LIMITATION: `pkg` is relative to `--root`, so a legal deep climb in the real repo looks
    like an over-climb when the scan is rooted at a subdirectory. Such an import is currently
    dropped silently rather than counted in `unresolved_imports`, which understates that blind
    spot. Dropping is still strictly better than the invented target it replaces.
    """
    if not node.level:
        return node.module or ""
    keep = len(pkg) - (node.level - 1)
    if keep < 0:
        return ""
    return ".".join(p for p in pkg[:keep] + (node.module or "").split(".") if p)


def py_targets(tree: ast.AST, rel: str) -> tuple[list[str], list[str]]:
    """(definite targets, maybe-targets), both absolute dotted.

    `from pkg import name` names a module OR a symbol inside one, and the AST cannot tell which.
    `pkg` is definite; `pkg.name` is a MAYBE — worth resolving, but its failure to resolve is not
    a gap in the graph, so it must not be counted as an unresolved import. Counting it would make
    the fidelity signal fire on ordinary, fully-understood code.
    """
    pkg = package_of(rel)
    plain = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    froms = [(n, absolute_head(n, pkg))
             for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    sure = plain + [head for _, head in froms if head]
    maybe = [f"{head}.{a.name}"
             for node, head in froms if head for a in node.names if a.name != "*"]
    return sure, maybe


def py_types(tree: ast.AST) -> tuple[int, int]:
    """(total types, abstract types). Abstract = Protocol/ABC base, or an @abstractmethod."""
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    return len(classes), sum(1 for cls in classes if is_abstract(cls))


def is_abstract(cls: ast.ClassDef) -> bool:
    """One class's answer to "is this a declared abstraction?" — what py_types counts."""
    bases = {b.id for b in cls.bases if isinstance(b, ast.Name)}
    bases |= {b.attr for b in cls.bases if isinstance(b, ast.Attribute)}
    marks = {d.id for d in cls.decorator_list if isinstance(d, ast.Name)}
    return (bool(bases & {"Protocol", "ABC", "ABCMeta"})
            or "runtime_checkable" in marks or has_abstract_member(cls))


def has_abstract_member(cls: ast.ClassDef) -> bool:
    """An @abstractmethod/@abstractproperty on any member, however it is spelled or imported."""
    return any(
        isinstance(d, ast.Name) and d.id.startswith("abstract")
        or isinstance(d, ast.Attribute) and d.attr.startswith("abstract")
        for fn in cls.body if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        for d in fn.decorator_list
    )


def scan_text(rel: str, src: str, lang: str) -> dict:
    """One record per non-Python file. The language is a lookup here, never a branch."""
    facts = LEXERS.get(lang, imports_lexers.ABSENT).read(Source(rel, src))
    return {"path": rel, "lang": lang, "loc": src.count("\n") + 1,
            "raw": sorted(set(facts.raw)), **facts.extra}


def scan_python(rel: str, src: str) -> dict:
    tree = ast.parse(src)
    total, abstract = py_types(tree)
    sure, maybe = py_targets(tree, rel)
    return {"path": rel, "lang": "python", "loc": src.count("\n") + 1,
            "raw": sorted(set(sure)), "raw_maybe": sorted(set(maybe) - set(sure)),
            "id": dotted(rel), "types": total, "abstract": abstract}


def scan_file(path: str) -> None:
    rel = os.path.relpath(path, ROOT) if ROOT else path
    lang = LANG_BY_EXT.get(os.path.splitext(path)[1])
    if lang is None:
        return
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    try:
        rec = scan_python(rel, src) if lang == "python" else scan_text(rel, src, lang)
    except SyntaxError as e:
        rec = {"path": rel, "lang": lang, "loc": src.count("\n") + 1, "raw": [],
               "unparseable": f"line {e.lineno}: {e.msg}"}
    sys.stdout.write(json.dumps(rec, separators=(",", ":")) + "\n")


def main() -> int:
    """Error boundary: one bad file must not cost the whole graph, so log a traceback and go on.

    Exit stays 0 by design — graph.sh reads a non-zero exit as "this scanner is unusable" and
    falls back to a coarser extractor for the entire language.
    """
    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        try:
            scan_file(path)
        except Exception:                            # noqa: BLE001 - boundary: log and continue
            traceback.print_exc()                    # full stack, per error-handling.md §1
            print(f"imports_scan: giving up on {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
