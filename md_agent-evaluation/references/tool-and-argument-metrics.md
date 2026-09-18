# Tool-call correctness: selection, arguments, execution, state

A function call is **structured data, not prose**. That is why this layer is worth more than any
answer-quality score: you can compare the selected function, parse and canonicalize the arguments,
and — when it is safe — execute the call or an equivalent sandboxed validator. Berkeley Function
Calling Leaderboard (BFCL)-style evaluation is the model here, and it has itself moved from AST-based
call checking into multi-turn and broader agentic settings. Lineage: `references/research-lineage.md` [1].

## The formulas — keep them exactly

| Metric | Formula | Reading |
|---|---|---|
| Tool precision | `TP / (TP + FP)` | TP = expected call matched; FP = unnecessary/hallucinated call. |
| Tool recall | `TP / (TP + FN)` | FN = required call omitted. |
| Tool F1 | `2 * precision * recall / (precision + recall)` | The headline tool-selection number. |
| Argument field F1 | F1 over canonical JSON paths and normalized values | Flatten nested JSON to paths such as `flight.date` or `attendee.email`. Compare both path presence and normalized values. |
| Execution success rate | `successful tool executions / attempted tool executions` | Non-executable calls that looked syntactically fine. |
| End-state goal match | `satisfied goal predicates / applicable goal predicates` | The outcome layer's real definition. |
| Unwanted side-effect rate | `unexpected state mutations / mutation opportunities` | Denominator is opportunities, not calls — see below. |

Two more, for the trajectory layer:

| Metric | Formula | Reading |
|---|---|---|
| Tool-call redundancy rate | `redundant_tool_calls / total_tool_calls` | Over-tooling and loops. Read with cost per successful task. |
| Recovery steps | number of extra actions from injected fault to first correct recovered trajectory | Long-horizon brittleness. Requires an injected fault; see `references/reliability.md`. |
| Sequence similarity | LCS or edit similarity over the ordered call-name sequence | **A diagnostic only.** Never the definition of correctness. |

**Sequence similarity has no single canonical normalization**, and the playbook does not pin one.
Record which one you computed — LCS length, LCS over the expected length, or edit distance over the
longer sequence — next to the number. A trajectory score whose normalization is unstated cannot be
compared across two runs, so the metric silently drifts into meaninglessness.

**Keep the schema-validity metric separate from semantic parameter correctness.** A call can be
schema-valid and semantically wrong (right shape, wrong date) or schema-invalid and semantically
intended. Merging them produces a number that moves for two unrelated reasons, and a regression in
one can be masked by an improvement in the other.

## Canonicalization rules matter more than they look

Every one of these is a rule about the **denominator or the comparison**, and getting one wrong
silently changes every argument metric downstream.

1. **Normalize equivalent timestamps to one time zone before comparing.** Without it, a correct agent
   in another zone scores as a wrong-argument failure.
2. **Normalize enums and aliases** ("NYC" vs "New York City") **only when the tool contract defines
   them as equivalent.** Normalizing beyond the contract hides a real defect: the tool will reject
   the value in production even though the eval passed it.
3. **Compare sets as sets only when order is semantically irrelevant; preserve array order when it
   changes meaning.** Set-comparing an ordered array marks a wrong itinerary as correct.
4. **Distinguish omitted optional fields from explicitly wrong fields.** Collapsing them makes
   "under-specified" and "actively wrong" the same number, and they need different fixes
   (schema examples vs canonicalization).
5. **For generated IDs, validate referential correctness rather than literal string equality.** A
   booking id the agent could not have known is not a wrong argument, and literal comparison scores
   every correct run as a failure.
6. **Keep a schema-validity metric separate** from semantic correctness, per above.

Write the canonicalizers **before** you compute a single argument metric. Canonicalizers introduced
afterwards change every historical number, and the eval's own history becomes unusable as a baseline.

## What "correct" means at this layer

Correct is: the required calls happened, no forbidden call happened, each call's canonical arguments
matched, each call executed, and the **final environment state satisfies the goal predicates**. The
trace is a means to a state change, not the thing being scored — `specs/case-schema.md` makes that
the unit of evaluation.

Run the arithmetic with `scripts/metrics.py tools` and `scripts/metrics.py fields`; the failure
classes these numbers point at are in `references/failure-taxonomy.md`.
