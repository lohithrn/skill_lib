# Stateful, long-horizon, and repeated-run reliability

An agent is a stochastic system talking to a mutable world. **A single passing run is not evidence.**
tau-bench evaluates realistic tool-agent-user interactions by checking the **final database state**
against an annotated goal state, and proposes `pass^k` to measure repeated-trial reliability.
ToolSandbox adds state dependencies and dynamic intermediate/final milestone checks. Both are strong
models for production agents because **the trace is only a means to an environment change**.
Lineage: `references/research-lineage.md` [2][3].

## The formulas — keep them exactly

| Metric | Formula | Reading |
|---|---|---|
| Repeat success rate | `successful_trials / k` | The average run. |
| Strict pass^k (per case) | `1` if all `k` repeated runs pass, otherwise `0` | The reliable run. Aggregate this indicator across test cases. |
| Tool-call redundancy rate | `redundant_tool_calls / total_tool_calls` | Loops and over-tooling. |
| Recovery steps | number of extra actions from injected fault to first correct recovered trajectory | Long-horizon brittleness. |

**Strict pass^k intentionally penalizes inconsistent behavior much more than one-shot success does.**
That asymmetry is the point: an agent that passes 4 of 5 runs on a payment workflow is not a
95%-successful agent, it is an agent that will corrupt one order in five. Report both numbers —
repeat success rate for the trend, `pass^k` for the launch decision.

**Never keep only the aggregate.** Keep every raw trace and final state for every trial. Without the
traces you can see that reliability dropped and never see which tool caused it, and the run cannot be
re-scored when a canonicalizer or a relevance grade changes.

## The stress matrix

Run each row deliberately. A suite that only replays the happy path measures the happy path.

| Stress dimension | Perturbation | Score |
|---|---|---|
| **Stochasticity** | Same case, same fixture, multiple seeds/runs | Repeat success; strict pass^k; variance. |
| **Tool faults** | Timeouts, malformed responses, transient 5xx, partial acknowledgements | Recovery success; duplicate-side-effect safety; recovery steps. |
| **Benign prompt changes** | Paraphrase, formatting changes, reordered irrelevant context | Robustness score and worst-slice score. |
| **Goal shift** | User changes destination/date/intent mid-dialogue | Goal-shift recovery time and obsolete-action rate. |
| **State dependency** | Later tools depend on earlier state creation or lookup | Milestone completion and final-state predicates. |

What each row is really testing:

1. **Stochasticity** exposes the lucky run. Without it, every other number in the report is a sample
   of size one and its confidence interval is undefined.
2. **Tool faults** expose the difference between a retry and a **duplicate mutation**. An agent that
   recovers by re-sending a booking has not recovered; it has double-booked. Score
   duplicate-side-effect safety separately from recovery success, or the two cancel out.
3. **Benign prompt changes** expose a suite that is measuring surface form. If a paraphrase moves the
   score, the number was never about capability.
4. **Goal shift** exposes plan invalidation: an agent that keeps executing the old plan after the
   user changes intent looks successful on the first goal and is wrong on the delivered one.
   Goal-shift robustness has its own benchmark lineage — [13].
5. **State dependency** is what makes an eval *stateful*. Ordering violations (a write before the
   lookup that justifies it) are invisible to any metric that reads only the final answer.

## Repeated runs and the rest of the report

- Fix `k` per scenario and state it in the report: `pass^5` and `pass^3` are not comparable.
- Run each stochastic case multiple times **before** computing any composite, or the composite is a
  weighted average of single samples.
- Reliability feeds two aggregation choices — worst-slice and lower-tail (CVaR) scoring — in
  `references/aggregation.md`. The illustrative `pass^5` gate is in `references/thresholds.md`.
- `scripts/metrics.py reliability` computes repeat success and strict `pass^k` from a trial list.
