# Ranking and retrieval: DCG, IDCG, NDCG, MRR, MAP

Use ranking metrics **whenever the agent returns an ordered list** — search results, products,
candidates, sources, tools, actions, or hypotheses. If the order is visible to a user or consumed by a
later step, an unranked accuracy number cannot see the defect: every relevant item can be present and
the list still be useless.

NDCG is the right default with **graded** relevance, because highly relevant items should count more,
and placing them earlier should count more. It traces back to cumulated-gain evaluation in information
retrieval — `references/research-lineage.md` [11].

## The formulas — keep them exactly

| Metric | Formula |
|---|---|
| `gain_i` | `2^(rel_i) - 1` |
| DCG@k | `sum_{i=1..k} gain_i / log2(i + 1)` |
| IDCG@k | DCG@k of the ideal relevance-sorted list |
| NDCG@k | `DCG@k / IDCG@k` |
| MRR | `mean(1 / rank_of_first_relevant_item)` |
| MAP@k | mean of `precision@r` at ranks `r` where a relevant item appears |
| Kendall tau | `(concordant_pairs - discordant_pairs) / all_pairs` |

**NDCG@k reads 1.0 ideal, 0 poor.** Ranks are 1-based: the `log2(i + 1)` discount is why rank 1 is
undiscounted and rank 2 already loses a factor.

**If IDCG is 0, the query is not informative for NDCG and should be excluded or re-labeled.** Never
report it as 0.0 — a `0/0` case scored as zero drags a whole scenario's mean down and points the fix
at the ranker instead of at the missing relevance labels.

**Kendall tau is for ordering fidelity**, useful when actual and ideal lists contain mostly the same
items and you care about the order rather than the membership. It is not a substitute for NDCG when
items are missing from the list.

## Rules for using them

1. **Fix `k` per scenario and record it.** NDCG@5 and NDCG@10 are different metrics; a table mixing
   them without saying so compares nothing.
2. **Leave the ranking column blank when ranking is not part of the task.** A blank is excluded from
   the denominator; a 0 is a failure the agent never had the chance to commit. This is the single most
   common way a composite score gets quietly wrong.
3. **Grade relevance with human raters and keep the grades versioned.** NDCG is only as good as its
   labels, and re-grading changes every historical number.
4. **Report MRR alongside NDCG when the product only needs one good hit.** MRR answers "how deep did
   the user have to read", which NDCG averages away.
5. **Ranking failures are their own class**: relevant items found but poorly ordered points at the
   ranking objective and reranking, not at retrieval —see `references/failure-taxonomy.md`.

The companion workbook carries a **10-rank** graded-relevance calculator for DCG, IDCG and NDCG; the
same arithmetic is in `scripts/metrics.py ndcg`. Retrieval quality itself (context precision/recall)
is a different question and lives in `references/grounding-and-judges.md`.
