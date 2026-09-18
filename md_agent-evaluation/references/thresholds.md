# Illustrative launch thresholds (not universal standards)

**These are example engineering gates**, shown to demonstrate how the metrics are operationalized —
not a standard to cite. **Tune them to consequence severity, baseline performance, task difficulty, and
human fallback availability.** A read-only summarizer and an agent that moves money do not share a
threshold table, and copying this one into both is how a number stops being a decision.

| Metric | Illustrative target | Notes |
|---|---|---|
| Critical policy / unauthorized side effects | **0** critical violations | Treat as a hard gate on high-risk tasks. |
| Prompt-injection resilience | **>= 0.99** on critical attack suite | For lower-risk read-only agents, choose a risk-appropriate threshold. |
| Task success | **>= 0.95** or statistically better than baseline | Always include confidence intervals. |
| Strict pass^5 | **>= 0.90** on core workflows | Higher for deterministic enterprise automation. |
| Tool F1 / Argument F1 | **>= 0.95** | Investigate even small drops on write tools. |
| Faithfulness | **>= 0.95** for evidence-backed answers | Use claim-level support auditing. |
| NDCG@10 | **>= 0.85** when ranking is user-visible | Tune relevance grades with human raters. |
| P95 latency / successful task | within product SLO | Use successful-task latency, not all-run latency alone. |
| Cost / successful task | within product budget | Track by scenario and model/tool mix. |
| Brier / ECE | improves vs baseline | Use for escalation/abstention if confidence drives decisions. |

## Reading the table without misusing it

1. **The first two rows are gates; the rest are objectives.** A gate is boolean and evaluated before
   aggregation; an objective is compared against a baseline. Mixing them lets a latency win pay for a
   policy violation (`references/safety.md`).
2. **"Statistically better than baseline" is a real requirement, not a hedge.** A 0.95 point estimate
   on 40 cases does not clear a 0.93 baseline — report the interval and the paired test
   (`references/aggregation.md`).
3. **Investigate even small drops on write tools.** A 0.01 drop in argument F1 spread across read tools
   is noise; the same drop concentrated on a tool that mutates state is a pending incident. Slice the
   F1 by tool before you decide which one you have.
4. **`pass^5` at 0.90 is stricter than task success at 0.95** — deliberately. Repeated-run consistency is
   the property that survives contact with production traffic; see `references/reliability.md`.
5. **Two of the rows have no number on purpose** — latency and cost are "within product SLO/budget",
   because the right value is a product decision and a fabricated number here would be copied as if it
   were measured. Fill them from the SLO, and record where the value came from.
6. **NDCG@10 applies only when ranking is user-visible.** If the order is invisible, the row does not
   apply and its cell stays blank rather than zero — a scored-zero non-applicable metric drags the
   composite down for a capability the product never exposed.

## When a threshold is missed

Do not renegotiate the threshold in the same session that missed it. Report:

- the metric, the measured value **with its interval**, and the target;
- the failure classes behind it from `references/failure-taxonomy.md`;
- whether a hard gate also failed — if so, the launch decision is already made;
- what would have to change for the number to move, from the fix column.

Then decide. A threshold edited to match the result is a threshold that has stopped measuring
anything, and the next reader will not know it moved.
