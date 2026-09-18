#!/usr/bin/env python3
"""Reduce a full graph.json to the cycle slice only. Reads stdin, writes stdout.

`graph.sh --cycles` exists because the refinement loop asks one question per pass ("did this
slice remove the cycle?") and the full graph.json is far too large to put in front of a model
that only needs the answer. This is a projection of the same artifact, never a second
measurement: every key here is copied verbatim from the input.

CG_CYCLES_FORMAT=json  the filtered artifact       (default)
CG_CYCLES_FORMAT=text  one block per cycle, plus the suggested cut

A cycle is DATA, not an error: exit 0 either way, and the caller asserts on the count. Exit 2
only when stdin was not a graph at all, because that is the case where reporting "0 cycles"
would be a lie.
"""

import json
import os
import sys

# Carried through even in cycles-only mode: a consumer that cannot see the fidelity caveats
# would read an empty `cycles` list as "acyclic", which is exactly the false negative
# references/graph-tooling.md section 9 warns about.
PASSTHROUGH = ("schema", "generated_at", "root", "languages", "fidelity", "degraded")


def main() -> int:
    try:
        doc = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"graph_cycles: stdin is not the graph JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(doc, dict) or "cycles" not in doc:
        print("graph_cycles: no `cycles` key; upstream did not build a graph", file=sys.stderr)
        return 2

    cycles = doc.get("cycles") or []
    out = {k: doc[k] for k in PASSTHROUGH if k in doc}
    out["cycles"] = cycles
    totals = doc.get("totals") or {}
    out["totals"] = {
        k: totals[k] for k in ("cycles", "nodes", "edges", "illegal_edges") if k in totals
    }

    RENDERERS.get(os.environ.get("CG_CYCLES_FORMAT"), emit_json)(out)
    return 0


def emit_json(out: dict) -> None:
    json.dump(out, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def render(out: dict) -> None:
    """The text view. Every loop here is one line deep because the per-item behaviour lives in a
    named function — the loop says "for each cycle", `render_cycle` says what a cycle looks like."""
    cycles = out.get("cycles") or []
    print(f"cycles: {out['totals'].get('cycles', len(cycles))}")
    for index, cyc in enumerate(cycles, 1):
        render_cycle(index, cyc)
    # An absence claim is only as strong as the graph behind it, so never print a bare
    # "none" without the caveats that would undermine it.
    for note in out.get("degraded") or []:
        print(f"  ! {caveat(note)}")
    if not cycles:
        print("\nno cycles found in what was scanned")


def render_cycle(index: int, cyc: dict) -> None:
    scc = cyc.get("scc") or []
    print(f"\n[{index}] {cyc.get('shape') or 'unshaped'}, {len(scc)} nodes")
    for member in scc:
        print(f"      {member}")
    weakest = cyc.get("weakest_edge") or {}
    if weakest:
        print(f"  cut candidate  {weakest.get('from')} -> {weakest.get('to')}"
              f"  (weight {weakest.get('weight')})")
    if cyc.get("break_with"):
        print(f"  move           {cyc['break_with']}")


def caveat(note) -> str:
    """A degraded note is either a string or a {language, reason} record, depending on which stage
    produced it. Normalising here keeps the branch out of the loop that prints them."""
    if isinstance(note, dict):
        return f"{note.get('language', note.get('scope', '?'))}: {note.get('reason', '')}"
    return str(note)


# The format is DATA, chosen by lookup. A second view is a new entry, not a new branch, and the
# default is the artifact rather than the pretty view: an unrecognised value must not silently
# print something a caller planned to parse.
RENDERERS = {"text": render, "json": emit_json}


if __name__ == "__main__":
    sys.exit(main())
