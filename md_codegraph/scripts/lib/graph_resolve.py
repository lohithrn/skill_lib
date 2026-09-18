#!/usr/bin/env python3
"""Node identity and import resolution: raw import text -> node ids -> edges.

This is the half of the graph build that decides WHAT THE NODES ARE and which import points at
which. It is deliberately separate from `graph_build.py`, which measures the graph once it exists,
because these two answer different questions and fail in different ways: a mistake here invents an
edge, a mistake there mis-scores a real one.

Resolution is conservative on purpose. An import that could mean two nodes is reported as
UNRESOLVED rather than attached to a guess, because an invented edge produces an invented cycle,
and a cycle is a blocker — the most expensive kind of false finding this skill can emit.
"""
from __future__ import annotations

import posixpath
from collections import namedtuple

SEP = {"python": ".", "java": ".", "go": "/", "ts": "/"}

Catalog = namedtuple("Catalog", "nodes index local")
# The three lookups resolution needs, measured once per graph. `nodes` answers "is this a node
# already", `index` answers "which node does this tail name", `local` answers "does the importer
# have a sibling by this name" — three different questions, one value carrying all three.

# `tail_hit` has three answers, not two, and `None` is already spoken for: it means "refuse this
# target". A distinct sentinel is what lets "nothing matched, try a shorter tail" stay separable
# from "something matched ambiguously, stop" — collapsing them would let an ambiguous long tail
# fall through to an even more ambiguous short one.
KEEP_LOOKING = object()


def node_id(rec: dict) -> str:
    """One id per node. A scanner that already knows the id (a python dotted name, a Go import
    path from `go list`) says so and is trusted; otherwise the id comes from the path.

    Go aggregates to the package directory, so several files become one node — that is what a Go
    import actually targets, and pretending files are nodes would invent intra-package edges.
    """
    path = rec["path"]
    lang = rec["lang"]
    if rec.get("id"):
        return rec["id"]
    if lang == "go":
        return posixpath.dirname(path) or "."
    if lang == "java":
        pkg = rec.get("pkg") or ""
        stem = posixpath.splitext(posixpath.basename(path))[0]
        return f"{pkg}.{stem}" if pkg else stem
    stem = posixpath.splitext(path)[0]
    return stem[: -len("/index")] if stem.endswith("/index") else stem


def merge(records: list[dict]) -> dict[str, dict]:
    """Collapse records that share a node id (Go packages) into one node."""
    nodes: dict[str, dict] = {}
    for rec in records:
        nid = node_id(rec)
        absorb(nodes.setdefault(nid, blank_node(nid, rec)), rec)
    return nodes


def blank_node(nid: str, rec: dict) -> dict:
    """A node with its identity fixed and every measurement still at zero."""
    return {"id": nid, "lang": rec["lang"], "path": rec["path"],
            "loc": 0, "raw": [], "raw_maybe": [],
            "types": 0, "abstract": 0, "files": 0}


def absorb(node: dict, rec: dict) -> None:
    """Fold one file's record into the node that owns it — a Go package absorbs several."""
    node["loc"] += rec.get("loc", 0)
    node["files"] += 1
    node["raw"].extend(rec.get("raw", ()))
    node["raw_maybe"].extend(rec.get("raw_maybe", ()))
    node["types"] += rec.get("types", 0)
    node["abstract"] += rec.get("abstract", 0)


def suffix_keys(nid: str, lang: str) -> list[str]:
    """Every tail of an id at a component boundary. A repo's own source root (`src`, the module
    prefix from go.mod, a package alias) is not visible from a file path, so matching on tails is
    how an import written from the root resolves onto a node discovered from disk."""
    sep = SEP.get(lang, "/")
    parts = nid.split(sep)
    return [sep.join(parts[i:]) for i in range(len(parts))]


def build_index(nodes: dict[str, dict]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for nid, node in nodes.items():
        for key in suffix_keys(nid, node["lang"]):
            index.setdefault(key, set()).add(nid)
    return index


def build_local(nodes: dict[str, dict]) -> dict[tuple[str, str], set[str]]:
    """(directory, file stem) -> the node ids that file could be, for same-directory lookup.

    A set, not a single id: two files in one folder can share a stem across extensions
    (`foo.py`, `foo.ts`), and picking one arbitrarily would attach a Python import to a
    TypeScript module. Ambiguity here is refused, exactly as it is in the suffix index.
    """
    local: dict[tuple[str, str], set[str]] = {}
    for nid, node in nodes.items():
        path = node["path"]
        key = (posixpath.dirname(path), posixpath.splitext(posixpath.basename(path))[0])
        local.setdefault(key, set()).add(nid)
    return local


def catalog(nodes: dict[str, dict]) -> Catalog:
    """Everything resolution needs in order to look a target up, built once per graph: the nodes
    themselves, the suffix index, and the per-directory index. One value, not three arguments
    threaded through every helper — Introduce Parameter Object."""
    return Catalog(nodes, build_index(nodes), build_local(nodes))


def exact_hit(target: str, lang: str, nodes: dict[str, dict]) -> str | None:
    """The target names a node outright. TypeScript resolves a folder to its `index` module,
    because `import x from './thing'` where `thing/` is a directory means `thing/index`."""
    if target in nodes:
        return target
    packaged = f"{target}/index"
    return packaged if lang == "ts" and packaged in nodes else None


def resolve(target: str, src: dict, cat: Catalog) -> str | None:
    """Map one raw import target, as written inside node `src`, onto a node id — or None.

    `src` rather than a bare language string: WHERE the import was written decides what a bare
    name may mean (see `sibling`), and that is not knowable from the target text alone.
    """
    return exact_hit(target, src["lang"], cat.nodes) or by_tail(target, src, cat)


def by_tail(target: str, src: dict, cat: Catalog) -> str | None:
    """Longest tail first, shortest last. A repo's own source root (`src`, the go.mod prefix, a
    package alias) is invisible from a file path, so matching tails is how an import written from
    the root lands on a node discovered from disk."""
    sep = SEP.get(src["lang"], "/")
    parts = target.split(sep)
    for start in range(len(parts)):
        hit = tail_hit(sep.join(parts[start:]), src, cat)
        if hit is not KEEP_LOOKING:
            return hit
    return None


def tail_hit(key: str, src: dict, cat: Catalog) -> str | None | object:
    """One candidate tail: the node it names, None to stop, or KEEP_LOOKING to try a shorter one.

    An AMBIGUOUS tail stops the search rather than falling through to a shorter and even more
    ambiguous one. An invented edge invents a cycle, and a cycle is a blocker — the most expensive
    false finding this skill can emit.
    """
    if SEP.get(src["lang"], "/") not in key:
        return sibling(key, src, cat.local)   # the last tail, and the only bare one
    hits = cat.index.get(key)
    if not hits:
        return KEEP_LOOKING
    return next(iter(hits)) if len(hits) == 1 else None


def sibling(name: str, src: dict, local: dict[tuple[str, str], set[str]]) -> str | None:
    """A bare `import name` resolved against the importer's OWN directory, and nowhere else.

    This is the flat-sibling idiom — `sys.path.insert(here)` then `import cap_pragma` in Python, a
    same-package reference in Java — and refusing it outright is what made this scanner report
    `edges: 0` over its own 13-module `lib/`: a package that plainly imports itself looked acyclic,
    which is the one thing a cycle detector must never do.

    Scoped to the importer's directory, because that scope is exactly what makes it safe. The old
    refusal existed so that `import os.path` could not attach to some distant `path.py`; here a
    bare name binds only when a matching file sits BESIDE the importer — which is also precisely
    when Python itself imports that file in preference to the stdlib one. A single-component name
    matching somewhere else in the tree stays unresolved, as before.
    """
    owners = local.get((posixpath.dirname(src["path"]), name))
    return next(iter(owners)) if owners and len(owners) == 1 else None


def add_edge(weights: dict, src: str, dst: str | None) -> None:
    """One resolved import as an edge. A node importing itself is not an edge."""
    if dst is None or dst == src:
        return
    weights[(src, dst)] = weights.get((src, dst), 0) + 1


def build_edges(nodes: dict[str, dict]) -> tuple[dict, int]:
    """Distinct (src, dst) pairs with a weight, plus the count of targets that resolved to nothing.

    Unresolved is reported rather than hidden: it is mostly third-party packages, which is fine,
    but it is also every dynamic import and every ambiguous name — and that is the honest measure
    of how much of the real graph this scan cannot see.
    """
    cat = catalog(nodes)
    weights: dict[tuple[str, str], int] = {}
    unresolved = 0
    for node in nodes.values():
        unresolved += node_edges(weights, node, cat)
    return weights, unresolved


def node_edges(weights: dict, node: dict, cat: Catalog) -> int:
    """One node's imports as edges. Returns how many of its targets resolved to nothing, which is
    the caller's `unresolved` tally and this scan's honest measure of what it could not see."""
    src = node["id"]
    unresolved = 0
    for target in node["raw"]:
        dst = resolve(target, node, cat)
        if dst is None:
            unresolved += 1
            continue
        add_edge(weights, src, dst)
    # `raw_maybe` is `from pkg import name` where `name` might be a submodule. Resolve it if
    # it lands, ignore it if it does not — its failure means "it was a symbol", which is not
    # a hole in the graph and must not inflate the fidelity signal.
    for target in node.get("raw_maybe", ()):
        add_edge(weights, src, resolve(target, node, cat))
    return unresolved


def adjacency(weights: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(forward, reverse) adjacency from the edge set. The reverse graph is not a convenience: it
    is what PageRank must run on to answer "who depends on me", which is the god-module question.
    """
    forward: dict[str, list[str]] = {}
    reverse: dict[str, list[str]] = {}
    for (src, dst) in weights:
        forward.setdefault(src, []).append(dst)
        reverse.setdefault(dst, []).append(src)
    return forward, reverse
