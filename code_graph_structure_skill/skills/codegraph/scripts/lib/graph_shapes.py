#!/usr/bin/env python3
"""Tangle shape classification — Al-Mutawa, Dietrich, Marsland & McCartin, ASWEC 2014.

Split out of `graph_metrics.py`, which is the general algorithm library. Shape is a level up from
that: it interprets a subgraph as one of six named cycle patterns, and each pattern implies a
DIFFERENT refactoring. Keeping it separate means `graph_metrics.py` stays a pure algorithm sink
that a test can exercise with a hand-drawn dict, while the interpretation lives where the
doctrine that reads it can be changed without touching Brandes or Tarjan.

Like everything under `scripts/lib`, a metric this file cannot compute within budget is ABSENT
from the result, never zero — `specs/graph-report.md` forbids reporting an estimate as a measure.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from graph_metrics import betweenness                                    # noqa: E402

CAP_CYCLE_HUB_NODES = 400       # Brandes again, once per tangle, to test multi-hub


def gini(values: list[float]) -> float | None:
    """Gini coefficient of a non-negative distribution, 0 = perfectly even, 1 = one node holds all.

    Used on the betweenness distribution inside a tangle: several vertices with high betweenness
    means several hubs, which is what separates a multi-hub from a star.
    """
    count = len(values)
    if count == 0:
        return None
    total = sum(values)
    if total <= 0:
        return 0.0                                       # every vertex equally central
    ordered = sorted(values)
    weighted = sum((i + 1) * v for i, v in enumerate(ordered))
    return round((2.0 * weighted - (count + 1) * total) / (count * total), 4)


def inner_edges(members: set[str], edges) -> set[tuple[str, str]]:
    """Edges with BOTH ends inside the tangle. Every shape formula is defined on this subgraph
    alone; counting an edge that leaves the tangle would make a small cycle look dense."""
    return {(s, d) for (s, d) in edges if s in members and d in members and s != d}


def degrees(inside: set[tuple[str, str]]) -> tuple[dict[str, int], dict[str, set[str]]]:
    """(undirected degree, undirected neighbour sets) over the tangle subgraph."""
    degree: dict[str, int] = {}
    friends: dict[str, set[str]] = {}
    for src, dst in inside:
        degree[src] = degree.get(src, 0) + 1
        degree[dst] = degree.get(dst, 0) + 1
        friends.setdefault(src, set()).add(dst)
        friends.setdefault(dst, set()).add(src)
    return degree, friends


def hub_spread(members: list[str], inside: set[tuple[str, str]]) -> tuple[float | None, str]:
    """(gini of betweenness inside the tangle, degradation-note). None means NOT TESTED, which the
    decision tree must treat as "fall through", never as "not a multi-hub"."""
    if len(members) > CAP_CYCLE_HUB_NODES:
        return None, (f"cycle shape: betweenness skipped for a {len(members)}-node tangle "
                      f"(cap {CAP_CYCLE_HUB_NODES}); multi-hub was not tested")
    adj: dict[str, list[str]] = {}
    for src, dst in inside:
        adj.setdefault(src, []).append(dst)
    scores, note = betweenness(sorted(members), adj)
    if not scores:
        return None, note or "cycle shape: betweenness unavailable; multi-hub was not tested"
    return gini([scores[n] for n in sorted(members)]), ""


def shape_ratios(members: list[str], inside: set[tuple[str, str]]) -> dict[str, float | None]:
    """The five path-independent shape ratios, as quoted in `references/arch-smells.md` §3."""
    v_count, e_count = len(members), len(inside)
    dense_den = v_count * v_count - 2 * v_count
    degree, friends = degrees(inside)
    chain_den = v_count - 2
    return {
        "ratio": v_count / e_count,
        "dense": (e_count - v_count) / dense_den if dense_den > 0 else None,
        "bckref": sum(1 for (s, d) in inside if (d, s) in inside) / e_count,
        # "a tangle classified as a star needs to have at least four vertices" (Al-Mutawa 2014)
        "star": max(degree.values()) / e_count if degree and v_count >= 4 else None,
        "chain": (min(sum(1 for n in members if len(friends.get(n, ())) == 2), chain_den)
                  / chain_den if chain_den > 0 else None),
    }


def classify(met: dict[str, float | None]) -> str:
    """The decision tree, first match wins. A None never satisfies a test, so an unmeasured metric
    falls through to the next shape instead of asserting its absence proves anything."""
    ratio, dense = met.get("ratio"), met.get("dense")
    bckref, star, chain, hub = met.get("bckref"), met.get("star"), met.get("chain"), met.get("hub")
    back = bckref is not None and bckref >= 0.75
    if ratio is not None and ratio >= 0.75:
        return "circle"
    if back and dense is not None and dense >= 0.75:
        return "clique"
    if back and chain is not None and chain >= 0.75:
        return "chain"
    if back and star is not None and star >= 0.75:
        return "star"
    if hub is not None and hub >= 0.50:
        return "multi-hub"
    if dense is not None and dense >= 0.45:
        return "semi-clique"
    return "unknown"


def cycle_shape(members: list[str], edges) -> tuple[str, dict, str]:
    """Classify one tangle by shape. Returns (shape, metrics, degradation-note).

    A bare SCC says only "there is a cycle"; the shape says which refactoring applies. A circle
    breaks with one inversion; a clique has to be re-designed; a star's centre is the real defect.
    """
    inside = inner_edges(set(members), edges)
    v_count, e_count = len(members), len(inside)
    metrics: dict[str, float] = {"vertices": v_count, "edges": e_count}

    if v_count == 2:
        return "tiny", metrics, ""                       # two mutually-importing modules
    if e_count == 0 or v_count < 2:
        return "unknown", metrics, ""                    # not a tangle we can measure

    ratios = shape_ratios(members, inside)
    ratios["hub"], note = hub_spread(members, inside)
    for name, value in ratios.items():
        if value is not None:
            metrics[name] = round(value, 4)
    return classify(ratios), metrics, note
