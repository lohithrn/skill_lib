#!/usr/bin/env python3
"""Fold the shell's fidelity notes into graph.json and decide the single `fidelity` verdict.

Separate from graph_build.py on purpose: the builder measures the graph, this decides how far
the measurement may be trusted. Those are two different questions and two different reasons to
change, so they are two files.

The rule that matters, from jobs/analyze.md phase 1b: **a degraded graph may not be used to
claim "0 cycles."** So `fidelity` is `native` only when every language present was read by
something exact. Anything lexical makes the whole graph lexical, because a cycle only needs one
unseen import to hide.
"""
from __future__ import annotations

import json
import os
import sys
import traceback

# Which extractor each language got, and whether that extractor is exact for import edges.
EXACT = {"python": True, "go": True, "ts": False, "java": False}
EXTRACTOR = {"python": "ast", "go": "source imports + go list", "ts": "lexical", "java": "lexical"}


def read_notes() -> list[str]:
    path = os.environ.get("CG_NOTES_FILE", "")
    if not path or not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return [line.strip() for line in fh if line.strip()]


def lang_entry(lang: str) -> dict:
    """One language's row, before anything is counted into it."""
    return {"name": lang, "files": 0, "nodes": 0, "loc": 0,
            "tooling": EXTRACTOR.get(lang, "unknown"),
            "fidelity": "native" if EXACT.get(lang) else "lexical"}


def languages(graph: dict) -> dict[str, dict]:
    """Per-language file and node counts, with the extractor named. A reader who knows one
    language is lexical can then discount exactly the part of the graph that deserves it.

    `files` and `nodes` are both reported because in Go they differ: one node is a package of
    several files, so nodes alone would make a Go repo look smaller than it is.
    """
    seen: dict[str, dict] = {}
    for node in graph.get("nodes", []):
        entry = seen.setdefault(node.get("lang", "unknown"), lang_entry(node.get("lang", "unknown")))
        entry["files"] += node.get("files", 1)
        entry["nodes"] += 1
        entry["loc"] += node.get("loc", 0)
    return seen


def vacuous_acyclicity(graph: dict) -> str | None:
    """`cycles: 0` over an edgeless graph is not a finding of health, it is a failed scan.

    A resolver that could not attach a single import still produces a well-formed artifact with
    `cycles: []`, and every downstream gate reads that as "no cycles". So the one case where the
    number is meaningless says so in `degraded`, where `jobs/analyze.md` phase 1b already looks.
    """
    totals = graph.get("totals", {})
    if totals.get("edges", 0) or not totals.get("nodes", 0):
        return None
    unresolved = totals.get("unresolved_imports", 0)
    if not unresolved:
        return None
    return (f"0 edges resolved from {unresolved} import target(s) over {totals['nodes']} nodes: "
            "the cycle, fan-in and propagation numbers are vacuous and may NOT be reported as 0")


def incomplete_scan() -> str | None:
    """A file that was skipped or would not parse is a hole, and a hole can hide a cycle.

    `graph.sh` counts them (unparseable source + refused paths) into `CG_INCOMPLETE`, because only
    the shell knows what it declined to hand the scanner. The count matters more than the reason:
    any hole means the graph is a lower bound, so the verdict cannot stay `native` — `verify.md`
    treats a native→degraded transition as the trip-wire for a void diff, and it can only fire if
    the word moves when coverage drops.
    """
    try:
        holes = int(os.environ.get("CG_INCOMPLETE", "0") or 0)
    except ValueError:
        holes = 0
    if holes <= 0:
        return None
    return (f"fidelity=degraded: {holes} file(s) were not read (skipped or unparseable), so this "
            "graph is a LOWER BOUND on edges and may NOT be used to claim 0 cycles")


def go_downgrade(graph: dict, langs: dict) -> None:
    """Without go.mod, Go package ids come from directory paths and resolve by suffix. That is
    not exact, so say so rather than letting the `go` row keep claiming native."""
    if "go" not in langs or os.environ.get("CG_GO_NATIVE") == "1":
        return
    langs["go"]["fidelity"] = "lexical"
    langs["go"]["tooling"] = "source imports, directory ids"


def annotate(graph: dict) -> None:
    """Decide the one `fidelity` word and the `degraded` list behind it, in place.

    Every reason degrades the SAME verdict, so they are collected in one place: a caller that had
    to check three keys would eventually check two. Ordering is deliberate — the loudest reason a
    reader must not miss is inserted last, so it lands first in the list.
    """
    langs = languages(graph)
    go_downgrade(graph, langs)
    graph["languages"] = [langs[k] for k in sorted(langs)]
    lexical = [entry["name"] for entry in graph["languages"] if entry["fidelity"] != "native"]
    graph["fidelity"] = "degraded" if lexical else "native"
    notes = list(graph.get("degraded", [])) + read_notes()
    for reason in (vacuous_acyclicity(graph), incomplete_scan()):
        if reason:
            notes.insert(0, reason)
            graph["fidelity"] = "degraded"
    if lexical:
        notes.insert(0, "fidelity=degraded: " + ", ".join(lexical)
                     + " read lexically. This graph may NOT be used to claim 0 cycles.")
    graph["degraded"] = notes


def main() -> int:
    """Error boundary: if annotation fails, exit 2 and let graph.sh refuse to emit a graph whose
    trustworthiness is unknown. An unannotated graph would silently read as exact."""
    try:
        graph = json.load(sys.stdin)
        annotate(graph)
        json.dump(graph, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    except Exception:                                # noqa: BLE001 - boundary: log and fail loudly
        traceback.print_exc()
        print("graph_notes: could not annotate fidelity", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
