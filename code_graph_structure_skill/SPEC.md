# SPEC — `/codegraph`

A skill that reads a codebase as a **graph**, finds where the graph is wrong, and
restructures it so that every branch point becomes an interface, every interface has
replaceable implementations, and the folder tree *is* the dependency graph.

Explicit-invocation only. Fans out to subagents. Returns a summary; artifacts go to disk.

---

## 1. The problem this solves

Codebases rot along two axes at once:

- **Vertical rot** — methods grow, nest, and branch. A 90-line method with four levels of
  `if/else` hides four different answers to one question inside one body.
- **Horizontal rot** — modules import each other in cycles, one folder becomes a hub, and
  the folder tree stops predicting the import graph. Reading the tree tells you nothing.

Existing tools address one axis. Linters cap complexity (vertical); architecture linters
cap edges (horizontal). Neither says *what the structure should become*. This skill does:
it names a single transformation that fixes both axes at once, and it can execute it.

---

## 2. The doctrine — Conflict → Port → Resolvers → Context (CPRC)

The one transformation. Everything else in the skill is bookkeeping around it.

> **Every conflict is an interface. Every interface has multiple implementations. Which
> implementation runs is decided by data, at the composition root — never by control flow
> at the call site.**

### 2.1 Conflict

A **conflict** is any point where more than one answer is possible. Mechanically detectable as:

| Surface form | The hidden question |
|---|---|
| `if/elif/else` on a type, flag, enum, or string | "which kind of thing is this?" |
| `switch` repeated on the same value in >1 place | "which variant?" (Fowler: *Repeated Switches*) |
| `try/except` with a real alternative path | "what do we do when the world says no?" |
| `if x is None` | "what is the absent case?" |
| a config/env lookup steering behaviour | "which environment?" |
| two blocks that differ in exactly one dimension | "which policy?" |
| a boolean parameter | "which of two behaviours did the caller want?" |
| a `# TODO: also handle …` | a conflict that has not arrived yet |

A conflict is **not** a guard clause that rejects bad input and returns, and it is **not** a
one-armed `if` guarding an optional side effect. Those stay.

### 2.2 Port

Each promoted conflict becomes exactly one interface — a **port**. Rules:

- The port's docstring states the conflict **as a question**. If you cannot phrase it as a
  question, it is not one conflict; it is several, and the port must be split (ISP).
- The port carries **one** question. Method count ≤ 3.
- The port lives in the *declaring* layer, not with its implementations. Callers depend on
  the question; only the composition root depends on the answers. (DIP, both halves.)

### 2.3 Resolvers

Each branch of the original conditional becomes one implementation — a **resolver** — in
its own file, inside a **subfolder named for the port**.

```
pricing/
├── price_port.py            # the conflict, as a question
├── pricing_service.py       # depends only on price_port
└── resolvers/               # the answers — one file each
    ├── list_price.py
    ├── contract_price.py
    ├── promotional_price.py
    └── absent_price.py      # Null Object: kills `if price is None`
```

Every port ships an **Absent/Null resolver**. That is what removes `else` and `None` checks
from callers rather than relocating them.

### 2.4 Selector

The `if` does not vanish — it **moves once**, from control flow into data:

1. **Registry** — `dict[discriminant, resolver]`, when the discriminant is a closed set.
2. **Chain of responsibility** — each resolver answers `handles(context) -> bool`; first
   match wins, `Absent` is last and always matches. Use when the discriminant is open.
3. **Double dispatch** — when two type axes vary together (Visitor).

Any of the three is legal. A residual `if` at the call site is not.

### 2.5 Context

Every resolver takes exactly one argument: an immutable **Context** value object carrying
all variables the problem needs — including variables no resolver uses yet.

This is the deliberate headroom seam. Adding a variable to the Context is additive; adding
a parameter to five resolvers is a breaking change across five files. The Context is why a
resolver node can be swapped without re-plumbing its neighbours.

Rules: frozen/readonly; no I/O; no behaviour beyond derived read-only properties; named for
the question's domain (`PricingContext`), never `Params`/`Options`/`Config`.

### 2.6 Composition root

One file per deployable. The only place that names concrete resolvers. Nothing else may
import a resolver module. If a test has to build a container to get a unit, the root has
leaked and the unit is no longer independently testable.

### 2.7 Common utils

The floor of the graph: pure functions, no I/O, no interfaces, zero project imports.
Everything may depend on utils; utils depend on nothing. Enforced as a graph rule, not a habit.

### 2.8 The layer rule

> Layer *n* **declares** conflicts. Layer *n+1* — a subfolder of *n* — **resolves** them.
> Edges point down and inward, toward common utils, never sideways, never up.

The folder tree therefore *is* the dependency graph, and the graph is checkable. That is the
whole of "code should feel like a knowledge graph": folders are question nodes, files are
answer nodes, imports are edges, and the legal edge set is a testable predicate.

### 2.9 The promotion threshold — where this doctrine goes wrong

Applying CPRC to every branch produces an unreadable interface farm. Promote a conflict only if
**at least one** holds:

1. Two or more answers exist **today**.
2. One answer exists and a second is named in a ticket, roadmap, or `TODO`.
3. The branch crosses an I/O boundary (network, disk, clock, randomness, process) — always
   promote; this is what makes the hexagon testable.
4. The same discriminant is switched on in two or more places (*Repeated Switches*).

Otherwise: guard clause, extracted method, or leave it. Record the decision as
`DEFERRED CONFLICT` in the spec with the reason. A deferred conflict is a named seam, not a
finding — do not simplify it away, and do not report it as debt.

### 2.10 Inheritance, honestly

The request was "inheritance and polymorphism everywhere." Delivered as:

- **Polymorphism everywhere** — yes. Every conflict dispatches on type.
- **Interface implementation everywhere** — yes. Every resolver implements a port.
- **Concrete-class inheritance** — only for Template Method over a *stable* base, and only
  when the base is abstract and holds no state. Concrete-inherits-concrete is the fragile
  base class problem (GoF: "favor object composition over class inheritance") and is
  rejected. Reuse arrives by **composition + delegation**; substitutability arrives by
  **interfaces**. Both are inheritance in the sense that matters — the sense LSP tests.
- The one place deep hierarchies are correct: **abstract contract test suites** (§5), where
  every resolver inherits the port's test suite and must pass it.

---

## 3. Hard limits

Non-negotiable, machine-checked, reported per violation with file:line.

Two columns, and they are not interchangeable. **Target** is what a review asks for and what
`caps.sh` reports as `*_minor`. **Hard** is what `caps.sh` reports as `*_major` and the only
column a generated fitness test may assert — a test written against the target column fails
code that is legal, and the ratchet stalls. The authority is `bash scripts/caps.sh --help`,
which prints the live defaults; every number below is overridable by its `CG_CAP_*` env var, so
read them rather than retyping them.

| Limit | Target | Hard | Resolution when exceeded |
|---|---|---|---|
| File length | ≤ 200 lines | ≤ 250 | split by conflict; extract resolvers to `resolvers/` |
| Method length | ≤ 15 lines | ≤ 25 | extract to a named private method or a util |
| Nesting depth inside a method | ≤ 1 | ≤ 1 | invert to guard clause, or promote to a port |
| Loop body length | ≤ 8 lines | ≤ 8 | extract the body to a named method |
| `else` / `elif` branches | 0 | 0 | registry, chain, or Null Object |
| Parameters per method | ≤ 3 (or 1 Context) | ≤ 4 | introduce Context |
| Methods per port | ≤ 3 | ≤ 3 | split the port (ISP) |
| Cycles in the module graph | 0 | 0 | invert the weaker edge behind a port |
| Public members per class | ≤ 5 | ≤ 7 | split by reason-to-change |
| Return points | ≤ 1 in the happy path | *not machine-checked* | review guideline; guard clauses exempt |

`else` reaches zero because every conflict has a total resolver set including `Absent`. A
`match`/`switch` used as a *registry literal* in the composition root is data, not control
flow, and is exempt.

---

## 4. The skill's own architecture demonstrates the doctrine

The skill is built the way it tells you to build. This is the primary correctness check on it.

```
code_graph_structure_skill/
├── SPEC.md                       # this file
├── .claude-plugin/plugin.json    # installable
├── agents/                       # RESOLVERS of the "who does this work?" conflict
│   ├── codegraph-cartographer.md #   → builds the graph
│   ├── codegraph-inspector.md    #   → finds violations on one dimension
│   ├── codegraph-architect.md    #   → proposes the target structure
│   ├── codegraph-adversary.md    #   → attacks the proposal
│   └── codegraph-surgeon.md      #   → applies one slice
└── skills/codegraph/
    ├── SKILL.md                  # THE CONFLICT: what does the user want? (router, ≤250 lines)
    ├── jobs/                     # THE RESOLVERS — one file per answer
    │   ├── analyze.md            #   /codegraph analyze
    │   ├── spec.md               #   /codegraph spec
    │   ├── apply.md              #   /codegraph apply
    │   ├── verify.md             #   /codegraph verify
    │   ├── fitness.md            #   /codegraph fitness — writes layer-4 tests only
    │   └── refine.md             #   the convergence loop (a callee, never a route)
    ├── specs/                    # OUTPUT CONTRACTS — the port signatures
    │   ├── graph-report.md
    │   ├── restructure-spec.md
    │   └── finding.md
    ├── references/               # COMMON UTILS — pure, depended-upon-only
    │   ├── doctrine.md           #   CPRC in operational detail
    │   ├── laws.md               #   Object Calisthenics, SOLID, connascence, GRASP
    │   ├── di-patterns.md        #   DI taxonomy + named anti-patterns
    │   ├── graph-metrics.md      #   formulas + thresholds
    │   ├── graph-tooling.md      #   exact commands, per language
    │   ├── smells.md             #   Fowler 24, Clean Code codes, architecture smells
    │   ├── arch-smells.md        #   the published architecture smells + their exact numbers
    │   ├── architecture.md       #   layering styles and the dependency rule
    │   ├── patterns.md           #   the pattern catalogue, by conflict shape
    │   ├── refactoring-moves.md  #   the mechanical move per finding
    │   ├── language-idioms.md    #   the doctrine expressed per language
    │   ├── naming.md             #   names as compressed structure
    │   ├── error-handling.md     #   failure as a conflict, not an exception
    │   ├── dead-code.md          #   reachability and orphan resolvers
    │   ├── testing-hierarchy.md  #   7 layers + contract-suite idioms
    │   ├── testing-contracts.md  #   the contract-suite shape itself
    │   └── refine-loop.md        #   convergence + stopping criteria
    └── scripts/                  # deterministic checks — never read, only run
        ├── caps.sh               #   file/method/nesting/else caps, JSON out
        ├── graph.sh              #   module graph → JSON, per language
        └── lib/                  #   the scanners and metric passes graph.sh routes to
```

`SKILL.md` is a router only: it resolves the conflict "which job?" and delegates. It never
contains job logic. Jobs never duplicate reference material; they cite it. References never
import each other. Same rule as the code it produces.

---

## 5. The test hierarchy the skill produces

Seven layers. **A test at layer *n* may not depend on any artifact of layer *n+1* or above** —
and that rule is itself enforced at layer 4.

| # | Layer | Scope | Doubles | Budget |
|---|---|---|---|---|
| 0 | Static | types, lint, caps | n/a | <30 s |
| 1 | Unit | one behaviour, real in-hexagon collaborators | ports only | <100 ms each |
| 2 | **Contract** | one port × **every** resolver, one shared suite | none | <60 s |
| 3 | Component | one hexagon via a primary port | all secondary ports | <5 min |
| 4 | **Fitness** | the graph itself: no cycles, layer direction, caps, contract registration | n/a | <60 s |
| 5 | Integration | one real adapter ↔ one real system | none for SUT | <5 min |
| 6 | E2E | critical journeys only | as few as possible | 15 min+ |

Layer 2 is the load-bearing addition and is absent from the published pyramid/trophy/honeycomb
models. It is how polymorphism becomes trustworthy: **one parameterized suite per port, every
resolver registered in it, an unregistered resolver is a build failure.** That is LSP enforced
mechanically rather than asserted in a code review.

Layer 4 is the graph as an executable test — the folder tree's claim about dependencies,
verified. Without it §2.8 is a wish.

---

## 6. Pipeline

```
/codegraph <target>
   │
   ├─ 0 SCOPE      cheap: languages, LOC, entry points, test runner, existing caps
   ├─ 1 ANALYZE    fan out N cartographer+inspector agents in parallel, one per dimension
   │               → .codegraph/graph.json, .codegraph/report.md
   ├─ 2 SPEC       architect drafts the target tree, port-by-port, slice-by-slice
   │               → .codegraph/restructure.md         ◄── STOP. User approves here.
   ├─ 3 VERIFY     adversary attacks the spec; refine loop, ≤3 passes           ─┐
   ├─ 4 APPLY      one surgeon per slice; tests green after every slice          │
   └─ 5 FITNESS    write the layer-4 tests; re-run caps + graph; report delta   ─┘
```

**Phase 2 is a hard gate.** Nothing is edited before the user approves the spec. `apply`
without an approved `.codegraph/restructure.md` refuses and runs `spec` instead.

Analysis dimensions, one agent each (parallel):
graph/cycles · caps & nesting · conditionals & type codes · DI & composition root ·
port/ISP shape · test layering & contract coverage · temporal coupling from git history.

Every agent writes its artifact to `.codegraph/` and returns **≤ 25 lines**. Bulk never
enters the orchestrator's context. That is the "summarized" requirement.

---

## 7. Finding contract

Nothing counts as a finding unless it has all seven fields. Borrowed shape: symptom → source →
consequence → remedy, plus location, ID and severity.

```
ID          CG-<dimension>-<n>
LOCATION    path:line (a range, not a file)
SYMPTOM     what is literally there
LAW         the named rule broken + its source
CONSEQUENCE what breaks or cannot change because of it
REMEDY      the exact CPRC move: conflict → port name → resolver files → context
SEVERITY    blocker | major | minor | deferred-conflict
```

A finding without a consequence and a remedy is noise and is dropped. "The current value is
the loosest possible" and "you collapsed X into one value" are **not** findings — they are
headroom, and the spec records them as `DEFERRED CONFLICT`.

---

## 8. Convergence loop

Refinement regresses without external ground truth, so the loop is gated on machine checks,
not on self-assessment.

```
budget = 3 passes
external truth = { test suite, caps.sh, graph.sh, type checker, mutation score }
each pass:  adversary attacks ONE fresh dimension (rotate, never repeat)
stop when:  no confirmed finding survives verification
        OR  externally-measured score does not improve  (accept-only-if-better)
        OR  3 passes spent
return:     best-scoring version, not the last
```

Asymmetric confirmation: a finding needs one adversary to confirm and is dropped if two
independent adversaries call it unreal. Feedback must be a rubric plus a machine-readable
stop flag, never prose.

---

## 9. Invocation

| Command | Effect |
|---|---|
| `/codegraph` | full pipeline on the repo, stopping at the phase-2 gate |
| `/codegraph analyze [path]` | phases 0–1 only. Read-only. Never edits |
| `/codegraph spec [path]` | phases 0–2. Read-only except `.codegraph/` |
| `/codegraph verify` | phase 3 on an existing spec |
| `/codegraph apply [slice]` | phases 4–5. Requires an approved spec |
| `/codegraph fitness` | write/refresh layer-4 tests only |
| `/codegraph review [path]` | findings only, no spec, no edits |

Gating: `disable-model-invocation: true`. The skill's description is never loaded into
context; nothing auto-triggers it; it appears in `/` autocomplete only.

**Deliberate deviation from the literal request:** the router does **not** set
`context: fork`. A forked subagent loses the `Agent` tool, which would kill the parallel
fan-out that phase 1 depends on. Isolation is achieved instead by contract — every heavy
job runs in a subagent (so its tool output never reaches the main context) and returns ≤25
lines with bulk on disk. Same outcome, and fan-out survives. Add `context: fork` to
`SKILL.md` only if you drop the parallel fan-out.

---

## 10. Definition of done

- [ ] `claude plugin validate . --strict` clean
- [ ] `/codegraph` never fires without an explicit `/`
- [ ] `SKILL.md` ≤ 250 lines and contains no job logic
- [ ] every reference file ≤ 600 lines, cites its sources, imports no other reference

  The 250-line law in §3 is a **code** law, and the reason is in §3's own resolution column:
  "split by conflict; extract resolvers". That resolution does not exist for prose — a reference is
  loaded whole, cited by `§`, and splitting one catalogue across two files makes a model read two
  files or miss half the rows. So prose gets its own cap, 600, enforced by
  `tests/smoke.sh` rather than asserted here. Worst today: `references/patterns.md` at 542.
  `SKILL.md` keeps the 250 cap because it is the router and is always in context.
- [ ] `scripts/caps.sh` runs on this repo and on all four first-class languages
- [ ] phase 2 gate provably blocks edits without an approved spec
- [ ] every finding the skill emits carries all seven contract fields
- [ ] the skill's own tree satisfies §2.8

## 11. Language coverage

First class — native graph tooling, real DI idiom, real contract-suite snippet:
**Python, TypeScript/JavaScript, Java/Kotlin, Go.**
Everything else: generic fallback (ripgrep caps + import-line graph + language-agnostic
CPRC), explicitly flagged as degraded in the report.
