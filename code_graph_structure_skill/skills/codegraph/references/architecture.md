# Architecture — the vocabulary, and the honest caveats

Where the doctrine came from, in the words of the people who named it. **conflict → port →
resolvers → Context** is a *synthesis* of DDD supple design, Ports & Adapters, and type-driven
modelling — cite the ancestor, not the synthesis. Two claims run through everything below:
**the interface belongs with the caller, not the implementer** (Fowler, *Separated Interface*);
and **a conditional resolved by the type checker beats one resolved at runtime** — §5 is the
strongest form of the doctrine, not a variation on it.

---

## 1. DDD tactical patterns — Evans, *Domain-Driven Design* (2003)

Quotes are from Evans' **Domain-Driven Design Reference** (2015, CC-BY), which prints each
pattern's "Therefore:" clause verbatim. Abridged where marked; nothing paraphrased silently.

| Pattern | Evans' rule ("Therefore:", abridged) | Smell it cures | Mechanical detector for its **absence** |
|---|---|---|---|
| **Ubiquitous Language** | "Use the model as the backbone of a language… Recognize that a change in the language is a change to the model." | Mysterious Name; Inconsistency (`G11`) | one concept spelled ≥2 ways across modules (`User`/`Customer`/`Account`); identifiers absent from any glossary |
| **Entity** | "When an object is distinguished by its identity, rather than its attributes, make this primary to its definition… Keep the class definition simple and focused on life cycle continuity and identity." | Large Class; identity compared by hand | `==` over all fields on a thing with a lifecycle; `a.id == b.id` written at call sites |
| **Value Object** | "When you care only about the attributes and logic of an element of the model, classify it as a value object… **Treat the value object as immutable.**" | ★ **Primitive Obsession**; Data Clumps | count `str`/`int`/`float`/`Decimal` in domain signatures; unit-suffixed names (`amount_cents`, `duration_days`, `ttl_seconds`) |
| **Service** | "When a significant process or transformation in the domain is not a natural responsibility of an entity or value object, add an operation to the model as a standalone interface declared as a service." | Feature Envy; duplicated process | the same multi-step domain operation inlined at ≥2 call sites |
| **Module** | "Choose modules that tell the story of the system… Give the modules names that become part of the ubiquitous language." | Dense Structure; Scattered Functionality | folder names are technical (`models/`, `helpers/`, `utils/`) rather than domain nouns — the folder tree is not the graph |
| **Aggregate** | "Cluster the entities and value objects into aggregates and define boundaries around each. Choose one entity to be the root… Define properties and invariants for the aggregate as a whole and give enforcement responsibility to the root." | Insider Trading; lost invariants | one transaction/`commit` writing ≥2 root types; an invariant checked in an application service instead of the root |
| **Factory** | "Shift the responsibility for creating instances of complex objects and aggregates to a separate object… Provide an interface that encapsulates all complex assembly… Create an entire aggregate as a piece, enforcing its invariants." | Temporary Field; half-built objects | `new X()` followed by ≥2 setters, repeated at ≥2 sites |
| **Repository** | "For each type of aggregate that needs global access, create a service that can provide the illusion of an in-memory collection of all objects of that aggregate's root type… Provide methods that select objects based on criteria meaningful to domain experts." | ★ **C11** (I/O client built inside business logic) | ORM/SQL imports or query strings inside a domain module |
| **Specification** | "Create a specification that is able to tell if a candidate object matches some criteria. The specification has a method `isSatisfiedBy(anObject) : Boolean`." | Repeated Switches over predicates | the same boolean expression duplicated in ≥2 files; a DB `WHERE` and an in-memory `if` encoding one rule |

**Value Object is the antidote to Primitive Obsession.** Cunningham's **Whole Value** (pattern 1
of *The CHECKS Pattern Language of Information Integrity*, 1994) states it earlier: "Because
bits, strings and numbers can be used to represent almost anything, any one in isolation means
almost nothing." His rule — "Construct specialized values to quantify your domain model and use
these values as the arguments of their messages", and "Do not expect your domain model to handle
string or numeric representations of the same information." That is why a Context holds `Money`,
never `float`.

### Aggregate design — Vernon's four rules

From Vaughn Vernon, *Effective Aggregate Design* (DDD Community essays, 2011), Parts I–II. Rule
headings verbatim:

| # | Rule (verbatim) | Part | Consequence for the graph |
|---|---|---|---|
| 1 | **"Rule: Model True Invariants In Consistency Boundaries"** | I | the aggregate boundary *is* the transaction boundary; ports never span it |
| 2 | **"Rule: Design Small Aggregates"** | I | small root = fewer edges; large clusters become hub-like dependencies |
| 3 | **"Rule: Reference Other Aggregates By Identity"** | II | hold `CustomerId`, not `Customer` — the single biggest edge-count reduction in a domain model |
| 4 | **"Rule: Use Eventual Consistency Outside the Boundary"** | II | cross-aggregate work becomes an event + a resolver, not an `if` in a service |

Vernon calls these heuristics, not laws: limiting modification to one aggregate instance per
transaction "may sound overly strict. However, it is a rule of thumb and should be the goal in
most cases." His decision procedure for rule 4 is a section titled **"Ask Whose Job It Is"** — if
the user who invoked the command owns the consistency, keep it transactional; otherwise make it
eventual. Do not report a rule-3 violation without answering that question.

### Specification — the doctrine applied to boolean logic

Evans & Fowler, *Specifications* (1998, preceding DDD ch. 9), state the problem in three parts —
**Selection**, **Validation**, **Construction-to-order** — and give three strategies: **Hard
Coded** (a Strategy), **Parameterized** (runtime-buildable, limited to exposed parameters), and
**Composite Specification**: "Create a particular form of interpreter for the specification.
Create leaf elements for the various kinds of tests. Create composite nodes for the and, or,
and not operators." A predicate is a conflict; a Specification is its port.

| Boolean form in code | Specification form | Why it is the same move |
|---|---|---|
| `if a and b and not c:` | `A().and_(B()).and_(C().not_())` | the operators become composite nodes — data, not control flow |
| a predicate duplicated in service + query | one Specification, two interpreters | one rule, one file, two adapters |
| a flag argument selecting a rule | pass the Specification in | kills F3/`G15` selector arguments |
| growing `elif` chain of unrelated tests | chain of Specifications, `Absent` last | the open-set selector from doctrine §5 |

The paper's own listed cost: "must invest in complex framework." Do not build a specification
algebra for two predicates.

---

## 2. Strategic design — Bounded Context and Context Map

**Bounded Context**: "Explicitly define the context within which a model applies. Explicitly set
boundaries in terms of team organization, usage within specific parts of the application, and
physical manifestations such as code bases and database schemas."

**Context Map**: "Identify each model in play on the project and define its bounded context…
Name each bounded context, and make the names part of the ubiquitous language. Describe the
points of contact between the models, outlining explicit translation for any communication…
Map the existing terrain. Take up transformations later." Evans credits Big Ball of Mud to Foote
& Yoder (laputan.org/mud). **Separate Ways** and **Big Ball of Mud** are *decisions* — record
them in the spec, never as findings.

| Relationship | Evans' rule (abridged, verbatim fragments) | Use when | Graph consequence |
|---|---|---|---|
| **Shared Kernel** | "Designate with an explicit boundary some subset of the domain model that the teams agree to share. **Keep this kernel small.**" | two teams, high trust, continuous integration | a shared sink node — this is what `utils/` is, done deliberately |
| **Customer/Supplier** | "Establish a clear customer/supplier relationship between the two teams, meaning downstream priorities factor into upstream planning." | upstream can be influenced | edge direction stays; contract tests enforce it |
| **Conformist** | "Eliminate the complexity of translation… by slavishly adhering to the model of the upstream team." | no leverage, upstream model is adequate | no port — you import their types on purpose |
| **Anticorruption Layer** | "As a downstream client, create an isolating layer to provide your system with functionality of the upstream system in terms of your own domain model." | upstream model is hostile, legacy, or "big balls of mud" | ★ the archetypal **port + adapter**; the foreign model stops at one folder |
| **Separate Ways** | "Declare a bounded context to have no connection to the others at all, allowing developers to find simple, specialized solutions within this small scope." | integration cost exceeds value | deliberate absence of an edge. Not a finding |
| **Open Host Service** | "Open the protocol so that all who need to integrate with you can do so." | many downstream consumers | one published port, N unknown callers |
| **Published Language** | "Use a well-documented shared language that can express the necessary domain information as a common medium of communication, translating as necessary into and out of that language." | integration across orgs | the wire schema is the interface; adapters translate at the edge |
| **Big Ball of Mud** | "Draw a boundary around the entire mess and designate it a big ball of mud. Do not try to apply sophisticated modeling within this context." | legacy you will not fix now | ★ a named, bounded no-go zone — quarantine, don't refactor |

---

## 3. Supple design — the seven patterns

This chapter, not the building blocks, is where the doctrine actually comes from.

| Pattern | Evans' rule (verbatim fragment) | Detector for its absence |
|---|---|---|
| **Intention-Revealing Interfaces** | "Name classes and operations to describe their effect and purpose, without reference to the means by which they do what they promise." | name leaks mechanism (`SqlPriceLoader`, `process`, `doWork`); a caller must open the implementation to predict behaviour |
| **Side-Effect-Free Functions** | "Place as much of the logic of the program as possible into functions… **Strictly segregate commands** (methods which result in modifications to observable state) into very simple operations that do not return domain information." | methods that both mutate and return domain data (CQS violation) |
| **Assertions** | "State post-conditions of operations and invariants of classes and aggregates. If assertions cannot be coded directly in your programming language, write automated unit tests for them." | no invariant test per aggregate; contracts stated only in prose |
| **Standalone Classes** | ★ "the difficulty of interpreting a design increases wildly as dependencies are added… **Low coupling is fundamental to object design. When you can, go all the way. Eliminate all other concepts from the picture.**" | import count per module; fan-out. This *is* "minimise graph edges", stated in 2003 |
| **Closure of Operations** | ★ "define an operation whose return type is the same as the type of its argument(s)… Such an operation is closed under the set of instances of that type. **A closed operation provides a high-level interface without introducing any dependency on other concepts.**" | `Money.add(other) -> float`; helpers that drag in a foreign type to combine two values of one type |
| **Conceptual Contours** | ★ "Decompose design elements (operations, interfaces, classes, and aggregates) into cohesive units… **Observe the axes of change and stability through successive refactorings and look for the underlying conceptual contours that explain these shearing patterns.**" | git co-change coupling with no static edge — the same set of files edited together across many commits means the cut is in the wrong place |
| **Declarative Design** | "a way to write a program, or some part of a program, as a kind of executable specification. A very precise description of properties actually controls the software." | rules encoded as procedures instead of composable data (registry, Specification) |

**Conceptual Contours and Standalone Classes are the two that matter most here**, and both are
edge-count arguments. Standalone Classes sets the target (zero avoidable edges per node);
Conceptual Contours tells you *where* to cut so the target is reachable — at empirically observed
axes of change, since "it isn't just grain size that counts, but just where the grain runs."
Evans names three oversimplifications to avoid: chopping fine for combinability, lumping large
to hide complexity, and seeking one uniform granularity. A resolver-per-branch split that ignores
the observed shear lines produces Lasagna Code and will be reported as such. Evans is also honest
about the ceiling: these patterns "can never give conventional object-oriented programs formal
rigor." §5 is where the rigor comes from.

---

## 4. Hexagonal vs Onion vs Clean — compared honestly

**Cockburn, "Ports and Adapters (Object Structural)"**, alternative name *Hexagonal
Architecture*, HaT Technical Report 2005.02, dated 2005-09-04. Intent, verbatim: "Allow an
application to equally be driven by users, programs, automated test or batch scripts, and to be
developed and tested in isolation from its eventual run-time devices and databases." Ports come
in two flavours, "*primary* and *secondary*", which "could be also called *driving* adapters and
*driven* adapters"; the distinction "lies in who triggers or is in charge of the conversation."
Primary ports go "on the left side (or top) of the hexagon", secondary right/bottom. His caveat:
primary/secondary should be a *consequence* of applying the pattern, not a shortcut around it.

**Palermo, Onion Architecture (2008)** — the four tenets, as he restates them himself:

1. "The application is built around an independent object model"
2. **"Inner layers define interfaces. Outer layers implement interfaces"**
3. "Direction of coupling is toward the center"
4. "All application core code can be compiled and run separate from infrastructure"

His governing rule: "all coupling is toward the center", and "The database is not the center.
It is external."

**Martin, "The Clean Architecture" (2012)** — the Dependency Rule, verbatim: "This rule says
that *source code dependencies* can only point *inwards*. Nothing in an inner circle can know
anything at all about something in an outer circle." Four rings, centre outward: **Entities**
(enterprise business rules) · **Use Cases** ("*application specific* business rules") ·
**Interface Adapters** · **Frameworks and Drivers**. He notes "the circles are schematic" — four
is not mandatory. On details: "The Web is a detail. The database is a detail… We keep these
things on the outside where they can do little harm." On frameworks (*Screaming Architecture*,
2011): "Frameworks are tools to be used, not architectures to be conformed to", and "The Web is
a delivery mechanism, and your application architecture should treat it as such." In *Clean
Architecture* (2017) ch. 26, titled "The Main Component, The Ultimate Detail", `Main` is "the
outer-most layer and… the lowest-level plugin to the application" — the one component allowed to
know every concrete type. That is the composition root, named.

| Concern | Hexagonal (Cockburn 2005) | Onion (Palermo 2008) | Clean (Martin 2012) |
|---|---|---|---|
| Primary metaphor | inside/outside, two regions | concentric rings | concentric rings, four named |
| Named units | ports + adapters | layers (core / infra) | Entities, Use Cases, Adapters, Frameworks |
| Direction rule | inside never knows the outside | "all coupling is toward the center" | "source code dependencies can only point inwards" |
| Distinguishes inbound/outbound | ★ **yes** — primary/driving vs secondary/driven | no explicit split | implicitly, via Adapters ring |
| Layer count fixed | no (n ports) | no | "the circles are schematic" |
| Where the interface is declared | with the application (the caller) | "Inner layers define interfaces" | inner ring; adapters implement |
| Entity/use-case split inside the core | not addressed | not prescribed | ★ **yes** — the one real addition |
| Composition/wiring | outside, by the configurer | IoC container at the edge | ★ `Main`, named as a component |
| Testing claim | run the app in full isolation | core compiles without infrastructure | "Independent of Frameworks… Testable… Independent of Database" |

**What is genuinely different, and what is renamed.** Martin himself flattens the distinction:
after listing Hexagonal, Onion, Screaming, DCI and BCE, he writes that "They all have the same
objective, which is the separation of concerns." Honestly assessed:

- **Renamed.** Dependency direction (identical in all three), interface ownership (identical),
  infrastructure at the edge (identical), "the database is a detail" (Palermo said it first, in
  those words).
- **Genuinely different.** (a) Cockburn's **primary/secondary port** distinction has no
  counterpart in Onion or Clean, and it is the most useful idea of the three for this doctrine —
  a driving port is your API, a driven port is your dependency, and only the second kind wants
  a fleet of resolvers. (b) Clean's **Entities vs Use Cases** split inside the core is a real
  additional constraint. (c) Clean names **`Main`** as a component; the other two leave wiring
  implicit. (d) Hexagonal is *not* a layered architecture — it is two regions and n ports;
  drawing it as rings, as Onion and Clean do, quietly reintroduces the layer count.

**Where does the interface live — with the caller, or the implementer?** All three say *with
the caller*, and the pattern that names it is Fowler's PoEAA **Separated Interface**: "Defines
an interface in a separate package from its implementation." Its companion is **Plugin** (Rice
& Foemmel, PoEAA, 2003): "Links classes during configuration rather than compilation." Together
they are the whole mechanism: Separated Interface says the port ships with the caller; Plugin
says the resolver is bound at configuration time, in `Main`. Doctrine §3 ("the port lives in the
declaring layer") and §7 (one composition root) are these two patterns, nothing more.

**The failure mode of all three** is Fowler's **Anemic Domain Model**: objects reduced to
"little more than bags of getters and setters" with "a set of service objects which capture all
the domain logic". His verdict — "The fundamental horror of this anti-pattern is that it's so
contrary to the basic idea of object-oriented design", and "If all your logic is in services,
you've robbed yourself blind." A port-and-resolver decomposition drifts here by default. The
counterweight is §1: Value Objects with behaviour, invariants on the root.

---

## 5. Type-driven design — deleting the conditional at compile time

**This is the strongest form of the doctrine.** A conflict the type checker resolves needs no
port, no registry, and no test. Prefer it over runtime dispatch whenever the language allows.

### 5.1 Parse, don't validate (Alexis King, 2019-11-05)

Her thesis: "the difference between validation and parsing lies almost entirely in how
information is preserved." A parser is "just a function that consumes less-structured input and
produces more-structured output"; the point is that "parseNonEmpty gives the caller access to
the information it learned, while validateNonEmpty just throws it away." Once parsing happens at
the boundary, "once those checks have been performed, they never need to be checked again!"

The argument against the alternative is **shotgun parsing**, a term she takes from the LangSec
paper *The Seven Turrets of Babel: A Taxonomy of LangSec Errors and How to Expunge Them* (2016):
"a programming antipattern whereby parsing and input-validating code is mixed with and spread
across" processing code — throwing a cloud of checks at the input and hoping one catches. Its
consequence is that the program is deprived "of the ability to reject invalid input instead of
processing it," leaving state unpredictable. **Every repeated `if x is None` (C4) and every
duplicated validation (C14) is shotgun parsing.** Her two headline rules: "Use a data structure
that makes illegal states unrepresentable" and "Push the burden of proof upward as far as
possible, but no further" — restated as "write functions on the data representation you wish you
had, not the data representation you are given." She calls these "ideals to strive for, not
strict requirements to meet."

### 5.2 Make illegal states unrepresentable (Yaron Minsky, Jane Street)

The phrase originates as a section heading in Minsky's **"Effective ML"** talk (Jane Street;
delivered as a guest lecture to Harvard's CS51 and reprinted with updated code on the Jane
Street Tech Blog as *Effective ML Revisited*). Exact heading: **"Make illegal states
unrepresentable."** His worked example is exactly the C10 conflict: a `connection_info` record
carrying a state variant *plus* a bag of optional fields (`last_ping_time`, `session_id`,
`when_disconnected`) that are meaningful in only some states — refactored into per-state records
attached to the variant constructors, so no invalid combination can be written down. Neighbouring
headings from the same talk are worth knowing: "Code for exhaustiveness", "Use uniform
interfaces", "Make common errors obvious". Goetz later adopts the phrase verbatim as DOP
principle 4 (§6).

### 5.3 Wlaschin — *Domain Modeling Made Functional* / "Designing with types"

The fsharpforfunandprofit series, in order, with his own subtitles:

| # | Post | Subtitle | Doctrine mapping |
|---|---|---|---|
| 2 | Single case union types | "Adding meaning to primitive types" | Primitive Obsession → newtype |
| 3 | Making illegal states unrepresentable | "Encoding business logic in types" | C10 deleted by construction |
| 4 | Discovering new concepts | "Gaining deeper insight into the domain" | Conceptual Contours, found by typing |
| 5 | Making state explicit | "Using state machines to ensure correctness" | C10 → one type per state |
| 6 | Constrained strings | "Adding more semantic information to a primitive type" | smart constructor |
| 7 | Non-string types | "Working with integers and dates safely" | Whole Value for numerics/dates |

The constrained-type recipe: "create wrapper types which have the constraints built into the
type", plus a `create` function that "takes a constructor function and creates new values using
it only when the validation passes" — returning `Some`/`None` rather than raising. The rule that
matters: the problem "should be dealt with when the string was *first created*, not when it is
*used*", and decisions like truncate-vs-fail "have to be taken *up front*." Honest caveat: in
that post the wrapper constructor is *public*, and enforcement comes from module organisation
and convention; he acknowledges the "only one place can construct it" question and defers it to
a separate gist. Private-constructor enforcement (F# signature files, Haskell smart-constructor
modules, Scala `private` case class apply) is real but is not what that article demonstrates.

**Railway Oriented Programming** (FP eXchange, 14 March 2014; also NDC London/Oslo 2014) is his
name for two-track error handling — `type TwoTrack a b = Either [a] (b,[a])`, success on one
track, failure on the other, functions composed along them, with "Mapping from exceptions to
error cases" as an explicit technique. He is clear the analogy is the only novel part: "although
I do lay claim to the silly analogy." **Contested, by him:** he links his own piece *Against
Railway-Oriented Programming* and warns against overuse, and notes the two-track type with bind
is not properly a monad. So: ROP replaces C7 (`try/except` doing real alternative work) with
values — but a guard clause that fails fast is still simpler than a Result chain.

### 5.4 Total functions, sum types, exhaustiveness

A **sum type** (ADT / sealed hierarchy / discriminated union) plus an exhaustive match *is* "one
resolver per case", checked by the compiler. A **total function** is one defined for every
input — which is what a total resolver set achieves at runtime and what a sum type achieves at
compile time. JEP 441 (Java 21) states the requirement precisely: with a sealed selector, "the
type coverage check can take into account the `permits` clause", so covering every permitted
subtype means "this switch block is exhaustive. As a result, no `default` label is needed" —
and the motivation section names the alternative it replaces: without patterns "we end up with a
chain of `if...else` tests", which "allows coding errors to remain hidden because we have used
an overly general control construct." The honest limit, also from the JEP: "Exhaustiveness is a
compile-time approximation of true run-time exhaustiveness" — separate compilation can add
cases later, so the compiler inserts a synthetic `default` that throws `MatchException`.

| Language | Closed-set mechanism | Exhaustiveness checked? | Enforcement to switch on |
|---|---|---|---|
| Haskell / OCaml / F# | ADT, single-case union | yes, natively | `-Wincomplete-patterns` / `-Werror`; F# warning FS0025 |
| Rust | `enum` | yes, `match` must be total | `#[non_exhaustive]` for open sets |
| Kotlin / Scala 3 | `sealed` | yes, when used as an expression | compiler warning → error |
| Java 21+ | `sealed interface` + records | yes, pattern `switch` | omit `default`; no `MatchException` in prod |
| TypeScript | discriminated union | only via the `never` trick | `@typescript-eslint/switch-exhaustiveness-check` |
| Python | `Literal` / `Enum` / union + `match` | ★ **no runtime check**; type-checker only | `mypy --strict` + `typing.assert_never` in the fallthrough |
| Go | none (no sum types) | no | `exhaustive` linter over enum `switch` |

For the bottom three rows, the check is a *linter obligation*, not a language guarantee — a
finding if absent. For the top four, an exhaustive match is **not a conflict** (doctrine §1) and
must not be converted into a registry.

### 5.5 Option/Maybe vs null

Hoare, at **QCon London 2009**, in a talk titled *Null References: The Billion Dollar Mistake*:
"I call it my billion-dollar mistake. It was the invention of the null reference in 1965." He
had been building the first thorough type system for references in an OO language (ALGOL W),
intending every reference use to be provably safe — and put in null anyway because it was so
easy to implement. Consequence for this doctrine: **C4 (`if x is None` repeated) is not a
conditional to promote — it is a type error to delete.** Replace with `Option`/`Maybe`/nullable
types plus a `Null`/`Absent` resolver at the boundary. `Optional` as a *field* type is the
anti-pattern; as a *return* type at a boundary it is the fix.

---

## 6. Data-Oriented Programming — Goetz, *Java* (InfoQ, 20 June 2022)

Goetz's four principles, verbatim headings and order:

| # | Principle (verbatim) | His gloss |
|---|---|---|
| 1 | **"Model the data, the whole data, and nothing but the data."** | one record per thing, clearly named components; "where alternatives exist, use sealed classes with a record per case"; behaviour in records limited to "derived quantities from the data itself, such as formatting" |
| 2 | **"Data is immutable."** | a mutable `int` field models not an integer but "a time-varying relationship between a specific object identity and an integer"; records are "shallowly immutable" |
| 3 | **"Validate at the boundary."** | in the record constructor "if the validation applies universally to all instances", else in the boundary code that received it |
| 4 | **"Make illegal states unrepresentable."** | "This is much better than having to check for validity all the time!" |

Principles 2–4 are the **Context** object of doctrine §6, arrived at independently: immutable,
validated once at the edge, illegal combinations unconstructible.

Against classic OO polymorphism, he argues sealed interfaces + records + pattern matching are
strictly better than **Visitor**: pattern matching "is clearly more concise than visitors, but
it is also more flexible and powerful", because visitors "require the domain to be built for
visitation" whereas pattern matching "supports much more ad-hoc polymorphism" and "composes
better" via nested patterns; and with sealed types "the compiler can type-check that a switch
handles all the option types."

**But read his conclusion before citing him as anti-OO.** He is explicit that DOP "is not at
odds with object orientation": OO remains strongest at "defining and defending boundaries" and
for modelling complex entities and rich libraries; DOP suits simple services over plain, ad-hoc
data. The two are "different tools for different granularities and situations." Anyone quoting
Goetz to justify replacing every interface with a `switch` is misquoting him.

---

## 7. The expression problem, and when NOT to reach for polymorphism

Wadler's formulation (note to the Java Generics list, 12 November 1998): the goal is "to define
a datatype by cases, where one can add new cases to the datatype and new functions over the
datatype" — without recompiling existing code, and while preserving static type safety (no
casts). He calls it "a new name for an old problem". His table metaphor: **cases are rows,
functions are columns.** Functional languages fix the rows and make adding columns easy;
object-oriented languages fix the columns and make adding rows easy. Handling both directions
is, in his words, "a salient indicator of [a language's] capacity for expression."

The decision rule follows directly from which axis is going to move.

| Situation | Growing axis | Choose | Why | Do NOT |
|---|---|---|---|---|
| New kinds of thing keep arriving; the operations on them are stable | rows (cases) | **port + resolvers**, one file each | adding a case adds a file and a registry entry; touches nothing else | don't add a case to N `switch`es |
| Case set is fixed and small; new operations keep arriving | columns (operations) | **sealed interface + exhaustive match**, or **Visitor** | adding an operation is one new function; the compiler finds every case it must handle | don't create a port — every new operation would break every resolver |
| Both axes move | both | **sealed core + typeclass/protocol per operation family** (or Specification for predicates) | the only way to keep both cheap; costs an indirection | don't pick one axis and hope |
| Language checks totality over a closed set | either | ★ **leave it alone** | it is already the doctrine, enforced by the type system | don't convert to runtime dispatch to satisfy a rule |
| The discriminant is open (plugins, tenants, unknown future inputs) | rows, unboundedly | **chain of responsibility + `Absent` last** | no closed set exists to be exhaustive over | don't fake a sealed enum |
| One case today, none named for tomorrow | neither | **inline it** | a one-resolver port is Speculative Generality | don't build the port "for symmetry" |

State plainly, and repeat it in every review: **a sealed hierarchy with compiler-checked
totality is already this doctrine, enforced by the type system, and must not be converted into
runtime dispatch to satisfy a rule.** Converting it *loses* a guarantee — it moves a compile-time
error to a `KeyError` at 3am — while adding files, edges, and a registration test. Record the
choice per port in the spec, naming the axis you expect to move and why. If the axis you named
turns out to be wrong, that is a re-cut along a **Conceptual Contour**, not a defect.
