# Aggregation: macro scores, hard gates, uncertainty, and comparisons

The workbook uses a **configurable weighted composite for dashboarding, with non-applicable groups
excluded from the denominator.** That composite is **intentionally secondary** to the metric vector
(`references/layers.md`) and to the hard gates (`references/safety.md`). Promote it to a decision and
you have replaced diagnosis with a scalar.

**Excluding non-applicable groups from the denominator is not optional.** Score a non-ranking task's
NDCG as 0 and the composite reports a ranking failure that never happened; leave it blank and the
denominator shrinks to the groups that applied. Blank means excluded, 0 means failed, and the two must
never be typed into the same cell.

## The techniques

| Technique | Use it for | Recommendation |
|---|---|---|
| **Macro average** | Avoid large scenarios dominating the score | Average per case, then per scenario, then across scenarios when scenario sizes differ materially. |
| **Worst-slice score** | Find brittle domains/users/tools | Report the minimum or lower-tail average across meaningful slices. |
| **CVaR / lower-tail mean** | Risk-sensitive quality | Average the worst **5-10%** of case scores; useful for long-tail production reliability. |
| **Wilson interval** | Binary task success | Report **95%** confidence interval, especially for small eval sets. |
| **Bootstrap CI** | Composite/NDCG/judge score | Resample **cases, not individual tool calls**, to preserve within-case dependence. |
| **McNemar test** | Paired binary success of Agent A vs B | Use on the same cases; focuses on discordant pass/fail pairs. |
| **Paired permutation/bootstrap** | Continuous paired metrics | Prefer paired tests because agents run on the same eval cases. |
| **Inter-rater agreement** | Human/judge rubric labels | Cohen kappa for 2 raters; Fleiss/Krippendorff for multiple/partial raters. |

Why each one is not interchangeable:

1. **Micro averaging lets one big scenario win the whole report.** Macro-average per case, then per
   scenario, then across scenarios; a micro mean over 400 easy retrieval cases and 20 hard stateful
   ones is a retrieval score wearing an agent's name.
2. **The mean hides the slice that is broken.** A worst-slice report is how you find the one tool, one
   locale or one customer segment where the agent fails consistently — which is also the segment that
   generates the incident.
3. **CVaR over the worst 5-10%** is the number that predicts production pain, because production pain
   is a tail event, not an average.
4. **A point estimate with no interval invites a launch decision it cannot support.** On a 40-case
   suite, 0.95 and 0.90 are frequently the same result; the Wilson interval says so and the bare
   number does not.
5. **Resampling tool calls instead of cases fakes precision.** Calls within a case are dependent, so
   resampling them shrinks the interval without adding information.
6. **Unpaired tests waste the design.** Agents are run on the *same* cases, so paired tests
   (McNemar for binary, paired permutation/bootstrap for continuous) have the power that an unpaired
   comparison throws away.

## Order of aggregation

1. Gates first (`references/safety.md`). A gate failure ends the decision.
2. Per-case metric vector, then macro per scenario, then across scenarios.
3. Worst-slice and lower-tail alongside the macro — never instead of it.
4. Confidence intervals on everything you intend to compare.
5. The weighted composite **last**, and only to rank candidates that already passed the gates.

## Do not optimize the eval into irrelevance

**Maintain hidden holdouts, rotate adversarial cases, monitor data leakage, and periodically
human-validate whether cases remain solvable and representative.** SWE-bench Verified is a useful
reminder that **benchmark quality itself can bias measured capability** — `references/research-lineage.md`
[12].

A suite that is fully visible to whoever is tuning the agent stops measuring the agent and starts
measuring the tuning. A case that has become unsolvable (a tool changed, a fixture rotted) reports a
permanent failure that no fix can clear, and teams learn to ignore the row — which is how a suite dies.

Thresholds to gate on: `references/thresholds.md`. `scripts/metrics.py aggregate` computes macro,
lower-tail and the Wilson interval.
