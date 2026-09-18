# Efficiency, cost, and confidence calibration

HELM argues for **multi-metric** evaluation rather than accuracy-only reporting — including
robustness, calibration, and efficiency. Lineage: `references/research-lineage.md` [7].

For agents there is one rule that reorders all of it: **efficiency must be conditioned on success. A
fast failed run is not useful.** Report cost and latency per *successful* task, or a broken agent that
gives up early wins the efficiency column.

## The formulas — keep them exactly

| Metric | Formula | Reading |
|---|---|---|
| Cost per successful task | `total model + tool cost / successful tasks` | Tool cost is in the numerator; a cheap model that calls an expensive API is not cheap. |
| Tokens per successful task | `total tokens / successful tasks` | Model-agnostic proxy; track with cost, not instead of it. |
| Retry efficiency | `1 / (1 + retries)` | A convenience diagnostic. |
| Brier score | `mean((p_success - outcome)^2)` | **Lower is better.** A proper scoring rule for probabilistic confidence. |
| ECE | `sum_b (n_b / N) * abs(mean_confidence_b - empirical_accuracy_b)` | Bin-level miscalibration. |

**Always read retry efficiency with recovery success**, because a necessary successful retry can be
correct behavior. Optimized alone, retry efficiency rewards an agent that gives up instead of one that
recovers — see the tool-fault row in `references/reliability.md`.

**Report ECE with Brier; ECE depends on binning.** Change the bin count and ECE moves without the model
changing at all, so an ECE reported alone can be tuned. Brier has no binning parameter, which is why it
is the one that anchors the pair.

**Calibration only matters if confidence drives a decision.** If a confidence number routes to
escalation, abstention, or a human, then a calibration failure — high confidence on failed tasks — is
an outage in the routing layer, not a cosmetic score. If nothing reads the confidence, say so and stop
computing it.

## Latency

- Report **P95 latency per successful task**, not mean latency over all runs. Mean over all runs is
  dominated by fast failures, and a mean hides the tail the user actually feels.
- Track by scenario and by model/tool mix. One aggregate latency over mixed scenarios is an average of
  different products.

## Do not collapse quality, latency and cost into one number

**Use a Pareto frontier.** An agent is Pareto-dominated if another agent is at least as good on
quality and no worse on both cost and latency.

Forcing the three into a single weighted number picks the trade-off *for* the reader, using weights
nobody in the room agreed to, and hides that two candidates are simply different products. Publish the
frontier and let the launch decision choose a point on it.

Aggregation techniques for the numbers on each axis — macro averaging, worst-slice, lower-tail,
confidence intervals — are in `references/aggregation.md`. Illustrative latency and cost gates ("within
product SLO", "within product budget") are in `references/thresholds.md`.
`scripts/metrics.py calibration` computes Brier and ECE.
