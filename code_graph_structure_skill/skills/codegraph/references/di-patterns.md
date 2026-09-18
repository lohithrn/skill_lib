# Dependency injection — the four patterns, the four anti-patterns, the smells

Sources: Seemann & van Deursen, *Dependency Injection Principles, Practices, and Patterns* (Manning,
2019 — "DIPPP", the 2nd ed. of *Dependency Injection in .NET*), plus the authors' own blogs where the
book is not quotable. Chapter numbers are the **2nd edition**; the 1st-ed. names changed and citing
the wrong one is how a rule loses its authority.

**The one-sentence test for what to inject** (van Deursen, 2013): *newables* are what the
application `new`s up by hand — primitives, entities, DTOs, view models, messages; they contain
little or no logic and code may safely depend on their implementation. *Injectables* are the types
that contain the logic. **Only injectables get abstracted and injected.** A `MoneyInterface` is a
category error; a `PaymentProcessor` interface is the point.

---

## 1. The four patterns (DIPPP ch. 4)

| Pattern | § | What it is | When |
|---|---|---|---|
| **Composition Root** | 4.1 | the single place, as close to the entry point as possible, where the object graph is composed | always, exactly one per deployable |
| **Constructor Injection** | 4.2 | "the act of statically defining the list of required Dependencies by specifying them as parameters to the class's constructor" | **the default choice** |
| **Method Injection** | 4.3 | "supplies a consumer with a Dependency by passing it as method argument on a method called **outside the Composition Root**" | the dependency varies per call — this is what a Context is for |
| **Property Injection** | 4.4 | assign after construction | only with a **good local default**, and only when the dependency is genuinely **optional** |

Verbatim rules worth enforcing mechanically:

- **"Constructor Injection should be your default choice for DI."**
- **"Keep the constructor free of any other logic"** — no work performed on dependencies. A
  constructor that opens a connection, reads config, or starts a thread is a finding: it makes the
  object impossible to construct in a test.
- **"An injectable should have a single constructor."** "The constructor is the definition of what
  dependencies a type requires." **Detector: >1 public constructor on an injectable.**
- **"Dependencies should hardly ever be optional."** Property Injection's cost is named:
  "Clients can forget to supply the Dependency, a code smell known as **Temporal Coupling**."
- A **Volatile Dependency** is "a Dependency that involves side effects that can be undesirable at
  times… modules that don't yet exist or that have adverse requirements on its runtime
  environment." Volatile ⇒ abstract it. Stable ⇒ do not.

### Local vs foreign defaults — the real trigger, not "any default is bad"

> "when such a prospective default is implemented in a **different assembly**… Such implementation
> is a **FOREIGN DEFAULT**. A class that has a hard reference to a FOREIGN DEFAULT causes tight
> coupling."
>
> "if the intended default implementation is defined in the **same library** as the consuming
> class, you won't have that problem… such **LOCAL DEFAULTS** often arise as implementations of the
> Strategy pattern."

**Detector: a default supplied across a package/assembly boundary is the smell.** A same-package
default is legitimate, and is exactly what licenses Property Injection. This distinction matters —
"never hard-code a default" over-fires on correct code.

---

## 2. The four anti-patterns (DIPPP ch. 5)

The 2nd-edition catalogue is **exactly four**. Do not present a fifth as a peer.

| Anti-pattern | § | Definition / tell | Detector |
|---|---|---|---|
| **Control Freak** | 5.1 | a class creates its own volatile dependencies | see the three forms below |
| **Service Locator** | 5.2 | "supplies application components outside the Composition Root with access to an **unbounded set** of Dependencies" | a container, `ServiceProvider`, `resolve()`, or `get(Class)` referenced outside the root |
| **Ambient Context** | 5.3 | "supplies application code outside the Composition Root with global access to a Volatile Dependency or its behavior **by the use of static class members**" | mutable static holding a volatile dependency; `DateTime.Now`, a static logger factory, thread-locals |
| **Constrained Construction** | 5.4 | a required constructor signature, so construction happens by convention/reflection | late-bound types constructed from config with an assumed ctor shape |

**Control Freak has three named forms — this is the detection taxonomy:**
`§5.1.1` newing up dependencies · `§5.1.2` factories · `§5.1.3` overloaded constructors.

Two quotes that carry more weight than any paraphrase:

- **"Service Locator is a dangerous pattern because it almost works."** Any component using it "is
  being **dishonest about its level of complexity**" — its constructor no longer states what it
  needs, so the graph is unreadable and the compiler cannot help.
- Ambient Context vs Singleton: "Ambient Context allows its Dependency to be **changed**, whereas
  the Singleton pattern ensures that its singular instance never changes."

### Bastard Injection — cite it correctly or not at all

**Bastard Injection was 1st ed. §5.2 and is retired as a name in the 2nd edition.** The construct
now lives at **§5.1.3, "Example: Control Freak through overloaded constructors."** Seemann's own
usage confirms both the original ("Consider this case of Bastard Injection (*Dependency Injection in
.NET*, section 5.2)", 2011) and the retirement ("Initially, I used what I in *Dependency Injection
in .NET* later called Bastard Injection", 2021).

Write it as: *Bastard Injection (1st ed. §5.2; in the 2nd ed. a form of Control Freak, §5.1.3).*

Related rename, frequently conflated with the above: **Poor Man's DI → Pure DI.**

One caveat to carry: Ambient Context's flip from pattern to anti-pattern rests on Seemann's 2019
blog testimony ("I included it in the first edition"), not on a 1st-ed. table of contents. **Cite the
blog, not the book.**

---

## 3. The code smells (DIPPP ch. 6) — exactly three

| Smell | § | Fix |
|---|---|---|
| **Constructor Over-injection** | 6.1 | **Facade Services** (§6.1.2) — a new abstraction covering a *cohesive* cluster of the dependencies, not a bag; or **domain events** (§6.1.3) |
| **Abuse of Abstract Factories** | 6.2 | inject the dependency, not a factory for it. A factory whose only job is `new` is a Control Freak with extra steps |
| **Cyclic dependencies** | 6.3 | break with an event/domain event, or split the type by reason-to-change |

**Do not cite a numeric threshold for Constructor Over-injection.** The often-repeated "more than 4
constructor arguments" has no source in the book. Judge it by **cohesion**: too many dependencies
means too many reasons to change, and the count is a symptom, not the rule. (This skill's own
params cap is a separate, self-declared limit — cite `laws.md`, not DIPPP, for it.)

**Facade Services is the right fix and the easy thing to get wrong.** A Facade Service must cover a
cohesive concept the domain would name. Grouping six unrelated dependencies into `HelperService` to
get the count down is the smell relocated, and `naming.md` §2 bans the name it would need.

---

## 4. Lifetime bugs (DIPPP ch. 8) — the ones that ship and then corrupt data

Lifestyles (§8.3): **Singleton · Transient · Scoped.** Bad choices (§8.4):

- **§8.4.1 Captive Dependency** — a longer-lived component holds a shorter-lived one, so the
  short-lived one outlives its scope. The classic: a singleton service holding a scoped DB context.
  Symptoms appear as stale data or cross-request leakage, never as a startup error.
- **§8.4.2 Leaky Abstraction** — "an Abstraction that leaks through implementation details of the
  underlying implementation." Two mechanical detectors, both quotable:
  - **"Parameterless factory methods are Leaky Abstractions."**
  - **"Abstractions that implement `IDisposable` are Leaky Abstractions. Application code shouldn't
    be responsible for the management of the lifetime of objects."** Generalise to any language: a
  port whose interface exposes `close()`, `dispose()`, `flush()`, a transaction handle, or a
  connection has leaked its implementation into its contract.
  - Van Deursen's general rule (2016): **"Service abstractions should not expose other service
    abstractions in their definition."** A port returning another port is the detector.
- **§8.4.3** tying instances to a thread's lifetime → concurrency bugs.

**A container is not required for any of this.** Pure DI — hand-wiring in the composition root — has
none of these failure modes at startup because the graph is a constructor expression the compiler
checks. Prefer it until the wiring genuinely hurts.

---

## 5. Passing the container around — the specific version of this the user asked about

The composition root may be handed to **top-level orchestration** where that is the pragmatic
choice. Everything below it receives **the specific interfaces it needs**, typed as interfaces.

A class that receives the whole `ConfigDependencyInjection` object and pulls dependencies out of it
internally is **Service Locator** (§5.2), whatever the parameter is named. Its constructor no longer
declares what it depends on, so:

- the dependency graph cannot be read from the code, only from runtime behaviour
- a test must build the whole container to exercise one method — the tell this skill checks for
- adding a dependency becomes invisible in review

**Detector, mechanical:** any constructor parameter whose type is the container, the config root, a
`ServiceProvider`, or a `Map<String, Object>` of services — outside the composition root itself.
`SKILL.md`'s hard limit "container uses in tests = 0" is this rule with a number on it.

---

## 6. Per-language composition roots

| Language | Root | Notes |
|---|---|---|
| Python | `config_dependency_injection.py` :: `ConfigDependencyInjection` | plain constructor calls; `Protocol` for ports. A DI framework is rarely worth it |
| TypeScript | `config_dependency_injection.ts` | plain functions returning wired objects; avoid decorator/reflection containers unless the framework forces one |
| Java | one `@Configuration` class, or hand-wired `main` | field injection is banned — it hides dependencies and defeats immutability |
| Kotlin | one module object, or Dagger/Hilt component | constructor injection only |
| Go | `wire.Build` in one file, or hand-wired `main` | accept interfaces, return structs; interfaces declared at the consumer |

**One root per deployable.** Two roots means two answers to "what is this program made of", and the
one you are not reading is the one that is wrong. Tests get their own wiring — a test composition
root that builds fakes is correct and expected; a test that reaches into the production container
is the leak.

---

## 7. Detection — what the `di` dimension measures

| ID | Rule | Severity |
|---|---|---|
| DI1 | volatile dependency constructed inside business logic (Control Freak §5.1.1) | **blocker** — the unit cannot be tested |
| DI2 | container / config root / `ServiceProvider` referenced outside the composition root (§5.2) | **blocker** |
| DI3 | mutable static or thread-local holding a volatile dependency (§5.3) | **blocker** |
| DI4 | >1 composition root per deployable | major |
| DI5 | field/setter injection where the dependency is required | major |
| DI6 | >1 public constructor on an injectable | major |
| DI7 | constructor performing work (I/O, threads, config reads) | major |
| DI8 | a foreign default — hard reference to an implementation in another package (§4.4) | major |
| DI9 | port exposing `close`/`dispose`/a transaction/another port (Leaky Abstraction §8.4.2) | major |
| DI10 | singleton holding a scoped dependency (Captive Dependency §8.4.1) | **blocker** where a container declares lifetimes |
| DI11 | a factory injected where the product could be injected (§6.2) | minor |
| DI12 | a test constructing the container to exercise one unit | major |

**Not findings.** Pure DI without a container. A `new` of a *newable* — an entity, DTO, value
object, or message — anywhere at all. A single-implementation port at an I/O boundary. A local
default in the same package. A framework-mandated shape (a Spring `@Component`, a Django settings
module, a `main` that necessarily knows everything).

---

## 8. Inheritance vs composition — verified, because "inheritance everywhere" needs a boundary

This doctrine wants **polymorphism everywhere and implementation inheritance almost nowhere**. The
sources say why, and they are specific enough to act on.

**The coupling claim, from Sutter & Alexandrescu, *C++ Coding Standards*, Item 34, p. 58:**

> "**Inheritance is the second-tightest coupling relationship in C++, second only to friendship.**
> Tight coupling is undesirable and should be avoided where possible. Therefore, prefer composition
> to inheritance unless you know that the latter truly benefits your design."

**The rule that resolves the whole argument, Item 37, p. 64 — it is literally the title:**
*"Public inheritance is substitutability. Inherit, not to reuse, but to be reused."*
You inherit so that **others** can use your subclass through the base's interface. Reuse of the
base's code is not a reason. Also: Item 35 — "Using a standalone class as a base is a serious
design error." Item 38 — "Practice safe overriding" (p. 66). Item 39 — NVI.

**Sutter's six legitimate reasons to inherit** (*C++ Report*, Oct 1998 / Jan 1999) — the sharpest
decision procedure available: you need access to a protected member · you need to override a virtual
function · you need base-subobject construction/destruction ordering · you need a shared virtual
base · you need "controlled polymorphism" (IS-A, but only in certain code) · the empty base class
optimization. Plus the seventh he adds: "We need public inheritance to express IS-A." His condition:

> "**Only use public inheritance to model true IS-A, as per the Liskov Substitution Principle**… a
> publicly-derived class object should be able to be used in any context where the base class object
> could be used and still guarantee the same semantics." / "**Never use public inheritance to
> implement 'almost IS-A'**" — "being 'a little bit incompatible' is a lot like being 'a little bit
> pregnant'."

**Bloch, *Effective Java* 3rd ed., Item 18 — the mechanically checkable boundary:**

> "**It is safe to use inheritance within a package**, where the subclass and the superclass
> implementations are under the control of the same programmers. It is also safe to use inheritance
> when extending classes specifically designed and documented for extension. **Inheriting from
> ordinary concrete classes across package boundaries, however, is dangerous.**"

**Detector: an `extends` edge crossing a package boundary to a non-final, non-abstract class.**
That is a graph query, which is exactly what this skill has. Scope limit, stated by Bloch himself:
"The problems discussed in this item do not apply to **interface inheritance**." Also: "**Unlike
method invocation, inheritance violates encapsulation**", and the test "**Is every B really an A?**"

Item 19's three rules for a class that *is* designed for extension: it must document its self-use of
overridable methods · "**you must test your class by writing subclasses before you release it**" ·
"**Constructors must not invoke overridable methods**, directly or indirectly."

**Two named failure modes to use by name:**

- **The SELF problem** (Bloch, citing Lieberman 1986) — the limit of the wrapper fix: a wrapped
  object doesn't know of its wrapper, so it passes `this` and callbacks elude the wrapper. Bloch's
  terminology note: "**Technically it's not delegation unless the wrapper object passes itself to
  the wrapped object.**"
- **The yo-yo problem** — Taenzer, Ganti & Podar, "Problems in Object-Oriented Software Reuse,"
  ECOOP'89, pp. 25–38, §3.1 "The Yoyo Problem," pp. 33–34 (spelled *yoyo* in the original):
  "Often we get the feeling of riding a yoyo when we try to understand one these message trees."
  [sic] And, nine years before "fragile base class" was named: "**We have discovered that a more
  important inter-class implementation dependency is the message control tree. A writer of a new
  subclass must understand how its superclasses are implemented in order to understand what messages
  an object sends itself and which of these methods should be refined.**" Their scale evidence: leaf
  classes that "**inherit more than three hundred methods from their superclasses!**" This is the
  canonical name for the cost of DIT — cite it whenever reporting hierarchy depth.

**Gamma, ten years after GoF** (artima interview) — the correction to a maximalist reading of
either side, and the single best citation for what this doctrine actually asks for:

> "**A common misunderstanding is that composition doesn't use inheritance at all. Composition is
> using inheritance, but typically you just implement a small interface and you do not inherit from
> a big class.**"

Also: "Inheritance is a cool way to change behavior. But we know that it's **brittle**… **From an
API point of view defining that a method can be overridden is a stronger commitment than defining
that a method can be called.**" And his name for the opposite failure: "**object exhibitionists** …
If you have exposed everything, you cannot change anything or you break all your clients."

**C++ Core Guidelines:** there is **no rule titled "Prefer composition"** — that statement lives
inside **C.120**'s Reason. Add **C.133 "Avoid `protected` data"** ("`protected` data complicates the
statement of invariants") — the checkable form of "no data in the base class."

**Holub, "Why extends is evil" — two corrections worth knowing before quoting it:** the 80% figure
is **Holub's own rule of thumb** ("My rule of thumb is that 80 percent of my code at minimum should
be written entirely in terms of interfaces"), not GoF and not a Gamma interview. And "**I'd leave out
classes**" is **James Gosling**, quoted by Holub — not Gamma. Gosling later clarified that "the real
problem wasn't classes per se, but rather implementation inheritance."

**Do not cite** (searched for, not found or not quotable): Bloch's often-repeated "there are no
reasonable defenses against this problem" · the names of Mikhajlov & Sekerinski's five requirements
for disciplining inheritance (LNCS 1445, pp. 355–382 — the paper is citable, the enumeration is not)
· the verbatim Control Freak and Constrained Construction definition boxes · a numeric threshold for
Constructor Over-injection · any Henney, Feathers, or Page-Jones quote on inheritance coupling.
Optional and verified: Sean Parent, "Inheritance Is The Base Class of Evil," GoingNative 2013.
