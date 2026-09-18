# Output contract: the evaluation case

## The unit of evaluation

**An agent eval case is an executable specification, not a prompt/answer pair.** The minimum unit is:

```
user prompt
+ available tools
+ policies
+ initial environment state
+ expected goal predicates
+ optional acceptable trajectory constraints
+ observed trace
+ final state
```

All eight parts, or the case cannot be scored:

| Part | Without it |
|---|---|
| user prompt | nothing to run |
| available tools | tool precision is undefined — you cannot call a call "hallucinated" without knowing what was offered |
| policies | there is no policy-compliance denominator, so `references/safety.md` has nothing to gate on |
| initial environment state | the run is not reproducible and the final state means nothing |
| expected goal predicates | "success" becomes a human's impression of the answer |
| trajectory constraints (optional) | you lose required/forbidden-call checking — but see the trap below |
| observed trace | no tool, argument or trajectory metric can be computed |
| final state | you are scoring prose instead of the world the agent changed |

A case missing the initial and final state is a **prompt/answer pair wearing an agent-eval label**, and
it cannot detect a wrong database mutation at all. Environment-plus-end-state design is the pattern from
tau-bench, ToolSandbox and WebArena — `references/research-lineage.md` [2][3][6].

## The trap: do not over-specify a single golden trajectory

**Do not over-specify a single golden trajectory when several tool sequences are valid.** Prefer
**goal-state predicates and required/forbidden calls.** Use sequence similarity as a **diagnostic, not
as the only definition of correctness.**

Why this is the trap that ruins suites: a golden trajectory fails every correct agent that took a
different valid route, so the suite reports regressions that are not regressions, the team learns to
distrust it, and the one true regression arrives inside that noise. It also freezes the tool design —
any refactor of the tool surface rewrites hundreds of expected traces.

The order to reach for:

1. **Goal-state predicates** — what must be true of the world afterwards. Primary, always.
2. **Required calls** — the calls whose *absence* is a defect regardless of the end state (an audit
   log write, a permission check).
3. **Forbidden calls** — the calls whose presence is a defect regardless of the end state (a delete, a
   send, a payment).
4. **Order constraints only where order is semantically required** — a lookup before a write, not
   step 3 before step 4 because that is how the reference run happened to go.
5. **Sequence similarity** — reported, never gating.

## The workbook's first four columns

The first four columns of the companion workbook are fixed by contract; anything else you add goes to
their right.

| Column | Meaning | Recommended representation |
|---|---|---|
| **1. Prompt** | The user task or test instruction. | Verbatim prompt plus hidden fixture metadata elsewhere if needed. |
| **2. Expected / Assert Function Calls** | Calls that should happen, in order when order is semantically required. | Names separated by arrows, or a machine-readable expected call graph. |
| **3. Expected Parameters (JSON)** | Canonical parameters for each expected call. | Normalized JSON: stable key order, canonical dates/time zones, normalized enums/IDs. |
| **4. NDCG@k** | Ranking quality: actual discounted gain divided by ideal discounted gain. | Computed from DCG@k and IDCG@k; leave blank when ranking is not part of the task. |

Three rules that keep those columns honest:

1. **Column 2 records order only where order is semantically required.** An arrow chain written for a
   run that happened to work is a golden trajectory by the back door.
2. **Column 3 is normalized at write time**, not at compare time: stable key order, canonical dates and
   time zones, normalized enums and IDs. Normalizing during comparison instead means every scorer
   re-implements the canonicalizer and they disagree — see
   `references/tool-and-argument-metrics.md`.
3. **Column 4 is blank, not 0, when ranking does not apply.** Blank is excluded from the composite
   denominator; 0 is a failure the agent was never given the chance to commit
   (`references/aggregation.md`).

The remaining columns — raw counts, per-group metrics, gates, cost, latency, trace pointer — are
described in `specs/workbook.md`.
