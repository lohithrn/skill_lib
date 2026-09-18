# Structure policy — `G1`–`G10`

The structural half of the standing policy. Copied here on purpose: this skill applies the same
numbers whether or not the `md_codegraph` skill is installed, so a review works from a bare checkout.
When both are installed, `md_codegraph` owns the *restructuring* and this file owns the *verdict* — and
if the two ever disagree on a number, `md_codegraph`'s `references/laws.md` is the source and this file
is the copy that drifted. Say so in the report rather than averaging them.

---

## G1 — Hard caps

Machine-checked. Report every breach with `file:line` and the measured number.

| Metric | Warn | **Hard** | Resolution |
|---|---|---|---|
| File length | 200 | **250 lines** | split by responsibility; extract resolvers to a subfolder |
| Code files directly in one folder | 5 | **7** | name the questions hiding in the flat list, one subfolder each — subfolders themselves are never counted |
| Method length | 15 | **25 lines** | extract a *named* method, or promote the branch to a port |
| Nesting depth in a method | — | **1**, measured from the method body | guard clauses, or extract the inner block to a named method |
| Loop body length | — | **8 lines** | extract the body: the loop shows repetition, the method shows per-item behaviour |
| `else` / `elif` | — | **0** outside a registry literal | registry, chain, or Null Object |
| Parameters | 3 | **4**, or 1 Context | introduce a Context |
| Public members per class | 5 | **7** | split by reason-to-change |
| Methods per port | — | **3** | the port carries more than one question; split it (ISP) |
| Inheritance depth | — | **2** | compose instead |

**Warn breach ⇒ `minor`. Hard breach ⇒ `major`. Hard breach at ≥2× the cap ⇒ still `major`, but
first within its severity.** Nesting is measured **from the method body**, so `for` + `if` is depth 1
and legal and a guard clause removes nesting. File length and folder fan-out are measured on **code
files only** — firing them on a README teaches a reader to ignore the tool.

**Folder fan-out counts files, never folders**, because depth is the remedy and a cap on depth would
punish the fix: a folder may hold any number of subfolders. It also skips `.tf`/`.tfvars`, where the
directory *is* the module, and `.h`/`.hpp`, where a header declares what its source answers — those are
**excluded from the count, so they can never breach and never need a citation**; a `folder_files` finding
on a Terraform module or a C/C++ header folder is fabricated, not measured. The one case that is counted
and still not a defect is a **total answer set** — nine providers answering one question is the fan-out
being measured, not breached — and that is what the `<folder>/.codegraph-exempt` citation is for. A
subfolder invented only to get a
count down — `part2/`, `other/`, `misc/` — is itself a finding: it satisfies the number and destroys
the property the number exists for.

Exempt from the `else` rule: a registry literal in the composition root, and an exhaustive match
over a sealed/ADT set the compiler checks. Both are data.

**A breach may be declared exempt in the source** with `# codegraph:exempt <metrics> -- <reason>`
above the declaration, in the first 20 lines for a whole-file cap, or — for a folder, which has no
declaration to sit above — in a `.codegraph-exempt` file inside it. It must name each metric and
carry a reason; a reasonless one suppresses nothing. The breach is still reported, at severity
`exempt`. The bar is a citation, not a mood.

Source: Fowler *Refactoring* 2nd ed. (Long Function, Long Parameter List); Martin *Clean Code* G23,
G30, F1; Bay *Object Calisthenics* rules 1–4 and 9.

## G2 — Conflict → Port → Resolvers → Context

> Every conflict is an interface. Every interface has multiple implementations. Which one runs is
> decided by data, at the composition root — never by an `if` at the call site. Every implementation
> receives one immutable Context carrying the whole problem.

- **Conflict** — any point with more than one possible answer: `if/elif/else` on a type or flag, a
  switch repeated in two files, `if x is None`, a boolean parameter, an env check.
- **Port** — one interface per conflict, ≤3 methods, docstring states the conflict **as a question**,
  declared beside its caller (Separated Interface), never with its implementations.
- **Resolvers** — one per answer, one per file, in a subfolder named for the port, plus an
  `Absent`/Null resolver so the set is **total**. Totality is what deletes `else`.
- **Selector** — the `if` moves once, into data: a registry map, a `handles(ctx)` chain, or a
  visitor. A residual `if` at the call site is the finding; a `match` inside the registry is not.
- **Context** — one frozen value object per conflict family, carrying every variable the problem
  needs *including ones nothing uses yet*. That is the headroom seam.

**The promotion threshold matters as much as the doctrine.** Promote a conflict only when two
answers exist today, a second is named in a ticket, the branch crosses an I/O boundary, or the same
discriminant is switched on in ≥2 places. Otherwise record a `deferred-conflict` and move on:
over-application produces an interface farm, which is a finding under `G10`.

A guard clause that rejects bad input and returns is **not** a conflict. A one-armed `if` guarding
an optional side effect is **not** a conflict. Those stay.

Source: Fowler *Repeated Switches*, *Replace Conditional with Polymorphism*; Martin *Clean Code*
G23; Fowler *Separated Interface*; Feathers *WELC* ch.25 for *Extract Interface* — cite it as
Feathers, it is not in Fowler's 2nd-ed. catalog.

## G3 — One composition root per deployable

The only place that names concrete implementations. Constructor injection only.

Findings: more than one root in a deployable · a class constructing its own collaborators (Control
Freak) · a service locator or container passed as a parameter · ambient/global static state · field
or setter injection where the constructor could carry it · **a test that touches the container** —
if a test has to build the container, the root has leaked into the code under test.

A **local** default (a value the module owns) is fine. A **foreign** default (a database, an HTTP
client, a clock) hardcoded as a fallback is Bastard Injection.

Source: Seemann & van Deursen *DI Principles, Practices and Patterns* ch.4–6.

## G4 — Zero module cycles

A cycle between modules is a `blocker`. It cannot be unit-tested apart, cannot be extracted, and
makes build order undefined.

Measure it — never assert it. With the `md_codegraph` graph script, or a native tool (`grimp`,
`lint-imports`, `depcruise`, `jdeps`, `go list -deps`). Without one, a lexical import sweep **may
not claim a cycle count**: report `graph not measured` and say so in the verdict line. **0 edges
with unresolved imports is a failed scan, not an acyclic repo.**

Break it by extracting the interface into the lower layer and pointing both halves down at it —
additive first, never by deleting one of the two imports.

Source: Martin, Acyclic Dependencies Principle (*Clean Architecture*, component principles).

## G5 — The layer rule: the folder tree IS the graph

Layer *n* declares conflicts; layer *n+1* — a subfolder — resolves them. Edges point **down and
inward**. Folders are question nodes, files are answer nodes, imports are edges, so the tree becomes
a testable predicate.

A sideways edge between two sibling folders is a violation. In an unrestructured repo nearly every
cross-folder edge is sideways, so `3518 of 3593 illegal` is a **distance-to-target measurement, not
3518 findings** — report which folder *pair* carries the mass, because that pair is the first fix,
and cap the reported count at that.

Common utils are the floor of the graph: pure, no I/O, zero project imports, a sink node.

**`src/` is the running system and nothing else.** Only code that executes in production and what
the deploy needs belongs under `src/` — entrypoints, resolvers, ports, the utils floor. Every test,
fixture, stub, recorded response and QE harness lives in one top-level `tests/` tree; generators,
publish scripts and experiments live in sibling top-level trees, never inside the package. A
non-runtime file under `src/` ships in the artifact as dependency surface with no owner, and its
imports count as edges — so a module reachable only from its own test measures as live and survives
every dead-code pass. Flag it as a **structure** finding against the tree, not as a test finding.

## G6 — A path names its subject, its role, and its answer

`payment/processors/stripe_payment_processor.py`, never `.../stripe.py`. The path must still make
sense alone in an editor tab, an import line, and a stack frame.

Banned names: `utils` `helpers` `common` `misc` `base` `logic` `manager` `data` `info` `stuff`
`process` `handle`. A port named after its first implementation is a finding; so is `Base*` carrying
shared mutable state.

**Report only names that mislead a reader who sees them alone.** The repo's own consistent
convention is not a finding. Idiomatic brevity in Go is not a finding. A framework-mandated file
name is not a finding. Every naming suggestion must state *how* the name misleads.

## G7 — Every caught exception logs a full traceback or re-raises with the cause

A bare `except: pass`, a `catch (e) {}`, an ignored `err`, or a log line without the stack is a
**blocker**: a real failure becomes invisible and the retry budget is spent silently.

The five legal things a catch block may do: re-raise · wrap-and-raise **with the cause attached** ·
log the full stack and return a defined fallback · translate into a domain error at a boundary ·
handle a genuinely expected condition that is part of the contract. Nothing else.

Also findings here: a remote call with no timeout · unbounded retry with no ceiling · no error
boundary at the deployable's edge · resilience decorators nested in the wrong order (timeout
innermost) · an exception logged twice at two layers.

Prefer the repo's own linter rule ID as the LAW: `ruff TRY400`/`TRY401`/`BLE001`, PMD
`PreserveStackTrace`, `errcheck`, `eslint no-empty`.

## G8 — Every port has an Absent resolver, a contract suite, and a registration test

- **Absent/Null resolver** — the set of answers must be total. Totality is what lets `else` go.
- **Contract suite** — one suite per port, run against *every* resolver including Absent. It tests
  the port's promises, not one implementation's behaviour. **Never rewrite a contract suite to make
  a resolver pass**: that inverts the oracle.
- **Registration test** — a new resolver that nobody registered must fail the build, not fall
  through to the default at run time.
- **Fitness tests** — the graph claims (`0 cycles`, `1 root`, `no sideways edges`, the hard caps)
  belong in `tests/fitness/` as executable assertions. A claim no test enforces is a habit.

Ports without a contract suite are usually the largest single gap in a repo. List them by name.

Source: Meszaros *xUnit Test Patterns*; ArchUnit / `import-linter` / `dependency-cruiser` for
layer-4 assertions; Liskov & Wing for what a contract suite is verifying.

## G9 — Never delete on suspicion

Static absence of callers is **not** proof. Before any deletion suggestion, clear the dynamic-usage
safelist and say which checks ran: entry points and CLI wiring · reflection and `getattr` dispatch ·
plugin/registry auto-discovery · config- or string-driven dispatch · generated code · database
migrations · serialization names · public API and downstream consumers · test-only helpers.

Cleared ⇒ a deletion suggestion **with** its `EVIDENCE` field. Not cleared ⇒ severity `minor`, worded
as `suspicious`, and the SUGGESTION is *add a usage probe or a deprecation log*, never *delete*.

## G10 — Abstraction must pay for itself

An interface, a folder, or a registry ships only if it removes real duplication, isolates real
variation, improves testability, protects a boundary, or kills a growing selection branch.
`ThingInterface` + `DefaultThing` with one implementation and no I/O boundary **is a finding** —
speculative structure has the same carrying cost as speculative code.

**The deletion test decides it, and it is what makes this rule reportable rather than a matter of
taste:**

> Imagine the module deleted and its callers left to fend for themselves. Complexity vanishes ⇒ it was
> a pass-through, and that is the finding. Complexity reappears at N call sites ⇒ it was earning its
> keep, and there is nothing to report.

So a `G10` finding must name the call sites complexity would *not* reappear at — that count is the
SYMPTOM, and it is why `ThingInterface` + one `DefaultThing` is reportable while a one-resolver port at
a Cognito boundary is not. No named sites ⇒ no finding: you have a suspicion about an abstraction, which
is exactly the shape of the taste-based review this policy exists to prevent.

Depth is **leverage at the interface** — how much behaviour a caller reaches per unit of interface they
must learn — not implementation-lines ÷ interface-lines. Never report a ratio: it rewards padding the
body, and a fat implementation behind a small interface is the *goal*, not the defect.

And the mirror of it: **headroom is not a defect.** An env-scoped name holding one value today, a
mode knob with one mode, a per-stage resource pointing at one target, a Context field nothing reads
yet — these are deliberate seams. Record them as `deferred-conflict`, never bill them as debt, never
simplify them away, and when unsure whether a seam is intentional, **ask**. A seam the maintainer has
already confirmed belongs in `.out-of-scope/` (`references/declined.md`), so the next review does not
ask twice.

Source: Fowler *Speculative Generality*; Ousterhout *A Philosophy of Software Design* ch.4–6
(shallow modules, pass-through methods); the deletion test and depth-as-leverage from the deep-module
vocabulary in Pocock, `skills/engineering/codebase-design`.
