# Failure taxonomy for engineering triage

**An eval is successful when it identifies what to fix, not merely which model won.** This table is
what turns a red number into an owner. Every finding you report should name a row.

| Failure class | Typical signature | Likely fix area |
|---|---|---|
| **Tool relevance** | Calls a tool when no call is needed, or chooses wrong API | Tool descriptions, routing, tool retrieval, abstention training. |
| **Argument omission/value** | Right API, wrong date/ID/filter or missing required field | Canonicalization, structured planning, schema examples, validation. |
| **Ordering/state dependency** | Uses a write tool before lookup/verification | Planner, state tracking, precondition checks. |
| **Premature stop** | Partial milestones complete but goal state not reached | Termination criteria, outcome verification. |
| **Over-execution/loop** | Repeated or redundant calls | Loop detection, cost-aware policy, explicit done-state. |
| **Recovery failure** | Timeout/tool error sends agent off trajectory | Retry policy, idempotency keys, error-aware planning. |
| **Grounding failure** | Answer claim unsupported by retrieved evidence | Retrieval quality, claim verification, citation enforcement. |
| **Ranking failure** | Relevant items found but poor ordering | Ranking objective, better relevance scoring, reranking. |
| **Policy violation** | Task completed while violating domain rule | Policy representation and gate checks. |
| **Prompt injection** | Untrusted tool data hijacks behavior | Trust-boundary design, instruction/data separation, defense-in-depth. |
| **Goal-shift lag** | Keeps executing old plan after user changes intent | Intent revision detection, plan invalidation. |
| **Calibration failure** | High confidence on failed tasks | Confidence modeling, abstention/escalation policy. |

## How to use it

1. **Classify every failed case into exactly one class** — the one that fired first in the trace. A
   case labelled with three classes gets triaged by nobody, because no team owns it.
2. **Cluster the traces, then count the clusters.** Twelve failures in one class is one bug; one
   failure in twelve classes is a suite telling you the agent is broadly weak, and the two get
   different responses.
3. **Read the fix column before proposing a prompt change.** Most of these rows are fixed in the
   planner, the tool contract, the retry policy, or the trust boundary — not in wording. A prompt tweak
   against an ordering/state-dependency failure moves the number without removing the defect, and it
   returns on the next fixture.
4. **Argument omission and argument value are the same row on purpose, but not the same metric.** Keep
   the omitted-vs-wrong distinction in the data (`references/tool-and-argument-metrics.md` rule 4) so
   the fix column can be chosen correctly.
5. **A class with no cases is a coverage question, not a win.** Zero prompt-injection failures on a
   suite with no injection cases means the suite has no injection cases — check
   `references/safety.md` before reporting it as clean.

## Which layer sees which class

| Class | Layer that detects it |
|---|---|
| Tool relevance, over-execution/loop | Tool use, Trajectory |
| Argument omission/value | Arguments |
| Ordering/state dependency, premature stop | Trajectory, Outcome (end-state predicates) |
| Recovery failure, goal-shift lag | Reliability (stress matrix) |
| Grounding failure | Ranking/RAG |
| Ranking failure | Ranking/RAG |
| Policy violation, prompt injection | Safety/security (hard gates) |
| Calibration failure | Efficiency/calibration |

A class no layer detects is a class you will find in production instead. The layer definitions are in
`references/layers.md`.
