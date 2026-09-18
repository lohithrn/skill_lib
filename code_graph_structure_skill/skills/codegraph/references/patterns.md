# Patterns — the named resolutions for a conflict

Every entry below is read through the doctrine: **a conditional is a conflict; a conflict
becomes a port; each branch becomes one resolver in its own file; selection is data at the
composition root; every resolver takes one immutable Context.** A pattern is only worth
naming here if it tells you *which shape of conflict it dissolves*.

Citations are to the primary source. Where a popular claim is wrong, it is corrected in place.

---

## 1. The 23 GoF patterns

Gamma, Helm, Johnson, Vlissides, *Design Patterns: Elements of Reusable Object-Oriented
Software* (Addison-Wesley, 1994). Intents are close paraphrases of the book's Intent section.

### 1.1 Creational

| Pattern | Intent (GoF) | Conflict as a question | Kills a conditional? |
|---|---|---|---|
| **Abstract Factory** | Provide an interface for creating families of related or dependent objects without specifying their concrete classes. | "Which whole *family* of collaborators are we running with?" | Yes — removes one `if` per product from every construction site, replacing N branches with one factory choice. Two axes (family × product) collapse to one selection. |
| **Factory Method** | Define an interface for creating an object, but let subclasses decide which class to instantiate; defer instantiation to subclasses. | "Which concrete thing does this abstract step need?" | Yes for `if kind == …: return X()`. But the subclass-per-choice form re-hides selection in a type hierarchy; a data-driven registry (§6) is usually the better resolver. |
| **Builder** | Separate the construction of a complex object from its representation so that the same construction process can create different representations. | "Which representation should this same assembly process emit?" | Yes — removes format/variant branches from inside the assembly loop; the Director walks parts once, the Builder resolver decides output. |
| **Prototype** | Specify the kinds of objects to create using a prototypical instance, and create new objects by copying that prototype. | "Which pre-configured starting state do we want?" | Yes — replaces a `switch` over configurations with a registry of cloneable exemplars. This *is* the doctrine's selector map with instances instead of factories. |
| **Singleton** | Ensure a class has only one instance and provide a global point of access to it. | "Who owns the single instance?" — a question the composition root already answers. | **No — it adds hidden coupling.** Rejected under DI: see §1.4. |

### 1.2 Structural

| Pattern | Intent (GoF) | Conflict as a question | Kills a conditional? |
|---|---|---|---|
| **Adapter** | Convert the interface of a class into another interface clients expect, letting classes work together that couldn't otherwise because of incompatible interfaces. | "How does *this* foreign shape satisfy our port?" | Yes — one adapter per foreign vendor replaces `if vendor == "stripe": … elif "adyen": …`. Canonical resolver-per-integration. |
| **Bridge** | Decouple an abstraction from its implementation so that the two can vary independently. | "Which two axes are varying together, and can they vary separately?" | Yes — turns an M×N conditional matrix (or class explosion) into M + N. The named cure for nested conditionals on two independent axes. |
| **Composite** | Compose objects into tree structures to represent part-whole hierarchies; let clients treat individual objects and compositions of objects uniformly. | "Is this one thing or many?" | Yes — deletes `if isinstance(node, Leaf)` everywhere. See §2.3. |
| **Decorator** | Attach additional responsibilities to an object dynamically; provide a flexible alternative to subclassing for extending functionality. | "Which optional cross-cutting behaviours wrap this call, in what order?" | Yes — replaces `if cache_enabled … if retry … if audit …` with a composed wrap list built from data. See §2.6. |
| **Facade** | Provide a unified interface to a set of interfaces in a subsystem; define a higher-level interface that makes the subsystem easier to use. | "What is the one sanctioned way in?" | Indirectly — removes call-order and setup branching from every client by having exactly one entry. |
| **Flyweight** | Use sharing to support large numbers of fine-grained objects efficiently. | "Which part of this state is intrinsic (shareable) and which extrinsic (per-use)?" | Not a conditional cure; it is a Context-purity cure — forces the immutable/shared split the doctrine wants. |
| **Proxy** | Provide a surrogate or placeholder for another object to control access to it. | "Should access to the real subject be mediated (lazily, remotely, or by permission)?" | Yes — removes `if not loaded: load()` and `if not allowed: raise` from callers. |

### 1.3 Behavioural

| Pattern | Intent (GoF) | Conflict as a question | Kills a conditional? |
|---|---|---|---|
| **Chain of Responsibility** | Avoid coupling the sender of a request to its receiver by giving more than one object a chance to handle it; chain the receiving objects and pass the request along until one handles it. | "Who, of an *open* set of candidates, handles this?" | Yes — the named cure for a long `if` chain of unrelated predicates. Order lives in the chain's data, not in `elif` order. |
| **Command** | Encapsulate a request as an object, thereby letting you parameterize clients with different requests, queue or log requests, and support undoable operations. | "Which action was asked for, and can it be stored, retried, or undone?" | Yes — a dispatch `switch` becomes a name→Command map; undo/queue/log stop being flags. |
| **Interpreter** | Given a language, define a representation for its grammar along with an interpreter that uses the representation to interpret sentences in the language. | "What did the user's expression mean?" | Yes — moves branching out of code into a *composable AST of resolvers*; Specification (§2.8) is Interpreter for booleans. |
| **Iterator** | Provide a way to access the elements of an aggregate object sequentially without exposing its underlying representation. | "How is this collection traversed?" | Yes — removes `if is_list … elif is_tree …` from every traversal; in Python/JS/Java this is a language feature, not a hand-built pattern. |
| **Mediator** | Define an object that encapsulates how a set of objects interact; promote loose coupling by keeping objects from referring to each other explicitly. | "Where does the interaction *policy* between these peers live?" | Yes — pulls "if the other widget is in state X" out of every peer into one place. Risk: the mediator becomes a god object. |
| **Memento** | Without violating encapsulation, capture and externalize an object's internal state so that the object can be restored to this state later. | "How do we get back to a previous state without exposing internals?" | Marginal on conditionals; central to immutability — snapshots instead of mutable rollback flags. |
| **Observer** | Define a one-to-many dependency between objects so that when one object changes state, all its dependents are notified and updated automatically. | "Who cares that this happened?" | Yes — removes the publisher's `if listener_a … if listener_b …`. Subscribers are registration data. |
| **State** | Allow an object to alter its behavior when its internal state changes; the object will appear to change its class. | "Which state is this object *in*, and what does that state permit?" | Yes — the named cure for behaviour keyed off a mutable status field. Difference from Strategy: State objects own the *transitions*; Strategy is chosen once from outside. |
| **Strategy** | Define a family of algorithms, encapsulate each one, and make them interchangeable; Strategy lets the algorithm vary independently from clients that use it. | "Which algorithm/policy does this caller want?" | Yes — the archetype. Port + resolvers + injected choice *is* Strategy. |
| **Template Method** | Define the skeleton of an algorithm in an operation, deferring some steps to subclasses; let subclasses redefine certain steps without changing the algorithm's structure. | "Which step of this fixed sequence differs?" | Yes, but via inheritance. Prefer the same skeleton with injected step-ports ("Strategy-ized Template Method") so resolvers stay composable and testable. |
| **Visitor** | Represent an operation to be performed on the elements of an object structure; let you define a new operation without changing the classes of the elements on which it operates. | "Which *operation* runs over this fixed set of node types?" | Yes — removes the type `switch` from every traversal. See §2.1. |

### 1.4 Why Singleton is rejected under DI

Singleton conflates two questions — *how many instances exist* (a lifetime concern the
composition root owns) and *how callers reach it* (global static access). Keeping the first
and deleting the second gives you "single instance registered in the container," which is
correct. Keeping the second gives you a Service Locator or Ambient Context.

- **Service Locator.** Fowler (*Inversion of Control Containers and the Dependency Injection
  Pattern*, 2004) presents Service Locator and Dependency Injection as the two options;
  Mark Seemann's rebuttal is the standard citation: "the problem with Service Locator is
  that it hides a class' dependencies, causing run-time errors instead of compile-time
  errors," and it "becomes unclear when you would be introducing a breaking change." His
  API argument: `new OrderProcessor()` compiles and then throws at runtime, so "we can't
  reasonably claim that this sort of API provides a positive developer experience." Later
  addenda: it *violates SOLID* (2014) and *violates encapsulation* (2015).
- **Ambient Context** (Seemann, *Dependency Injection in .NET*) is the same defect wearing a
  typed static property — `DateTimeProvider.Current`, `Clock.now()`, a static logger. It
  makes the dependency invisible in the signature and makes tests order-dependent.
- Under the doctrine the concrete harm is precise: a Singleton/locator call inside a resolver
  is a **dependency not carried by the Context**, so the resolver is no longer substitutable
  and the composition root no longer describes the system.

---

## 2. The patterns asked about, in depth

### 2.1 Visitor

**Intent.** Represent an operation to be performed on the elements of an object structure,
so new operations can be added without changing the element classes.

**Structure.** `Element.accept(Visitor v)` calls `v.visitFoo(this)`. Two dispatches: the
first on the element's runtime type (virtual `accept`), the second on the visitor's runtime
type (`visitFoo` overload chosen statically per element type). That is **double dispatch**,
simulated in single-dispatch languages.

```python
class Node:            def accept(self, v): raise NotImplementedError
class Num(Node):       def accept(self, v): return v.visit_num(self)
class Add(Node):       def accept(self, v): return v.visit_add(self)

class Eval:            # one resolver = one operation over the whole set
    def visit_num(self, n): return n.value
    def visit_add(self, n): return n.left.accept(self) + n.right.accept(self)
```

**Expression problem** (Wadler, 1998, verbatim): "The goal is to define a datatype by cases,
where one can add new cases to the datatype and new functions over the datatype" — and to do
so "without recompiling existing code, and while retaining static type safety (e.g., no
casts)." His table picture: cases are rows, functions are columns; functional languages fix
the rows and let you add columns, OO fixes the columns and lets you add rows.

**Use when** the *element set is closed* and the *operation set is open* (AST passes, IR
lowering, pretty-printers, type-checkers, serializers over a fixed schema).

**Wrong when** the element set changes: adding one node type edits *every* visitor
interface and every implementation — a fan-out change, exactly the coupling the doctrine
otherwise forbids. Also wrong when the operation needs to see combinations of nodes
(Goetz: pattern matching "composes better"; nested cases in visitors get "quite messy and
error-prone"). Also poor when elements must not expose the state the visitor needs.

**Acyclic Visitor** (Robert C. Martin, 1996) breaks the element→visitor-interface dependency
cycle: the base `Visitor` is a degenerate/marker interface, each element declares its own
`FooVisitor` interface, and `accept` does a *safe downcast* — `if (v instanceof FooVisitor)`.
Cost: dispatch becomes a runtime cast and exhaustiveness is lost; benefit: a visitor may
handle a subset, and new elements don't force edits to existing visitors.

**Modern replacement on closed sets:** sealed interface + records + exhaustive `switch`
pattern matching (§6).

### 2.2 Delegation

**Intent.** An object forwards a request to a *delegate* it holds, so behaviour is chosen by
composition instead of inheritance. Not a GoF chapter pattern (GoF discusses it as a
technique in §1.6, "Inheritance versus Composition"), but the mechanism under Strategy,
State, Decorator, Proxy and Bridge.

**Language idioms.**
- Kotlin: `class Repo(db: Db) : Db by db` — compiler-generated forwarding; also property
  delegation (`by lazy`, `by Delegates.observable`).
- Ruby: `require 'forwardable'; extend Forwardable; def_delegators :@list, :size, :<<` (and
  `Delegator`/`SimpleDelegator` from `delegate`).
- Python: `__getattr__` forwarding, or `functools.wraps` for function-level.
- Go: struct embedding (promoted methods) — delegation with implicit forwarding.
- C#/Java: hand-written forwarders, or Lombok `@Delegate`.

**Fowler refactorings.** *Replace Superclass with Delegate* (1st ed: **Replace Inheritance
with Delegation**) — when a subclass uses only part of its superclass or the superclass is
not a true generalization. *Replace Subclass with Delegate* (new in 2nd ed) — when a subclass
hierarchy encodes one axis of variation you'd rather vary at runtime, or when a second axis
arrives and inheritance can only express one. Inverse pair: *Hide Delegate* / *Remove Middle
Man*, which is the honest tension — too much delegation produces the Middle Man smell.

### 2.3 Composite

**Intent.** Compose objects into tree structures; let clients treat individual objects and
compositions uniformly.

**How it kills the conditional.** Before: every traversal contains `if isinstance(node,
Leaf): total += node.cost else: total += sum(c.cost() for c in node.children)`. After: both
`Leaf.cost()` and `Group.cost()` implement the same port, and the client calls `cost()` with
no branch. The recursion lives in one resolver.

**Uniformity vs type-safety (GoF's own trade-off, "Consequences" §2).** Putting `add`/`remove`
/`getChild` on the *Component* maximizes uniformity — clients never branch — but a `Leaf.add`
must fail at runtime. Putting them only on *Composite* is type-safe but forces clients to
know which they hold, reintroducing the cast/branch. Ruling for this skill: put child
management on Composite only, and give Component a read-only `children()` returning empty
for leaves; then clients still don't branch, and no method lies.

### 2.4 Builder — GoF vs Bloch vs Fluent Interface

**GoF Builder** varies the *representation*: one Director walks the parts in a fixed order,
and interchangeable Builders emit different products (`RTFReader` → `TeXConverter` /
`ASCIIConverter`). The conflict is "which output form?", and Builders are resolvers.

**Bloch Builder** (*Effective Java*, Item 2: "Consider a builder when faced with many
constructor parameters") solves a different problem: telescoping constructors and the
JavaBeans setter pattern. One product, one builder, many optional parameters, validity
checked in `build()`, product immutable. There is no family of builders and no Director.

```java
Pizza p = new Pizza.Builder(Size.LARGE).addTopping(HAM).sauceInside().build();
```

**Fluent Interface is not the same thing, but not for the reason usually cited.** Fowler's
*FluentInterface* bliki (2005, named in a workshop with Eric Evans) does **not** contain a
Builder contrast — the frequently repeated "Fowler says a fluent interface is not a builder"
is a misattribution. What the bliki actually says: "many people seem to equate fluent
interfaces with Method Chaining," and "Certainly chaining is a common technique to use with
fluent interfaces, but true fluency is much more than that." His test: "The key test of
fluency, for us, is the Domain Specific Language quality," with "the intent … to do something
along the lines of an internal DomainSpecificLanguage."

**The Builder/fluent separation lives in *Expression Builder*** (Fowler, *Domain-Specific
Languages*, ch. 32; dslCatalog): "An object, or family of objects, that provides a fluent
interface over a normal command-query API." The point is *layering* — "the fluent interface
is clearly isolated," and the domain model keeps a clean command-query API underneath.

**The CQS warning, verbatim from the bliki:** "The common convention in the curly brace world
is that modifier methods are void," which he likes "because it follows the principle of
CommandQuerySeparation," then: "This convention does get in the way of a fluent interface, so
I'm inclined to suspend the convention for this case." He also concedes "Fluent interfaces
lead to methods that make little sense individually" (ExpressionBuilder), and hedges: "I
haven't seen a lot of fluent interfaces out there yet, so I conclude that we don't know much
about their strengths and weaknesses."

### 2.5 Fluent Interface / method chaining / internal DSL

**Right when:** test data builders (`aUser().inOrg(acme).withRole(ADMIN).build()`), query
construction (SQLAlchemy, jOOQ, LINQ), mock expectations (JMock/Mockito), pipeline/middleware
assembly, and configuration DSLs — all cases where a *whole expression* is the unit of
meaning and the result is read far more often than debugged.

**Costs:** (a) debuggability — one statement, one stack frame, no intermediate names, poor
breakpoints; (b) CQS violation — setters return `this`, so you cannot tell a query from a
command; (c) subclassing is hard — chained methods return the base type, so a subclass loses
its type mid-chain (the self-type / F-bounded-generics problem, `<T extends Builder<T>>`); (d)
half-built objects are observable unless the fluent layer is a separate Expression Builder;
(e) IDE/error messages degrade because individual methods are meaningless.

**Rule for this skill:** a fluent surface is allowed *only* as a separate layer (Expression
Builder) over a command-query API, and it must terminate in one `build()`/`execute()` that
validates. Never make the resolver interface itself fluent.

### 2.6 Decorator vs Proxy vs Adapter, and stacking order

All three wrap one object and implement one interface. The discriminating rule is
**intent + who controls the wrappee's lifetime + does the interface change**:

| | Interface vs wrappee | Intent | Who supplies the wrappee | Count |
|---|---|---|---|---|
| **Adapter** | **Different** (converts) | Make an incompatible thing fit an expected port | Caller supplies the foreign object | Usually one |
| **Decorator** | **Same** (adds behaviour) | Add responsibilities dynamically, composably | Caller supplies; wrapper adds to it | **Stackable, N deep** |
| **Proxy** | **Same** (controls access) | Control *whether/when/where* the real call happens (lazy, remote, protection, caching) | **Proxy usually creates/owns or locates** the subject | Usually one |

One-sentence test: *Adapter changes the interface. Decorator adds to the behaviour. Proxy
governs access to the subject.* If callers can't tell the wrapper from the wrappee and you can
apply it twice meaningfully, it's a Decorator.

**Stacking order matters and must be data, not code.** Innermost is closest to the real call.
Canonical order for an outbound call:

```
Logging( Metrics( CircuitBreaker( Retry( Timeout( Cache( Real ))))))
```
- **Retry inside CircuitBreaker**: the breaker should see the *final* outcome of the retry
  budget, otherwise every logical call inflates the failure count.
- **Timeout inside Retry**: each attempt must be individually bounded.
- **Cache innermost-but-one**: a cache hit should skip retry/timeout entirely — placing Cache
  *outside* Retry is also defensible; decide once and record it.
- **Logging/Metrics outermost**: they must observe total latency including retries.

Build the stack by folding a list of decorator names from config: `reduce(lambda inner, name:
DECORATORS[name](inner), reversed(cfg.middleware), real)`.

### 2.7 Null Object / Special Case

- **Null Object** — Bobby Woolf, in *Pattern Languages of Program Design 3* (Addison-Wesley,
  1997): provide an object with neutral ("do nothing") behaviour to stand in for the absence
  of a real object, so callers need no null test. GoF-adjacent, not in GoF.
- **Introduce Special Case** — Fowler, *Refactoring* 2nd ed.; catalog alias listed as
  **Introduce Null Object** (renamed because "null" is only the commonest special case;
  "unknown customer", "anonymous user", "zero money", "vacant slot" are the same shape).
  PoEAA also carries **Special Case**: "A subclass that provides special behavior for
  particular cases."

```python
class NullCustomer(Customer):
    name = "occupant"
    def is_unknown(self): return True
    def billing_plan(self): return BasicPlan()
```

Use when the same `if x is None` (or `if x == UNKNOWN`) test repeats in more than one caller.
Do **not** use when absence is an *error* that must halt the flow — then the answer is a
Result/Either (§3) or an exception at the boundary, not a silent no-op. Null Object that
swallows a required action is a bug factory.

### 2.8 Specification

**Intent.** Reify a predicate as a first-class object so that business rules can be named,
tested, combined and passed around. Eric Evans & Martin Fowler, *Specifications* (1997);
Evans, *Domain-Driven Design* (2003), ch. 9; Jimmy Nilsson, *Applying Domain-Driven Design
and Patterns* (2006), for the query/persistence-facing variant.

Three uses Evans names: **validation** (does this object satisfy the rule?), **selection /
querying** (find all objects satisfying it), and **construction-to-order** (build something
that satisfies it).

**This is the doctrine applied to boolean logic.** A compound `if` is a conflict; the port is
`Specification.is_satisfied_by(candidate) -> bool`; each clause is one resolver in its own
file; `And`/`Or`/`Not` are composite resolvers; the composition root assembles the rule from
data. It is Composite + Interpreter over `bool`.

```python
class Spec(Protocol):
    def is_satisfied_by(self, c: Ctx) -> bool: ...
class And(Spec):
    def __init__(self, *s): self.s = s
    def is_satisfied_by(self, c): return all(x.is_satisfied_by(c) for x in self.s)
class Not(Spec): ...
class Or(Spec): ...

OVERDUE = And(InvoiceUnpaid(), DueBefore(days=30), Not(DisputeOpen()))
```

Costs: a spec tree is slower and harder to translate to SQL than a query — hence Nilsson's
double-dispatch/"specification-to-query" variants; and a spec that needs I/O to answer is no
longer a pure predicate, so put the data it needs in the Context.

### 2.9 Fowler PoEAA — the doctrine's own vocabulary

Exact catalog intents (martinfowler.com/eaaCatalog):

| Pattern | Fowler's one-line intent | Role in the doctrine |
|---|---|---|
| **Separated Interface** | "Defines an interface in a separate package from its implementation." | **The literal PoEAA name for "port lives in the declaring layer, resolvers live elsewhere."** |
| **Plugin** | "Links classes during configuration rather than compilation." | **The literal name for "which resolver runs is decided by data at the composition root."** |
| **Registry** | "A well-known object that other objects can use to find common objects and services." | The selector map. Caution: a registry reached *statically* from inside a resolver degenerates into Service Locator (§1.4); it must be read only by the composition root. |
| **Service Stub** | "Removes dependence upon problematic services during testing." | The test resolver for every port that crosses a boundary. |
| **Layer Supertype** | "A type that acts as the supertype for all types in its layer." | Where the Context base and shared resolver scaffolding live — keep it thin or it becomes Interface Bloat. |
| **Gateway** | "An object that encapsulates access to an external system or resource." | One port per external system; vendor differences become resolvers. |
| **Mapper** | "An object that sets up a communication between two independent objects." | Keeps two models from branching on each other; neither side knows the other. |
| **Repository** | "Mediates between the domain and data mapping layers using a collection-like interface for accessing domain objects." | The persistence port. |
| **Unit of Work** | "Maintains a list of objects affected by a business transaction and coordinates the writing out of changes and the resolution of concurrency problems." | Transaction boundary as an object. |
| **Service Layer** | "Defines an application's boundary with a layer of services that establishes a set of available operations and coordinates the application's response in each operation." | Where the composition root's use cases live. |
| **Data Transfer Object** | "An object that carries data between processes in order to reduce the number of method calls." | Wire shape; not the Context. |
| **Value Object** | "A small simple object, like money or a date range, whose equality is not based on identity." | The building block of an immutable Context. |

---

## 3. Top 25 patterns as actually used today

Ranking synthesises current teaching/usage sources (refactoring.guru and sourcemaking
catalogs, PoEAA, POSA, Azure/AWS cloud pattern catalogs, and modern language guides) against
what appears in mainstream framework APIs. GoF and non-GoF are interleaved deliberately.

| # | Pattern | One-line intent | Conflict as a question | Language idiom |
|---|---|---|---|---|
| 1 | **Dependency Injection** | Supply a component's collaborators from outside instead of letting it construct or locate them. | "Who decides which implementation this code runs against?" | Spring/Guice/Dagger, .NET `IServiceCollection`, Python constructor args + `dependency-injector`, NestJS providers, Go plain constructor functions / wire |
| 2 | **Strategy** | Encapsulate interchangeable algorithms behind one interface. | "Which policy does the caller want?" | Interface + impls; Python/JS/Go: a function value or `Callable` |
| 3 | **Adapter** | Convert a foreign interface into the one clients expect. | "How does this vendor satisfy our port?" | Wrapper class per SDK; Go implicit interface satisfaction |
| 4 | **Repository** | Collection-like interface over persistence for domain objects. | "Where do aggregates come from?" | Spring Data, EF Core `DbSet`, SQLAlchemy repo, Prisma wrapper |
| 5 | **Factory / Factory Method** | Create objects without naming their concrete class at the call site. | "Which concrete thing here?" | Static factory functions, `dict[str, Callable]`, `@classmethod` |
| 6 | **Observer / Publish-Subscribe** | Notify many dependents of a state change without coupling to them. | "Who cares this happened?" | `EventEmitter`, RxJS, Kafka/SNS, signals, `addEventListener` |
| 7 | **Decorator** | Add responsibilities to an object dynamically and composably. | "Which cross-cutting behaviours wrap this?" | Python decorators, ASP.NET/Express **middleware**, gRPC interceptors |
| 8 | **Middleware / Pipeline** | Chain handlers so each may act, transform, and pass the request on. | "What sequence of stages processes this request?" | Express/Koa, ASP.NET Core, Django middleware, `http.Handler` wrapping |
| 9 | **Builder (Bloch)** | Construct an immutable object with many optional parameters safely. | "Which of many optional inputs did the caller supply?" | Java builder, Rust `derive_builder`, TS options object, **Go functional options** |
| 10 | **Singleton (as container lifetime)** | Exactly one instance of a service for the process. | "How many of these should exist?" | DI container `Singleton` scope — *not* a static accessor (§1.4) |
| 11 | **Command** | Encapsulate a request as an object so it can be queued, logged, undone. | "Which action, and can it be replayed?" | CQRS command handlers, task/job objects, `Runnable`, Redux actions |
| 12 | **Facade** | One unified higher-level interface over a subsystem. | "What is the sanctioned way in?" | SDK client classes, service modules, `index.ts` barrel |
| 13 | **Template Method** | Fix the algorithm skeleton, defer varying steps. | "Which step differs?" | Abstract base with hooks; pytest fixtures; framework lifecycle methods |
| 14 | **Value Object / Immutable Object** | A small object whose equality is by value, never identity, and whose state never changes. | "Is this a thing or a measurement?" | `record` (Java/C#), `@dataclass(frozen=True)`, Kotlin `data class`, `readonly` |
| 15 | **DTO** | Carry data across a process boundary in one call. | "What crosses the wire?" | Pydantic model, `record`, TS interface, protobuf message |
| 16 | **Result / Either (Railway Oriented)** | Model success and failure as one returned value instead of control flow. | "Did this succeed, and what is the failure?" | Rust `Result`, Go `(T, error)`, `Either` in fp-ts/Arrow/Vavr; Wlaschin's ROP |
| 17 | **State** | Behaviour changes with the object's state, including transitions. | "What state is this in, and what does it permit?" | State machine libs (XState, Stateless), sealed states + `switch` |
| 18 | **Proxy** | A surrogate controlling access to the real subject. | "Should this call be mediated?" | ORM lazy loading, gRPC/`Retrofit` stubs, JS `Proxy`, `__getattr__` |
| 19 | **Iterator / Generator** | Sequential access without exposing representation. | "How is this traversed?" | `yield`, `IEnumerable`, `Iterator`, async iterators |
| 20 | **Circuit Breaker** | Stop calling a failing remote dependency until it recovers. | "Is this dependency healthy enough to call?" | Nygard, *Release It!* (2007); Resilience4j, Polly, Envoy outlier detection |
| 21 | **Retry (with backoff + jitter)** | Re-attempt a transient failure under a bounded budget. | "Is this failure transient?" | Polly, `tenacity`, Resilience4j, AWS SDK adaptive retry |
| 22 | **Composite** | Treat individual objects and trees of them uniformly. | "One or many?" | React element trees, DOM, filesystem/AST models |
| 23 | **Chain of Responsibility** | Pass a request along candidate handlers until one handles it. | "Who, of an open set, handles this?" | Auth filter chains, Netty pipeline, log handlers |
| 24 | **CQRS** | Separate the write model from the read model. | "Is this a command or a query?" | Greg Young, from Meyer's CQS; MediatR, separate read replicas/projections |
| 25 | **Object Pool** | Reuse expensive objects instead of creating and destroying them. | "Is creation the bottleneck?" | JDBC/HikariCP, `sql.DB`, thread pools, `sync.Pool` |

**Honourable mentions, defined tersely (each is a real conflict resolution but ranks below the
top 25 by breadth of use):** *Unit of Work* (transaction boundary — "what changed and when
does it flush?"); *Service Layer*; *Options / Functional Options* (Go; Rob Pike, "Self-
referential functions and the design of options," 2014 — "which of many optional knobs?");
*Module / Barrel* ("what is public?"); *Bulkhead* (Nygard — "which failures may spread?");
*Saga* (Garcia-Molina & Salem, 1987 — "how do we undo a distributed transaction?"); *Event
Sourcing* ("is state the truth, or the log?"); *Ambassador / Sidecar* (cloud — "where does
out-of-process infrastructure live?"); *Feature Toggle* (Fowler/Hodgson — "should this code
path be live yet?" — the one case where a conditional is *deliberately* kept, and must be
time-boxed); *Monad / Optional* ("how do I sequence operations that may not produce a
value?"); *Lazy Initialization*, *Memoization*, *Double-Checked Locking* (POSA2 — famously
broken pre-Java 5 / without `volatile`); *Copy-on-Write*; *Multiton*; *Type Object* (Johnson
& Woolf, PLoPD3 — "should this variation be a class or a row of data?"); *Entity-Component-
System* ("composition over deep game-object hierarchies"); *Extension Object* (Gamma, PLoPD3);
*Twin* (Mössenböck — multiple inheritance without language support); *Curried Object*
(partial application reified); *Blackboard* (POSA1 — no deterministic solution strategy);
*Producer-Consumer*, *Active Object*, *Monitor Object*, *Reactor*, *Half-Sync/Half-Async*,
*Leader/Followers* (all Schmidt, Stal, Rohnert & Buschmann, **POSA2**, *Patterns for
Concurrent and Networked Objects*, 2000 — the conflict is always "which thread/context does
this work run on, and who waits?").

---

## 4. The conflict → pattern decision table

The core deliverable. "Fowler move" names are *Refactoring* 2nd ed. (2018).

| Code shape | The question it hides | Primary resolution (pattern + Fowler move) | Fallback | Anti-pattern if overdone |
|---|---|---|---|---|
| `if/elif/else` on a type code or enum | "Which kind of thing is this?" | **Strategy** / **State** port + one resolver per case; *Replace Conditional with Polymorphism*, *Replace Type Code with Subclasses* | Sealed interface + exhaustive pattern-match switch; `dict[enum, handler]` (§6) | A class per trivial branch → **Poltergeist**, **Lasagna Code** |
| The same `switch` repeated in >1 place | "Which variant?" (Fowler smell: **Repeated Switches**) | One port; move every arm into its resolver; *Replace Conditional with Polymorphism* + *Move Function* | `EnumMap`/registry of records so exhaustiveness is checked once | Over-abstracting a switch used twice with two arms |
| `if x is None` | "What is the absent case?" | **Null Object / Special Case**; *Introduce Special Case* (1st ed: *Introduce Null Object*) | `Optional`/`Maybe`, or default at the boundary via *Encapsulate Variable* | Null Objects that silently swallow required work |
| Boolean flag parameter | "Which of two behaviours did the caller want?" | Two named functions or two resolvers; ***Remove Flag Argument*** (1st ed: *Replace Parameter with Explicit Methods*) | Enum + `Parameterize Function` if the axis is real and open | Explosion of near-identical named methods → **Interface Bloat** |
| `if env == "prod"` | "Which environment are we in?" | **Plugin** + **Registry**: env→resolver map read *once* at the composition root; *Replace Conditional with Polymorphism* | Config object injected into Context (`Separated Interface` + per-env wiring) | Inner-Platform Effect: a homemade config interpreter; env checks leaking back into resolvers |
| `try/except` with a real alternative path | "What do we do when the world says no?" | **Result/Either** or a **fallback resolver** (Decorator: primary→secondary); *Replace Error Code with Exception* / *Replace Exception with Precheck* (whichever direction is wrong today) | Chain of Responsibility over sources | Exceptions as routine control flow, or a `Result` monad in a language with no support for it |
| Two near-identical blocks differing in one operation | "Which step differs?" | **Template Method** with injected step-port, or **Strategy**; *Parameterize Function*, *Extract Function*, *Substitute Algorithm* | Higher-order function parameter | Deep template hierarchies where only leaves matter |
| Long `if` chain of unrelated predicates (open set) | "Who, of an open set, handles this?" | **Chain of Responsibility**; ordered handler list as data; *Decompose Conditional* first | **Specification** tree, or predicate→handler registry | Chain with hidden ordering dependencies; nothing handles it and it fails silently |
| Two type axes varying together | "Are these two axes actually independent?" | **Bridge** (or **Abstract Factory** for families); *Replace Subclass with Delegate* | Two injected ports on one Context | M×N interfaces for a 2×2 problem — **Speculative Generality** |
| Behaviour depending on a mutable status field | "What state is this in, and what may it do next?" | **State** pattern; *Replace Type Code with Subclasses* (1st ed alias: *Replace Type Code with State/Strategy*) | Explicit state machine table (state × event → state, action) | Hand-rolled state objects for a two-state boolean |
| Conditional deciding **whether** to act (guard) | "Is this input even in scope?" | **Leave it** — *Replace Nested Conditional with Guard Clauses*; keep guards flat at the top of the function | *Introduce Assertion*, precondition in the constructor / Value Object | Promoting guards to ports → **Poltergeist**; a `NoOpValidator` for every check |
| Conditional deciding **how** to act | "Which of several answers is right?" | Promote to a port with resolvers (the doctrine's core move) | Data dispatch table (§6) | Ports with exactly one implementation forever |
| Conditional inside a loop | "Are these two loops wearing one body?" | *Split Loop*, then *Replace Loop with Pipeline* (`filter`/`map`/`reduce`); *Slide Statements* | *Extract Function* on the body, then dispatch on the extracted call | Unreadable 6-stage pipelines; pipelines over huge data where a loop is required |
| Error / absent / empty / default cases | "What is the neutral value here?" | **Special Case** + **Null Object**; *Introduce Special Case*; make the default a registered resolver | `Result` with an explicit `Empty` variant | Defaults that hide misconfiguration (silent fallback to `prod`-like behaviour) |
| Conditional on another object's field (**Feature Envy**) | "Whose decision is this?" | *Move Function* to the data's owner; *Extract Function* then move; **Tell, Don't Ask** | *Preserve Whole Object* / *Introduce Parameter Object* if several fields travel together | *Remove Middle Man* forgotten → chains of pure forwarders |
| Conditional selecting a cross-cutting concern (retry/cache/log) | "Which wrappers apply, in what order?" | **Decorator** stack composed from a config list; *Replace Function with Command* if it needs identity | Middleware/Pipeline; AOP/interceptors | 8-deep wrap stacks nobody can trace; ordering bugs (retry outside the breaker) |
| Conditional on a collection being empty | "Is emptiness special, or just the zero case?" | Make it not special: *Encapsulate Collection*, return an empty collection never `null`; fold/reduce with an identity | Special Case object for "no results" if callers must display something | `EmptyList` subclasses that behave differently → surprise |
| Conditional selecting an output format/serializer | "Which representation?" | **GoF Builder** or **Strategy**: `format → Serializer` registry; *Replace Conditional with Polymorphism* | **Visitor** over a closed node set for structural output | A serializer plugin framework for two formats |
| Conditional selecting a validation rule set | "Which rules apply to this case?" | **Specification** composed with `And`/`Or`/`Not`; *Decompose Conditional*, *Consolidate Conditional Expression* | Rule list as data, evaluated by one engine | A rules engine (**Inner-Platform Effect**) for a dozen rules |
| Nested conditionals combining two independent axes | "Which two questions are tangled here?" | Split into two ports (**Bridge**-shaped); *Decompose Conditional*, then *Split Phase* | Table keyed by the pair `(a, b) → handler` | Cartesian class explosion; abstract classes with one subclass each |
| Conditional on a hard-coded environment/tenant list | "Which tenant/stage is this?" | **Registry** + **Plugin**: the list becomes wiring data, never a literal in a resolver; *Replace Conditional with Polymorphism* | *Introduce Parameter Object* → a `TenantContext` field on the immutable Context | A tenant-plugin SPI for two tenants; tenant ids re-appearing inside resolvers |

---

## 5. Fowler refactoring names (2nd ed.), with 1st-edition aliases

The catalog lists 66 refactorings; secondary names are labelled **aliases**, explicitly
including "names for first edition refactorings that it replaces."

**Renamed from the 1st edition (alias shown in the catalog):**

| 2nd ed. name | 1st ed. / alias |
|---|---|
| **Introduce Special Case** | Introduce Null Object |
| **Remove Flag Argument** | Replace Parameter with Explicit Methods |
| **Replace Superclass with Delegate** | Replace Inheritance with Delegation |
| **Replace Primitive with Object** | Replace Data Value with Object · Replace Type Code with Class |
| **Replace Type Code with Subclasses** | Extract Subclass · Replace Type Code with State/Strategy |
| **Replace Function with Command** | Replace Method with Method Object |
| **Replace Constructor with Factory Function** | Replace Constructor with Factory Method |
| **Encapsulate Variable** | Encapsulate Field · Self-Encapsulate Field |
| **Encapsulate Record** | Replace Record with Data Class |
| **Change Function Declaration** | Add Parameter · Remove Parameter · Rename Function/Method · Change Signature |
| **Parameterize Function** | Parameterize Method |
| **Extract Function** / **Move Function** | Extract Method / Move Method |
| **Slide Statements** | Consolidate Duplicate Conditional Fragments |
| **Remove Subclass** | Replace Subclass with Fields |
| **Replace Exception with Precheck** | Replace Exception with Test |

**Same name in both editions (no alias):** Replace Conditional with Polymorphism · Decompose
Conditional · Consolidate Conditional Expression · Replace Nested Conditional with Guard
Clauses · Extract Class · Inline Class · Extract Superclass · Collapse Hierarchy · Pull Up
Method · Pull Up Field · Pull Up Constructor Body · Push Down Method · Push Down Field ·
Introduce Parameter Object · Preserve Whole Object · Encapsulate Collection · Hide Delegate ·
Remove Middle Man · Substitute Algorithm · Separate Query from Modifier · Split Loop ·
Replace Inline Code with Function Call · Replace Temp with Query · Move Field.

**New in the 2nd edition (no 1st-ed. ancestor):** Replace Subclass with Delegate · Combine
Functions into Class · Combine Functions into Transform · Split Phase · Replace Loop with
Pipeline · Replace Derived Variable with Query · Return Modified Value · Replace Command with
Function · Move Statements into Function · Move Statements to Callers · Replace Query with
Parameter · Change Reference to Value · Change Value to Reference · Rename Field · Rename
Variable · Replace Magic Literal (alias: Replace Magic Number with Symbolic Constant).

**Two names to stop citing as 2nd-ed. refactorings:** **Extract Interface** is *not* in the
2nd-edition catalog (it was a 1st-edition refactoring; use *Extract Superclass* or the tool
command, and say so). **Extract Subclass** survives only as an alias of *Replace Type Code
with Subclasses*.

---

## 6. Table-driven / data dispatch — a legitimate alternative to subtype polymorphism

Subtype polymorphism is not the only way to delete an `if`. Moving the branch into **data**
is the same doctrine (selection by data at a composition root) with a cheaper resolver.

| Mechanism | Language | Shape |
|---|---|---|
| Registry / dispatch dict | Python, JS, Ruby | `HANDLERS: dict[Kind, Callable[[Ctx], Out]]`, filled by decorator registration at import of the composition root |
| `functools.singledispatch` | Python | `@area.register` per type — open set of *types*, closed set of *functions*; the true dual of Visitor |
| Map of funcs | Go | `var ops = map[string]func(Ctx) error{}` — the idiomatic Go replacement for a Strategy interface with one method |
| `EnumMap` / `EnumSet` | Java | Dense array-backed table keyed by enum; pairs with an enum whose constants carry behaviour |
| Sealed interface + records + exhaustive `switch` | **Java 21+** (also Kotlin `sealed` + `when`, Rust `enum` + `match`, TS discriminated union) | `sealed interface Shape permits Circle, Rect {}` then `return switch (s) { case Circle c -> …; case Rect r -> …; }` — compiler-checked exhaustiveness, no `default` |

**Brian Goetz's Data-Oriented Programming argument** (*Data Oriented Programming in Java*,
InfoQ, 2022): "Data-oriented programming encourages us to model *data as data*." Four
principles: "Model the data, the whole data, and nothing but the data"; "Data is immutable";
"Validate at the boundary"; "Make illegal states unrepresentable." On Visitor specifically:
"Pattern matching is clearly more concise than visitors, but it is also more flexible and
powerful" — visitors require a domain "built for visitation," while "pattern matching supports
much more ad-hoc polymorphism," and crucially it "composes better," since nested patterns
express compound conditions that get "quite messy and error-prone" with visitors. He does not
declare a winner: OO "shines at defining and defending *boundaries*" (versioning,
encapsulation, compatibility), and "The techniques of OOP and data-oriented programming are
not at odds."

**The honest decision rule (the expression problem, Wadler 1998).** Cases are rows, functions
are columns; OO fixes the columns and lets you add rows, functional/pattern-matching fixes the
rows and lets you add columns.

- **Open set of cases, closed set of operations** (new payment providers, new tenants, new file
  formats keep arriving; operations are stable) → **subtype polymorphism**: port + one resolver
  file per case. Adding a case adds a file and a registry line; no existing file changes.
- **Closed set of cases, open set of operations** (a fixed AST, a fixed protocol, a fixed set of
  domain events; new passes keep arriving) → **sealed hierarchy + exhaustive pattern matching**
  (or Visitor in older languages). Adding an operation adds a file; adding a case makes the
  compiler point at every switch that must change — which is the *desired* failure.
- **Both open** → you are paying the expression problem in full. Pick which axis you protect,
  write it down in the ADR, and accept fan-out on the other. Typeclasses/traits (Rust, Scala,
  Haskell) and `singledispatch` buy you both at the cost of coherence rules.
- **Neither open (2 cases, 1 operation, no growth signal)** → keep the `if`. See §7.

---

## 7. Over-application anti-patterns

| Anti-pattern | Source | Shape | Test that catches it |
|---|---|---|---|
| **Poltergeist** (a.k.a. Gypsy Wagon) | Brown et al., *AntiPatterns* (1998) | Short-lived stateless classes that only invoke methods on another class; a "resolver" with no logic | Can you delete the class and call the target directly with no loss? Then do. |
| **Lasagna Code** | folklore, contrasted with Spaghetti | So many strictly ordered layers that a one-field change edits eight files | Count files touched by a one-field feature. >4 for a trivial change is a smell. |
| **Interface Bloat** | Bertrand Meyer, "fat interface"; ISP (Martin) | A port with 12 methods where no implementer needs all of them | Any resolver throwing `NotImplementedError` proves the port is >1 question. Split (ISP). |
| **Single-implementation interface** | ongoing debate; both sides are legitimate | `IFooService` + exactly one `FooService` | See below. |
| **Speculative Generality** | Fowler, *Refactoring*, smell #22 | Hooks, abstract classes, unused parameters and TODO-driven extension points for needs that never came | "Is there a second implementation, a test double that *needs* the seam, or a named upcoming requirement?" No to all three → *Collapse Hierarchy* / *Inline Class* / *Remove Dead Code*. |
| **Inner-Platform Effect** | folklore / *AntiPatterns* lineage | A homemade configurable rules/workflow/DSL engine that reimplements the host language, badly | If the config file is Turing-complete, you wrote a language. Write code instead. |
| **AbstractFactoryFactory / "Enterprise FizzBuzz"** | *FizzBuzzEnterpriseEdition* (GitHub, 2011) — the deliberate reductio | Interfaces, factories, strategies and DI wiring for a 6-line loop; the joke is that every pattern is applied *correctly* | The parody is the acceptance test for this skill's output: if the transformation could be a slide in FizzBuzzEnterpriseEdition, it is wrong. |
| **Patternitis / pattern-happy** | Norvig (1996/98); Hannemann & Kiczales (2002); McConnell, *Code Complete* 2e pp.104–105 | Patterns applied for their own sake; complexity and indirection added with no variation to absorb | See Norvig's claim below. |

**Norvig, *Design Patterns in Dynamic Programming* (Object World, 5 May 1996), verbatim:**
"16 of 23 patterns have qualitatively simpler implementation in Lisp or Dylan than in C++ for
at least some uses of each pattern," and — the next slide — "16 of 23 patterns are either
invisible or simpler, due to:" **First-class types (6):** Abstract-Factory, Flyweight,
Factory-Method, State, Proxy, Chain-Of-Responsibility · **First-class functions (4):** Command,
Strategy, Template-Method, Visitor · **Macros (2):** Interpreter, Iterator · **Method
Combination (2):** Mediator, Observer · **Multimethods (1):** Builder · **Modules (1):**
Facade. Note what the claim is *not*: he does not say the patterns are useless, and "invisible
or simpler" is per-use, not universal. The correct reading for this skill: in Python/JS/Kotlin,
a *function value* is often the whole resolver, and a class is ceremony. (Compare Hannemann &
Kiczales 2002, who removed code-level dependencies in 17 of 23 using AspectJ.)

**The single-implementation-interface debate, both sides.**
*For the interface:* it names the question (the port's name is the conflict as a question); it
is the seam for a **Service Stub** in tests without mocking a concrete class; it enforces the
dependency direction (**Separated Interface** — callers compile against the declaring layer, not
the implementation); it documents the contract independent of one implementation's accidents;
and adding implementation #2 requires no edits to callers, so the *option* is real headroom.
*Against:* it doubles the file count and the "jump to definition" cost; modern mocking and
`final`-class-friendly test tooling remove the testability argument; the interface is usually
just the public methods of the one class, so it carries no independent design thought and
drifts; YAGNI — an interface extracted later by a tool costs almost nothing. *Resolution used
here:* an interface is justified when at least one holds — (a) two or more resolvers exist or
are named in the backlog, (b) it crosses a process/IO boundary (so a Service Stub is needed),
or (c) it crosses a layer boundary the dependency rule must protect. Otherwise leave the
concrete class and extract the interface the day the second answer arrives.
