# Architecture smells — the published rules, verbatim, with their numbers

The graph-level catalog. Every rule here is stated the way its source states it, with the source's
own thresholds. Cite the smell **and** the variant you used: "Hub-Like Dependency (Arcan rule)" is
arguable; "hub-like" is not.

**This file is offline by construction.** Every rule below is computable from (a) the module/type
dependency graph and (b) `git log`. Nothing here requires a network call, a vendor tool, a license,
or a benchmark corpus. Where a source's rule depends on a 100-project benchmark, the fixed
published fallback is given and marked `FALLBACK`.

**Input column legend:** `S` = static source/bytecode graph only · `H` = also needs local git
history (`git log --numstat`) · `T` = needs topic modelling or concern extraction → **out of scope,
report as "not detected, needs concern analysis"**, never guess it.

---

## 1. Read this before reporting any of them

1. **Same name, different rule.** Six tools define "Cyclic Dependency" six ways (§9). A finding
   that says "cyclic dependency" without the variant cannot be checked and will be argued away.
2. **Two threshold philosophies.** *Fixed literals* (27,000 LOC, 30 classes, fan-in ≥ 20,
   DIT > 6, co-change > 2) and *distribution-derived* (median, mean + stdev, quantiles over the
   analysed system). Both are published. Offline, derive distributions **within the analysed
   system only** — that is exactly what Arcan's research build does, and Mo et al. endorse it
   explicitly: "Thresholds can be determined manually or automatically by using statistics (such
   as the median, mean plus standard deviation, etc.)."
3. **State the threshold you used in the finding.** `specs/finding.md` requires the number.
4. **Design smell ≠ architecture smell.** Cyclic/Deep/Wide Hierarchy are *design* smells in
   Suryanarayana/Designite and *architecture* smells in current Arcan. Say which frame you are in.
5. **Headroom is not a smell.** See `smells.md` §6. A single-resolver port, an env-scoped name
   sharing one value, a mode knob with one mode: not findings.

---

## 2. Arcan — the instability/coupling family

Arcelli Fontana, Pigazzini, Roveda, Tamburri, Zanoni, Di Nitto, "Arcan: A Tool for Architectural
Smells Detection," ICSA Workshops 2017, pp. 282–285, DOI `10.1109/ICSAW.2017.16`.
Instability smells: same authors, ICSME 2016, pp. 433–437, DOI `10.1109/ICSME.2016.33`.
Debt index: Roveda et al., SEAA 2018, pp. 408–416, DOI `10.1109/SEAA.2018.00073`.
Rules below are the ones in Arcan's own AGPL source, which is the ground truth; the commercial
build's adaptive variants are noted separately.

| Smell | Level | Input | Rule as published |
|---|---|---|---|
| **Cyclic Dependency** (CD) | class + package | S | any strongly connected component, then classified into a *shape* (§3) |
| **Hub-Like Dependency** (HL) | class + package | S | `fanIn > median(fanIn) ∧ fanOut > median(fanOut) ∧ |fanIn − fanOut| ≤ (fanIn+fanOut)/4` |
| **Unstable Dependency** (UD) | package | S | package `x` has ≥1 dependency on `y` with `I(y) > I(x)`; reported when `DoUD = badDeps/totalDeps > 30%` |
| **God Component** (GC) | package | S | package LOC above threshold; `FALLBACK` **27,000 LOC** (Lippert & Roock) or **> 30 classes** (Designite), else `> median package LOC` in this system |
| **Implicit Cross-Package Dependency** (ICPD) | file | H | two files in **different** packages, co-changed `> 2` times, **and** that pair is `> 0.6` of *each* file's co-change edges |
| **Cyclic Hierarchy** | class | S | a supertype depends on one of its own subtypes |
| **Deep Hierarchy** | class | S | inheritance depth above threshold (`FALLBACK` DIT > 6, Designite) |
| **Wide Hierarchy** | class | S | direct subtype count above threshold (`FALLBACK` NC > 10, Designite) |

**The three numbers that matter.**

- **HL divisor is 4.** Source: `HubLikeDetector.java`, `private static final int THRESHOLD = 4;`
  then `fanIn > medianFanIn && fanOut > medianFanOut && |fanIn − fanOut| <= totalDeps / THRESHOLD`.
  Medians are over the set of *distinct non-zero* fan values, not over all nodes.
  Published restatement (Sas et al., arXiv:2203.08702): "a component where the number of ingoing
  and outgoing dependencies is higher than the median in the system and the absolute difference
  between these ingoing and outgoing dependencies is less than a quarter of the total number of
  dependencies of the component."
- **UD filter is 30%.** `DoUD = BadDependencies / TotalDependencies`; ICSA 2017: "The filter
  threshold … (DoUD) was set at 30%, since this value highlights the largest share of correct UD
  instances, according to a manual validation we performed while exploring different thresholds
  over several projects." Instability is Martin's: `I = Ce / (Ca + Ce)`, returning `0.0` when
  `Ca + Ce = 0`. Commercial build adds a slack term: `Instability(x) > Instability(y) + delta`.
- **GC is 27,000 LOC only as a fallback.** Arcan's docs: "While Lippert and Rook suggest to use a
  fixed threshold of 27.000 lines of code to detect the smell, our approach is more sophisticated
  and data-driven … `LinesOfCode = Max(LinesOfCode_System, LinesOfCode_Benchmark)`". The adaptive
  threshold "is always larger than the median lines of code of the packages/components in the
  system and benchmark", so **> median package LOC is the offline-legal floor**. Published
  concrete instance: JUnit was analysed with a threshold of **7,800 LOC**. Arcan's LOC "does not
  count blank lines and commented lines". Severity `δ(x) = LOC(x) − T_median`.

**Known false positives Arcan itself documents** — check these before reporting:
CD from Factory Method implementations and from nested/hidden classes; HL from abstract classes,
interfaces, and Singletons; HL from a class whose fan-out is mostly to platform libraries
(`java.util.*`) rather than to system classes. **Count only first-party edges.**

**Severity, if you rank findings** (SEAA 2018): `ASIS(as) = SeverityScore(as) × PageRank(as)`;
`ADI = Σ (1/W)(ASIS × w) × History`, `W` = total dependencies involved in ≥1 smell. SeverityScore
is the in-system quantile of: number of unstable dependencies (UD) · `elementsInCycle × min edge
occurrences` (CD) · total dependencies (HL). PageRank with damping 0.85. Offline: quantiles over
this system's own smell instances, and say so.

---

## 3. Cycle shapes — the decision tree

Al-Mutawa, Dietrich, Marsland, McCartin, "On the Shape of Circular Dependencies in Java Programs,"
ASWEC 2014, pp. 48–57, DOI `10.1109/ASWEC.2014.15`. Full taxonomy also in Al-Mutawa's MSc thesis,
Massey University 2013, `https://mro.massey.ac.nz/handle/10179/5465`.
A cycle is a **tangle** (an SCC). Shape drives the remedy, so classify before proposing one.

Metrics on the tangle subgraph `G = (V, E)`:

```
DENSE  = (|E| − |V|) / (|V|² − 2|V|)
RATIO  = |V| / |E|
BCKREF = |{(a,b) ∈ E | (b,a) ∈ E}| / |E|
STAR   = max_v deg(v) / |E|                      # requires |V| ≥ 4
CHAIN  = min(|{v | friends(v) = 2}|, |V|−2) / (|V|−2)
HUB    = Gini coefficient of betweenness centrality
```

Decision tree, **in this order** (first match wins):

| Test | Shape | Remedy |
|---|---|---|
| `|V| = 2` | **tiny** | invert the weaker edge behind a port (DIP) |
| `RATIO ≥ 0.75` | **circle** | cut one edge — any one; the cheapest single fix in the catalog |
| `BCKREF ≥ 0.75 ∧ DENSE ≥ 0.75` | **clique** | ★ do not patch edges; extract a new component (ADP) or merge — the boundary is wrong |
| `BCKREF ≥ 0.75 ∧ CHAIN ≥ 0.75` | **chain** | layer it; the pairs are mutually recursive by accident |
| `BCKREF ≥ 0.75 ∧ STAR ≥ 0.75` | **star** | the centre is a hub answering several questions → split by conflict |
| `HUB ≥ 0.5` | **multi-hub** | several centres; split each, then re-measure |
| `DENSE ≥ 0.45` | **semi-clique** | as clique, but a targeted extraction may hold |
| otherwise | **unknown** | report the SCC, no shape claim |

Reference definitions: clique satisfies `|E| = |V|(|V| − 1)`; circle satisfies `|E| = |V|`; a star
has "a central hub vertex, which is an endpoint … for all edges in the tangle"; multi-hub "contains
more than one hub. A vertex is considered as a hub if it has a relatively high betweenness than
other vertices in the same tangle." Classification is stable in **96%** of cases.

**Base rate** (Qualitas Corpus 20101126, 95 projects, 5,004 class-level tangles): tiny 2,376 ·
star 927 · circle 723 · multi-hub 687 · chain 226 · unknown 47 · semi-clique 10 · clique 8.
So: tiny and multi-hub dominate; **a real clique is rare and always significant.**

**Arcan implements 5 of the 7** (`tiny, circle, clique, star, chain`, plus `unclassified`) and
computes star/chain by counting tiny cycles through a shared centre: `star` = centre shared by
**> 2** tiny cycles, `chain` = centre shared by exactly **2**. It does not implement semi-clique
or multi-hub — one of the two most common shapes. If you report those two, say the rule is
Al-Mutawa's, not Arcan's.

---

## 4. Designite — the seven architecture smells

Sharma, Singh, Spinellis, "An empirical investigation on the relationship between design and
architecture smells," *EMSE* 25(5):4020–4068, 2020, DOI `10.1007/s10664-020-09847-2`.
These are the most literally reproducible rules in the literature — use them as the default.
A component = a package/namespace. A depends on B if a class in A refers to a class in B by
association, aggregation, or composition.

| Smell | Input | Rule and number |
|---|---|---|
| **Cyclic Dependency** | S | DFS for cycles in the component graph; exploration stops after **5 hops** |
| **Unstable Dependency** | S | `I = Ce / (Ce + Ca)`; flag when a dependent component is *more stable* than this one |
| **Ambiguous Interface** | S | component exposes exactly **one** public/internal method, **and** has **≥ 5 classes** |
| **God Component** | S | **> 30 classes** OR **> 27,000 LOC** ("following the recommendations by Lippert et al.") |
| **Feature Concentration** | S | `LCC = disconnected subgraphs / total classes` over association+aggregation+composition+inheritance; flag when **LCC > 0.2** |
| **Scattered Functionality** | S | a method accessing **≥ 2** external components, flagged only when such accesses occur **more than once** |
| **Dense Structure** | S | average degree `2|E| / |V|` over the whole-repo component graph **> 5**; **at most one instance per repository** |

Design-smell thresholds from the same tool (`ThresholdsDTO.java`), useful because they are the
numbers behind "God Class"-style claims: complexMethod 8 · longMethod 100 · longStatement 120 ·
longParameterList 5 · longIdentifier 30 · imperativeAbstraction LOC 50 · multifacetedAbstraction
`LCOM ≥ 0.8 ∧ fields ≥ 7 ∧ methods ≥ 7` · unnecessaryAbstraction `methods = 0 ∧ fields ≤ 5` ·
brokenModularization `methods = 0 ∧ fields ≥ 5` · **hubLikeModularization `fanIn ≥ 20 ∧ fanOut ≥ 20`**
· insufficientModularization `publicMethods ≥ 20 ∨ methods ≥ 30 ∨ WMC ≥ 100` · deepHierarchy
`DIT > 6` · wideHierarchy `NC > 10` · cyclicallyDependentModularization `SCC size ≥ 2`.

Catalogue names, so you cite them exactly — **architecture (7):** Cyclic Dependency, Unstable
Dependency, Ambiguous Interface, God Component, Feature Concentration, Scattered Functionality,
Dense Structure. **Design (18, Java):** Imperative / Unnecessary / Multifaceted / Unutilized
Abstraction, Feature Envy · Deficient / Unexploited Encapsulation · Broken / Insufficient /
Hub-like / Cyclically-dependent Modularization · Wide / Deep / Multipath / Cyclic / Rebellious /
Missing / Broken Hierarchy. (C# adds Duplicate Abstraction and Unfactored Hierarchy.)
**Implementation (10):** Abstract Function Call From Constructor · Complex Conditional · Complex
Method · Empty catch clause · Long Identifier · Long Method · Long Parameter List · Long Statement
· Magic Number · Missing default. **Testability (4):** Hard-wired dependencies · Global state ·
Excessive dependency · Law of Demeter violation. **Test (8):** Assertion roulette · Conditional
test logic · Constructor initialization · Eager test · Empty test · Exception handling · Ignored
test · Unknown test.

Prevalence, for calibrating how much to report: 750 Java + 361 C# repos, > 50 MLOC — ~45% of Java
and 66% of C# repos follow the Pareto principle for architecture smells (MSR 2021). **A handful of
components carry most of the debt. Rank and report the top 5.**

---

## 5. The Drexel family — history-based anti-patterns

Mo, Cai, Kazman, Xiao, Feng, "Architecture Anti-Patterns: Automatically Detectable Violations of
Design Principles," *IEEE TSE* 47(5):1008–1028, 2021, DOI `10.1109/TSE.2019.2910856`
(supersedes "Hotspot Patterns," WICSA 2015, pp. 51–60, DOI `10.1109/WICSA.2015.12`).
These are the only formally defined architecture smells that combine structure with revision
history, and the paper's own finding is that **Unstable Interface and Crossing "contribute the
most by far"** to bug- and change-proneness. Hunt those two first when history is available.

Primitives: `nest(x,y)` = x is an inner class of y · `#cochange(x,y)` = times x and y changed in
the same commit · `SRelation(x,y)` = `depend ∨ inherit ∨ nest`, in either direction.

| Anti-pattern | Input | Rule | Thresholds used in the paper |
|---|---|---|---|
| **Unstable Interface** | H | a file whose structural dependents `Fset_S` and co-change partners `Fset_H` are both large, and whose intersection is large: `|Fset_S| > StructImpact ∧ |Fset_S ∩ Fset_H| > HistoryImpact` | **both impacts = 10** ("an unstable interface has to structurally and evolutionarily impact at least 10 other files"); at 2, "hundreds of trivial instances were identified within Cassandra" |
| **Modularity Violation Group** | H | greedy minimal cover of file pairs with **no** structural relation either way but `#cochange > thr`, each group around a `f_core` | **co-change > 2** |
| **Unhealthy Inheritance Hierarchy** | S | parent depends on a child, **or** a client depends on both the parent and its children | none — structural, exact |
| **Crossing** | H | a file with high fan-in **and** high fan-out that co-changes with both its dependents and its dependencies | **fan-in and fan-out both = 4**, co-change > 2 |
| **Clique** | S | a strongly connected file set (replaces WICSA-2015 "Cross-Module Cycle", "to reduce the number of instances the user has to examine") | none |
| **Package Cycle** | S | `∃f₁,fᵢ ∈ Pa, ∃f₂,fⱼ ∈ Pb | depend(f₁,fⱼ) ∧ depend(f₂,fᵢ)` | none |

**The co-change threshold is 2**, everywhere: "the detection of all three history-related
anti-patterns relies on the co-change threshold. In our evaluation, we set this threshold to be 2,
to avoid trivial cases where two files were changed together just once." The earlier WICSA 2015
paper used **4** and additionally required `Impact_thr > 50%` of the DRSpace's files. Cost:
detection is worst-case `O(n³)` — 4 s for 301 files, 76 s for 11,732.

**Implicit Cross-module Dependency** (WICSA 2015, verbatim): "Suppose there are two independent
modules within the same layer, m1, m2. If, for all the files in m1, there is no structural relation
with any of the files in m2, but there exist files in m1 which change together with one or more
files in m2 more than `cochange_thr` times, then we consider the two modules follow a Implicit
Cross-module Dependency pattern." `cochange_thr = 4` there. Note this is the *module-pair* form;
Arcan's ICPD (§2) is the *file-pair* form with a 0.6 ratio test. Different rules, near-identical
names — always say which.

**Modularity Violation** proper: Wong, Cai, Kim, Dalton, "Detecting Software Modularity
Violations," ICSE 2011, pp. 411–420, DOI `10.1145/1985793.1985850`. A violation is a **recurring
discrepancy** between the impact scope predicted from the designed structure and the one predicted
from change coupling — not a single co-change. "Suppose that the set of discrepancies is
{{a,b,c}, {a,b}}. Then, we say that {a,b} is a modularity violation that occurred twice, and
{a,b,c} is a modularity violation that occurred once." Offline-usable numbers: report a violation
only at **≥ 2 occurrences**, prefer **≥ 3** (precision rose from 66% → 67% on Hadoop and 40% → 42%
on Eclipse JDT); association-rule support searched over **2..10**, confidence and weight thresholds
over **0..0.95 in 0.05 steps**, impact-scope weight threshold example **0.75**, Robillard exponent
**α = 0.25**. Clio flagged violations on average **6 (Hadoop) and 5 (JDT) releases before** the team
actually refactored — that is the argument for reporting them at all.
Its four symptom categories, with counts (JDT / Hadoop): cyclic dependency 72/58 · code clone
52/18 · poor inheritance hierarchy 19/37 · **unnamed coupling 25/66** ("We call the fourth category
unnamed because they are not easily detectable using existing techniques").

**If you need the structure behind these:** a **DRSpace** (Xiao, Cai, Kazman, ICSE 2014,
DOI `10.1145/2568225.2568241`) is a set of files plus one or more selected relation types, whose
files cluster into a design rule hierarchy, with **leading classes** in the first layer. "In all
three projects, more than 50% of the error-prone files are captured by just 5 error-prone
DRSpaces." The **HCP matrix** (ICSE 2016, DOI `10.1145/2884781.2884822`) holds conditional
co-change probabilities; keep only links `≥ 0.3` ("to avoid keeping weak connections") and, across
multiple paths, keep the highest. Its four debt patterns are **Hub** (structural both ways +
history dominance one way), **Anchor Submissive**, **Anchor Dominant**, and **Modularity
Violation** (no structural edge either way + history coupling). Findings: **51%–85%** of maintenance
effort goes to servicing these debts; the **top 5 cover 20%–41%**; Modularity Violation debt is the
most common and most expensive, Hub the least.

**Decoupling Level** (Mo et al., ICSE 2016, DOI `10.1145/2884781.2884825`), if you want one number
for "how independently can this be worked on": `DL = Σ_layers DL_Li`; for upper layers
`DL_Li = Σ_j (files(Mj)/allFiles) × (1 − deps(Mj)/lowerLayerFiles)`; for the last layer
`SizeFactor(Mj) = files(Mj)/allFiles` when `files(Mj) ≤ 5`, else that divided by `log₅(files(Mj))`.
The **5-file cutoff** is justified as: measured averages of 2.11 and 3.27 files per module across 41
projects, and "people can comfortably process approximately 5 'chunks' of information at a time."
100 files as 25 modules of 4 → DL 100%; as 4 modules of 25 → 50%; as one module of 100 → 35%.
**Propagation Cost** (MacCormack) = non-empty cells ÷ total cells of the transitively closed DSM;
calibration: "from the 46 open source projects with more than 1000 files, 70% of them have PCs
lower than 20%." So **PC > 20% is above the open-source norm**, and PC alone is a weak signal —
that critique is why DL exists.

---

## 6. Garcia et al. — the connector/interface family

Garcia, Popescu, Edwards, Medvidovic, "Toward a Catalogue of Architectural Bad Smells," QoSA 2009,
LNCS 5581, pp. 146–162, DOI `10.1007/978-3-642-02351-4_10` (short version: CSMR 2009,
DOI `10.1109/CSMR.2009.59`). Their definition, verbatim: "we define architectural smells as a
commonly used architectural decision that negatively impacts system lifecycle qualities."
The 2009 papers give **no detection algorithm** — descriptions and UML schematics only. Detection
rules below come from the later operationalizations, and you must attribute them there.

| Smell | Input | Definition (verbatim) | Operational rule |
|---|---|---|---|
| **Connector Envy** | S | "Components with Connector Envy encompass extensive interaction-related functionality that should be delegated to a connector. Connectors provide the following types of interaction services: communication, coordination, conversion, and facilitation … Components that extensively utilize functionality from one or more of these four categories suffer from the Connector Envy smell." | **no shipping detector exists.** Predicates only (Mo et al., MTD 2013): a component implementing a connector interface; a component whose share of an interaction concern exceeds `th`; a data-flow interface whose parameter equals another interface's return value |
| **Scattered Parasitic Functionality** | T | "multiple components are responsible for realizing the same high-level concern and, additionally, some of those components are responsible for orthogonal concerns" — violates separation of concerns twice | ARCADE `detect(arch, .20, .20)`: drop topics below proportion **0.20**, count clusters per topic, flag topics whose count exceeds **mean + stdev**, and mark a cluster parasitic if it also carries another topic at ≥ **0.20** |
| **Ambiguous Interface** | S | "an Ambiguous Interface offers only one public service or method, although its component offers and processes multiple services. The component accepts all invocation requests through this single entry-point and internally dispatches to other services or methods. Second, since the interface only offers one entry-point, the accepted type is consequently overly general." | Designite's form: **one** public method **and ≥ 5 classes** (§4). ★ This is a textbook conflict — one port per question |
| **Extraneous Adjacent Connector** | S | "occurs when two connectors of **different types** are used to link a pair of components" (8 connector types exist; the paper focuses on procedure-call + event) | **no shipping detector.** Predicate: `connected(c1,n1) ∧ connected(n1,c2) ∧ connected(c1,n2) ∧ connected(n2,c2) ∧ type(n1) ≠ type(n2)`. Practical form: the same pair of modules talks both by direct call and by event/queue |

Distinguished from Fowler explicitly: Scattered Parasitic Functionality differs from shotgun
surgery "because the code smell is agnostic to orthogonal concerns." Extraneous Adjacent Connector
matters because "having two architectural elements that communicate over different connector types
in parallel carries the danger that the beneficial effects of each individual connector may cancel
each other out" — and it is *acceptable* in desktop apps mixing sync calls with async GUI events.

**ARCADE** (Schmitt Laser, Medvidovic, Le, Garcia, ESEC/FSE 2020, DOI `10.1145/3368089.3417941`,
`https://github.com/usc-softarch/arcade_core`) ships 11 smells but only **one** of Garcia's four.
Its thresholds, from source: Concern Overload — topics above proportion **0.10**, flag clusters
above **mean + stdev**. Dependency Cycle — Kosaraju SCC with **size > 2** (note: *excludes* pairs,
unlike everyone else). Link Overload — flag when in-, out-, or total degree exceeds
**mean + 1.5 × stdev**. The general policy, verbatim from the TSE version: "a given number of
concerns is excessive if that number exceeds the mean plus standard deviation of the number of
concerns across the modules of the software system in question." Mo et al. used the **median** of
components per concern (3, in their subject) for the same job.

**Coverage reality check:** of Garcia's four, only Ambiguous Interface and Scattered Functionality
have any shipping detector anywhere. Connector Envy and Extraneous Adjacent Connector are
inspection findings — report them as such, with the pair of modules and the two connector kinds
named.

---

## 7. Lippert & Roock — the original taxonomy

Lippert, Roock, *Refactoring in Large Software Projects: Performing Complex Restructurings
Successfully*, Wiley, 2006, ISBN 0-470-85892-3; ch. 3 "Architecture Smells", pp. 29–79. (German
original: *Refactorings in großen Softwareprojekten*, dpunkt, 2004.) The source of the term
"architecture smell" and of the 27,000-LOC figure everyone reuses. 29 smells in 5 groups.

**Dependency graphs (§3.2):** Obsolete Classes · Tree-like Dependency Graphs · Static Cycles in
Dependency Graphs · Visibility of Dependency Graphs.

**Inheritance hierarchies (§3.3):** Type Queries ("Type queries in the system (`instanceof`) can be
regarded as smells") · List-like Inheritance Hierarchy · Subclasses Do Not Redefine Methods ·
Inheritance Hierarchies without Polymorphic Assignments · Parallel Inheritance Hierarchies ·
Inheritance Hierarchy Too Deep.

**Packages (§3.4):** Unused Packages · Cycles between Packages ("Cycles between packages will
frequently lead to cycles between subsystems") · **Too Small Packages** — "Packages with one or two
classes are often not worth the effort of introducing them: the complexity created by the package
is not offset by its additional structuring" · Too Large Packages · Packages Too Deep or
Unbalanced · Packages Not Clearly Named ("various packages with names like `util`, `base`,
`framework` and `toolkit` … side by side in the same system and on the same level").

**Subsystems (§3.5):** **No Subsystems** — "If the system consists of more than **100 packages**" ·
Subsystem Too Large · Subsystem Too Small · **Too Many Subsystems** — "If a system consists of many
more than **30 subsystems** without further grouping, the understandability of the system will be
seriously impaired" · Subsystem-API Bypassed · Subsystem-API Too Large · Cycles between Subsystems
· Overgeneralization.

**Layers (§3.6):** No Layers · Upward References between Layers (Cycles between Layers) · Strict
Layers Violated · Too Many Layers ("Too many layers in a system often cause too many indirections.
One indication of unnecessary indirections are dumb delegations") · References between Vertically
Separated Layers · (unnumbered) Inheritance between Protocol-Oriented Layers.

Their §3.1 grounds all of it in 14 principles: DRY, Speaking Code, OCP, LSP, DIP, ISP, REP, CRP,
CCP, ADP, SDP, SAP, Tell-Don't-Ask, Separation of Concerns — see `laws.md`.

**Not in Lippert & Roock**, despite being widely attributed to them: "unused/unnecessary
abstractions" (their smell is Obsolete Classes / Unused Packages), "subclass knows about
superclass", "dependencies not made explicit" (theirs is *Visibility of* Dependency Graphs), "too
shallow hierarchies". Implicit Cross-Module Dependency is Mo/Cai/Kazman/Xiao, not them.

---

## 8. Vendor rule IDs and their published numbers

Cite these when the repo already runs the tool — a finding that maps to an existing rule lands far
more easily. **Do not run these tools; this skill is offline.** Use the numbers as calibration.

**Structure101:** Fat threshold — **methods 15** ("The industry norm … is usually 10-15. By
default, Structure101 Studio takes the value of 15"), **classes / packages / everything else 120**.
Design (package-level) tangle threshold **0%** — "package-level dependency tangles are always
considered undesirable"; Tangle = minimum-feedback-set weight ÷ total references between the
parents. XS: `excess% = max(V − T, 0)/V`, `XS = excess% × LOC`, summed recursively. Slice
tangledness `√(Σ|T(i)|²)/N`.

**Sonargraph:** `CCD = Σ DependsOn`, `ACD = CCD/N`, `NCCD = CCD / CCD(balanced binary tree of the
same size)`. Cyclicity `= Σ groupSize²`; `relCyclicity = 100·√cyclicity / #packages`. Critical cycle
group sizes: component **6**, package **6**, module **2**. Legacy-plugin alert grid
(warning/error): Structural Debt Index **400/1600** · Relative Cyclicity **5/15** · Biggest Cycle
Group **4/8** · NCCD **6.5/10.0**. Relative Entanglement guidance: "<10% ok, never over 5%",
"10%–20% early stages of the BBoM", ">50% really problematic". Maintainability Level "over 90" for
well-designed systems. **Sonargraph ships no default metric thresholds** — users create them.

**NDepend:** `I = Ce/(Ce+Ca)`; "Assemblies where `NormDistFromMainSeq` is higher than **0.7** might
be problematic"; relational cohesion `H = (R+1)/N`, good range **1.5–4.0**, rule fires below
**0.8** with > 20 types. Coupling rule ND1410: `CC ≥ 10` (method) / `25` (type), `NbTypesUsed ≥ 90`,
`typesUsed ≥ 40/90`, `namespacesUsed ≥ 5/10`. `TypeCe > 50` = "depends on too many other types".
ND1007 poor cohesion: `LCOM > 0.91 ∧ fields > 10 ∧ methods > 10` (the rule's prose says 0.84; the
executable query says 0.91). ND1000 types > **200 LOC** · ND1001 > **20 methods** · ND1002 > **15
fields** · ND1200 interfaces ≥ **14 methods** · ND1202 base classes ≥ **4**. Debt rating A < 5%,
B 5–10%, C 10–20%, D 20–50%, E ≥ 50%; SQALE baseline **18 man-days per 1,000 logical LOC**.

**STAN4J:** Fat = edge count. Tangled = red (feedback) edge weight ÷ total. ACD as a percentage:
**0% = empty graph, 50% = chain, 100% = cycle**; ">50% implies a tangle". `D = A + I − 1` in
`[−1,+1]`: **−1 = Zone of Pain, +1 = Zone of Uselessness**. Publishes no numeric rating boundaries.

**ArchUnit:** `slices().matching("..app.(*)..").should().beFreeOfCycles()` and
`modules().definedByPackages(...).should().beFreeOfCycles()` — no size threshold; the only numbers
are performance caps `cycles.maxNumberToDetect` (**100**) and `cycles.maxNumberOfDependenciesPerEdge`
(**20**). Documented bound: "for any non-trivial (n >= 5) acyclic graph of components the RACD is
bound by **0.6**". Its Abstractness counts **public classes only**.

**jQAssistant:** exactly two cycle rules, `java:AvoidCyclicPackageDependencies` and
`java:AvoidCyclicArtifactDependencies`, with **zero numeric thresholds**. The Cypher is worth
copying as the reference formulation of "package cycle":

```cypher
MATCH (p1:Package)-[:DEPENDS_ON]->(p2:Package),
      path = allShortestPaths((p2)-[:DEPENDS_ON*]->(p1))
WHERE p1 <> p2
RETURN p1 as Package, nodes(path) as Cycle ORDER BY Package.fqn
```

**SonarQube:** `sqale_debt_ratio` = debt ÷ (cost to develop one line × lines), where "the cost to
develop one line of code is predefined in the database (by default, **30 minutes**)"; Maintainability
rating A ≤ 5%, B < 10%, C < 20%, D < 50%, E ≥ 50%. It ships **no** architectural cycle metric.

**No numbers published, do not invent any:** Designite's documentation (thresholds exist only in the
papers, §4) · CodeMR (five qualitative levels only) · Lattix (docs unavailable) · Sonargraph's
Structural Debt Index formula.

---

## 9. Name collisions — resolve before reporting

The same phrase means different rules. Pick one, name it, use its number.

| Phrase | Variants you must disambiguate |
|---|---|
| **Cyclic Dependency** | Arcan: SCC + shape (any size ≥ 2) · Designite: component DFS capped at **5 hops** · Drexel *Clique*: SCC of files · ARCADE: SCC **size > 2** (excludes pairs) · Designite design-level: SCC size ≥ 2 · jQAssistant / ArchUnit: any cycle, no threshold · NDepend: mutual pairs (ND1400) then ≥ 3-namespace cycles (ND1401) · Sonargraph: "critical" at group size **6** |
| **Hub-Like** | Arcan: `fanIn > median ∧ fanOut > median ∧ |Δ| ≤ total/4` · Designite: `fanIn ≥ 20 ∧ fanOut ≥ 20` · NDepend ND1410: `typesUsed ≥ 90 ∧ namespacesUsed ≥ 10 ∧ CC ≥ 25` · ARCADE Link Overload: `> mean + 1.5·stdev` · Drexel *Crossing*: fan-in and fan-out **≥ 4** *plus* co-change on both sides |
| **God Component** | Lippert & Roock: **27,000 LOC** · Designite: **> 30 classes ∨ > 27,000 LOC** · Arcan: adaptive, always **> median package LOC** (JUnit run used 7,800) |
| **Implicit Cross-module Dependency** | Arcan ICPD: file pair, different packages, co-change **> 2**, ratio **> 0.6** both ways · WICSA 2015 ICMD: *module* pair with **no** structural relation at all and co-change **> 4** |
| **Modularity Violation** | ICSE 2011: **recurring** discrepancy between predicted impact scopes, ≥ 2 (prefer ≥ 3) occurrences · TSE 2021 MVG: greedy cover of no-structural-edge pairs with co-change **> 2** · ICSE 2016: no structural edge + HCP link either way |
| **Unstable Dependency** vs **Unstable Interface** | UD (Arcan/Designite): a *package* depending on less stable packages, `I = Ce/(Ca+Ce)`, 30% filter · UIF (Drexel): a *file* with ≥ 10 structural dependents that also co-changes with ≥ 10 of them. Unrelated rules |
| **Scattered Functionality** vs **Scattered Parasitic Functionality** | Designite: a method touching ≥ 2 external components, more than once (structural, `S`) · Garcia/ARCADE: one concern across many components + orthogonal concerns, needs topic models (`T`) |

---

## 10. Offline computability matrix

What this skill can honestly claim, given only a checkout and `git log`.

**"Detectable" is three different claims, and they are not interchangeable** — the same distinction
`graph-metrics.md` §9 draws with `Computed: yes / reserved / no`:

| Tag | Meaning |
|---|---|
| **[script]** | `scripts/graph.sh` or `scripts/caps.sh` emits the number today. Assertable in a fitness test |
| **[derive]** | computable from what those scripts emit, by arithmetic the analysing agent does itself. State the formula and the inputs in the finding |
| **[read]** | needs a metric nothing here computes (`dit`, `noc`, `lcom4`, `wmc`, `rfc`, `cbo`) or a human reading the code. Legitimate, but it is an inspection result: say so, and never put a number on it that no tool printed |

| Available input | Detectable |
|---|---|
| Source tree only (`S`) | **[script]** Cyclic Dependency + all 7 shapes · Hub-Like · Unstable Dependency · God Component · Propagation Cost · Package Cycle · Clique · Zone of Pain / Uselessness — every one of these reads a key `graph.sh`/`caps.sh` emits. **[derive]** Dense Structure · Feature Concentration · Scattered Functionality (Designite form) — arithmetic over `edges[]`/`nodes[]`. **[read]** Ambiguous Interface · Unhealthy Inheritance Hierarchy · Cyclic/Deep/Wide Hierarchy — these need `dit`/`noc`/`lcom4`, which nothing here computes · the Lippert & Roock catalogue is mixed, tagged per smell in §1 |
| Plus `git log` (`H`) | all **[derive]**: no bundled script reads history (`graph-tooling.md` §8 is the command set, run by hand). Unstable Interface · Crossing · Modularity Violation / MVG · Implicit Cross-module Dependency (both forms) · HCP debt patterns (Hub, Anchor Submissive, Anchor Dominant) |
| Needs topic models (`T`) | **[read]** at best: Scattered Parasitic Functionality · Concern Overload — **report as not detected**, name the concern you suspect, and stop |
| Needs a benchmark corpus | Arcan's adaptive GC/HL thresholds, ADI quantile grades — substitute in-system median / mean + stdev and **say so in the finding** |

Two smells from the classic catalog have no detector anywhere and are inspection-only: **Connector
Envy** and **Extraneous Adjacent Connector**. Report them with the module pair and the two
connector kinds named, or not at all.

---

## 11. Over-application — how this doctrine fails

Symmetric to the above, and mandatory in every verification pass. **Lasagna Code** (too many
delegation layers; Lippert & Roock's "Too Many Layers" — "dumb delegations"), **Poltergeist** (a
class existing only to invoke another), **Zone of Uselessness** (high abstractness, high
instability — abstract and nothing uses it; ★ delete it, this is Speculative Generality at
component scale), and **Speculative Generality** at port level (a port with one resolver and no
named second case). If a restructuring proposal would raise the delegation depth without removing
a conflict, it is not a fix.
