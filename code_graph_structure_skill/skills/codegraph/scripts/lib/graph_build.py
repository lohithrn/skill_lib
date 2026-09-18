#!/usr/bin/env python3
"""Measure the graph and emit `graph.json`. Reads imports_scan.py's JSONL on stdin.

The build is three collaborators, one responsibility each, so a wrong number can be traced to one
file: `graph_resolve.py` decides what the nodes are and which import points at which,
`graph_metrics.py` and `graph_shapes.py` compute, `graph_roles.py` judges legality. This file
orchestrates them and shapes the report — it holds no algorithm and no doctrine of its own.

Two value objects carry the measurements from `run` to whoever quotes them: `Measured` (everything
known PER NODE) and `Sections` (the finished sections plus the two PER-GRAPH scalars) — Introduce
Parameter Object, as `scan_python.py` does with `Measure`. Two, not one: doctrine.md §6 forbids the
god bag, one Context per family of questions.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_metrics as gm                                              # noqa: E402
import graph_resolve as gres                                            # noqa: E402
import graph_roles as gr                                                # noqa: E402
import graph_shapes as gs                                               # noqa: E402

ROOT = os.environ.get("CG_ROOT", "")

Measured = namedtuple("Measured", "nodes roles fan_in fan_out ranks between")
# Every PER-NODE fact the report quotes, measured once in `run`: the nodes, the role judged for
# each, and the four metric maps keyed by node id — one value, not six maps passed in order.

Sections = namedtuple("Sections", "edges cycles ports unresolved cost")
# The finished sections plus the two PER-GRAPH scalars: `totals` counts one value, not seven args.


def abstractness(node: dict) -> float | None:
    return round(node["abstract"] / node["types"], 3) if node["types"] else None


def assemble_nodes(measured: Measured) -> list[dict]:
    return [node_entry(nid, node, measured) for nid, node in sorted(measured.nodes.items())]


def node_entry(nid: str, node: dict, measured: Measured) -> dict:
    """One node as the report states it. An uncomputable metric is OMITTED, never zeroed."""
    metrics = node_metrics(nid, node, measured)
    return {"id": nid, "kind": "package" if node["lang"] == "go" else "module",
            "path": node["path"], "loc": node["loc"], "lang": node["lang"],
            "layer": gr.depth(node["path"]),
            "role": measured.roles.get(nid, "unknown"),
            "metrics": {k: v for k, v in metrics.items() if v is not None}}


def node_metrics(nid: str, node: dict, measured: Measured) -> dict:
    unstable = gm.instability(measured.fan_in.get(nid, 0), measured.fan_out.get(nid, 0))
    abstract = abstractness(node)
    return {"fan_in": measured.fan_in.get(nid, 0), "fan_out": measured.fan_out.get(nid, 0),
            "instability": unstable, "abstractness": abstract,
            "distance": gm.distance(abstract, unstable),
            "pagerank": measured.ranks.get(nid), "betweenness": measured.between.get(nid)}


def describe_cycles(comps: list[list[str]], weights: dict) -> tuple[list[dict], list[str]]:
    """Report cycles exactly; SUGGEST a cut. Minimum feedback arc set is NP-hard, so the
    weakest edge is a candidate, never a claim of minimality.

    Each cycle also carries its Al-Mutawa 2014 `shape` plus the `shape_metrics` that produced it,
    so a finding can quote the number instead of asserting the label. Returns (cycles, notes);
    notes belong in `degraded`."""
    cycles = []
    notes: list[str] = []
    for comp in sorted(comps, key=len, reverse=True):
        if len(comp) < 2:
            continue
        cycles.append(cycle_entry(sorted(comp), weights, notes))
    return cycles, notes


def cycle_entry(comp: list[str], weights: dict, notes: list[str]) -> dict:
    """One SCC: its members, its shape with the metrics behind the label, and a candidate cut.
    A shape note is per-graph, not per-cycle, so it is appended to `notes` once."""
    shape, shape_metrics, note = gs.cycle_shape(comp, weights.keys())
    if note and note not in notes:
        notes.append(note)
    entry: dict = {"scc": comp, "size": len(comp), "shape": shape,
                   "shape_metrics": shape_metrics}
    entry.update(cut_suggestion(comp, weights))
    return entry


def cut_suggestion(comp: list[str], weights: dict) -> dict:
    """The weakest edge inside the cycle, offered as the break. Minimum feedback arc set is
    NP-hard, so the weakest edge is a candidate, never a claim of minimality."""
    members = set(comp)
    inner = [(w, s, d) for (s, d), w in weights.items() if s in members and d in members]
    if not inner:
        return {}
    weakest = min(inner)
    return {"weakest_edge": {"from": weakest[1], "to": weakest[2], "weight": weakest[0]},
            "break_with": (f"invert {weakest[1]} -> {weakest[2]} behind a port declared "
                           f"in {weakest[1]} (DIP); candidate cut, not a minimal one")}


def describe_ports(measured: Measured, weights: dict) -> list[dict]:
    importers: dict[str, list[str]] = {}
    for (src, dst) in weights:
        importers.setdefault(dst, []).append(src)
    return [port_entry(nid, importers.get(nid, []), measured)
            for nid in sorted(n for n, r in measured.roles.items() if r == "port")]


def port_entry(nid: str, users: list[str], measured: Measured) -> dict:
    """One port with the evidence it is honoured: how many resolvers answer it, whether the
    resolver set is total, where its contract suite lives, and who reaches past the root."""
    nodes, roles = measured.nodes, measured.roles
    suites = [u for u in users
              if roles.get(u) == "test" and "contract" in gr.name_words(nodes[u]["path"])]
    resolvers = [u for u in users if roles.get(u) == "resolver"]
    absent = [r for r in resolvers if gr.is_absent_resolver(nodes[r]["path"])]
    return {"port": nid, "resolvers": len(resolvers),
            "has_absent_resolver": bool(absent),
            "contract_suite": nodes[suites[0]]["path"] if suites else None,
            "imported_outside_root": sorted(u for u in users
                                            if roles.get(u) in ("service", "adapter"))}


def hub_like(fan_in: dict, fan_out: dict) -> list[str]:
    """Arcan's Hub-Like Dependency with in-repo medians: high both ways and roughly balanced."""
    med_in = gm.median(list(fan_in.values()))
    med_out = gm.median(list(fan_out.values()))
    hubs = []
    for nid, incoming in fan_in.items():
        outgoing = fan_out.get(nid, 0)
        total = incoming + outgoing
        balanced = total and abs(incoming - outgoing) <= total / 4
        if incoming > med_in and outgoing > med_out and balanced:
            hubs.append(nid)
    return sorted(hubs)


def role_counts(roles: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for role in roles.values():
        counts[role] = counts.get(role, 0) + 1
    return counts


def totals(measured: Measured, sections: Sections) -> dict:
    """Every headline number in one flat object, because a later phase asserts on these."""
    nodes, edges, ports = measured.nodes, sections.edges, sections.ports
    counts = role_counts(measured.roles)
    out = {"files": sum(n["files"] for n in nodes.values()),
           "loc": sum(n["loc"] for n in nodes.values()),
           "nodes": len(nodes), "edges": len(edges),
           "cycles": len(sections.cycles),
           "illegal_edges": sum(1 for e in edges if not e["legal"]),
           "unresolved_imports": sections.unresolved,
           "ports": counts.get("port", 0), "resolvers": counts.get("resolver", 0),
           "composition_roots": counts.get("root", 0), "utils": counts.get("util", 0),
           "contract_suites": sum(1 for p in ports if p["contract_suite"]),
           "ports_without_suite": sum(1 for p in ports if not p["contract_suite"]),
           "ports_without_absent": sum(1 for p in ports if not p["has_absent_resolver"]),
           "avg_degree": round(2 * len(edges) / len(nodes), 2) if nodes else 0}
    if sections.cost is not None:
        out["propagation_cost"] = sections.cost
    return out


def assign_roles(nodes: dict, adj: dict) -> tuple[dict[str, str], dict[str, str]]:
    """(roles, dirs). Roles are refined against the edge set, because `resolver` is a structural
    fact about who a node answers to, not a naming convention (graph_roles.refine_roles)."""
    dirs = {nid: gr.directory(n["path"]) for nid, n in nodes.items()}
    roles = {nid: gr.initial_role(n["path"], n["types"], n["abstract"])
             for nid, n in nodes.items()}
    gr.refine_roles(roles, dirs, adj)
    return roles, dirs


def judge_edges(weights: dict, roles: dict, dirs: dict) -> list[dict]:
    """Every edge with `legal` COMPUTED by the doctrine, never guessed, and the rule it broke."""
    edges = []
    for (src, dst), weight in sorted(weights.items()):
        legal, reason = gr.legality(src, dst, roles, dirs)
        edges.append({"from": src, "to": dst, "kind": "import", "weight": weight,
                      "legal": legal, "reason": reason})
    return edges


def unresolved_note(unresolved: int) -> list[str]:
    """An import the scan could not resolve is an edge nobody reports, so `degraded` says so."""
    if not unresolved:
        return []
    return [f"{unresolved} import targets could not be resolved to a node "
            f"(external packages, dynamic imports, or ambiguous names)"]


def document(measured: Measured, sections: Sections, degraded: list[str]) -> dict:
    """The report, assembled. Nothing is measured here: the shape of the output and the numbers in
    it can never be wrong for the same reason."""
    return {"schema": "codegraph/1",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "root": ROOT,
            "nodes": assemble_nodes(measured),
            "edges": sections.edges, "cycles": sections.cycles, "ports": sections.ports,
            "hub_like": hub_like(measured.fan_in, measured.fan_out),
            "totals": totals(measured, sections),
            "degraded": degraded + unresolved_note(sections.unresolved)}


def run(records: list[dict]) -> dict:
    nodes = gres.merge(records)
    weights, unresolved = gres.build_edges(nodes)
    adj, reverse = gres.adjacency(weights)
    roles, dirs = assign_roles(nodes, adj)

    ids = sorted(nodes)
    fan_in, fan_out = gm.fan(ids, list(weights))
    ranks = gm.pagerank(ids, reverse)                 # reversed: rank "who depends on me"
    between, between_note = gm.betweenness(ids, adj)
    cost, cost_note = gm.propagation_cost(ids, adj)
    measured = Measured(nodes, roles, fan_in, fan_out, ranks, between)

    cycles, shape_notes = describe_cycles(gm.tarjan_scc(ids, adj), weights)
    sections = Sections(judge_edges(weights, roles, dirs), cycles,
                        describe_ports(measured, weights), unresolved, cost)
    degraded = [note for note in (between_note, cost_note, *shape_notes) if note]
    return document(measured, sections, degraded)


def main() -> int:
    """Error boundary: a build failure prints its traceback and exits 2 so graph.sh can report
    a degraded graph rather than emit half a JSON document that a later phase would trust."""
    try:
        records = [json.loads(line) for line in sys.stdin if line.strip()]
        sys.stdout.write(json.dumps(run(records), indent=2) + "\n")
        return 0
    except Exception:                                # noqa: BLE001 - boundary: log and fail loudly
        traceback.print_exc()
        print("graph_build: could not build the graph", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
