# The convergence loop — and why it is gated on machines, not on opinion

Recursive self-improvement of a spec **regresses** without external ground truth. This is the
best-documented negative result in the area and the loop below is designed around it.

---

## 1. The negative result you must design around

Measured degradation when a model critiques and revises its own reasoning with no external
signal: GSM8K accuracy falling 95.5 → 91.5 → 89.0 across 1/3/5 self-correction rounds;
CommonSenseQA collapsing 75.8 → 38.1. Earlier positive results relied on **oracle labels
deciding when to stop** — and the gains vanish when the oracle is removed.

Three consequences, all binding:

1. **Preventing correct→incorrect flips is the whole game.** Never accept a revision that
   scores worse on an external measure.
2. **The failure mode is mistake *localisation*, not repair.** Given the location of an error, a
   model fixes it reliably. So **make the locator external and cheap** — that is what
   `scripts/caps.sh`, `scripts/graph.sh`, the type checker, and the test suite are for.
3. **Put the full requirement in the initial prompt.** A "gain" from iteration is often just
   information withheld on turn one. Documented case: full-requirement-up-front scored 81.8,
   and self-refining on top of a weaker initial prompt dropped it to 75.1.

No study has shown self-correction succeeding on feedback from a prompted model alone, absent
reliable external feedback. Therefore: **this loop never runs without at least one machine check
attached to the dimension being refined.**

---

## 2. External ground truth — the loop's oracle

Before the loop starts, establish which of these actually run in the target repo. Record the
answer in `.codegraph/oracle.json`. The loop's budget is spent only on dimensions an oracle covers.

| Oracle | Command | Gates |
|---|---|---|
| test suite | repo's own runner | behaviour preservation |
| `scripts/caps.sh` | bundled | file lines, method lines, nesting, `else`, params |
| `scripts/graph.sh` | bundled | cycles, fan-in/out, layer direction, orphan resolvers |
| type checker | `mypy`/`tsc --noEmit`/`javac`/`go vet` | signature and totality breaks |
| linter | repo's own | style + the `else`/early-return rules |
| mutation score | `mutmut`/`stryker`/`pitest`, **diff-scoped** | whether the new tests bite |
| fitness tests | layer 4 | the graph claims the spec makes |

**If no oracle exists for a dimension, the loop does not refine that dimension.** It reports the
finding once, flagged `UNVERIFIED`, and moves on. Refining an unverifiable dimension is how the
regression above happens.

---

## 3. The loop

```
budget      = 3 passes                        # 2-3 rounds capture most of the benefit
best        = (spec_0, score(spec_0))          # score from the oracle set, never self-assessed
dimensions  = rotate([graph, caps, conditionals, di, ports, tests, temporal])

for t in 0 .. budget-1:
    dim      = dimensions[t]                   # a FRESH dimension each pass, never a repeat
    critique = adversary(dim, spec_t, history) # returns {rubric: {...}, findings: [...], stop: bool}

    if critique.stop:                    break     # model-emitted machine-readable stop flag
    if critique.rubric == max:            break     # nothing left to find on any dimension
    if plateau(rubric_t, rubric_{t-1}):   break     # score did not move
    if critique.findings == []:           break     # no confirmed finding survived verification

    spec_next = refine(spec_t, critique, full_history)   # keep the WHOLE history, not just last

    if trivial_diff(spec_next, spec_t):   break     # unchanged twice ⇒ converged
    if score(spec_next) < best.score:     break     # ACCEPT-ONLY-IF-BETTER; hard stop
    best = max(best, (spec_next, score(spec_next)))

return best.spec                                    # BEST-of-passes, not the last pass
```

Five stopping criteria, any one of which ends the loop. Design notes on each:

- **Fresh dimension per pass.** Re-attacking the same dimension produces "everything looks good"
  — the documented failure where a self-critic approved 94% of instances. Rotation forces new
  information into each pass.
- **Machine-readable stop flag, plus a per-criterion rubric.** Never free prose. Prose feedback
  cannot be compared across passes, so plateau detection is impossible.
- **Accept-only-if-better, on the oracle score.** This is the single guard that prevents the
  documented correct→incorrect flips.
- **Return best, not last.** Later passes give minor improvements at best and regressions at
  worst; the maximum across passes is the honest output.
- **Budget 3.** Published loops cap at 4 and report diminishing returns; 2–3 rounds yield most of
  the benefit.

---

## 4. Adversarial verification of findings

Findings from the analysis phase are **claims**, not facts. Each is challenged before it reaches
the spec.

**The adversary's job is to attack, not to grade.** Its prompt says so explicitly. It receives
the finding and the code, *without* the finder's reasoning — context isolation, so it cannot be
anchored by the original argument.

Fixed return schema, no prose outside it:

```
VERDICT     CONFIRMED | REFUTED | UNCLEAR
LOCATION    the line the verdict actually applies to
ATTACK      the specific reason it might be wrong
CONSEQUENCE the concrete failure this finding predicts, or why no failure follows
FIXABLE     yes | no | not-worth-it
```

**Asymmetric thresholds.** A finding needs **one** CONFIRMED to survive. It is dropped on **two
independent REFUTED**. UNCLEAR twice ⇒ downgraded to `minor` and reported as an observation, not
a required change. Rationale: false findings cost trust far more than missed ones cost coverage,
and the analysis phase already over-generates.

**Early exit:** if the adversary refutes ≥50% of a dimension's findings, that dimension's
detector is miscalibrated — stop verifying it, report the calibration failure, and re-run the
detector with a tightened threshold instead of spending the budget.

---

## 5. Applying the loop to the spec vs to the code

Two different loops. Do not merge them.

### Spec loop (phase 3, before any edit)
- Oracle: the graph and caps measurements of the **current** code, plus the spec's internal
  consistency (does every port named in the target tree have resolvers, a Context, a registry,
  and a contract suite?).
- Budget 3, dimensions rotated, output = the approved spec.
- Cheap. No edits. Run it fully.

### Code loop (phase 4–5, after each slice)
- Oracle: the **actual test suite plus caps plus graph plus type checker**, run for real.
- Budget: **1 pass per slice.** Not 3. A slice that needs three refinement passes is
  mis-specified — revert it and re-slice rather than iterating on the edit.
- Hard rule: **tests green before and after every slice.** A slice that leaves them red is
  reverted, not patched forward. Independent revertability is the whole point of slicing.

---

## 6. Rubric — what the adversary scores

Score each 0–3. Total 0–24. This is the number the accept-only-if-better gate compares.

| Criterion | 0 | 3 |
|---|---|---|
| **Conflict coverage** | branches remain unpromoted with no `DEFERRED CONFLICT` note | every branch is promoted or explicitly deferred with a reason |
| **Port quality** | ports are noun-bags or >3 methods | each port is one question, ≤3 methods, named as a role |
| **Resolver totality** | no `Absent` resolver; callers still null-check | resolver set is total; no caller branches |
| **Context discipline** | resolvers take 5 params; clock/env read inside | one frozen Context; all ambient state injected |
| **Composition root** | concrete types named in business code | one root; nothing else imports a resolver |
| **Graph legality** | cycles, sideways edges, utils depending upward | acyclic, edges point down/in, utils is a sink |
| **Test hierarchy** | no contract suite; layer bleed | contract suite per port + registration test + layer-4 fitness tests |
| **Slice safety** | slices touch 40 files, not revertable | each slice independently revertable, tests green at each step |

A spec scoring below 16 is not presented for approval — it goes back through a pass.

---

## 7. What the loop must never do

1. **Never refine on self-assessment alone.** No oracle for the dimension ⇒ no refinement.
2. **Never accept a lower-scoring revision.** Not "to explore." The gate is hard.
3. **Never re-attack the same dimension twice** within one loop.
4. **Never exceed budget** to "just try once more." That is where the measured regressions live.
5. **Never let the adversary see the finder's reasoning.** Anchoring destroys independence.
6. **Never treat "no findings" as failure.** A clean pass is the intended terminal state and the
   loop should exit on it immediately.
7. **Never rewrite the contract suite to make a refined resolver pass.** That inverts the oracle.
8. **Never merge the spec loop and the code loop.** Spec iteration is cheap and gets 3 passes;
   code iteration is expensive and destructive and gets 1.
