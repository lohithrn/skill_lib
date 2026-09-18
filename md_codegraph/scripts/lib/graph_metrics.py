#!/usr/bin/env python3
"""Graph algorithms only. This module knows nothing about code, files or languages.

It is the sink node of the scripts: it imports nothing from the rest of the skill, so it can be
tested with a hand-drawn adjacency dict and no repo at all. Every function is total — it returns
`None` for a metric it cannot compute within budget rather than a plausible number, because
`specs/graph-report.md` requires an unmeasurable metric to be OMITTED, never zeroed.

Interpretation lives elsewhere on purpose: `graph_shapes.py` turns these numbers into a named
cycle shape, `graph_roles.py` turns paths into doctrine. Nothing in here knows either.
"""
from __future__ import annotations

# Budgets. Above these, a metric is omitted with a reason instead of running for minutes.
CAP_CLOSURE_NODES = 3000        # propagation cost is O(V*E)
CAP_BETWEENNESS_NODES = 1200    # Brandes is O(V*E) with a much larger constant


# codegraph:exempt method_lines, loop_body, nesting -- Tarjan 1972 (SIAM J. Comput. 1:2, p. 157),
# kept in the paper's own single-loop form so it can be checked line by line against the source.
# Splitting the lowlink update across helpers hides the one invariant the algorithm rests on:
# `low[v]` may only be lowered from a vertex still on the stack. See references/graph-metrics.md.
def tarjan_scc(nodes: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
    """Strongly connected components, Tarjan 1972, iterative so deep graphs cannot blow the stack.

    Returns every SCC, including singletons; the caller decides that |SCC| >= 2 is the defect.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    out: list[list[str]] = []
    counter = 0

    for root in nodes:
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, child_i = work.pop()
            if child_i == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            descended = False
            kids = adj.get(node, ())
            for i in range(child_i, len(kids)):
                kid = kids[i]
                if kid not in index:
                    work.append((node, i + 1))
                    work.append((kid, 0))
                    descended = True
                    break
                if kid in on_stack:
                    low[node] = min(low[node], index[kid])
            if descended:
                continue
            if low[node] == index[node]:
                comp: list[str] = []
                while True:
                    popped = stack.pop()
                    on_stack.discard(popped)
                    comp.append(popped)
                    if popped == node:
                        break
                out.append(comp)
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return out


def fan(nodes: list[str], edges: list[tuple[str, str]]) -> tuple[dict[str, int], dict[str, int]]:
    """(fan_in, fan_out) counted over DISTINCT node pairs, so a repeated import is one edge."""
    fan_in = {n: 0 for n in nodes}
    fan_out = {n: 0 for n in nodes}
    for src, dst in set(edges):
        _bump(fan_out, src)
        _bump(fan_in, dst)
    return fan_in, fan_out


def _bump(counter: dict[str, int], key: str) -> None:
    """Count only nodes that are in the scan. An edge to something outside it is real, but it is
    not a degree of any node we can report on, and inventing a key would invent a node."""
    if key in counter:
        counter[key] += 1


def instability(fan_in: int, fan_out: int) -> float | None:
    """I = Ce / (Ca + Ce), Martin. Undefined for an isolated node — None, not 0."""
    total = fan_in + fan_out
    return round(fan_out / total, 3) if total else None


def distance(abstractness: float | None, unstable: float | None) -> float | None:
    """D = |A + I - 1|, Martin 2017. NOT the perpendicular distance, which carries a /sqrt(2);
    every mainstream tool reports this form, so this form is what a reader can compare against."""
    if abstractness is None or unstable is None:
        return None
    return round(abs(abstractness + unstable - 1), 3)


def pagerank(nodes: list[str], adj: dict[str, list[str]],
             damping: float = 0.85, iterations: int = 40) -> dict[str, float]:
    """PageRank on the graph as given. Run it on the REVERSED graph to rank "who depends on me",
    which is the god-module question. Normalised so the mean is 1: a score of 8 means eight times
    the average node's importance, which is readable without knowing the node count."""
    count = len(nodes)
    if not count:
        return {}
    rank = {n: 1.0 / count for n in nodes}
    sweep = _Sweep(nodes, adj, damping)
    for _ in range(iterations):
        rank = sweep.once(rank)
    return {n: round(v * count, 3) for n, v in rank.items()}


class _Sweep:
    """One PageRank iteration. The node set, the graph and the damping factor are fixed for the
    whole run, so they are held once here instead of being re-threaded through forty calls."""

    def __init__(self, nodes: list[str], adj: dict[str, list[str]], damping: float) -> None:
        self.nodes = nodes
        self.adj = adj
        self.known = set(nodes)
        self.damping = damping
        self.base = (1.0 - damping) / len(nodes)

    def once(self, rank: dict[str, float]) -> dict[str, float]:
        nxt = {n: self.base for n in self.nodes}
        for node in self.nodes:
            self._push(nxt, node, rank[node])
        return nxt

    def _push(self, nxt: dict[str, float], node: str, mass: float) -> None:
        """Send a node's mass to its children — or to EVERY node when it has none. A sink that
        keeps its mass makes the total leak away instead of summing to one, so `kids or nodes`
        is the redistribution, written as a choice of target list rather than as a branch."""
        kids = [k for k in self.adj.get(node, ()) if k in self.known]
        targets = kids or self.nodes
        share = self.damping * mass / len(targets)
        for target in targets:
            nxt[target] += share


def _reachable(start: str, adj: dict[str, list[str]], known: set[str]) -> int:
    seen = {start}
    work = [start]
    while work:
        fresh = [k for k in adj.get(work.pop(), ()) if k in known and k not in seen]
        seen.update(fresh)
        work.extend(fresh)
    return len(seen) - 1                               # exclude the start itself


def propagation_cost(nodes: list[str], adj: dict[str, list[str]]) -> tuple[float | None, str]:
    """MacCormack, Rusnak & Baldwin 2006: nonzero cells of the visibility matrix over N^2.

    "If I change one random file, what fraction of the system can see the change." Returns
    (value, reason-if-omitted) so the caller can put the reason in `degraded`.
    """
    count = len(nodes)
    if count == 0:
        return None, "no nodes"
    if count > CAP_CLOSURE_NODES:
        return None, f"transitive closure skipped: {count} nodes exceeds cap {CAP_CLOSURE_NODES}"
    known = set(nodes)
    total = sum(_reachable(n, adj, known) for n in nodes)
    return round(total / (count * count), 4), ""


# codegraph:exempt method_lines, loop_body, nesting -- Brandes 2001 (J. Math. Sociol. 25:2, Alg. 1),
# kept as the paper's two-phase forward BFS / reverse accumulation in one body. The two phases share
# sigma, dist, preds and the traversal stack; handing four mutable maps to a helper would cost more
# in coupling than the nesting saves, and the correctness argument is per-phase, not per-function.
def betweenness(nodes: list[str], adj: dict[str, list[str]]) -> tuple[dict[str, float], str]:
    """Brandes 2001, unweighted. High betweenness with low own complexity is a pure broker:
    the file every change routes through. Returns ({}, reason) when over budget."""
    count = len(nodes)
    if count > CAP_BETWEENNESS_NODES:
        return {}, f"betweenness skipped: {count} nodes exceeds cap {CAP_BETWEENNESS_NODES}"
    known = set(nodes)
    score = {n: 0.0 for n in nodes}
    for source in nodes:
        stack: list[str] = []
        preds: dict[str, list[str]] = {n: [] for n in nodes}
        sigma = {n: 0.0 for n in nodes}
        dist = {n: -1 for n in nodes}
        sigma[source] = 1.0
        dist[source] = 0
        queue = [source]
        head = 0
        while head < len(queue):
            node = queue[head]
            head += 1
            stack.append(node)
            for kid in adj.get(node, ()):
                if kid not in known:
                    continue
                if dist[kid] < 0:
                    dist[kid] = dist[node] + 1
                    queue.append(kid)
                if dist[kid] == dist[node] + 1:
                    sigma[kid] += sigma[node]
                    preds[kid].append(node)
        delta = {n: 0.0 for n in nodes}
        while stack:
            node = stack.pop()
            for pred in preds[node]:
                delta[pred] += (sigma[pred] / sigma[node]) * (1.0 + delta[node])
            if node != source:
                score[node] += delta[node]
    scale = (count - 1) * (count - 2)
    if scale > 0:
        score = {n: round(v / scale, 4) for n, v in score.items()}
    return score, ""


def median(values: list[int]) -> float:
    """Median over DISTINCT non-zero values, which is what Arcan's hub-like detector uses.
    The plain median of a dependency distribution is almost always 0 or 1 and flags nothing."""
    distinct = sorted({v for v in values if v})
    if not distinct:
        return 0.0
    mid = len(distinct) // 2
    if len(distinct) % 2:
        return float(distinct[mid])
    return (distinct[mid - 1] + distinct[mid]) / 2.0
