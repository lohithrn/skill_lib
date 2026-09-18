#!/usr/bin/env python3
"""Render graph.json as the four views a human actually reads. Reads JSON on stdin.

Deliberately four views and nothing else:

  1. cycles          — every SCC of size >= 2, largest first, with its shape and a candidate cut
  2. illegal edges   — the layer rule, violated, grouped by reason
  3. top by rank     — who the codebase depends on, whether or not that was the design
  4. port health     — ports missing a contract suite or an Absent resolver

A 3,000-edge dump is not a finding, so the full edge list is never printed. That is what the
JSON is for.
"""
from __future__ import annotations

import json
import sys
import traceback

TOP_N = 10
MAX_CYCLES = 8
MAX_MEMBERS = 8
MAX_ILLEGAL = 12


def head(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def show_cycles(graph: dict) -> None:
    cycles = graph.get("cycles", [])
    head(f"1. Cycles — {len(cycles)} (any SCC of 2+ is a blocker; ADP violated)")
    if not cycles:
        note = "" if graph.get("fidelity") == "native" else "  [fidelity=degraded: unverified]"
        print("  none found" + note)
        return
    for cycle in cycles[:MAX_CYCLES]:
        show_one_cycle(cycle)


def show_one_cycle(cycle: dict) -> None:
    """One tangle: members (truncated), its shape, the ratios behind the shape, and a cut."""
    members = cycle["scc"]
    shown = ", ".join(members[:MAX_MEMBERS])
    more = f" (+{len(members) - MAX_MEMBERS} more)" if len(members) > MAX_MEMBERS else ""
    print(f"  [{cycle['size']}] {cycle.get('shape') or '?'}: {shown}{more}")
    quoted = ratio_line(cycle.get("shape_metrics") or {})
    if quoted:
        print(f"      {quoted}")
    if cycle.get("break_with"):
        print(f"      cut: {cycle['break_with']}")


def ratio_line(met: dict) -> str:
    """The measured ratios, in reading order. A ratio the shape pass could not compute is absent
    from `met`, so it is absent here too rather than printed as a zero."""
    order = ("ratio", "bckref", "dense", "star", "chain", "hub")
    return "  ".join(f"{k}={met[k]}" for k in order if k in met)


def show_illegal(graph: dict) -> None:
    illegal = [e for e in graph.get("edges", []) if not e.get("legal")]
    head(f"2. Illegal edges — {len(illegal)} (doctrine §9: down, or inward to utils)")
    grouped: dict[str, list[dict]] = {}
    for edge in illegal:
        grouped.setdefault(edge.get("reason", "unspecified"), []).append(edge)
    for reason, edges in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(edges):>4}  {reason}")
        for edge in edges[:3]:
            print(f"          {edge['from']} -> {edge['to']}")
    if not illegal:
        print("  none")


def show_top(graph: dict) -> None:
    nodes = graph.get("nodes", [])
    ranked = sorted(nodes, key=lambda n: -(n["metrics"].get("pagerank") or 0))[:TOP_N]
    head("3. Most depended-on — this table IS your architecture, designed or not")
    print(f"  {'rank':>6} {'in':>4} {'out':>4} {'I':>5} {'A':>5} {'D':>5} {'loc':>6}  role/id")
    for node in ranked:
        met = node["metrics"]
        cells = (met.get("pagerank"), met.get("fan_in"), met.get("fan_out"),
                 met.get("instability"), met.get("abstractness"), met.get("distance"),
                 node.get("loc"))
        text = " ".join(f"{'-' if v is None else v:>{w}}"
                        for v, w in zip(cells, (6, 4, 4, 5, 5, 5, 6)))
        print(f"  {text}  {node.get('role')}/{node['id']}")
    hubs = graph.get("hub_like", [])
    if hubs:
        print(f"\n  hub-like (high both ways, balanced): {', '.join(hubs[:5])}")


def show_ports(graph: dict) -> None:
    ports = graph.get("ports", [])
    head(f"4. Port health — {len(ports)} ports")
    if not ports:
        print("  no ports detected: every conflict in this repo is still answered inline")
        return
    for port in ports:
        gaps = port_gaps(port)
        print(f"  {port['resolvers']:>3} resolvers  {port['port']}  "
              f"[{'; '.join(gaps) if gaps else 'ok'}]")


def port_gaps(port: dict) -> list[str]:
    """What is missing around one port: a contract suite every resolver must pass, an Absent
    resolver for the empty case, and importers that are not the composition root."""
    gaps = []
    if not port.get("contract_suite"):
        gaps.append("NO contract suite")
    if not port.get("has_absent_resolver"):
        gaps.append("no Absent resolver")
    if port.get("imported_outside_root"):
        gaps.append(f"{len(port['imported_outside_root'])} non-root importers")
    return gaps


def show_totals(graph: dict) -> None:
    totals = graph.get("totals", {})
    keys = ("nodes", "edges", "cycles", "illegal_edges", "avg_degree", "propagation_cost",
            "ports", "resolvers", "ports_without_suite", "composition_roots",
            "unresolved_imports")
    line = "  ".join(f"{k}={totals[k]}" for k in keys if k in totals)
    print(f"codegraph graph  {graph.get('root', '')}  fidelity={graph.get('fidelity', '?')}")
    print("  " + line)
    for note in graph.get("degraded", []):
        print(f"  ! {note}")


def main() -> int:
    """Error boundary: a render failure must not look like an empty graph."""
    try:
        graph = json.load(sys.stdin)
        show_totals(graph)
        show_cycles(graph)
        show_illegal(graph)
        show_top(graph)
        show_ports(graph)
        return 0
    except Exception:                                # noqa: BLE001 - boundary: log and fail loudly
        traceback.print_exc()
        print("graph_render: could not render the graph", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
