# Job: refine — run the convergence loop, gated on measurements

The operational form of `../references/refine-loop.md`. Read that file for *why* each rule exists;
this file is *how* to run it. Do not restate it — cite the section.

Not a route in `SKILL.md`, and it is not invoked directly — it is a callee. Two loops use it, and
they are never merged (`../references/refine-loop.md` §5):

- the **spec loop** — the procedure `jobs/spec.md` phase 2e ("refine, machine-gated") performs.
  Read this file when you reach that phase; it cites `references/refine-loop.md`, not this file.
- the **code loop** — the procedure `jobs/apply.md` phase 4d performs after each slice, and the
  phase-3 mode of `jobs/verify.md` phase 5a, which hands off here by name.

It writes no new artifact shape: the spec loop updates `.codegraph/restructure.md`, the code loop
appends its pass log to `.codegraph/applied.md`. Plus a ≤25-line summary.

**Fully offline.** Scores come from the repo's own runner, `scripts/caps.sh`, `scripts/graph.sh`,
the type checker already installed, the linter already installed, and `git log`. No URL is fetched,
no package installed, no tool downloaded, no network service called, no credential handled.

**The loop is gated by measurements, never by the model's judgement alone.** A pass with no oracle
number attached to the dimension it touched is discarded, not accepted.

---

## Phase R0 — establish the oracle, or refuse

1. Read `.codegraph/oracle.json`. For each entry record the **exact command** and whether it runs
   here. The oracle table is `../references/refine-loop.md` §2.
2. A dimension with no oracle **is not refined**. Report its findings once as `UNVERIFIED` and
   remove it from the rotation. Refining an unverifiable dimension is how the loop regresses.
3. Score the starting artefact: `spec_0` on the 8-criterion rubric
   (`../references/refine-loop.md` §6, 0–3 each, total 0–24), or `code_0` on suite + caps + graph +
   types. Write it down. `best = (artefact_0, score_0)`.
4. If **no** oracle runs at all — no tests, no type checker, no linter — the loop does not start.
   Say so and return the artefact unchanged. There is nothing to gate on.
5. Put the whole requirement in the pass-0 prompt. A "gain" from iteration is usually information
   withheld on turn one (`../references/refine-loop.md` §1, item 3).

---

## Phase R1 — the loop body, one pass

Repeat this body verbatim, at most `budget` times. `t` is the pass index, from 0.

1. `dim = rotation[t]` — a **fresh** dimension every pass, from
   `[graph, caps, conditionals, di, ports, tests, temporal]`. Never re-attack a dimension inside
   one loop; a self-critic re-reading its own work approves ~94% of it.
2. Launch **one** `codegraph-adversary` per unit under attack — per slice for the spec loop, per
   changed file for the code loop — in a single message. Each gets the artefact and the code, and
   **never the author's reasoning**. Context isolation is the point.
3. Require the fixed return schema from `../references/refine-loop.md` §4:
   `VERDICT` · `LOCATION` · `ATTACK` · `CONSEQUENCE` · `FIXABLE`, plus `rubric` and a boolean
   `stop`. **No prose outside the schema** — prose cannot be compared across passes, so plateau
   detection becomes impossible.
4. Apply the asymmetric thresholds: **1 CONFIRMED keeps a finding · 2 independent REFUTED drops it
   · 2 UNCLEAR downgrades it to `minor`.** A surviving finding must still satisfy all seven fields
   of `../specs/finding.md`, or it is dropped here rather than carried.
5. Check the stopping criteria in R2 **before** revising. If any fires, exit and return `best`.
6. Revise **one dimension only**, passing the *whole* pass history, not just the last critique.
   Three simultaneous edits make the score unattributable.
7. Re-measure. Run the oracle commands again — the same commands, same flags, same root.
8. **Accept only if better.** `score(artefact_next) >= best.score` ⇒ `best = artefact_next`.
   Strictly lower ⇒ discard the revision and **exit the loop**. Never take a worse pass "to
   explore"; this gate is what prevents the documented correct→incorrect flips.
9. Append one row to the pass log: `t · dim · findings kept · score before → after · kept|discarded`
   — into `.codegraph/restructure.md` for the spec loop, `.codegraph/applied.md` for the code loop.

Return `best.artefact` — the **best** pass, not the last.

---

## Phase R2 — stopping criteria, all machine-checked

Any one of these ends the loop. Evaluate them in this order, at the top of every pass.

| # | Criterion | The check that decides it |
|---|---|---|
| S1 | budget spent | `t == budget` |
| S2 | adversary stop flag | `critique.stop == true` — the boolean, not a sentence |
| S3 | nothing left to find | `critique.rubric` is at max on every criterion (24/24) |
| S4 | plateau | `rubric_t == rubric_{t-1}` — no criterion moved |
| S5 | no confirmed finding survived | the kept-finding list is empty after R1.4 |
| S6 | no-op iteration | `trivial_diff(next, current)` — see R3 |
| S7 | regression | `score(next) < best.score` — hard stop, discard the revision |
| S8 | calibration failure | one dimension's findings were ≥50% REFUTED |

S5 is the **intended** terminal state. A clean pass is success, not a failed pass — exit on it
immediately and do not go looking for something to change.

S8 is not a refinement: stop verifying that dimension, tighten its detector threshold, re-run the
detector **once**, and say so in the report (`../references/refine-loop.md` §4).

---

## Phase R3 — what makes an iteration a no-op

An iteration is a no-op — and therefore S6 — when **any** of these holds. Check mechanically, in
this order; the first hit ends the loop.

1. **The artefact did not change.** Byte-identical outside a timestamp. `graph.json` is
   deterministic per `../specs/graph-report.md` §5, so this comparison is meaningful.
2. **Only prose changed.** No section, slice, port, resolver, Context field, oracle command, or
   revert line differs. Rewording is not refinement.
3. **The score did not move.** Same rubric total *and* the same per-criterion vector.
4. **The change is unmeasurable.** The edited dimension has no oracle in `oracle.json`, so the
   revision cannot be shown to be better — treat as a no-op and discard it.
5. **The only change is more ports.** Refining by adding abstraction is how this doctrine fails
   (`../references/arch-smells.md` §11). The usual real improvement is a **smaller** artefact:
   fewer slices, more deferrals, a tighter blast radius.
6. **The change only closes a `deferred-conflict`.** Headroom is not a defect: a permissive default
   a future environment will tighten, env-scoped names sharing one value today, a mode knob with
   one mode, a single-resolver port at an I/O boundary. See `../references/smells.md` §6. Closing
   one without being asked is a no-op at best and a regression at worst.

Two consecutive no-ops are impossible: the first one exits the loop.

---

## Phase R4 — budgets, and they are hard

| Loop | Budget | Unit of a pass | Oracle |
|---|---|---|---|
| **Spec loop** (phase 2e/3) | **3 passes** | the whole `.codegraph/restructure.md` | rubric §6 + the current code's caps/graph measurements + internal consistency |
| **Code loop** (phase 4d/5, per slice) | **1 pass** | one applied slice | the real suite + `caps.sh` + `graph.sh` + type checker |

1. Never exceed the budget "to try once more". That is exactly where the measured regressions live
   (`../references/refine-loop.md` §1).
2. A slice needing a second code pass is **mis-specified**. Revert it and re-slice; do not iterate
   on the edit. Tests green before and after every slice, always.
3. Below **16/24** the spec is not presented for approval — spend a pass. At or above 16/24 with
   every mechanical check in `jobs/spec.md` phase 2d passing, stop early.
4. The rubric total is the number the accept-only-if-better gate compares. Nothing else.

---

## Return to the conversation

≤25 lines. Never paste the artefact, the critiques, or a JSON file.

```
CodeGraph refine: spec loop on <repo> @ <sha>   19/24 (pass 2 of 3 kept)
Passes     0 graph 15→17 kept · 1 ports 17→19 kept · 2 tests 19→17 discarded (S7)
Exit       S7 regression on pass 2 — returned best, not last
Findings   11 attacked · 7 CONFIRMED · 3 REFUTED (dropped) · 1 UNCLEAR ×2 (→ minor)
Oracle     pytest · caps.sh · graph.sh · mypy   (no mutation tool: `temporal` UNVERIFIED)
Changed    slices 9 → 7 · ports 10 → 8 · deferrals 11 → 14 (smaller, not larger)
Headroom   14 deferred conflicts untouched
Not covered temporal dimension has no oracle here and was never refined

Best: .codegraph/restructure.md (pass 1)
Next: check §9 Approval, then /codegraph apply <slices>
```

---

## Refusals

- **No oracle for the dimension.** Report it once as `UNVERIFIED`; never refine it, never score it.
- **A revision that scores lower.** Discarded, loop exits. Not negotiable, not "to explore".
- **Prose feedback instead of the schema.** Re-request the pass in schema form once, then stop.
- **Showing the adversary the author's reasoning.** Anchoring destroys independence; refuse.
- **Rewriting a contract suite, fitness test, or characterization test so a refined resolver
  passes.** That inverts the oracle. The port is wrong — say so and stop.
- **A second refinement pass on one applied slice.** The slice is mis-specified; revert and
  re-slice via `jobs/spec.md`.
