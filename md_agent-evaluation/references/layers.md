# The eight metric layers

The whole framework rests on one claim: **score the outcome, the trajectory, and the risk surface
separately.** A fluent final answer can hide a wrong tool call, a bad JSON argument, a wrong database
mutation, a brittle retry loop, or a security failure. One aggregate number is useful for dashboards,
but it is not sufficient for diagnosis or launch decisions.

Report a **metric vector**, not a scalar. A single number cannot tell you which of the eight layers
below failed, and a launch decision made on it is a decision made without knowing what will break.

## The layers

| Layer | Primary metrics | What it catches |
|---|---|---|
| **Outcome** | Task success; end-state goal match; milestone completion | Did the user-visible job actually get done? |
| **Tool use** | Tool precision/recall/F1; relevance/no-call accuracy; execution success | Wrong, missing, hallucinated, or non-executable calls. |
| **Arguments** | JSON exact match; field precision/recall/F1; schema-valid rate | Correct tool with wrong parameters, dates, IDs, filters, or constraints. |
| **Trajectory** | LCS/edit similarity; redundant calls; retries; recovery steps | Wrong order, loops, over-tooling, and brittle long-horizon behavior. |
| **Ranking/RAG** | NDCG@k; MRR; MAP@k; context precision/recall; faithfulness | Bad search ordering, missed evidence, and unsupported claims. |
| **Reliability** | Repeat success; strict pass^k; perturbation robustness; lower-tail score | Stochastic systems that look good on a lucky single run. |
| **Safety/security** | Policy compliance; unwanted side effects; prompt-injection resilience; attack success rate | Successful-but-unsafe behavior and compromised tool boundaries. |
| **Efficiency/calibration** | Latency; cost; redundancy; Brier score; ECE | Expensive, slow, overconfident agents. |

Every metric named in that table is load-bearing. Dropping one drops the failure class in the third
column — you do not stop having the bug, you stop being able to see it.

## Where each layer is specified

| Layer | Formulas and rules live in |
|---|---|
| Outcome, Tool use, Arguments | `references/tool-and-argument-metrics.md` |
| Trajectory | `references/tool-and-argument-metrics.md` (redundancy, recovery) and `references/reliability.md` (stress) |
| Ranking | `references/ranking-metrics.md` |
| RAG grounding, judges | `references/grounding-and-judges.md` |
| Reliability | `references/reliability.md` |
| Safety/security | `references/safety.md` |
| Efficiency/calibration | `references/efficiency-and-calibration.md` |
| Combining any of them | `references/aggregation.md`, then `references/thresholds.md` |

## Layer ordering is not cosmetic

Compute the layers in this order, and never invert it:

1. **Deterministic layers first** — end state, tool selection, schema validity, execution success,
   ranking. These are arithmetic over structured data: they are cheap, reproducible, and they
   localize the failure to a line in a trace.
2. **Model or human judges last**, and only for open-ended quality. A judge run before the
   deterministic layers spends money grading answers whose tool calls were already wrong, and its
   verdict then hides the real defect behind a prose score.

**Trajectory is a diagnostic layer, never the definition of correctness.** See
`references/failure-taxonomy.md` for the mapping from a layer's failure signature to the engineering
fix, and `specs/case-schema.md` for the trap that ranks first among evaluation mistakes:
over-specifying one golden trajectory.
