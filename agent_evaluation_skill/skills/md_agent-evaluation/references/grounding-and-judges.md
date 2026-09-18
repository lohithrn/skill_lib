# Grounding, citations, and LLM-as-a-judge

Two separate questions live here, and merging them is the classic RAG evaluation mistake:

1. **Did retrieval bring the right evidence?** — context precision / context recall.
2. **Do the generated claims follow from that evidence?** — faithfulness.

RAGAS popularized exactly that split: context precision/recall diagnose **retrieval**, faithfulness
diagnoses **generation**. Lineage: `references/research-lineage.md` [8]. With one blended
"answer quality" score you cannot tell a retriever bug from a hallucination, and the two fixes are in
different systems.

## The formulas — keep them exactly

| Metric | Formula |
|---|---|
| Faithfulness | `supported answer claims / total answer claims` |
| Citation precision | `supported cited claims / cited claims` |
| Citation recall | `citation-worthy claims with supporting citation / citation-worthy claims` |

**Claim-level, not answer-level.** The denominators are claims, so an answer with nine supported
sentences and one invented number scores 0.9 and not "pass". Answer-level grading rounds that
invented number away, which is the failure a grounding metric exists to catch.

**Citation precision and recall move in opposite directions under pressure.** An agent that cites
everything scores high recall and low precision; one that cites nothing scores the reverse. Report both
or neither.

## Judging open-ended quality

An LLM judge scales evaluation, and it brings documented biases with it. MT-Bench documents
**position, verbosity, self-enhancement, and reasoning** biases — [9]. **Treat the judge as another
model that needs validation**, on the same footing as the system under test.

1. **Use explicit rubrics with anchored examples, not a vague "rate quality" prompt.** An unanchored
   rubric drifts between runs, so the judge's own scale becomes an uncontrolled variable and score
   movement stops meaning anything.
2. **Randomize A/B order and run order-swapped judgments for pairwise comparisons.** Position bias
   otherwise awards the win to a slot rather than to a system.
3. **Blind the judge to model identity and remove irrelevant verbosity when possible.** Unblinded,
   self-enhancement bias inflates one candidate; verbose, verbosity bias inflates the longer answer.
4. **Use multiple judges or repeated judgments for high-impact decisions.** One judgment on a launch
   decision is a sample of size one from a biased estimator.
5. **Human-audit a stratified sample and report human-judge agreement before scaling automated
   judging.** Without a measured agreement number you do not know whether the judge is grading the
   task or its own preferences — and every downstream number inherits that error silently.
6. **Keep factual/grounding checks separate from stylistic preference.** A judge asked for both
   returns one number in which a well-written wrong answer beats an ugly right one.

Report inter-rater agreement with the right coefficient: **Cohen kappa for 2 raters,
Fleiss/Krippendorff for multiple or partial raters** — see `references/aggregation.md`.

## Order of operations

Compute the deterministic layers first — state, tool, schema, execution, ranking
(`references/tool-and-argument-metrics.md`, `references/ranking-metrics.md`) — **then** apply model or
human judges to open-ended quality. A judge run first grades answers whose tool calls were already
wrong, and its prose verdict then hides the defect that actually broke the task. The full running
order is `jobs/run-eval-pass.md`.
