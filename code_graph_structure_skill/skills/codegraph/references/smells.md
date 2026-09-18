# Smell catalogs — the named things to look for

Use the **names**. A finding that cites a named smell and its source is arguable; a finding
that says "this feels messy" is noise. Every smell below maps to a CPRC move or a hard limit.

---

## 1. Fowler, *Refactoring* 2nd ed. (2018), ch. 3 — all 24, in book order

| # | Smell | CPRC resolution |
|---|---|---|
| 1 | **Mysterious Name** | rename to the question it answers; ports named as questions |
| 2 | **Duplicated Code** | Extract; if the copies differ in one dimension → that dimension is the conflict |
| 3 | **Long Function** | hard limit 15 lines; extract, then promote the branch |
| 4 | **Long Parameter List** | → **Context** value object (§6 of doctrine) |
| 5 | **Global Data** | → inject via Context or constructor; Ambient Context anti-pattern |
| 6 | **Mutable Data** | frozen Context, immutable value objects, CQS |
| 7 | **Divergent Change** | one module changing for ≥2 reasons → split by actor (SRP) |
| 8 | **Shotgun Surgery** | one change touching many files → missing port; also a codemod slice |
| 9 | **Feature Envy** | method more interested in another object → Move Function (Information Expert) |
| 10 | **Data Clumps** | the same 3+ params travelling together → **Context** / Value Object |
| 11 | **Primitive Obsession** | `str`/`float` for domain concepts → Value Object, newtype |
| 12 | **Repeated Switches** | ★ the highest-confidence conflict signal (C2) → port + resolvers |
| 13 | **Loops** | Replace Loop with Pipeline; a branch inside a loop is a conflict |
| 14 | **Lazy Element** | a class/function that isn't earning its keep → inline; also Ousterhout's shallow module |
| 15 | **Speculative Generality** | ★ the anti-doctrine smell — a port with one resolver and no named second case |
| 16 | **Temporary Field** | field set only in some paths → separate the paths into resolvers |
| 17 | **Message Chains** | `a.b().c().d()` → Hide Delegate; Law of Demeter; connascence of position |
| 18 | **Middle Man** | a class that only delegates → Remove Middle Man; Ousterhout's pass-through method |
| 19 | **Insider Trading** | (1st ed. *Inappropriate Intimacy*) two modules knowing each other's internals |
| 20 | **Large Class** | hard limit 250 lines; split by conflict |
| 21 | **Alternative Classes with Different Interfaces** | ★ two classes doing the same job differently → **extract a port**, unify signatures |
| 22 | **Data Class** | a bag of getters/setters with no behaviour → move behaviour in, or make it a Context |
| 23 | **Refused Bequest** | ★ subclass ignoring/raising on inherited behaviour → LSP violation → sibling resolver |
| 24 | **Comments** | comments explaining *what* → extract and name. (Ousterhout dissents; see `laws.md`) |

Name changes from 1st ed., so you cite the right one: Long Method → **Long Function**;
Switch Statements → **Repeated Switches** (only *repeated* switches count); Inappropriate
Intimacy → **Insider Trading**; Lazy Class → **Lazy Element**. Removed: Parallel Inheritance
Hierarchies (folded into Shotgun Surgery), Incomplete Library Class. Added: Mysterious Name,
Global Data, Mutable Data, Loops.

**refactoring.guru groupings** (1st-ed names) — useful for reporting by category:
*Bloaters* · *OO Abusers* · *Change Preventers* · *Dispensables* · *Couplers*.

---

## 2. Martin, *Clean Code* ch. 17 "Smells and Heuristics" — 66 coded items

Cite the code (`G23`, `F3`) — it is compact and unambiguous.

**Comments (C1–C5):** C1 Inappropriate Information · C2 Obsolete Comment · C3 Redundant
Comment · C4 Poorly Written Comment · C5 Commented-Out Code

**Environment (E1–E2):** E1 Build Requires More Than One Step · E2 Tests Require More Than One Step

**Functions (F1–F4):** F1 Too Many Arguments · F2 Output Arguments · **F3 Flag Arguments** (→ C5
conflict, always promote) · F4 Dead Function

**General (G1–G36):** G1 Multiple Languages in One Source File · G2 Obvious Behavior Is
Unimplemented · G3 Incorrect Behavior at the Boundaries · G4 Overridden Safeties · G5
Duplication · G6 Code at Wrong Level of Abstraction · **G7 Base Classes Depending on Their
Derivatives** · G8 Too Much Information · G9 Dead Code · G10 Vertical Separation · G11
Inconsistency · G12 Clutter · G13 Artificial Coupling · G14 Feature Envy · **G15 Selector
Arguments** · G16 Obscured Intent · G17 Misplaced Responsibility · **G18 Inappropriate Static**
· G19 Use Explanatory Variables · G20 Function Names Should Say What They Do · G21 Understand
the Algorithm · **G22 Make Logical Dependencies Physical** · **G23 Prefer Polymorphism to
If/Else or Switch/Case** · G24 Follow Standard Conventions · G25 Replace Magic Numbers with
Named Constants · G26 Be Precise · G27 Structure over Convention · **G28 Encapsulate
Conditionals** · **G29 Avoid Negative Conditionals** · G30 Functions Should Do One Thing ·
**G31 Hidden Temporal Couplings** · G32 Don't Be Arbitrary · G33 Encapsulate Boundary
Conditions · **G34 Functions Should Descend Only One Level of Abstraction** (SLAP) · G35 Keep
Configurable Data at High Levels · **G36 Avoid Transitive Navigation** (Demeter)

**Java (J1–J3):** J1 Avoid Long Import Lists by Using Wildcards · J2 Don't Inherit Constants ·
J3 Constants versus Enums

**Names (N1–N7):** N1 Choose Descriptive Names · N2 Choose Names at the Appropriate Level of
Abstraction · N3 Use Standard Nomenclature Where Possible · N4 Unambiguous Names · N5 Use Long
Names for Long Scopes · N6 Avoid Encodings · N7 Names Should Describe Side-Effects

**Tests (T1–T9):** T1 Insufficient Tests · T2 Use a Coverage Tool! · T3 Don't Skip Trivial
Tests · T4 An Ignored Test Is a Question about an Ambiguity · T5 Test Boundary Conditions ·
T6 Exhaustively Test Near Bugs · T7 Patterns of Failure Are Revealing · T8 Test Coverage
Patterns Can Be Revealing · T9 Tests Should Be Fast

The five in **bold** under General plus F3/G15 are this skill's primary hunting ground:
**G23, G28, G29, G22, G31, G34, F3, G15, G7, G18**.

---

## 3. Architecture smells — the graph-level catalog

From Lippert & Roock, *Refactoring in Large Software Projects*, and Arcelli Fontana et al. /
the Arcan tool. These are the smells the graph phase reports; they have no single-file location.

| Smell | Detection rule | Resolution |
|---|---|---|
| **Cyclic Dependency** | any SCC of size ≥2 in the module graph (Tarjan) | invert the weaker edge behind a port (DIP), or extract a new component (ADP) |
| **Hub-Like Dependency** | a node with both fan-in and fan-out above the 90th percentile | split by conflict; it is answering several questions |
| **God Component** | LOC or class count ≫ median; high WMC and CBO | split by reason-to-change (CCP) |
| **Unstable Dependency** | component depends on one with higher Instability *I* | reverse per SDP: depend in the direction of stability |
| **Implicit Cross-module Dependency** | co-change coupling in git with no static edge | make the logical dependency physical (**G22**) |
| **Ambiguous Interface** | one entry point taking a discriminator and dispatching internally | ★ textbook conflict — one port per question |
| **Scattered Functionality** | one concern implemented across many unrelated modules | gather behind a port; usually a missing folder-level question |
| **Feature Concentration** | one module implementing several unrelated concerns | opposite of the above; split |
| **Dense Structure** | graph edge density far above expectation | usually a missing utils layer plus missing ports |
| **Modularity Violation** | co-changing files in different modules | re-cut the module boundary (Louvain communities as a proposal) |
| **Zone of Pain** | low Abstractness, low Instability (concrete + heavily depended on) | extract ports; add abstraction |
| **Zone of Uselessness** | high Abstractness, high Instability (abstract + nothing uses it) | ★ delete it — this is Speculative Generality at component scale |

**Lasagna Code** (too many delegation layers) and **Poltergeist** (a class that exists only to
invoke another) are the over-application smells. Both are how *this doctrine* fails. Check for
them in every verification pass.

---

## 4. Static-analyzer rule names worth citing

Use these when the repo already runs the tool — a finding that maps to an existing rule ID is
far easier to land.

**SonarQube (OOP-relevant):** `S3776` Cognitive Complexity · `S1541` cyclomatic complexity ·
`S1067` expression complexity · `S134` nesting depth · `S138` method lines · `S107` too many
parameters · `S1200` class coupling · `S1448` too many methods · `S1820` too many fields ·
`S110` inheritance depth · `S1479`/`S1151` switch size · `S6541` **Brain Method** · `S6539`
**Monster Class** · `S4144`/`S1871`/`S1192` duplication · `S1104` public fields · `S1214`
constant-only interfaces · `S1118` utility-class constructors · `S125`/`S1144`/`S1172` dead
code · **`S6813` field dependency injection should be avoided**.

**PMD `category/java/design.xml`:** AvoidDeeplyNestedIfStmts · CognitiveComplexity ·
CollapsibleIfStatements · CouplingBetweenObjects · CyclomaticComplexity · **DataClass** ·
ExcessiveImports · ExcessiveParameterList · ExcessivePublicCount · **GodClass** ·
**LawOfDemeter** · LogicInversion · LoosePackageCoupling · MutableStaticState · NcssCount ·
NPathComplexity · SimplifyBooleanReturns · SimplifyConditional · SingularField · SwitchDensity ·
TooManyFields · TooManyMethods · UseUtilityClass.

**Checkstyle:** DesignForExtension · FinalClass · HideUtilityClassConstructor ·
InterfaceIsType · OneTopLevelClass · VisibilityModifier · ClassDataAbstractionCoupling ·
ClassFanOutComplexity · BooleanExpressionComplexity · JavaNCSS · NPathComplexity.

**Python:** `pylint` R0912 too-many-branches · R0913 too-many-arguments · R0915
too-many-statements · R0902 too-many-instance-attributes · R0904 too-many-public-methods ·
C0301 line-too-long · R1705 no-else-return · R1720 no-else-raise · R1723 no-else-break.
`ruff` rule families: `PLR09*` (complexity), `RET505-508` (superfluous-else), `SIM1*`
(simplifiable if), `C901` (mccabe), `ARG` (unused arguments), `TRY300` (else in try).
**`RET505` and `SIM108` are the literal machine checks for the no-`else` rule.**

**TypeScript:** `eslint` complexity · max-depth · max-lines · max-lines-per-function ·
max-params · no-else-return · @typescript-eslint/no-explicit-any ·
@typescript-eslint/switch-exhaustiveness-check · eslint-plugin-boundaries element rules ·
eslint-plugin-sonarjs (`sonarjs/no-all-duplicated-branches`, `sonarjs/cognitive-complexity`).

**Go:** `gocyclo` · `gocognit` · `funlen` · `nestif` · `cyclop` · `gocritic` (`singleCaseSwitch`,
`ifElseChain`) · `depguard` (import boundaries) · `revive` early-return rule ·
`exhaustive` (enum switch totality).

---

## 5. LLM-generated-code smells

Relevant because much of the code this skill will restructure was itself machine-written, and
its smell profile differs from human code. Published findings, treat as directional:

- The increase in smells in LLM code is dominated by **implementation smells** (long/complex
  methods, deep nesting, magic literals, duplicated blocks) far more than **design smells**;
  design-level structure is comparatively less degraded. So: **prioritize the vertical caps
  pass on machine-written code, and the graph pass on human-written legacy.**
- Recurring concrete patterns: over-long single functions that inline every branch rather than
  extracting; defensive `if x is None` at every level instead of one boundary parse;
  re-implemented utilities instead of reuse; near-duplicate helpers with divergent names;
  swallowed exceptions; and comments restating the next line.
- Research to cite if asked: taxonomies of LLM code smells with detector tooling, studies
  splitting implementation vs design smell increase, and benchmark work on smell propensity.
  Verify arXiv IDs before quoting them; several circulating IDs are wrong.

---

## 6. What is NOT a finding

Refuse to report these. They are the false positives that make an architecture report useless.

1. **"The current value is the loosest possible."** A permissive default that a future
   environment will tighten is headroom, not a defect.
2. **"You collapsed X into one value."** Env-scoped names sharing one value today, a mode knob
   set to one mode, a per-stage resource pointing at one target — all deliberate seams.
3. **A single-implementation port at an I/O boundary.** Justified by testability alone.
4. **A `DEFERRED CONFLICT`** recorded in the spec with a reason.
5. **A registry `match`/`switch` in the composition root.** Data, not control flow.
6. **An exhaustive match over a sealed set** where the compiler checks totality.
7. **Duplication younger than the third occurrence.** Rule of Three; the wrong abstraction
   costs more than the duplication.
8. **Style the repo's own linter already permits**, unless it breaks a hard limit.
9. **A `# TODO`.** It is a *deferred conflict marker* — record it, don't bill for it.
10. **Anything without a consequence and a remedy.** See `../specs/finding.md`.
