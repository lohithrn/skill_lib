# Job: run one evaluation pass

The recommended protocol, in order. **The order is the job** — steps 3, 4 and 5 are each cheap before
the step above them and expensive after, and inverting 5 and 6 buys judge tokens for answers whose tool
calls were already wrong.

This job writes nothing into the system under test. It produces numbers, a triage list, and one verdict.

## 1. Define the scenario slices

Slice before you write a case, because the slice decides which layers apply:

**tool-only · stateful workflows · retrieval/ranking · long-horizon · memory ·
adversarial/security · product-specific high-risk actions.**

A suite with no adversarial slice reports zero injection failures forever
(`references/safety.md`); a suite with no long-horizon slice reports recovery metrics it never
measured. Multi-environment and long-horizon slice design has published precedent —
`references/research-lineage.md` [4][5].

## 2. Annotate the predicates first

**Annotate goal-state predicates and critical policy predicates first. Add expected
calls/parameters only where they are truly required.**

Predicates written after the traces are read get written to match the traces, and the suite then
certifies whatever the agent did. Expected calls added "for completeness" become a golden trajectory —
the trap in `specs/case-schema.md`.

## 3. Build the canonicalizers

**Create canonicalizers for JSON values, dates, IDs, sets, and generated references before computing
argument metrics.** All six rules in `references/tool-and-argument-metrics.md` apply here.

Introduced later, a canonicalizer changes every historical number and destroys the baseline you were
about to compare against.

## 4. Run each stochastic case multiple times

**Run each stochastic case multiple times. Keep every raw trace and final state; never retain only the
aggregate.** Fix `k` per scenario and record it. Add the stress rows from `references/reliability.md`:
seeds, tool faults, benign paraphrase, goal shift, state dependency.

Discard the traces and you keep a number nobody can triage or re-score.

## 5. Compute the deterministic metrics

**Compute deterministic metrics first: state, tool, schema, execution, ranking.**

| Metrics | Formulas | Calculator |
|---|---|---|
| End-state, tool, argument, execution, redundancy | `references/tool-and-argument-metrics.md` | `scripts/metrics.py tools`, `scripts/metrics.py fields` |
| NDCG@k, MRR, MAP@k, Kendall tau | `references/ranking-metrics.md` | `scripts/metrics.py ndcg`, `scripts/metrics.py mrr`, `scripts/metrics.py map` |
| Repeat success, strict pass^k | `references/reliability.md` | `scripts/metrics.py reliability` |
| Brier, ECE | `references/efficiency-and-calibration.md` | `scripts/metrics.py calibration` |
| Macro, lower-tail, Wilson | `references/aggregation.md` | `scripts/metrics.py aggregate` |

Run `python3 scripts/metrics.py --help` for the input shapes, and `python3 scripts/metrics.py --selftest`
to confirm the arithmetic on the pinned examples before you trust a number it prints.
Every metric it cannot compute is **omitted and named as unmeasured — never zeroed**.

## 6. Then judge the open-ended quality

Apply model or human judges only to what deterministic checks cannot reach, under every rule in
`references/grounding-and-judges.md` — anchored rubrics, order swapping, blinding, repeated judgments.

## 7. Validate the judge

**Validate the automated judge on a human-audited stratified sample and measure judge
agreement/bias.** Report the agreement coefficient (Cohen kappa for 2 raters, Fleiss/Krippendorff for
more). An unvalidated judge's score is an unbounded error term inside every aggregate that contains it.

## 8. Report the full shape

**Report per-case, per-scenario, macro, worst-slice, and confidence intervals. Compare candidate
agents on paired cases.** Techniques and their reasons: `references/aggregation.md`.

## 9. Gate, then rank

**Gate critical safety/security failures. Use the weighted composite only for ranking otherwise
acceptable candidates.** Print the gate verdict above the composite. Illustrative targets:
`references/thresholds.md`.

## 10. Triage, do not celebrate

**Inspect the error taxonomy and trace clusters. An eval is successful when it identifies what to fix,
not merely which model won.** Classify every failure into one row of
`references/failure-taxonomy.md` and cluster the traces.

## 11. Refresh the suite

**Refresh the suite as tools, policies, product behavior, and attack strategies change.** Keep hidden
holdouts, rotate adversarial cases, monitor leakage, and re-validate that cases are still solvable and
representative (`references/aggregation.md`).

---

## The verdict, in ≤25 lines

End every pass with:

1. **Gates** — passed or failed, and the count of critical violations. This line comes first.
2. **Task success** with its interval, and `pass^k` with `k` stated.
3. **The metric vector** — one number per applicable layer of `references/layers.md`, blanks for
   non-applicable groups.
4. **Worst slice**, named, with its score.
5. **The top three failure classes** by case count, each with its fix area.
6. **What was not measured**, and why — degraded, not zeroed.
7. **One next action.**

Never report a single aggregate score as the verdict. It cannot carry items 1, 3, 4 or 6, which are the
four that decide anything.
