#!/usr/bin/env python3
"""Offline calculator for the agent-assessment metrics in this skill.

Standard library only. Reads nothing but the JSON you hand it, writes nothing but JSON
on stdout, and touches no network. Every formula here is the one printed in the
matching references/ file -- nothing is rounded, simplified or invented.

Usage:
    python3 scripts/metrics.py <command> [file.json]     # file, or stdin
    python3 scripts/metrics.py --help
    python3 scripts/metrics.py --selftest

Commands and their input shapes:

  tools        {"tp": 7, "fp": 1, "fn": 2}
               {"expected": ["a","b"], "actual": ["a","c"]}       (multiset compare)
               -> precision = TP/(TP+FP), recall = TP/(TP+FN), f1

  fields       {"expected": {...nested JSON...}, "actual": {...}}
               -> flattens to canonical paths (flight.date, attendee.email),
                  then precision/recall/f1 over path presence AND value equality,
                  plus omitted_optional vs wrong_value, kept apart on purpose

  ndcg         {"relevance": [3,2,3,0,1], "k": 10}
               -> gain_i = 2^rel_i - 1, dcg@k, idcg@k, ndcg@k
                  idcg == 0 -> ndcg is null and the case is marked excluded

  mrr          {"first_relevant_ranks": [1,3,null]}
               -> mean(1/rank) over queries that HAVE a relevant item, plus the count
                  of queries that do not. The two are never folded into one number.

  map          {"queries": [[1,0,1],[0,1,0]], "k": 3}
               -> mean of precision@r at ranks r where a relevant item appears

  kendall      {"actual": ["a","b","c"], "ideal": ["b","a","c"]}
               -> (concordant - discordant) / all_pairs

  trajectory   {"expected": ["a","b","c"], "actual": ["a","c"]}
               -> lcs_length and BOTH normalizations, unlabelled by design:
                  the playbook pins no canonical one, so you must record which you used

  reliability  {"cases": [[true,true],[true,false]]}
               -> per case: repeat_success_rate = successes/k, strict_pass_k indicator
                  aggregate: mean repeat success, mean strict pass^k, k

  calibration  {"pairs": [[0.9,1],[0.6,0]], "bins": 10}
               -> brier = mean((p-outcome)^2), ece = sum_b (n_b/N)*|conf_b - acc_b|

  aggregate    {"scenarios": [[1,0,1],[1]], "successes": 38, "trials": 40, "tail": 0.1}
               -> macro (per case, then per scenario, then across), lower-tail/CVaR mean
                  over the worst `tail` fraction, and the Wilson 95% interval

Exit codes: 0 result on stdout, 2 the input could not be read as this command's shape.
"""

import json
import math
import sys

Z95 = 1.959963984540054  # two-sided 95% normal quantile, for the Wilson interval


def _ratio(num, den):
    """None, never 0.0, when the denominator is empty: an unmeasurable metric is
    omitted and reported as unmeasured, never zeroed."""
    return None if den == 0 else num / den


def prf(tp, fp, fn):
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1}


def cmd_tools(data):
    if "tp" in data:
        return prf(int(data["tp"]), int(data.get("fp", 0)), int(data.get("fn", 0)))
    expected, actual = list(data["expected"]), list(data["actual"])
    remaining = list(expected)
    tp = 0
    for call in actual:
        if call in remaining:
            remaining.remove(call)
            tp += 1
    return prf(tp, len(actual) - tp, len(remaining))


def flatten(obj, prefix=""):
    """Nested JSON -> {canonical path: value}. Array order is preserved as an index,
    because collapsing an ordered array to a set marks a wrong itinerary correct."""
    out = {}
    if isinstance(obj, dict):
        for key in obj:
            out.update(flatten(obj[key], f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            out.update(flatten(item, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def cmd_fields(data):
    expected = flatten(data["expected"])
    actual = flatten(data["actual"])
    tp = sum(1 for p in expected if p in actual and actual[p] == expected[p])
    wrong_value = sum(1 for p in expected if p in actual and actual[p] != expected[p])
    omitted = sum(1 for p in expected if p not in actual)
    extra = sum(1 for p in actual if p not in expected)
    result = prf(tp, wrong_value + extra, wrong_value + omitted)
    result["omitted_optional"] = omitted
    result["wrong_value"] = wrong_value
    result["unexpected_path"] = extra
    result["json_exact_match"] = 1 if expected == actual else 0
    return result


def dcg(relevance, k):
    return sum((2 ** rel - 1) / math.log2(i + 1)
               for i, rel in enumerate(relevance[:k], start=1))


def cmd_ndcg(data):
    relevance = list(data["relevance"])
    k = int(data.get("k", len(relevance)))
    actual = dcg(relevance, k)
    ideal = dcg(sorted(relevance, reverse=True), k)
    return {"k": k,
            "gains": [2 ** rel - 1 for rel in relevance[:k]],
            "dcg_at_k": actual,
            "idcg_at_k": ideal,
            "ndcg_at_k": None if ideal == 0 else actual / ideal,
            "excluded": ideal == 0,
            "note": ("idcg is 0: the query is not informative for ndcg and must be "
                     "excluded or re-labelled, never scored 0.0" if ideal == 0 else "")}


def cmd_mrr(data):
    ranks = list(data["first_relevant_ranks"])
    hits = [r for r in ranks if r]
    return {"queries": len(ranks),
            "queries_with_a_relevant_item": len(hits),
            "queries_with_none": len(ranks) - len(hits),
            "mrr_over_queries_with_a_relevant_item": _ratio(
                sum(1.0 / r for r in hits), len(hits)),
            "note": ("queries with no relevant item are counted, not folded in: the "
                     "convention for them is yours to state")}


def average_precision(flags, k):
    flags = list(flags)[:k]
    relevant_seen = 0
    precisions = []
    for rank, flag in enumerate(flags, start=1):
        if flag:
            relevant_seen += 1
            precisions.append(relevant_seen / rank)
    return _ratio(sum(precisions), len(precisions))


def cmd_map(data):
    queries = data["queries"]
    k = int(data.get("k", max((len(q) for q in queries), default=0)))
    per_query = [average_precision(q, k) for q in queries]
    scored = [ap for ap in per_query if ap is not None]
    return {"k": k, "average_precision_per_query": per_query,
            "queries_with_no_relevant_item": len(per_query) - len(scored),
            "map_at_k": _ratio(sum(scored), len(scored))}


def cmd_kendall(data):
    actual, ideal = list(data["actual"]), list(data["ideal"])
    shared = [item for item in actual if item in ideal]
    concordant = discordant = 0
    for i in range(len(shared)):
        for j in range(i + 1, len(shared)):
            a, b = shared[i], shared[j]
            if ideal.index(a) < ideal.index(b):
                concordant += 1
            else:
                discordant += 1
    pairs = concordant + discordant
    return {"items_in_both_lists": len(shared), "concordant_pairs": concordant,
            "discordant_pairs": discordant, "all_pairs": pairs,
            "kendall_tau": _ratio(concordant - discordant, pairs)}


def lcs_length(a, b):
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def cmd_trajectory(data):
    expected, actual = list(data["expected"]), list(data["actual"])
    length = lcs_length(expected, actual)
    return {"lcs_length": length,
            "len_expected": len(expected), "len_actual": len(actual),
            "lcs_over_expected": _ratio(length, len(expected)),
            "lcs_over_longer_sequence": _ratio(length, max(len(expected), len(actual))),
            "note": ("a diagnostic, never the definition of correctness; the playbook "
                     "pins no canonical normalization, so record which one you report")}


def cmd_reliability(data):
    cases = data["cases"]
    per_case = []
    for trials in cases:
        successes = sum(1 for t in trials if t)
        per_case.append({"k": len(trials),
                         "repeat_success_rate": _ratio(successes, len(trials)),
                         "strict_pass_k": 1 if trials and successes == len(trials) else 0})
        if len(trials) == 0:
            per_case[-1]["strict_pass_k"] = None
    ks = {c["k"] for c in per_case}
    rates = [c["repeat_success_rate"] for c in per_case if c["repeat_success_rate"] is not None]
    strict = [c["strict_pass_k"] for c in per_case if c["strict_pass_k"] is not None]
    return {"k": ks.pop() if len(ks) == 1 else sorted(ks),
            "cases": per_case,
            "mean_repeat_success_rate": _ratio(sum(rates), len(rates)),
            "strict_pass_k_rate": _ratio(sum(strict), len(strict))}


def cmd_calibration(data):
    pairs = [(float(p), float(o)) for p, o in data["pairs"]]
    bins = int(data.get("bins", 10))
    n = len(pairs)
    brier = _ratio(sum((p - o) ** 2 for p, o in pairs), n)
    buckets = [[] for _ in range(bins)]
    for p, o in pairs:
        index = min(bins - 1, int(p * bins))
        buckets[index].append((p, o))
    ece = 0.0
    detail = []
    for index, bucket in enumerate(buckets):
        if not bucket:
            continue
        conf = sum(p for p, _ in bucket) / len(bucket)
        acc = sum(o for _, o in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(conf - acc)
        detail.append({"bin": index, "n": len(bucket),
                       "mean_confidence": conf, "empirical_accuracy": acc})
    return {"n": n, "brier_score": brier, "bins": bins,
            "ece": None if n == 0 else ece, "bin_detail": detail,
            "note": "report ece with brier; ece depends on binning, brier does not"}


def wilson(successes, trials, z=Z95):
    if trials == 0:
        return None
    phat = successes / trials
    denom = 1 + z * z / trials
    center = (phat + z * z / (2 * trials)) / denom
    half = z * math.sqrt(phat * (1 - phat) / trials + z * z / (4 * trials * trials)) / denom
    return {"point": phat, "low": center - half, "high": center + half,
            "confidence": 0.95}


def cmd_aggregate(data):
    scenarios = data.get("scenarios", [])
    per_scenario = [_ratio(sum(cases), len(cases)) for cases in scenarios]
    scored = [s for s in per_scenario if s is not None]
    flat = sorted(score for cases in scenarios for score in cases)
    tail = float(data.get("tail", 0.1))
    take = max(1, int(math.ceil(len(flat) * tail))) if flat else 0
    result = {"per_scenario_mean": per_scenario,
              "macro_across_scenarios": _ratio(sum(scored), len(scored)),
              "micro_across_cases": _ratio(sum(flat), len(flat)),
              "worst_slice_scenario_mean": min(scored) if scored else None,
              "tail_fraction": tail, "tail_cases_used": take,
              "lower_tail_mean_cvar": _ratio(sum(flat[:take]), take) if take else None}
    if "trials" in data:
        result["wilson_95"] = wilson(int(data["successes"]), int(data["trials"]))
    return result


COMMANDS = {"tools": cmd_tools, "fields": cmd_fields, "ndcg": cmd_ndcg, "mrr": cmd_mrr,
            "map": cmd_map, "kendall": cmd_kendall, "trajectory": cmd_trajectory,
            "reliability": cmd_reliability, "calibration": cmd_calibration,
            "aggregate": cmd_aggregate}


def close(a, b, tol=1e-12):
    return abs(a - b) <= tol


def selftest():
    """Pinned expected values, computed by hand from the printed formulas."""
    checks = []

    r = cmd_tools({"tp": 8, "fp": 2, "fn": 2})
    checks.append(("tools precision", close(r["precision"], 0.8)))
    checks.append(("tools recall", close(r["recall"], 0.8)))
    checks.append(("tools f1", close(r["f1"], 0.8)))

    r = cmd_tools({"expected": ["a", "b", "c"], "actual": ["a", "b", "x"]})
    checks.append(("tools multiset", (r["tp"], r["fp"], r["fn"]) == (2, 1, 1)))

    r = cmd_fields({"expected": {"flight": {"date": "2026-01-02"}, "seat": "4A"},
                    "actual": {"flight": {"date": "2026-01-03"}}})
    checks.append(("fields tp", r["tp"] == 0))
    checks.append(("fields wrong vs omitted",
                   (r["wrong_value"], r["omitted_optional"]) == (1, 1)))

    # rel = [3,2,3,0,1,2] at k=6: gains 7,3,7,0,1,3
    # dcg  = 7/1 + 3/log2(3) + 7/2 + 0/log2(5) + 1/log2(6) + 3/log2(7)
    # idcg = ideal order [3,3,2,2,1,0]
    r = cmd_ndcg({"relevance": [3, 2, 3, 0, 1, 2], "k": 6})
    want_dcg = 7 + 3 / math.log2(3) + 7 / 2 + 0 + 1 / math.log2(6) + 3 / math.log2(7)
    want_idcg = 7 + 7 / math.log2(3) + 3 / 2 + 3 / math.log2(5) + 1 / math.log2(6) + 0
    checks.append(("dcg", close(r["dcg_at_k"], want_dcg)))
    checks.append(("idcg", close(r["idcg_at_k"], want_idcg)))
    checks.append(("ndcg", close(r["ndcg_at_k"], want_dcg / want_idcg)))

    r = cmd_ndcg({"relevance": [0, 0, 0]})
    checks.append(("idcg 0 is excluded, not zero",
                   r["ndcg_at_k"] is None and r["excluded"] is True))

    r = cmd_mrr({"first_relevant_ranks": [1, 2, None, 4]})
    checks.append(("mrr", close(r["mrr_over_queries_with_a_relevant_item"],
                                (1 + 0.5 + 0.25) / 3)))
    checks.append(("mrr misses counted", r["queries_with_none"] == 1))

    # [1,0,1]: precision@1 = 1/1, precision@3 = 2/3  -> ap = (1 + 2/3)/2
    r = cmd_map({"queries": [[1, 0, 1], [0, 1, 0]], "k": 3})
    checks.append(("ap", close(r["average_precision_per_query"][0], (1 + 2 / 3) / 2)))
    checks.append(("map", close(r["map_at_k"], ((1 + 2 / 3) / 2 + 0.5) / 2)))

    # actual [a,b,c] vs ideal [b,a,c]: pairs (a,b) discordant, (a,c) and (b,c) concordant
    r = cmd_kendall({"actual": ["a", "b", "c"], "ideal": ["b", "a", "c"]})
    checks.append(("kendall", close(r["kendall_tau"], (2 - 1) / 3)))

    r = cmd_trajectory({"expected": ["a", "b", "c", "d"], "actual": ["a", "c", "d"]})
    checks.append(("lcs", r["lcs_length"] == 3))
    checks.append(("lcs over expected", close(r["lcs_over_expected"], 0.75)))

    r = cmd_reliability({"cases": [[True, True, True], [True, True, False],
                                   [False, False, False]]})
    checks.append(("repeat success", close(r["mean_repeat_success_rate"],
                                           (1 + 2 / 3 + 0) / 3)))
    checks.append(("strict pass^k punishes inconsistency",
                   close(r["strict_pass_k_rate"], 1 / 3)))

    r = cmd_calibration({"pairs": [[1.0, 1], [0.0, 0], [0.5, 1], [0.5, 0]], "bins": 2})
    # brier = (0 + 0 + 0.25 + 0.25)/4
    checks.append(("brier", close(r["brier_score"], 0.125)))
    # bin 0 holds p=0.0: conf 0, acc 0 -> 0. bin 1 holds 1.0,0.5,0.5: conf 2/3, acc 2/3 -> 0
    checks.append(("ece", close(r["ece"], 0.0)))

    r = cmd_aggregate({"scenarios": [[1, 1, 1, 0], [1, 0]], "successes": 4,
                       "trials": 6, "tail": 0.5})
    checks.append(("macro is not micro", close(r["macro_across_scenarios"], 0.625)
                   and close(r["micro_across_cases"], 4 / 6)))
    # flat sorted = [0,0,1,1,1,1]; tail 0.5 of 6 cases = the worst 3 -> (0+0+1)/3
    checks.append(("cvar over the worst half",
                   r["tail_cases_used"] == 3
                   and close(r["lower_tail_mean_cvar"], 1 / 3)))
    w = r["wilson_95"]
    checks.append(("wilson brackets the point",
                   w["low"] < w["point"] < w["high"] and w["low"] > 0))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    print(f"\n{len(checks) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv[1] == "--selftest":
        return selftest()
    command = COMMANDS.get(argv[1])
    if command is None:
        print(f"unknown command: {argv[1]}; try --help", file=sys.stderr)
        return 2
    raw = open(argv[2], encoding="utf-8").read() if len(argv) > 2 else sys.stdin.read()
    try:
        data = json.loads(raw)
    except ValueError as exc:
        print(f"input is not JSON: {exc}", file=sys.stderr)
        return 2
    try:
        result = command(data)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"input does not match the {argv[1]} shape ({exc}); see --help",
              file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
