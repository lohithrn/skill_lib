# Doctrine — Conflict → Port → Resolvers → Context

The one transformation. Everything else this skill knows is bookkeeping around it.

> **Every conflict is an interface. Every interface has multiple implementations. Which
> implementation runs is decided by data, at the composition root — never by an `if` at the
> call site. Every implementation receives one immutable Context carrying the whole problem.**

---

## 1. Find the conflict

A **conflict** is any point in code where more than one answer is possible. Detect it, don't
intuit it. These are the surface forms, in descending order of yield:

| # | Surface form | The hidden question | Confidence |
|---|---|---|---|
| C1 | `if/elif/else` on a type, enum, flag, or string literal | "which kind of thing is this?" | high |
| C2 | The same `switch`/`match` on the same value in ≥2 files | "which variant?" (*Repeated Switches*) | highest |
| C3 | `isinstance` / `instanceof` / `kind_of?` / type assertion | "which kind, asked rudely?" | highest |
| C4 | `if x is None` / `if (!x)` / `x?.y ?? z` repeated | "what is the absent case?" | high |
| C5 | A boolean parameter that selects behaviour | "which of two behaviours did the caller want?" | highest |
| C6 | `if env == "prod"` / feature-flag read in business logic | "which environment/tenant/rollout?" | high |
| C7 | `try/except` where the handler does real alternative work | "what do we do when the world says no?" | high |
| C8 | Two blocks differing in exactly one operation | "which policy?" | medium |
| C9 | A long `if` chain of unrelated predicates | "who claims this input?" (open set) | high |
| C10 | Behaviour that depends on a mutable status field | "which state are we in?" | high |
| C11 | Direct construction of an I/O client inside business logic | "which side of the boundary is this?" | highest |
| C12 | `# TODO: also handle …`, or a ticket naming a second case | a conflict that has not arrived yet | medium |
| C13 | A `dict`/`switch` mapping a key to a *behaviour name* | already a registry — extract the port | medium |
| C14 | Duplicated validation with slightly different rules | "which invariant applies here?" | medium |

### Not a conflict — leave these alone

- A **guard clause** that rejects bad input and returns/raises immediately.
- A one-armed `if` gating an optional side effect (logging, metrics, cache warm).
- A **pure value selection** with no behaviour: `limit = requested or DEFAULT`.
- A **registry literal** in the composition root. That `match` is data, not control flow.
- Exhaustive pattern matching over a **sealed/ADT closed set** where the language checks
  totality at compile time. That is already polymorphism, done by the type system.
- A loop's termination condition.

---

## 2. The promotion threshold — the most important rule here

Promoting every conflict produces an unreadable interface farm and a slower, harder codebase.
Promote a conflict only if **at least one** of these holds:

1. **Two answers exist today.** Two real branches with different behaviour.
2. **A second answer is named** in a ticket, roadmap, `TODO`, or the user's own words.
3. **The branch crosses an I/O boundary** — network, disk, clock, randomness, environment,
   subprocess, message bus. Always promote. This is what makes the hexagon testable and is
   the single highest-value application of the doctrine.
4. **The discriminant is switched on in ≥2 places** (C2). Promote even if there are only two
   answers; the duplication is the cost.
5. **The branch is inside a method that already exceeds a hard limit** and cannot be brought
   under it by guard clauses and extraction alone.

Otherwise: guard clause, extracted named method, dict lookup, or leave it.

Record every non-promotion as a **`DEFERRED CONFLICT`** in the spec, with the reason and the
trigger that would promote it. A deferred conflict is a **named seam, not debt** — it is
documented headroom. Never report it as a finding. Never "simplify" it away.

### The counter-arguments you must hold at the same time

- **YAGNI** (Fowler): building for a presumptive feature costs the build, the drag of carrying
  it, and the cost of removing it. The threshold above is YAGNI's answer: a *named* second
  case is not presumptive.
- **"Duplication is far cheaper than the wrong abstraction"** (Sandi Metz). If you cannot name
  the question the port answers, you do not yet know the abstraction. Duplicate, wait, then
  extract. Prefer **Shameless Green** first.
- **Ousterhout's shallow-module argument.** A port whose interface is as large as its one
  implementation is negative value — it adds an edge and hides nothing. Ports must be *deep*:
  small interface, meaningful implementation.
- **Lasagna code.** N layers of one-line delegation is worse than the `if` it replaced.
  Ousterhout's **pass-through method** red flag applies: if a resolver only forwards to
  another object, the port is at the wrong altitude.

---

## 3. Name the port as a question

Each promoted conflict becomes exactly **one** interface — a **port**.

- The port's docstring **states the conflict as a question.** If you cannot phrase it as one
  question, it is several conflicts; split the port (ISP).
- **≤ 3 methods.** Go proverb: "The bigger the interface, the weaker the abstraction."
- The port lives in the **declaring** layer, beside its caller — not with its implementations.
  Callers depend on the question; only the composition root depends on the answers. That is
  DIP's second half, and Fowler's **Separated Interface** pattern by name.
- Name it for the **role**, not the mechanism: `PriceSource`, not `PriceStrategyManager`.
  Reject `-er` bags: `Manager`, `Helper`, `Util`, `Processor`, `Handler`, `Coordinator` as
  *port* names. (Bugayenko's rule; contested for classes, sound for ports.)
- **Intention-revealing** (Evans): the name must let a caller predict behaviour without
  reading an implementation.

```python
class PriceSource(Protocol):
    """Which price applies to this line item, for this customer, right now?"""
    def price_for(self, ctx: PricingContext) -> Money: ...
```

One question. One method. One argument.

---

## 4. One resolver per answer, one file each, in a named subfolder

Every branch of the original conditional becomes one **resolver** — a class implementing the
port, alone in its own file, inside a subfolder named for the port.

```
pricing/
├── price_source.py            # the port: the question
├── pricing_context.py         # the Context: the problem's variables
├── pricing_service.py         # the caller: imports the port ONLY
└── sources/                   # the answers
    ├── __init__.py            #   registry — the only place the answers are named
    ├── list_price.py
    ├── contract_price.py
    ├── promotional_price.py
    └── absent_price.py        #   Null Object: total resolver set
```

Rules:

- **One resolver per file.** File name = resolver name, snake/kebab per language convention.
- **A resolver may not import a sibling resolver.** Siblings are alternatives, not collaborators.
  If one needs another, it is a Decorator and belongs in `decorators/`, or the port is split wrong.
- **A resolver may not import the registry.** Edges point one way.
- **Every port ships an `Absent`/`Null`/`NoOp` resolver** making the resolver set *total*. This
  is what deletes `else` and `if x is None` from callers instead of relocating them.
- A resolver's body should be **≤ 15 lines and ≤ 1 nesting level**. If it is not, the resolver
  itself contains a conflict — recurse.
- **Nothing outside the composition root and the registry may import a resolver module.**
  Enforced as a layer-4 fitness test, not a habit.

### Decorators, not flags

Cross-cutting variation (retry, cache, log, timing, auth, rate-limit) is **never** a branch
inside a resolver and never a constructor flag. It is a decorator implementing the same port
and wrapping another instance of it. Composition order is declared once, in the composition root.

```
sources/decorators/
├── cached_price.py       # PriceSource -> PriceSource
├── retried_price.py
└── audited_price.py
```

---

## 5. Move the `if` into data — the selector

The conditional does not vanish. It **moves once**, from control flow into data, and lands in
exactly one of three shapes:

| Selector | Use when | Shape |
|---|---|---|
| **Registry** | discriminant is a closed, known set | `dict[Key, Port]`, or `EnumMap`, or a sealed-interface exhaustive `match` in the root |
| **Chain of responsibility** | discriminant is open, or predicates overlap | each resolver answers `handles(ctx) -> bool`; first match wins; `Absent` is last and always matches |
| **Double dispatch / Visitor** | two type axes vary together | visitor over a closed element set |

A residual `if` at the **call site** is a violation. A `match` in the **registry** is not.

```python
# registry — data, not control flow
SOURCES: Mapping[PriceKind, PriceSource] = {
    PriceKind.LIST:        ListPrice(),
    PriceKind.CONTRACT:    ContractPrice(repo),
    PriceKind.PROMOTIONAL: PromotionalPrice(clock),
}
# call site — no branch at all
price = SOURCES.get(ctx.kind, ABSENT_PRICE).price_for(ctx)
```

**Registration must be impossible to forget.** Prefer a mechanism where adding a resolver file
without registering it fails a test: decorator-based registration plus a coverage assertion, a
subclass walk, an `ArchUnit` rule, or a glob-count assertion. See `testing-contracts.md`.

---

## 6. The Context carries the whole problem

Every resolver takes **exactly one argument**: an immutable Context value object carrying every
variable the problem needs — *including variables no resolver uses yet*.

```python
@dataclass(frozen=True, slots=True)
class PricingContext:
    """Everything a price decision may need to know."""
    customer_id: CustomerId
    sku: Sku
    quantity: Quantity
    as_of: datetime          # never call the clock inside a resolver
    channel: Channel
    currency: Currency
    tenant: TenantId         # unused by every resolver today — deliberate headroom
```

Why this is load-bearing:

- **It is the headroom seam.** Adding a field to the Context is additive. Adding a parameter to
  five resolvers is a breaking change across five files plus their tests. This is precisely what
  lets a resolver node be replaced without re-plumbing its neighbours.
- It kills **Long Parameter List** and **Data Clumps** in one move (Fowler: *Introduce Parameter
  Object*, *Preserve Whole Object*).
- It kills **hidden temporal coupling** and ambient state: no resolver reads a clock, an env var,
  a global, or a request-local. If it is needed, it is in the Context, put there by the caller.
- It makes every resolver a **pure function of one value**, so unit tests are one construction
  and one call.

Rules: frozen/readonly; **no I/O**; no methods beyond derived read-only properties; primitives
wrapped as **Value Objects** (`Money`, `Sku`, `TenantId`) not `str`/`float`; named for the
question's domain (`PricingContext`), never `Params`, `Options`, `Args`, `Config`, `Data`.
Provide a `with_*`/`replace` copy helper, never a setter.

**Do not** let the Context become a god bag. One Context per conflict family, not one per app.
If two conflicts need disjoint halves of a Context, that is two Contexts.

---

## 7. One composition root

One file per deployable binary. The only place that names concrete resolvers, opens
connections, reads env, and decides decorator order.

```python
def wire(env: Mapping[str, str]) -> Application:
    clock  = SystemClock()
    repo   = PostgresContractRepo(dsn=env["DSN"])
    prices = {
        PriceKind.LIST:     ListPrice(),
        PriceKind.CONTRACT: Cached(Retried(ContractPrice(repo)), ttl=60),
    }
    return Application(PricingService(Registry(prices, ABSENT_PRICE)))
```

Rules (Seemann):

- **Only applications have composition roots.** Libraries and frameworks must not.
- **Pure DI first.** Reach for a container only when hand-wiring genuinely doesn't scale, and
  then reference the container *only* from the root.
- **Constructor injection only.** Field/property injection hides dependencies and defeats
  immutability (Sonar `S6813`). Setter injection means an object can exist half-built.
- Named anti-patterns to reject on sight: **Service Locator**, **Ambient Context**,
  **Control Freak** (`new` inside business logic), **Bastard Injection** (a "convenient"
  default concrete dependency), **Constrained Construction**, **captive dependency**
  (a long-lived object holding a short-lived one).
- **If a test must touch the container to build a unit, the root has leaked** and the unit is no
  longer independently testable. That is a blocker finding.

---

## 8. Common utils — the floor of the graph

`utils/` (or `common/`, `kernel/`) is pure: total functions, value objects, no I/O, no ports,
**zero project imports**. Everything may depend on it; it depends on nothing.

- If a util needs a dependency, it is not a util — it is a service with a port.
- If a util has an `if` on an enum, it is a conflict; promote it out of utils.
- Utils are the only place duplication is genuinely cheaper than abstraction, and the only
  layer exempt from the port doctrine.
- A cycle through utils is a blocker. Utils are a sink node, always.

---

## 9. The layer rule — the folder tree *is* the graph

> Layer *n* **declares** conflicts. Layer *n+1* — a **subfolder** of *n* — **resolves** them.
> Edges point down (into subfolders) and inward (toward utils). Never sideways between
> sibling resolvers. Never up from a resolver to its caller.

Consequences, all machine-checkable:

1. **A folder is a question node.** Its name is the conflict it owns.
2. **A file is an answer node.** One answer per file.
3. **An import is an edge.** The legal edge set is a predicate over paths.
4. **Depth = specificity.** The deeper you go, the more concrete and the more replaceable.
5. **Reading the tree predicts the graph.** If it does not, the tree is a lie and the tree is
   what gets fixed — not the rule.

This is the whole of "code should feel like a knowledge graph." Traversing folders is
traversing the question/answer graph, and layer-4 fitness tests assert the traversal is legal.

---

## 10. Inheritance and polymorphism, honestly

The instruction is "inheritance and polymorphism everywhere." Delivered as:

- **Polymorphism everywhere — yes.** Every promoted conflict dispatches on type or on a
  registry, never on a call-site branch.
- **Interface implementation everywhere — yes.** Every resolver implements a port.
- **Abstract base + Template Method — yes, narrowly.** Only over a *stable, abstract,
  stateless* base, and only when the varying steps genuinely outnumber the fixed ones.
  Prefer **hook methods** with empty defaults over forcing `super()` calls.
- **Concrete class inheriting concrete class — no.** That is the fragile base class problem.
  GoF: "favor object composition over class inheritance." Reuse arrives by **composition and
  delegation**; substitutability arrives by **interfaces**.
- **Depth ≤ 2** in any implementation hierarchy (port → resolver). Depth ≥ 3 is a finding.
- **`super()` in a resolver is a smell.** It couples the child to the parent's execution order
  — connascence of algorithm plus of timing.
- **Refused Bequest is a blocker**: a subclass that ignores, guts, or raises on inherited
  behaviour is an LSP violation and must become a sibling resolver instead.

The one place deep hierarchies are correct: **contract test suites**. Every resolver inherits
its port's shared test suite and must pass it unmodified. That is the only inheritance whose
whole purpose is to be substitutable, and it is where LSP gets *enforced* rather than asserted.

### And when polymorphism is the wrong answer

The **expression problem**: subtype polymorphism makes adding a *case* cheap and adding an
*operation* expensive; algebraic data types with exhaustive matching make adding an *operation*
cheap and adding a *case* expensive.

- Cases will grow, operations are stable → **ports + resolvers** (this doctrine).
- Operations will grow, cases are fixed and few → **sealed interface / ADT + exhaustive match**,
  or a **Visitor**. A sealed hierarchy with compile-checked totality is *already* the doctrine,
  enforced by the compiler. Do not convert it into runtime dispatch to satisfy a rule.

State which side of this you chose, in the spec, per port.
