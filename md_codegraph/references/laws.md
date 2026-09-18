# Laws — every named rule, every numeric cap, and its source

Cite the **name** and the **source**. `[P]` = quoted from the primary text, fetched and checked here. `[P*]` = primary text reached by another agent
this session; the quote and its page number were **not independently re-fetched here**, so treat a page number as one remove from the source. `[S]`
= checked against a reliable secondary (author's blog, vendor docs, tool source). Unverifiable claims were cut, not hedged. `SKILL.md` holds our
caps and is the authoritative column; §8 flags every published disagreement, and **§9 says plainly that our caps are a house style with a rationale,
not a validated threshold.**

---
## 1. SOLID, in the original words

| # | Statement | Source | Mechanical detection |
|---|---|---|---|
| **SRP** | "each software module should have one and only one reason to change"; "Gather together the things that change for the same reasons. Separate those things that change for different reasons."; "*This principle is about people.*" `[P]` — later restated "A module should be responsible to one, and only one, actor." `[S]` (*Clean Architecture* 2017 ch. 7) | Martin, *SRP*, blog.cleancoder.com, 8 May 2014 | git co-change: one file edited by commits from ≥2 unrelated features (Divergent Change); map each public method to its requesting role |
| **OCP** (Meyer) | open = "still available for extension"; closed = "available for use by other modules" `[S]`; *OOSC* §3.3 heading: "Modules should be both open and closed" `[S]` | Meyer, *OOSC*, 1988 | — (mechanism is subclassing a released **concrete** class) |
| **OCP** (Martin) | "To paraphrase him: SOFTWARE ENTITIES (CLASSES, MODULES, FUNCTIONS, ETC.) SHOULD BE OPEN FOR EXTENSION, BUT CLOSED FOR MODIFICATION." `[P]` | Martin, *The Open-Closed Principle*, C++ Report 1996 | adding a case requires editing an existing file = violation |
| **LSP** | 1987: "If for each object o1 of type S there is an object o2 of type T such that for all programs P defined in terms of T, the behavior of P is unchanged when o1 is substituted for o2 then S is a subtype of T" `[S]`. 1994 Subtype Requirement: "Let φ(x) be a property provable about objects x of type T. Then φ(y) should be true for objects y of type S where S is a subtype of T." `[S]` | Liskov, OOPSLA'87 keynote; Liskov & Wing, TOPLAS 16(6), 1994 | run the port's shared contract suite against **every** resolver |
| **ISP** | "CLIENTS SHOULD NOT BE FORCED TO DEPEND UPON INTERFACES THAT THEY DO NOT USE." `[P]` | Martin, *The Interface Segregation Principle*, C++ Report 1996 | an implementer whose body is `pass`/`raise NotImplemented`; a caller using <half an interface |
| **DIP-A** | "HIGH LEVEL MODULES SHOULD NOT DEPEND UPON LOW LEVEL MODULES. BOTH SHOULD DEPEND UPON ABSTRACTIONS." `[P]` | Martin, *The Dependency Inversion Principle*, C++ Report 1996 | import graph: business logic naming a driver/adapter module |
| **DIP-B** | "ABSTRACTIONS SHOULD NOT DEPEND UPON DETAILS. DETAILS SHOULD DEPEND UPON ABSTRACTIONS." `[P]` | ibid. | a port module importing a concrete SDK type in a signature |

**Martin's OCP is explicitly a paraphrase of Meyer, and the mechanisms differ.** Meyer keeps a *compiled, concrete* class closed and extends it by
inheritance, reusing implementation; Martin freezes an *abstract* interface and varies behind it by dynamic binding, reusing only the contract. We
use Martin's: concrete-inherits-concrete is banned (`doctrine.md` §10). The Xerox-printer origin story for ISP is **not** in his 1996 column —
folklore.

**LSP's conditions** `[S]`: contravariant parameters · covariant returns · no new exception types · preconditions not strengthened · postconditions
not weakened · invariants preserved · **history constraint** (no state transition the supertype forbids — Liskov & Wing's own contribution). A
contract suite is the enforcement.

**DIP is not DI and is not IoC.** **IoC** is the phenomenon — the framework owns the flow and calls your code; Fowler: "Inversion of Control is too
generic a term, and thus people find it confusing" `[P]`. **DI** is one *technique* for supplying dependencies ("we settled on the name *Dependency
Injection*" `[P]`), whose rival is Service Locator: "the application class asks for it explicitly … With injection there is no explicit request"
`[P]`. **DIP** is a *principle* about the **direction** of source dependencies and **who owns** the abstraction — textbook DI still violates it if
you inject a concrete class or declare the interface in the implementer's package. Ownership, mechanized: interfaces "belong in the package that
uses values of the interface type, not the package that implements those values", and "Do not define interfaces before they are used" `[P]` (Go Code
Review Comments) — Fowler's **Separated Interface**, and our port placement.

---
## 2. Component principles — the graph-level laws

Dropped from most SOLID summaries; these are what the graph phase enforces. Verbatim below: Martin, *Granularity*, C++ Report, Nov–Dec 1996 `[P]`.

| Cohesion | Verbatim | Detection |
|---|---|---|
| **REP** | "THE GRANULE OF REUSE IS THE GRANULE OF RELEASE. ONLY COMPONENTS THAT ARE RELEASED THROUGH A TRACKING SYSTEM CAN BE EFFECTIVELY REUSED. THIS GRANULE IS THE PACKAGE." | code reused across deployables with no versioned release boundary |
| **CCP** | "THE CLASSES IN A PACKAGE SHOULD BE CLOSED TOGETHER AGAINST THE SAME KINDS OF CHANGES. A CHANGE THAT AFFECTS A PACKAGE AFFECTS ALL THE CLASSES IN THAT PACKAGE." | git co-change clusters straddling component boundaries (Shotgun Surgery) |
| **CRP** | "THE CLASSES IN A PACKAGE ARE REUSED TOGETHER. IF YOU REUSE ONE OF THE CLASSES IN A PACKAGE, YOU REUSE THEM ALL." | a consumer importing 1 symbol from a 40-symbol component |

**The tension triangle.** CCP pushes components *larger*, CRP *smaller*, REP bounds both by what ships as one release; the three cannot be maximized
together. Young systems lean CCP; published libraries lean REP + CRP. (*Clean Architecture* ch. 13 draws this as a tension diagram; that wording is
unverified here.)

| Coupling | Verbatim | Metric |
|---|---|---|
| **ADP** | "THE DEPENDENCY STRUCTURE BETWEEN PACKAGES MUST BE A DIRECTED ACYCLIC GRAPH (DAG). THAT IS, THERE MUST BE NO CYCLES IN THE DEPENDENCY STRUCTURE." | Tarjan SCC of size ≥2 |
| **SDP** | "Depend in the direction of stability." Restated: "Depend upon packages whose I metric is lower than yours." | **I = Ce/(Ca+Ce)** ∈ [0,1] |
| **SAP** | "Stable packages should be abstract packages." — in *Clean Architecture*, "A component should be as abstract as it is stable" `[S]` | **A = Na/Nc** ∈ [0,1] |

**Breaking a cycle — the only two techniques** `[P]`: (1) "Apply the Dependency Inversion Principle (DIP)" — put an abstract base carrying the
interface the client needs *into the client's package*; (2) "Create a new package" that both cycle members depend on.

**Ca** = "The number of classes outside the package that depend upon classes inside the package"; **Ce** = outgoing; **Na** = abstract classes;
**Nc** = all classes `[P]`. **Main Sequence** = the line **A + I = 1**; distance, verbatim, is **D = |A+I−1| / √2** (range [0, ~0.707]) and **D′ =
|A+I−1|** (range [0,1]) `[P]` — *Clean Architecture* (2017) publishes the normalized form as plain **D** `[S]`, so the familiar formula is the
book's D and the 1996 paper's D′. Target ≈ 0. **Zone of Pain** = lower left (A≈0, I≈0): "Since the elements there are concrete, they cannot be
extended … and since they have lots of incomming dependencies, the change will be very painful" `[P]` — extract ports, though non-volatile
concretions (a string library, a frozen schema) may legitimately live there. **Zone of Uselessness** = upper right, "packages that are highly
abstract and that nobody depends upon" `[P]` — **delete it**, it is Speculative Generality at component scale.

> **The Dependency Rule.** "The overriding rule that makes this architecture work is The Dependency Rule. This rule says that source code
> dependencies can only point inwards. Nothing in an inner circle can know anything at all about something in an outer circle." `[P]` — Martin, *The
> Clean Architecture*, 13 Aug 2012.

Mechanically: for every import, `layer(importer) ≥ layer(imported)` — `doctrine.md` §9 is the same predicate over folder paths.

---
## 3. Object Calisthenics — Jeff Bay, *The ThoughtWorks Anthology* (2008)

The provenance for **no `else`**, **one level of indentation**, and **wrap primitives**. Bay frames the nine as an **exercise**: "spend 20 hours and
1000 lines writing code that conforms 100% to these rules", after which "you can relax and go back to using these 9 rules as guidelines" — and he
concedes "sometimes classes are a little more than 50 lines" `[P]`.

| # | Rule | Number | Here |
|---|---|---|---|
| 1 | One level of indentation per method | **1**; "limit method length to 5 lines" is stated here, as a guideline | our nesting cap **is** Bay's number |
| 2 | Don't use the `ELSE` keyword | **0** | our `else` cap; `ruff RET505`/`SIM108` are the checks |
| 3 | Wrap all primitives and Strings | — | Value Objects in the Context; kills Primitive Obsession |
| 4 | First class collections | — | "any class that contains a collection should contain no other member variables" |
| 5 | One dot per line | **1** | Law of Demeter, mechanized |
| 6 | Don't abbreviate | names of **1–2 words** | intention-revealing names |
| 7 | Keep all entities small | **"no class over 50 lines and no package over 10 files"** | the 50-line class is far stricter than ours; the 10-file package is **looser** — ours is 5/**7** (§8) |
| 8 | No classes with more than two instance variables | **2** | pushes composition; conflicts with our Context |
| 9 | No getters/setters/properties | — | Bay: "Another way this rule is commonly stated is 'Tell, don't ask'" |

**The five named critics, strongest first** `[S]`. (1) **Braithwaite's if-vs-iff argument** — "Just because we observe some property of good
software, it does not follow that software deliberately written to exhibit this property will be good"; that is the correct frame for every cap in
§8. (2) **Nat Pryce**, an insider: "not a single one of those rules touches on the one thing common between object-oriented languages: polymorphism"
— they describe abstract data types. (3) **Dubroy** (2008): "If you break your code up into 10 different methods, then that's 10 different places I
have to look"; "You're just writing spaghetti code by a different name." (4) **Christian Vest Hansen**: the 50-line rule produces *lower* cohesion
and *higher* coupling — and **Binstock, the rules' own popularizer, publicly conceded the point.** (5) **Mike Simons**: they are a canonical form
like database 5NF, something you normalize *through*, not a target state. Resolution: 1, 2, 5, 7 as caps; 3, 4, 8, 9 as pressure.

---
## 4. Connascence — Meilir Page-Jones; popularized by Jim Weirich

Two components are connascent if changing one requires changing the other to stay correct.

| Kind | Definition | Detection hint |
|---|---|---|
| **Name** (static, weakest `[P]`) | "multiple components must agree on the name of an entity" `[P]` | rename the symbol, count edits (LSP references) |
| **Type** | must agree on a type | shared DTO shape; annotation/signature match |
| **Meaning / Convention** | must agree on what a *value means* | magic literals `0`/`1`/`""`/`"active"`, sentinel returns, status strings |
| **Position** | must agree on order | ≥3 positional args, tuple returns, CSV column order → Context |
| **Algorithm** | must agree on an algorithm | duplicated hash / checksum / serialization / validation in ≥2 modules |
| **Execution** (dynamic) | order of execution matters | `init()` before `run()`; field set by one method, read by another |
| **Timing** | *when* matters | sleeps in tests, timeouts, TTL assumptions, race windows |
| **Value** | values must change together | one invariant split across objects (`start`/`end`, total vs lines) |
| **Identity** | must reference the *same instance* | shared mutable singleton, cache/session passed by reference |

**Three axes** `[P]` (connascence.io): **strength** — stronger connascence is "harder to discover, or harder to refactor"; **degree** — how many
entities are involved; **locality** — "Connascent elements that are close together in a codebase are better than ones that are far apart." **Rules
of thumb:** (1) convert **strong** connascence into **weaker** (meaning → type; position → name); (2) reduce **degree** and improve **locality** —
strong connascence *inside* one module is fine, the same strength *across* a boundary is a finding. Static kinds are compile-time detectable,
dynamic kinds are not, which is why only contract tests catch them. Promoting a conflict to a port converts scattered connascence of
meaning/algorithm into connascence of name on one port.

---
## 5. Cohesion and coupling — Myers (1975) and Yourdon & Constantine (1979)

**Cite it as** the six-level coupling scale (Myers, *Reliable Software Through Composite Design*, Petrocelli/Charter 1975, ch. 4) `[P*]`, built on
the coupling concept of Stevens, Myers & Constantine, *Structured design*, IBM Systems Journal 13(2), 1974 `[P*]`, and elaborated as four factors in
Yourdon & Constantine, *Structured Design*, 1979 (SD79), ch. 6 `[P*]`. **The ranked ladder is Myers', not Y&C's**: "stamp coupling" and "external
coupling" have *zero* occurrences in the full SD79 text and are absent from the 1974 paper, and SD79 says "common-environment coupling". Only *data*
and *control* coupling appear in all three.

**Prefer this over any ladder position when a level is ambiguous** (SD79 p. 77) `[P*]`: "Coupling as an abstract concept — the degree of
interdependence between modules — may be operationalized as the probability that in coding, debugging, or modifying one module, a programmer will
have to take into account something about another module." That is the direct ancestor of Beck's change-relative definition.

**Coupling, worst → best** (Myers 1975 p. 33, his order verbatim) `[P*]`: **content** (reaching into another module's internals) · **common**
(shared global/mutable state) · **external** (a shared imposed format, protocol, or device) · ★ **control** (passing a module information on what to
do) · **stamp** (a whole record passed where one field is used) · **data** (elementary values as parameters). Y&C offer no ladder; instead four
factors (SD79 §6.1 p. 78) — **type of connection · complexity of interface · type of information flow · binding time** — three in the 1974 paper
(Table 1) `[P*]`.

**Cohesion, worst → best** (SD79 ch. 7 names) `[P*]`: **coincidental** (arbitrary — the `utils`/`helpers` grab-bag) · **logical** (same broad
category, different natures; one entry point with a mode flag) · **temporal** (grouped by *when* — `init()`, `cleanup()`) · **procedural** (grouped
because they run in this sequence) · **communicational** (same data) · **sequential** (one part's output is the next's input) · **functional** (one
well-defined task). **The level count differs by source, and the two numeric scales must never be mixed in one metric:** six in 1974 (called
*binding*, no procedural), seven in SD79 (procedural inserted 4th, renamed *cohesion*), a different seven in Myers 1975 (called *strength*,
"classical" for temporal, plus an extra *informational*) — and the weights run in **opposite** directions (SD79 §7.3: coincidental 0 … functional
10; Myers p. 149: functional 0.2, coincidental 0.95) `[P*]`.

**Score a module as a MIN over its elements, never an average** (SD79 §7.3 p. 121) `[P*]`: "The cohesion of a module is approximately the highest
level of cohesion which is applicable to all elements of processing in the module" — it "behaves as if it were 'only as strong as its weakest
link.'" And name the goal correctly: **"Constantine's Law" is folklore** — zero hits in the full SD79 text, whose only named laws are Murphy's,
Mealy's and Conway's. Use Myers p. 33, "Thus the goal is achieving high strength and low coupling", or SMC74 p. 121, "The objective here is to
reduce coupling by striving for high binding" `[P*]`.

★ **Control coupling is the boolean-flag smell, named.** SMC74 p. 120 `[P*]`: "Control arguments are an additional complication to the essential
data arguments required for performance of some task, and an alternative structure that eliminates the complication always exists." A
`bool`/mode/`what_to_do` parameter selecting behaviour is Fowler's *Flag Argument*, Martin's **F3/G15**, doctrine conflict **C5**, and control
coupling — one defect, four names, always promote. **Logical cohesion and control coupling are the same defect seen from two sides**, so a
flag-argument finding reports both. "Message coupling" and "no coupling" are later textbook additions, not in the originals.

**Do not re-introduce the standard version of this error.** "Yourdon & Constantine's 7 cohesion levels and 6 coupling levels" — the form in which
this material is almost always taught, and the form of the brief this file was written from — **conflates three different texts and two incompatible
numeric scales.** The coupling ladder is Myers', the cohesion names and the 0–10 weights are SD79's, the six-level *binding* list is SMC74's, and
Myers' own strength weights run in the opposite direction. There is no single source that contains "7 and 6". Cite the text you actually mean, and
never combine numbers across two of them.

---
## 6. GRASP — Craig Larman, *Applying UML and Patterns* (3rd ed., 2004)

Nine responsibility-assignment patterns `[S]`; the four in bold are this skill's working set.

| Pattern | One line |
|---|---|
| **Information Expert** | "Assign responsibility to the class that has the information needed to fulfill it" — the fix for Feature Envy |
| Creator | B creates A if B aggregates, records, closely uses, or holds A's initializing data |
| Controller | a non-UI object that receives and handles a system event |
| Low Coupling / High Cohesion | the two evaluative patterns: minimize reliance on others, keep each object focused |
| **Polymorphism** | assign type-varying behaviour to the types, not to a conditional |
| **Pure Fabrication** | "a class that does not represent a concept in the problem domain," invented for cohesion/coupling — a registry, a resolver set |
| **Indirection** | "Assign the responsibility to an intermediate object to mediate between other components" — the port |
| **Protected Variations** | "Identify points of predicted variation or instability; assign responsibilities to create a stable interface around them" |

**Protected Variations is the closest published statement of this doctrine**, and the load word is *predicted* — which is the promotion threshold.
Attribution of PV to Cockburn is unconfirmed: cite Larman.

---
## 7. Law of Demeter — Lieberherr & Holland (Northeastern, 1987–89)

Proposed by Ian Holland in the **Demeter** project. Sources: Lieberherr, Holland & Riel, OOPSLA'88; Lieberherr & Holland, *Assuring good style for
object-oriented programs*, IEEE Software 6(5), 1989 `[S]`.

**Formulation (for functions):** a method `m` of object `a` may invoke methods of only `[S]`: `a` itself · `m`'s parameters · objects instantiated
within `m` · `a`'s direct components · globals in scope. Slogans: "Only talk to your immediate friends"; "don't talk to strangers." **Object form**
= a runtime constraint on reachable receivers; **class form** = a static constraint on the class graph, checkable from declarations, so it is what a
linter enforces (PMD `LawOfDemeter`). At method level it "leads to narrow interfaces"; at class level, "wide … interfaces" `[S]`.

**Tell, Don't Ask** is the positive restatement — Andy Hunt & Dave Thomas, *The Art of Enbugging*, IEEE Software Jan/Feb 2003, pp. 10–11, crediting
Alec Sharp, *Smalltalk by Example* (1997). Fowler dissents: "But personally, I don't use tell-dont-ask" — it breeds *GetterEradicators* when "there
are times when objects collaborate effectively by providing information" `[P]`.

**Wrapper-explosion critique** `[S]`: compliance "may result in having to write many wrapper methods to propagate calls to components", at time and
space cost. The checkable form of that failure is Ousterhout's **Pass-Through Method** (*APOSD* §7.1) — a method that only forwards, adding an edge
and no abstraction — with **Conjoined Methods** as its companion red flag. Basili et al. (1996) sharpen it: Demeter lowers RFC (good) and raises WMC
(bad). And the dot count is not the law (Haack, 2009): a fluent builder or a pure value chain is fine; reaching through a *foreign* object's
structure is not.

---
## 8. The numeric caps — consolidated

The **This skill** column is authoritative (`SKILL.md`, machine-checked by `scripts/caps.sh`). Published figures are evidence, never an override; §9
gives their empirical standing.

| Metric | This skill (warn/**hard**) | Published value(s) | Source | Contested? |
|---|---|---|---|---|
| File / class length | 200 / **250**, **code files only** | **50** lines/class `[P]`; **100** lines/class `[S]`; "60 is a common limit … each software module should fit on one printed page" `[P]` | Bay r7; Metz r1; NIST SP 500-235 | **yes** — Bay and Metz are 2.5–5× stricter than us |
| Method / function length | 15 / **25** | **5** `[P]` (Bay r1, Metz r2); "two, three, or four lines long" `[P]` (*Clean Code* p. 34); **~60** = one printed page `[P]` (NASA P10 R4); "one or two screenfuls … 80x24" `[P]` (Linux); "about 40 lines → think about whether it can be broken up" `[S]` (Google C++) | many | **yes** — the widest disagreement in the field; Ousterhout rejects length caps outright (§9) |
| Nesting depth | **1** | **1** `[P]` (Bay r1); "if you need more than 3 levels of indentation, you're screwed anyway, and should fix your program" `[P]` | Bay; Linux CodingStyle | Linux tolerates 3; Bay is our provenance |
| Loop body length | **8** | none published | this skill | local rule, no authority claimed |
| `else` / `elif` count | **0** outside a registry | **0** — "Don't use the ELSE keyword" `[P]` | Bay r2 | yes — dogma when a two-armed `if` is clearest |
| Parameters | 3 / **4** or 1 Context | "Pass no more than **four** parameters into a method. Hash options are parameters." `[S]` (Metz r3); refactor above **two** `[P]` (Bugayenko); locals "shouldn't exceed 5-10" `[P]` (Linux) | | mild |
| Methods per port | **3** | no number published: "The bigger the interface, the weaker the abstraction" `[P]`; "Do not define interfaces before they are used" `[P]`; "Expose fewer than five public methods" `[P]` | Go Proverbs; Go CRC; *Elegant Objects* §3.1 | the number is ours, the direction is theirs |
| Implementation hierarchy depth | **2** (port → resolver) | no published cap; "DITs > 5 could be overkill" `[S]`; Sonar `S110` flags deep trees | NASA SATC | ours is stricter by design |
| Module-graph cycles | **0** | 0 — ADP `[P]` | Martin 1996 | no |
| Public members per class | 5 / **7** | **<5** public methods `[P]`; "A human brain can generally easily keep track of about 7 different things" `[P]`; WMC threshold **100**, methods/class 20 preferred / 40 acceptable `[S]` | *Elegant Objects* §3.1; Linux; NASA SATC | 7±2 applied to code is folk psychology |
| Composition roots per deployable | **1** | "A Composition Root is a (preferably) unique location in an application where modules are composed together" `[P]` | Seemann, 2011 | no |
| Instance variables / attributes | — (Context exempt) | **2** `[P]` (Bay r8); **≤4** attributes `[P]` (*Elegant Objects* §2.1) | | **yes** — both irreconcilable with a Context; we reject them |
| Files directly in one folder | 5 / **7** code files | **10** per package `[P]` | Bay r7 | ours is stricter; Bay's is the only published number in the neighbourhood |
| Cyclomatic complexity | not capped directly (implied by 25 lines + nesting 1) | **10** — "a reasonable, but not magical, upper limit" `[P]`; large `case` statements exempted `[P]`; "limits as high as 15 have been used successfully as well" `[P]`; bands 1–10 simple / 11–20 moderate / 21–50 high / >50 "untestable program (very high risk)" `[P]` | McCabe, IEEE TSE SE-2(4), 1976, p. 314; NIST SP 500-235 §2.5; **bands: CMU/SEI-97-HB-001 p. 147, not NIST** | **yes** — NIST: the limit "remains somewhat controversial" `[P]` |
| Cognitive complexity | not capped | **15** per method — the analyzer default `[P]` (Java, Python, PHP, JS/TS, C#/VB; C# adds property max 3) | Sonar `S3776` source | the white paper itself publishes **no** threshold `[P]` |
| NPath | not capped | **200** `[S]` | Checkstyle/PMD, from Nejmeh's "informal NPATH limit of 200" at AT&T Bell Labs, CACM 31(2), 1988 | an in-house limit tooling adopted, not a formal recommendation |
| Assertion density | — | "a minimum of **two** assertions per function" `[P]` | NASA/JPL P10 R5 | safety-critical context only |

**Three scope rules, without which every number above is misread.**

**1. The 250-line cap is scoped to code extensions.** `caps.sh` measures `file_lines` on source files only; markdown, data and config files are not
measured and are not findings. The cap is a claim about how much *code* one file may hold, so firing it on prose is a false finding — and a tool
that emits false findings gets ignored wholesale, which costs far more than an unmeasured README. This reference file is itself well over 250 lines,
deliberately. Length limits on prose, if you want them, are a different rule with a different justification, and this skill does not make one.

**2. The folder cap counts files, never folders, and its remedy is a name.** `folder_files` is the only cap whose subject is a directory, and it
exists because of `doctrine.md` §9: a folder is a question node, a file is an answer node. Nineteen answers directly under one folder is not a
quantity problem, it is a **missing question** — the folder's name no longer predicts what is inside it, so the tree has stopped being the graph and
the reader is back to opening files to find out. Hence the shape of the cap: **5 warn / 7 hard on the code files directly in a folder, and no cap
whatsoever on subfolders.** Depth is the remedy, so charging for depth would punish the fix; a folder holding twenty folders and two files is
correct by this rule and usually excellent. Three scoping details, each of which would otherwise produce a false finding: `.tf`/`.tfvars` are not
counted, because in Terraform the directory *is* the module and the remedy the cap asks for would create a different module; `.h`/`.hpp` are not
counted, because a header declares the answer its source defines; and a **total answer set is not a breach** — nine resolvers answering one
question, one per file, is exactly what §4 of the doctrine asks for, and splitting them into sub-buckets to satisfy a number is the interface farm
wearing a different hat. That last case is what the folder-level exemption is for, and its home is a `.codegraph-exempt` file **in the folder**
(`codegraph:exempt folder_files -- <reason>`), because a directory has no declaration to put a pragma above. Same two conditions as rule 3 and the
same `exempt` severity in the report — including the failure mode: a marker that names `folder_files` and gives no reason after `--` suppresses
nothing, the breach keeps its real severity, and the folder is additionally reported as `exempt_without_reason`, exactly as a reasonless source
pragma is. A marker that cites nothing is not a quieter cap; it is a second finding.

**3. An exemption is a seam, not an escape hatch — and the difference is mechanical.** `scripts/lib/cap_pragma.py` reads a source-line pragma placed
directly above the declaration (above the first decorator, when there is one). Two metrics have no declaration to sit above, so each has one other
home and the same grammar: `file_lines` is exempted in the **first 20 lines of the file**, and `folder_files` in a **`.codegraph-exempt` file inside
the folder** (rule 2). The pragma itself:

```
# codegraph:exempt method_lines, loop_body, nesting -- <reason>
```

Three properties are what make it a seam, and all three are enforced, not documented: (a) it **must name each metric** it suppresses, so there is no
exempt-everything form and no pragma can quietly widen its own scope later; (b) it **must carry a reason** after `--` — a pragma without one
suppresses **nothing** and is itself reported as `exempt_without_reason`, so the lazy form is louder than the breach it tried to hide; (c) a
suppressed finding is still **printed, with severity `exempt`**, so the report states what it chose not to count. An invisible exemption is
indistinguishable from a bug.

**The standard for a new one is a citation, not an excuse.** There are exactly **two** exemptions in this entire skill, both in
`scripts/lib/graph_metrics.py`: **Tarjan 1972** (SIAM J. Comput. 1:2, p. 157) and **Brandes 2001** (J. Math. Sociol. 25:2, Algorithm 1). Each is
kept in its paper's own single-body form so a reader can check it line by line against the published algorithm. That is the bar: the exemption
exists because the *published shape is the correctness argument*, and splitting it would make the code harder to verify, not easier. "This function
is complicated" is not that.

**NASA/JPL "Power of Ten"** — Holzmann, IEEE Computer, 2006 `[P]`. The strongest published backing for hard, tool-checkable caps: "The rules will
have to be specific enough that they can be checked mechanically." All ten: **(1)** simple control flow only — no `goto`, `setjmp`/`longjmp`, or
direct or indirect **recursion**; **(2)** every loop has a statically provable fixed upper bound; **(3)** no dynamic memory allocation after
initialization; **(4)** no function longer than a **sheet of paper (~60 lines)**, one statement per line; **(5)** **≥2 assertions per function**,
side-effect-free, never provably always true; **(6)** declare data at the smallest possible scope; **(7)** check every non-void return value and
validate every parameter inside the callee; **(8)** preprocessor limited to includes and simple macros, "rarely … more than one or two"
conditional-compilation directives; **(9)** at most **one level of pointer dereferencing**, none hidden in macros or typedefs, no function pointers;
**(10)** compile at the most pedantic setting with **zero warnings**, plus daily static analysis, also at zero. 1/2/4/5/6/7/10 transfer to any
language.

**Cognitive Complexity vs cyclomatic** — Campbell, SonarSource white paper v1.7, 2023 `[P]`. Three rules: ignore shorthand (no increment for the
method itself, for null-coalescing, or for `try`/`finally`); +1 per break in linear flow; extra increments for nesting. A whole `switch` "incurs a
single structural increment" where cyclomatic increments per `case`; one per `catch` however many types; one per *sequence* of like logical
operators; and unlike cyclomatic it charges "each method in a recursion cycle". Use it, not cyclomatic, to argue a method is *hard to read* rather
than *long*.

**Maintainability Index** — Coleman–Oman model 1 `[P]`: `MI = 171 − 5.2·ln(aveVol) − 0.23·aveV(g′) − 16.2·ln(aveLOC) + 50·sin(√(2.46·perCM))`.
Bands, per HP `[P]`: <65 poor, 65–85 fair, ≥85 excellent. Visual Studio rescales — `MAX(0,(171 − 5.2·ln(V) − 0.23·CC − 16.2·ln(LOC))·100/171)`, no
comment term — with 0–9 low, 10–19 moderate, 20–100 good `[P]`. Directional only; never a finding on its own.

**Chidamber & Kemerer** (MIT CISR WP 249, 1992 / IEEE TSE 20(6), 1994) `[P]`: **WMC** Σ method complexities (= method count if unity) · **DIT**
depth to root · **NOC** immediate subclasses · **CBO** classes coupled to · **RFC** |response set| · **LCOM** |P|−|Q| over method pairs, floored at
0. NASA SATC thresholds `[S]`: CBO **5**, RFC **100** ("very few classes with RFC over 50"), WMC **100**; none published for NOC or LCOM. Defect
correlation — Basili, Briand & Melo, IEEE TSE 22(10), 1996, 180 C++ classes `[P]`: **DIT and RFC very significant** (p=0.0000), **CBO significant**,
WMC marginal (p=0.06), **NOC significant but inverse** (more children → *fewer* faults), **LCOM insignificant in all cases**; multivariate kept DIT,
RFC, NOC, CBO and class origin, dropping WMC and LCOM. Caveat: 5–14 KSLOC student systems. So CBO/RFC drive the graph pass; LCOM is a hint.

**Metz's caveat** — "You should break these rules only if you have a good reason or your pair lets you", published as an explicit paraphrase of Metz
by Caleb Hearth, thoughtbot, 17 May 2013, and called "rule zero. It is immutable." `[P]` Her other line governs our promotion threshold:
"duplication is far cheaper than the wrong abstraction" (RailsConf 2014; written up Jan 2016) `[P]`.

**Bugayenko / Elegant Objects** — verified positions `[P]`: never return `NULL`; no code in constructors; no getters/setters; immutable objects; no
`-ER` names; no static methods, "not even private ones"; no `instanceof`/casting/reflection; no public method without an interface; no ORM; no
implementation inheritance. Verified numbers: **≤4 attributes** (§2.1), **<5 public methods** (§3.1), refactor above **2 arguments**. The
circulating "Bugayenko: 5-line methods / 250-line classes" figures **do not exist** in his corpus; his actual claim is that an ideal method body is
a single `return`. His no-getters, no-static and no-null positions are contested and break at framework boundaries.

---
## 9. Where these laws contradict each other — and what the evidence says

**The honest framing, first.** The nine Object Calisthenics rules have **never been empirically evaluated**, individually or as a bundle (OpenAlex
full-text: 1 hit — Loubser, *Software Engineering for Absolute Beginners*, Apress 2021, not research; Crossref: 1; arXiv: 0; DBLP bot-walled). Same
for Metz's four rules and for every numeric threshold in §8 — 5 lines/method, 100 lines/class, 4 parameters, and our own 25/250. **Our caps are a
house style with a stated rationale, not a validated threshold**; they are defensible as a *consistency* mechanism, and Braithwaite's if-vs-iff
argument (§3) is why they must never be reported as evidence-based. The strongest primary-source support for this position is the founders' own
hedge on their own numbers — SD79 p. 98, "These seven points do not constitute a linear scale. There are no data now extant that would permit
assigning more than a rank to each level", and p. 121–122, "It still would be inappropriate to add or subtract such numbers, as that would require
interval measurement" `[P*]`. If Constantine would not average his own cohesion scale, do not average ours.

**The size confound — the most defensible result in the corpus, and it cuts against us.** Sjøberg et al., IEEE TSE 39(8):1144–1156, 2013: "None of
the 12 investigated smells was significantly associated with increased effort after we adjusted for file size and the number of changes; Refused
Bequest was significantly associated with decreased effort" `[S]`. Olbrich et al. (ICSM 2010): the sign flips for God and Brain classes once
normalized for size `[S]`. Hall et al., ACM TOSEM 23(4):33, 2014: "Switch Statements had no effect on faults in any of the three systems" `[S]` —
directly against using `G23` as a *fault* argument. El Emam et al., IEEE TSE 27(7):630–650, 2001, is the class-size confound itself `[S]`.
Synthesis: **Long Method's apparent harm is largely its length, and Extract Method does not remove lines.** Argue caps from readability and review,
not defect rates.

**Two citation traps, since our caps invite both.** (1) McConnell's six studies showing longer routines had fewer defects (*Code Complete* 2e §7.4,
p. 173) are refuted in the same post that reproduces them — "if we model the relationship between any variable X and 1/X, we will get a negative
association" (Dubroy) — and they are Fortran/Pascal/assembly. Cite neither side as proof. (2) Buse & Weimer readability (IEEE TSE 36(4), 2010) does
**not** model method length at all — its snippets are three consecutive statements — so readability research cannot arbitrate method boundaries.

- **Ousterhout vs Martin on method length.** *A Philosophy of Software Design vs Clean Code* (github.com/johnousterhout/aposd-vs-clean-code,
  2024–25) `[P]`. *APOSD* §9.8: "length by itself is rarely a good reason for splitting up a method … developers tend to break up methods too much",
  and "Methods containing hundreds of lines of code are fine if they have a simple signature and are easy to read"; §5.5: "information hiding can
  often be improved by making a class slightly larger." Over-decomposition yields **shallow** methods and **entanglement** — you must flip between
  methods to understand one. Martin concedes over-decomposition exists, defends the One Thing Rule where the extraction is *meaningful*, and would
  "rather err on the side of decomposition" since extractions "can always be inlined." Ours: 25 lines hard, extract only what is nameable.
- **Ousterhout vs Martin on comments.** *Clean Code*: "Comments are always failures"; Ousterhout was "horrified" and writes "5-10x more lines of
  comments" `[P]`. Martin's rebuttal: the hostility is to *gratuitous* comments, and every comment is "potential misinformation." Ours: names carry
  *what*, comments carry *why* — a port docstring stating the question is not a failure.
- **Our own nesting cap vs a published algorithm.** The two places in this skill where the nesting cap of 1 demonstrably fights
  *correctness-checking* are both classic graph algorithms — Tarjan's SCC and Brandes' betweenness — whose published shape **is** the citation:
  restructured to satisfy the cap, they can no longer be diffed against the paper. Both are exempted, by name and with the paper cited (§8). Read
  that as the honest boundary of the rule rather than a hole in it: a house style that admits where it loses to a verifiable source is stronger than
  one that claims to be universal.
- **DRY vs decoupling.** Removing duplication creates a shared dependency, so two components now change together (the CCP/CRP conflict; Go: "A
  little copying is better than a little dependency" `[P]`). Utils are the one layer where we prefer duplication (`doctrine.md` §8).
- **YAGNI vs a port per conflict.** Fowler: a presumptive feature is "any code that supports a feature that isn't yet being made available for use",
  costing **build, delay, carry, repair** `[P]`. A port with one resolver and no named second case is exactly that cost; the promotion threshold is
  our answer — two real answers, a *named* second, an I/O boundary, or one discriminant in ≥2 places.
- **Beck's "fewest elements" vs adding an interface.** The fourth rule of simple design: anything not serving passes-tests / reveals-intention /
  no-duplication should be removed `[S]`. An interface is an element and must pay for itself in one of the first three — usually a test.
- **Performance vs polymorphism.** Muratori, *"Clean" Code, Horrible Performance* (28 Feb 2023) `[S]` is the live dissent against replacing switches
  with dynamic dispatch; cite it as a hot-path trade-off only. **Do not cite** Brian Will's "OOP is Bad" against Replace Conditional with
  Polymorphism — the talk explicitly puts polymorphism out of scope, so it is a miscitation — and do not cite Blow or Acton for readability claims.

| Rule | Statement | Source |
|---|---|---|
| **Rule of Three** | two similar pieces are tolerable; at the third, extract — "three strikes and you refactor" | Don Roberts, in Fowler, *Refactoring* `[S]` |
| **YAGNI** | don't build a presumptive feature; four costs: build, delay, carry, repair `[P]` | Fowler, *Yagni*, 2015 |
| **Hyrum's Law** | "With a sufficient number of users of an API, it does not matter what you promise in the contract:" all observable behaviour will be depended on `[P]` | Hyrum Wright; named by Titus Winters |
| **Conway's Law** | organizations "are constrained to produce designs which are copies of the communication structures of these organizations" `[S]` | Conway, *How Do Committees Invent?*, Datamation, Apr 1968 |
| **SLAP** | "Functions Should Descend Only One Level of Abstraction" — mixing levels in one function is the defect | Martin, *Clean Code* **G34** |
| **Boy Scout Rule** | leave the code cleaner than you found it; a mess should be "as socially unacceptable as littering" `[S]` | Martin |
| **Chesterton's Fence** | don't remove the fence until you can say why it went up `[S]` | Chesterton, *The Thing* (1929) |
| **CQS** | a method is either a command that changes state or a query that returns data — never both `[S]` | Meyer, Eiffel / *OOSC* |

A `DEFERRED CONFLICT` records the YAGNI side without losing the analysis. See `smells.md` §6.
