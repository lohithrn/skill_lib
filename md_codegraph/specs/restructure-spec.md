# Output contract — the restructure spec

Written to `.codegraph/restructure.md`. **This is the phase-2 gate.** Nothing is edited until the
user approves this file. `/md_codegraph apply` refuses to run without it.

The spec is a plan a different agent — or a human, next month — can execute without re-deriving
anything. If a slice cannot be executed from the spec alone, the spec is incomplete.

---

## Fixed structure

```markdown
# Restructure spec — <repo> @ <git sha>

## 1. Verdict and scope
## 2. Target tree
## 3. Ports (one subsection per port)
## 4. Slices (one subsection per slice, ordered)
## 5. Fitness tests to add
## 6. Deferred conflicts
## 7. Out of scope
## 8. Rollback
## 9. Approval
```

---

## 1. Verdict and scope

```markdown
Current: ERODED — 3 blockers, 11 majors. 4 cycles, 31 files over 250 lines, 341 `else`.
Target:  SOUND  — 0 cycles, 0 files over 250, 0 `else` outside registries, 8 ports each with a
                  contract suite, 1 composition root.
Effort:  9 slices · ~14 h of agent time · every slice independently revertable
Blast:   87 files touched, 31 files created, 4 deleted. No public API change.
Risk:    the pricing slice touches the money path; it is slice 7, after the tests exist.
```

State honestly what will **not** improve. If the graph will still have a hub after this spec, say so.

---

## 2. Target tree

The full destination tree, with a one-line comment per new file saying which conflict it answers.
Mark `[new]`, `[moved from …]`, `[split from …]`, `[deleted]` on every line that changes.

```
src/billing/
├── billing_context.py           [new]   the problem's variables, frozen
├── discount_policy.py           [new]   PORT: which discount applies to this tier?
├── invoice_service.py           [was 214 lines → 96] depends on the port only
├── policies/                    [new]   the answers
│   ├── __init__.py              [new]   registry: EnumMap tier → policy, ABSENT default
│   ├── standard_discount.py     [new]   ← invoice_service.py:88-99
│   ├── silver_discount.py       [new]   ← invoice_service.py:100-115
│   ├── gold_discount.py         [new]   ← invoice_service.py:116-136
│   └── absent_discount.py       [new]   Null Object; deletes the else at :137
└── tests/
    ├── discount_policy_contract.py  [new]  layer 2, shared by all 4 resolvers
    └── test_registry_coverage.py    [new]  build failure if a resolver is unregistered
```

**Every extracted resolver must cite its source line range.** `← invoice_service.py:100-115` is
how a reviewer verifies nothing was invented and nothing was lost.

---

## 3. Ports — one subsection each

```markdown
### Port: `DiscountPolicy`

Question      Which discount applies to this customer's tier, for this subtotal, right now?
File          src/billing/discount_policy.py
Signature     discount_for(ctx: BillingContext) -> Money
Declared in   billing (with its caller) — Separated Interface; resolvers live in policies/
Kind          open set (a fourth tier is named in the roadmap) → registry with ABSENT default
Dispatch      EnumMap[Tier, DiscountPolicy] in policies/__init__.py
Expression-problem call: cases will grow, operations are stable → resolvers, not a sealed match.

Context       BillingContext(customer_id, tier, subtotal, as_of, currency, tenant)
              `tenant` is unused by every resolver today — deliberate headroom, do not remove.
              `as_of` exists so no resolver reads a clock.

Resolvers
| file | answers | from | absent? |
|---|---|---|---|
| standard_discount.py | tier=STANDARD | invoice_service.py:88-99  | no |
| silver_discount.py   | tier=SILVER   | invoice_service.py:100-115 | no |
| gold_discount.py     | tier=GOLD     | invoice_service.py:116-136 | no |
| absent_discount.py   | tier missing/unknown | invoice_service.py:137-141 (the else) | yes |

Contract suite  billing/tests/discount_policy_contract.py
  - returns Money in ctx.currency
  - discount ≤ subtotal, ≥ 0  (postcondition, all resolvers)
  - idempotent for the same ctx
  - raises DiscountUnavailable — the SAME type — for an unpriceable ctx
  - property: for all generated BillingContext, currency is preserved
Registration    test_registry_coverage.py asserts policies/*.py == registry keys ∪ {absent}

Deletes         the if/elif/elif/else at invoice_service.py:88-141
                the duplicate tier switch at reporting/summary.py:31-44
Wiring          composition_root.py: DISCOUNTS mapping, wrapped in Cached(ttl=60) for GOLD only
Resolves        CG-COND-007, CG-CAPS-003, CG-GRAPH-001 (the cycle goes with the duplicate switch)
```

A port subsection missing **Deletes**, **Contract suite**, or **Registration** is incomplete.

---

## 4. Slices — the execution order

A **slice** is the unit of work and the unit of revert. Rules:

1. **Tests green before and after.** No exceptions.
2. **One slice = one commit.** No behaviour change and refactoring in the same commit.
3. **Independently revertable.** `git revert <slice>` must leave a working tree.
4. **≤ 15 files touched**, or it is split. A 40-file slice is a codemod — say so and name the tool.
5. **Extract the interface before moving anything.** Always.

```markdown
### Slice 3 — extract DiscountPolicy port and its resolvers

Depends on   slice 1 (characterization tests), slice 2 (BillingContext)
Files        7 changed, 8 created, 0 deleted
Technique    Extract Interface (Feathers, *WELC* ch.25 — not in Fowler 2nd ed.)
             → Branch by Abstraction (Fowler bliki) → Replace Conditional with Polymorphism
             (Fowler, *Refactoring* 2nd ed. ch.10)
Steps
  1. Add `discount_policy.py` with the port. No implementation. Commit.
  2. Add the 4 resolvers, each copying its source range verbatim. No caller change. Commit.
  3. Add the contract suite + registry coverage test. Both must fail for a missing resolver. Commit.
  4. Add the registry in `policies/__init__.py`. Commit.
  5. Point `invoice_service.py` at the registry; delete the if/elif chain. Commit.
  6. Point `reporting/summary.py` at the registry; delete its duplicate switch. Commit.
  7. Wire in the composition root; delete the now-dead tier constant. Commit.
Oracle       pytest -q · scripts/caps.sh --json --root src/billing · scripts/graph.sh --cycles
Green when   suite passes, invoice_service.py ≤ 250 lines, 0 `else` in billing/, cycle count 4→3
Revert       `git revert` steps 7→1 in reverse; steps 1-4 are additive and safe to leave
Risk         GOLD tier had an undocumented rounding difference at :131 — characterization test
             `test_gold_rounds_half_up` in slice 1 pins it before the move.
```

### Slice ordering algorithm

1. **Characterization tests first**, for every hotspot the spec will touch. Never restructure
   untested code.
2. **Context objects next** — they are additive and unlock everything else.
3. **Leaves before roots.** Extract ports whose resolvers depend on nothing before ports whose
   resolvers depend on other ports.
4. **Cycles before hubs.** Break cycles early; they distort every later measurement.
5. **The hub last.** The most-depended-on module moves after everything pointing at it is stable.
6. **Codemod slices alone**, never mixed with hand edits, and always with the tool named
   (`libcst`, `ts-morph`/`jscodeshift`, `OpenRewrite`, `gofmt -r`, `comby`, `ast-grep`).
7. **Fitness tests last** — they lock in the shape, so they land once the shape is right.

---

## 5. Fitness tests to add

Every graph claim the spec makes becomes an executable test at layer 4. List each with its file
and its tool.

```markdown
| # | Claim | Test | Tool |
|---|---|---|---|
| F1 | no cycles among src modules | tests/fitness/test_no_cycles.py | import-linter acyclic_siblings |
| F2 | nothing outside the root imports policies/ | tests/fitness/.importlinter forbidden | import-linter |
| F3 | domain does not import adapters | same | import-linter layers |
| F4 | every port has a contract suite | tests/fitness/test_contract_coverage.py | custom |
| F5 | utils imports nothing from src | .importlinter forbidden | import-linter |
| F6 | no test imports a higher test layer | tests/fitness/test_layering.py | custom |
| F7 | zero `*_major` cap violations — the hard column only, read from `caps.sh --json`, never a number retyped here | tests/fitness/test_caps.py | scripts/caps.sh |
```

F7 exists because the caps must be **a test, not a habit.**

---

## 6. Deferred conflicts

The headroom inventory. Recorded so the next reader knows these are deliberate.

```markdown
| ID | location | seam | promote when |
|---|---|---|---|
| CG-COND-019 | config/regions.py:12 | three env names → one bucket value | a region needs a distinct value |
| CG-COND-023 | pipeline.py:40 | BUILD_MODE knob, one mode today | a second mode ships |
```

**These are not work items.** Never move one into a slice without asking.

---

## 7. Out of scope

Explicit. Anything a reader might expect and will not get, with the reason. **Three required
subsections** — a spec with only the first one has not done the hard part:

```markdown
### 7a. Will be done — but not in this spec
Real work, correctly deferred: no oracle, a degraded graph, a different team's directory,
or it belongs in the next spec after this one lands. Each with the finding ID.

### 7b. Suspicious — needs verification before anyone acts
Findings that are probably real but not provable from static analysis. Every dead-code candidate
whose EVIDENCE line came back `suspicious` lands here, with **the specific check that would
settle it** — a coverage run, a log line shipped for one release, an owner to ask.
Nothing in 7b may appear in a slice. This section exists so uncertainty is recorded rather than
resolved by guessing.

### 7c. Declined — fixing it would make the code worse
Findings deliberately not acted on, with the reason. Typically: an interface with one answer and
no boundary (would be ceremony), a conditional that validates rather than selects behaviour,
duplication under the Rule of Three, a rename that is only a convention change, a sealed set the
compiler already checks. Each line names the rule that *would* have applied and why it does not.
```

7c is the anti-over-engineering record. **A spec with an empty 7c is suspect**: it means every
detected pattern was converted, which is how a codebase acquires an interface farm. Abstraction
ships only when it removes real duplication, isolates real variation, improves testability,
protects a boundary, or kills a growing behaviour-selection branch — otherwise it goes in 7c.

## 8. Rollback

The whole-spec escape hatch: the branch name, the base sha, and the single command that undoes
everything. Plus: which slices are additive-only (safe to keep even if the rest is reverted).

## 9. Approval

```markdown
- [ ] Target tree reviewed
- [ ] Port questions are the right questions
- [ ] Slice order and blast radius accepted
- [ ] Deferred conflicts confirmed as deliberate headroom
- [ ] Approved to apply: slices ___ (or `all`)
```

`/md_codegraph apply` reads this block. Unchecked approval ⇒ it refuses and prints what is missing.

---

## Quality bar before presenting

Score against the rubric in `../references/refine-loop.md` §6. **Below 16/24, do not present it
— run another refinement pass.** Also check, mechanically:

- every port has a question, ≤3 methods, an Absent resolver, a contract suite, and a
  registration test
- every resolver cites a source line range
- every slice has an oracle command and a revert
- every finding ID from the report appears in exactly one slice, or in §6, or in §7
- the target tree contains no file the spec does not explain
