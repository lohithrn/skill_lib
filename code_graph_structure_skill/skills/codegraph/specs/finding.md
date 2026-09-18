# Output contract — a finding

**The Iron Law: nothing is a finding unless it has all seven fields. A finding without a
consequence and a remedy is not a finding — it is noise, and it is dropped.**

Order is fixed. Fields are never omitted, never merged, never reordered.

```
ID           CG-<DIM>-<nnn>
LOCATION     path/to/file.ext:startLine-endLine
SYMPTOM      what is literally in the code, in one sentence, no judgement
LAW          the named rule broken — Rule name (Source)
CONSEQUENCE  what breaks, or what cannot change, because of it
REMEDY       the exact CPRC move: conflict → port name → resolver files → context
SEVERITY     blocker | major | minor | deferred-conflict
```

`<DIM>` is one of: `GRAPH` `CAPS` `COND` `DI` `PORT` `TEST` `TIME` `ERR` `DEAD` `NAME`.

Two dimensions carry a **mandatory eighth field**:

- `DEAD` — an `EVIDENCE` line listing the searches run and the §2 safelist checks cleared
  (`../references/dead-code.md` §6). Without it the finding is dropped: a wrong deletion causes an
  outage, not a bad review.
- `NAME` — the finding must state **how the name misleads a reader who sees it alone**, in a stack
  frame or an import line. "I would have named it differently" is not a finding
  (`../references/naming.md` §7).

---

## Worked example

```
ID           CG-COND-007
LOCATION     src/billing/invoice_service.py:88-141
SYMPTOM      A 54-line method branches on `customer.tier` in an if/elif/elif/else chain,
             and the same `tier` value is switched on again in reporting/summary.py:31.
LAW          Repeated Switches (Fowler, Refactoring 2nd ed. ch.3); G23 Prefer Polymorphism
             to If/Else or Switch/Case (Martin, Clean Code ch.17); method length 54 > 15
CONSEQUENCE  Adding a fourth tier requires edits in two files that no test connects, and the
             compiler cannot tell you the second site was missed. Both sites already disagree
             on the handling of tier=None.
REMEDY       Conflict: "which discount applies to this customer's tier?"
             Port:     billing/discount_policy.py :: DiscountPolicy.discount_for(ctx) -> Money
             Context:  billing/billing_context.py :: BillingContext(customer_id, tier, subtotal,
                       as_of, currency, tenant)
             Resolvers: billing/policies/{standard,silver,gold,absent}_discount.py
             Selector: EnumMap registry in billing/policies/__init__.py, ABSENT as default
             Tests:    billing/tests/discount_policy_contract.py + registry coverage test
             Deletes:  the else branch at :137 and the duplicate switch at reporting/summary.py:31
SEVERITY     major
```

---

## Field rules

### ID
Stable within a run. Referenced by the spec's slices and by verification verdicts. Never reused.

### LOCATION
**A line range, not a file.** `src/foo.py` is not a location. If the symptom spans files, pick the
primary site and list the others inside SYMPTOM. Ranges must be re-checkable after an edit.

### SYMPTOM
What is literally there. No adjectives. No "poorly structured", no "messy", no "should".
Include the measured number when a hard limit is involved (`54 lines`, `4 nesting levels`,
`7 parameters`, `fan-in 31`). A reader must be able to verify the symptom without judgement.

### LAW
A **named** rule plus its **source**. Acceptable sources: Fowler *Refactoring* 2nd ed.,
Martin *Clean Code* (`G23`-style codes) / *Clean Architecture* (component principles), Bay
*Object Calisthenics*, Liskov & Wing, Meyer, Page-Jones (connascence), Larman (GRASP), Evans,
Ousterhout, Metz, Seemann (DI anti-patterns), Lippert & Roock (architecture smells), a Sonar/PMD/
ruff/eslint rule ID, or one of this skill's own hard limits from `../references/laws.md`.

"This violates SOLID" is not a law — say **which** letter and why. "Best practice" is not a source.

### CONSEQUENCE
The concrete failure the finding predicts. One of these shapes:

- **Change amplification** — "adding a fifth X requires edits in N unrelated files."
- **Silent divergence** — "the two sites already disagree on case Y."
- **Untestable** — "this cannot be unit-tested without a live Z."
- **Foreclosed** — "the second tenant named in TICKET-numbered work cannot be added without re-plumbing."
- **Break** — "input Q produces wrong output R" (only with a reproducing case).

If you cannot write one of these, **drop the finding.** Aesthetics is not a consequence.

### REMEDY
The full CPRC move, spelled out with real names and real paths — not "consider extracting an
interface." Must include: the conflict as a question · the port file and signature · the Context
type and its fields · every resolver file · the selector and where it lives · the contract suite
path · and what the change **deletes**. The `Deletes:` line is mandatory: a remedy that only adds
is suspect.

### SEVERITY

| Severity | Meaning | Gate |
|---|---|---|
| **blocker** | breaks the system as designed, or makes a unit untestable, or a graph cycle | must be in slice 1 |
| **major** | change amplification across ≥2 files, or a hard-limit breach ≥2× the cap | must be in the spec |
| **minor** | a single-site hard-limit breach; local, no cross-file consequence | batched, optional |
| **deferred-conflict** | a real seam deliberately left open | **recorded, never fixed** |

---

## `deferred-conflict` — how to record headroom without billing for it

A deferred conflict is documented headroom. It appears in the spec's inventory, never in the
remediation list, and never counts toward a score.

```
ID           CG-COND-019
LOCATION     src/config/regions.py:12-19
SYMPTOM      `REGIONS` maps three env names to the same bucket value.
LAW          — (none broken)
CONSEQUENCE  — (none; the seam permits per-region divergence without re-plumbing)
REMEDY       none. Promote to a port when a second region gets a distinct value.
SEVERITY     deferred-conflict
```

---

## Automatic non-findings — refuse to emit these

1. "The current value is the loosest possible."
2. "You collapsed X into one value" — env-scoped names sharing one value, a mode knob set to one
   mode, a per-stage resource pointing at one target. All deliberate seams.
3. A single-resolver port **at an I/O boundary** — justified by testability alone.
4. A registry `match`/`switch` in the composition root — data, not control flow.
5. An exhaustive match over a sealed set where the compiler checks totality.
6. Duplication with fewer than three occurrences (Rule of Three).
7. A `# TODO` — that is a deferred-conflict marker, not debt.
8. Style the repo's own linter permits, unless a hard limit breaks.
9. Anything whose CONSEQUENCE field would read "harder to read."
10. Anything found only by pattern-matching a file name rather than reading the code.

---

## Verification verdict (appended by the adversary, phase 3)

```
VERDICT      CONFIRMED | REFUTED | UNCLEAR
LOCATION     the line the verdict actually applies to
ATTACK       the specific reason the finding might be wrong
EVIDENCE     the command that ran and the number it printed, or "none" — never a recollection
CONSEQUENCE  the concrete failure this finding predicts, or why no failure follows
FIXABLE      yes | no | not-worth-it
```

This is the one wire format. `../references/refine-loop.md` §4 defines it; this block repeats it
only because the adversary block is appended to a finding and a reader needs both shapes in one
place. If they ever disagree, refine-loop.md §4 wins. `CONSEQUENCE` subsumes what an earlier
draft called `COUNTER`: state the failure the finding predicts, or state that none follows —
which is how a finding gets dropped. No prose outside these six lines.

Survival: **1 CONFIRMED keeps it. 2 independent REFUTED drops it. 2 UNCLEAR downgrades it to
minor.** The adversary never sees the finder's reasoning — only the finding and the code.

---

## Report ordering

Blockers first, then majors by consequence severity, then minors batched by file, then the
deferred-conflict inventory last under its own heading. Within a severity, order by descending
`change-amplification × hotspot-score` so the highest-leverage item is first.

Each finding is **≤ 20 lines rendered**. A finding needing more than that is two findings.
