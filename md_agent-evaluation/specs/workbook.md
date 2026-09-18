# Output contract: the evaluation workbook

The playbook has a companion spreadsheet, `eval.xlsx`. **The workbook is the execution template; this
skill is the explanation** — what to measure, why, how to compute it, and how to avoid the traps.

**The binary workbook is not shipped with this skill.** What matters and what is reproducible is the
column-and-sheet contract below: rebuild it in any spreadsheet, a CSV, or a table in your tracker, and
the numbers behave the same. Do not parse or regenerate a binary you cannot diff in review.

## The six sheets

| Sheet | Purpose |
|---|---|
| **Eval** | Main **100-row** evaluation harness. First four columns are Prompt, expected assert/function calls, expected JSON parameters, and NDCG@k. Raw inputs and computed metric groups live on the same row. |
| **Run_Summary** | Dashboard: task success, composite score, tool/argument quality, NDCG, grounding, policy, reliability, cost, latency, redundancy, scenario breakdown, and group chart. |
| **Metric_Catalog** | **48** metric definitions, formulas, inputs, failure signatures, and research lineage. |
| **Ranking_Calc** | **10-rank** graded-relevance calculator for DCG, IDCG, and NDCG. |
| **Config** | Weights, ranking cutoff, cost/latency targets, and safety hard-gate thresholds. |
| **Sources** | Research references used to design the template. |

## Row layout

One row per case per run. Left to right:

1. **The four contract columns** — `specs/case-schema.md`. Column 4 blank when ranking does not apply.
2. **Raw trace-derived inputs** — TP/FP/FN counts for calls and for argument fields, attempted and
   successful executions, satisfied and applicable goal predicates, mutation opportunities and
   unexpected mutations, total and redundant calls, retries, recovery steps, claim counts, trial
   outcomes, tokens, cost, latency.
3. **Computed metric groups**, one block per layer of `references/layers.md`.
4. **Gate columns** — critical violations, injection outcome, unauthorized mutation. Booleans, computed
   before any composite (`references/safety.md`).
5. **Trace URL** — a pointer to the raw run, kept for every row.

**Raw counts to the left of computed metrics, always.** A workbook that stores only the computed metric
cannot be re-scored when a canonicalizer or a relevance grade changes, and every historical number
becomes uncomparable the first time you fix a scorer.

**Keep the trace pointer on the row.** A metric with no trace behind it cannot be triaged into a
failure class, so `references/failure-taxonomy.md` cannot be applied and the number stays a number.

## Suggested workflow

1. **Duplicate or overwrite the five EXAMPLE rows.** They are there to show the shape; leaving them in
   a real run contaminates every aggregate with fixture data.
2. **Ingest your trace-derived counts and scores** — not hand-typed impressions of them.
3. **Keep Trace URL pointing to the raw run.**
4. **Change Config weights only after you have decided which metrics are launch gates versus
   optimization objectives.** Weights tuned before that decision encode the tuner's preference and then
   outvote the gates; the gate/objective split is in `references/thresholds.md`.

## Non-applicable is blank, never zero

This is the one workbook rule that silently corrupts a dashboard: **a non-applicable group is excluded
from the composite denominator, so its cells are blank.** A 0 in a non-applicable cell reports a failure
the agent never had the opportunity to commit, and the composite then punishes scenarios for
capabilities the product does not expose (`references/aggregation.md`).

The arithmetic for every computed column is in `scripts/metrics.py`; the formulas it implements are the
ones in `references/tool-and-argument-metrics.md`, `references/ranking-metrics.md`,
`references/reliability.md`, `references/efficiency-and-calibration.md` and `references/aggregation.md`.
