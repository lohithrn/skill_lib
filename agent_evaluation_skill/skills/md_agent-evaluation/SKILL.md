---
name: md_agent-evaluation
description: Evaluate a production AI agent the way its failures actually happen — score the outcome, the trajectory and the risk surface separately across eight layers (outcome, tool use, arguments, trajectory, ranking/RAG, reliability, safety/security, efficiency/calibration), treat every case as an executable specification with goal-state predicates instead of one golden trajectory, gate critical safety failures before any composite, and report macro/worst-slice/interval numbers instead of a single aggregate. Carries the formulas (tool F1, JSON-field F1, NDCG@k, MRR, MAP@k, strict pass^k, faithfulness, Brier, ECE, Wilson, CVaR), the failure taxonomy, and illustrative launch gates. Advises and measures; never edits a tree.
when_to_use: When designing, auditing or running an evaluation of a tool-using or stateful AI agent — choosing metrics, writing eval cases, computing a score, or deciding whether an agent may launch.
allowed-tools: Read, Grep, Glob, Bash(python3:*)
---

# Agent evaluation

A router. It resolves one conflict — **which question about measurement is being asked?** — and sends
you to the one file that answers it. No formulas live here: they are in `references/`, the running
order is in `jobs/`, the case and workbook contracts are in `specs/`.

## The gate — read this first

**This skill advises and measures. It does not modify a tree.**

- No `Edit` and no `Write` tool is granted at all. Nothing in this skill has a path that writes source,
  a test, a fixture, or an agent's prompt. Every output is a number, a finding, or a recommendation the
  user applies.
- **Never run the system under test from here.** Running an agent means executing its tools against a
  real environment; this skill reads traces and final states that a harness already produced.
- The only code it executes is its own offline calculator, `scripts/metrics.py`, on JSON you hand it.
- **Never invent a number.** A metric no trace supports is reported as **unmeasured**, named in a
  `degraded` list — never zeroed, never estimated. A zero is a claim that the agent failed; an omission
  is a claim that you did not look. They are different findings.

## The core principle

> **Score the outcome, the trajectory, and the risk surface separately.**

A fluent final answer can hide a wrong tool call, a bad JSON argument, a wrong database mutation, a
brittle retry loop, or a security failure. **One aggregate number is useful for dashboards, but it is
not sufficient for diagnosis or launch decisions.** Report a metric vector.

## The eight layers

| Layer | Primary metrics | What it catches |
|---|---|---|
| **Outcome** | Task success; end-state goal match; milestone completion | Did the user-visible job actually get done? |
| **Tool use** | Tool precision/recall/F1; relevance/no-call accuracy; execution success | Wrong, missing, hallucinated, or non-executable calls. |
| **Arguments** | JSON exact match; field precision/recall/F1; schema-valid rate | Correct tool with wrong parameters, dates, IDs, filters, or constraints. |
| **Trajectory** | LCS/edit similarity; redundant calls; retries; recovery steps | Wrong order, loops, over-tooling, brittle long-horizon behavior. |
| **Ranking/RAG** | NDCG@k; MRR; MAP@k; context precision/recall; faithfulness | Bad search ordering, missed evidence, unsupported claims. |
| **Reliability** | Repeat success; strict pass^k; perturbation robustness; lower-tail score | Stochastic systems that look good on a lucky single run. |
| **Safety/security** | Policy compliance; unwanted side effects; prompt-injection resilience; attack success rate | Successful-but-unsafe behavior and compromised tool boundaries. |
| **Efficiency/calibration** | Latency; cost; redundancy; Brier score; ECE | Expensive, slow, overconfident agents. |

Every metric named there is load-bearing: drop one and you keep the bug in the third column, you just
stop being able to see it. Full version, plus the order to compute them in:
`references/layers.md`.

## Route

| The question | Read |
|---|---|
| Which metrics do I need at all? | `references/layers.md` |
| What is a case, and what goes in the first four columns? | `specs/case-schema.md` |
| How do I score tool calls, arguments, state, redundancy? | `references/tool-and-argument-metrics.md` |
| How do I score an ordered list? | `references/ranking-metrics.md` |
| How do I score repeated runs, faults, goal shift? | `references/reliability.md` |
| How do I score citations, and can an LLM judge? | `references/grounding-and-judges.md` |
| How do I score safety, injection, side effects? | `references/safety.md` |
| How do I score cost, latency, confidence? | `references/efficiency-and-calibration.md` |
| How do I combine and compare the numbers? | `references/aggregation.md` |
| What number is good enough to launch? | `references/thresholds.md` |
| A number is red — what do I fix? | `references/failure-taxonomy.md` |
| How do I run a whole pass, in order? | `jobs/run-eval-pass.md` |
| Where do the rows and sheets live? | `specs/workbook.md` |
| Which paper is this from? | `references/research-lineage.md` |

Read the one row you need. Do not inline a reference file wholesale into the conversation.

## The unit of evaluation

**An agent eval case is an executable specification, not a prompt/answer pair.** The minimum unit:

```
user prompt + available tools + policies + initial environment state
+ expected goal predicates + optional acceptable trajectory constraints
+ observed trace + final state
```

A case with no initial and final state cannot detect a wrong database mutation at all — it is scoring
prose about the world instead of the world. Full contract: `specs/case-schema.md`.

**The trap, named explicitly: do not over-specify a single golden trajectory when several tool
sequences are valid.** Prefer **goal-state predicates plus required/forbidden calls**, and use
sequence similarity as a **diagnostic, never as the only definition of correctness**. A golden
trajectory fails every correct agent that took a different valid route, so the suite reports
regressions that are not regressions, the team learns to distrust it, and the one real regression
arrives inside that noise.

## Non-negotiables

1. **Three surfaces, three scores.** Outcome, trajectory, risk. Reporting one number for all three is
   the failure this skill exists to prevent: it cannot say which layer broke, so nothing can be fixed.
2. **Gates before aggregation.** A critical policy violation, a leak of protected data, an executed
   injected instruction, or an unauthorized mutation is a **gate failure even if the weighted score is
   high**. Without the gate, 1000 easy cases outvote the one that mutated the wrong row
   (`references/safety.md`).
3. **`k` runs, not one.** Report repeat success **and** strict pass^k, with `k` stated. A single
   passing run of a stochastic system is not evidence, and `pass^k` is what penalizes inconsistency
   (`references/reliability.md`).
4. **Predicates before traces.** Annotate goal-state and critical policy predicates first; add
   expected calls and parameters only where they are truly required. Predicates written after the
   traces get written to match the traces.
5. **Canonicalizers before argument metrics.** Time zones, enums, sets, optional-vs-wrong fields,
   generated IDs. A canonicalizer added later changes every historical number
   (`references/tool-and-argument-metrics.md`).
6. **Deterministic metrics first, judges last.** State, tool, schema, execution and ranking are
   arithmetic; a judge is a model that needs validating. Judging first spends money grading answers
   whose tool calls were already wrong (`references/grounding-and-judges.md`).
7. **Blank is not zero.** A non-applicable group is excluded from the composite denominator. Scoring
   NDCG 0 on a task with no ranking reports a failure the agent never had the chance to commit
   (`references/aggregation.md`).
8. **Efficiency is conditioned on success.** Cost, tokens and latency are **per successful task**. A
   fast failed run is not useful, and mean-over-all-runs rewards an agent that gives up early
   (`references/efficiency-and-calibration.md`).
9. **Every point estimate carries an interval.** Wilson for binary success, bootstrap over **cases,
   not tool calls**, paired tests for A-vs-B. Without them, 0.95 and 0.90 on a 40-case suite are
   frequently the same result and the launch decision does not know it.
10. **Keep every raw trace and final state.** Never retain only the aggregate. A metric with no trace
    cannot be triaged into a failure class, and a run with no trace cannot be re-scored when a
    canonicalizer or a relevance grade changes.
11. **Triage, don't crown.** **An eval is successful when it identifies what to fix, not merely which
    model won.** Every failed case gets one row of `references/failure-taxonomy.md`.
12. **Do not optimize the eval into irrelevance.** Hidden holdouts, rotated adversarial cases, leakage
    monitoring, periodic human validation that cases are still solvable and representative. A suite
    fully visible to whoever is tuning the agent measures the tuning.
13. **Say which metrics are derived diagnostics.** JSON-field F1, LCS trajectory score, citation F1,
    retry efficiency and lower-tail aggregation are engineering diagnostics, not standardized
    benchmark metrics. Presenting one as standardized invites a comparison against published numbers
    that were never computed the same way (`references/research-lineage.md`).

## Scripts

`scripts/metrics.py` — offline, standard-library-only, JSON in and JSON out, no network, no writes.
It implements exactly the formulas printed in the reference files.

| Command | Computes |
|---|---|
| `tools`, `fields` | tool precision/recall/F1; JSON-path field F1, exact match, omitted-vs-wrong |
| `ndcg`, `mrr`, `map`, `kendall` | DCG/IDCG/NDCG@k, MRR, MAP@k, Kendall tau |
| `trajectory` | LCS length and both normalizations, unlabelled by design |
| `reliability` | repeat success rate, strict pass^k |
| `calibration` | Brier score, ECE with its bin count |
| `aggregate` | macro, micro, worst slice, lower-tail CVaR, Wilson 95% interval |

Run `python3 scripts/metrics.py --help` for every input shape, and `python3 scripts/metrics.py --selftest`
before trusting a number — **24 pinned checks** against hand-computed values. An unmeasurable metric
comes back `null` with a note, never `0`.

## What this does NOT do

1. **It does not report one aggregate score as a launch decision.** The composite is for ranking
   candidates that already cleared the gates. Asked for "the number", it returns the gate verdict, the
   metric vector, and the worst slice, and says why the scalar was refused.
2. **It does not treat a single lucky run as a pass.** No `k`, no reliability claim; one run is
   reported as one sample with no interval, and any pass/fail language is withheld.
3. **It does not score a fluent answer without checking the tool calls and the final state.** An
   answer-only grade is refused with the reason: it cannot see a wrong mutation, a bad argument, or an
   executed injection.
4. **It does not write, patch, or tune the agent under test** — no prompt edits, no fixture edits, no
   suite edits. It says what to change and where.
5. **It does not renegotiate a threshold in the session that missed it.** A target edited to match the
   result has stopped measuring anything (`references/thresholds.md`).
6. **It does not average away a P0/P1 violation.** Critical violations are counted, never meaned.
7. **It does not parse or regenerate a binary workbook.** The column-and-sheet contract in
   `specs/workbook.md` is the portable part; rebuild it anywhere.
8. **It does not fabricate relevance grades, policy predicates, or a product SLO.** Where the source
   gives no number — latency and cost targets — it says "from the SLO" and asks.

## Checklist before saying done

- [ ] Gates computed and printed **above** the composite, with a critical-violation count
- [ ] `k` stated, repeat success **and** strict pass^k reported
- [ ] Every applicable layer has a number; non-applicable groups are blank, not zero
- [ ] Cost and latency are per successful task, P95 not mean
- [ ] Every compared number carries an interval, and A-vs-B used paired cases
- [ ] Every failed case has one failure class and a fix area
- [ ] Unmeasured metrics are named as unmeasured, never zeroed
- [ ] Derived diagnostics are labelled as derived
- [ ] Raw traces and final states retained for every trial
- [ ] Nothing in the system under test was edited, and the report says so
