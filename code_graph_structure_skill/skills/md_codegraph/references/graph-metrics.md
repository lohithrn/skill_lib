# Graph metrics — formulas, thresholds, and which ones this skill actually computes

The metric layer under `arch-smells.md`. That file holds the **named smells** and their published
detection rules; this file holds the **numbers those rules are built from**, plus the numbers you
may quote on their own. Never restate a smell rule from here — cite `arch-smells.md` and its
section number instead. No threshold here contradicts one there; where both exist, `arch-smells.md`
wins because it quotes the tool's own source.

**All distributions are computed within this system only, never against a benchmark corpus we do
not ship.** "Above median" means above the median of the repo in front of you. The only fixed
literals allowed are the published ones marked below with a source.

**Source markers:** `[P]` = quoted from the primary text · `[S]` = checked against a reliable
secondary (vendor docs, tool source) · `[derived]` = arithmetic on a cited number, not itself
published · `[unverified]` = circulates widely, no primary source reached — never quote one bare.
No page numbers are given where the edition was not in hand.

**Computed column:** `yes → k` = `graph.sh` emits it under JSON key `k` · `reserved → k` = the key
exists in `specs/graph-report.md` but the current build does not emit it, so report **"not
computed"**, never a guess · `no` = out of scope offline, say which input is missing.

---

## 1. Read this before quoting a number

1. **A metric with no threshold is not a finding.** Every number you report carries its cutoff and
   the cutoff's source. `specs/finding.md` requires both.
2. **`None` is not `0`.** `I` is undefined for an isolated node; `A` is undefined for a file with no
   type declarations. `graph.sh` omits the key entirely in those cases. An omitted key means *not
   measurable*, and reading it as zero puts clean files in the Zone of Pain.
3. **Caps degrade, they do not lie.** Betweenness is skipped above 1200 nodes, transitive closure
   above 3000. When that happens the reason lands in `degraded[]` and the metric is absent. Quote
   `degraded[]` in the report; do not substitute an estimate.
4. **Ranked, not scored.** For every metric without a published literal, report the top decile
   inside this repo and say so. "`fan_out` is in this repo's top decile at 34" is checkable;
   "`fan_out` is high" is not.
5. **Size confounds most class metrics.** El Emam et al. (2001) showed the C&K suite's validity is
   largely explained by class size `[S]`. Report `loc` next to any per-node metric.

---

## 2. Martin's component metrics — Ca, Ce, I, A, D

Robert C. Martin, "OO Design Quality Metrics: An Analysis of Dependencies" (1994), restated in
*Agile Software Development* (2002) and *Clean Architecture* (2017).

| Metric | Formula | Reading | Computed |
|---|---|---|---|
| **Ca** (afferent coupling) | count of distinct components **outside** this one that depend on it | who breaks if I change | yes → `nodes[].metrics.fan_in` |
| **Ce** (efferent coupling) | count of distinct components **outside** this one that it depends on | how much can break me | yes → `nodes[].metrics.fan_out` |
| **I** (instability) | `I = Ce / (Ca + Ce)`, range `[0,1]` | `0` = maximally stable, `1` = maximally unstable | yes → `nodes[].metrics.instability` |
| **A** (abstractness) | `A = Na / Nc` — abstract classes+interfaces over total classes, range `[0,1]` | `0` = wholly concrete | yes → `nodes[].metrics.abstractness` |
| **D** (distance from the Main Sequence) | `D = |A + I − 1|`, range `[0,1]` | `0` = on the line | yes → `nodes[].metrics.distance` |

Counts are over **distinct pairs**: importing the same module twice is one edge. Intra-component
edges count for neither Ca nor Ce.

**Two D's exist. Use the second.** Martin's 1994 paper defines the perpendicular distance
`D = |A + I − 1| / √2` with range `[0, 0.707]`; *Clean Architecture* drops the divisor and uses
`D' = |A + I − 1|` with range `[0,1]` `[S]`. This skill computes the **undivided** form. If you
compare against a tool that reports the `/√2` version, multiply before comparing.

**The Main Sequence** is the line `A + I = 1`: stable components should be abstract, unstable ones
concrete. The two failure corners:

| Zone | Where | Means | What to do |
|---|---|---|---|
| **Zone of Pain** | `A ≈ 0`, `I ≈ 0` (`D ≈ 1`) | concrete, rigid, heavily depended on | do not "fix" it if it is genuinely stable — a schema, a value type, or `string` itself lives here. Flag only when it also changes: pair with `churn` |
| **Zone of Uselessness** | `A ≈ 1`, `I ≈ 1` (`D ≈ 1`) | abstract with nobody depending on it | leftover interface, speculative port. Cross-check `ports[]` before calling it dead; see `dead-code.md` |

**Threshold.** Martin gives no literal — the guidance is that `D` "should be as close to zero as
possible" `[S]`. Use in-system ranking: report the highest-`D` components, and treat `D > 0.5` as
the reporting floor (half the range) so that near-line noise never reaches a finding. State the
zone, `A`, `I`, `D`, `loc` and `fan_in` together; one of them alone is unreadable.

**Instability gap** (the metric behind the Stable Dependencies Principle, `laws.md` §2):
`gap(edge) = I(target) − I(source)`. Positive means a more stable component depends on a less
stable one — the SDP violation. Sort violations by `gap × fan_in(source)`; that ordering puts the
edges with the widest blast radius first. `graph.sh` does not emit `gap`; both `I` values are in
`nodes[]`, so compute it in the report. Arcan's **Unstable Dependency** smell adds a
degree-of-participation filter on top of this — its rule and its `30%` divisor are in
`arch-smells.md` §2; do not re-derive them here.

---

## 3. Lakos levelization — CCD, ACD, NCCD, RACD

John Lakos, *Large-Scale C++ Software Design* (1996), the levelization chapters.

| Metric | Formula | Reading | Computed |
|---|---|---|---|
| **CCD** | `CCD = Σ_{c ∈ C} depends(c)` where `depends(c)` = number of components you must have to compile and test `c`, **including `c` itself** | total build/test weight of the system | no — needs a component (not file) partition |
| **ACD** | `ACD = CCD / N` | average components pulled in per component | no |
| **NCCD** | `NCCD = CCD / CCD_balanced_binary_tree(N)` | `> 1.0` means worse-coupled than a balanced binary tree of the same size | no |
| **RACD** | `RACD = ACD / N` | scale-free version of ACD | no |

A cycle makes `depends(c)` identical for every member, so CCD explodes quadratically inside a
tangle: an SCC of size `k` contributes at least `k²`. That is why levelization is stated as
"break cycles first, then measure."

**Breaking a cycle: what is cheap and what is NP-hard.** Finding the cycles exactly is linear —
Tarjan (1972) is one DFS at `O(|V|+|E|)` and emits SCCs in reverse topological order of the
condensation `[P]`. Choosing the *fewest* edges to cut is not: minimum Feedback Arc Set is NP-hard
(Karp 1972, one of the original 21; Garey & Johnson GT8) `[S]`, APX-hard with no constant-factor
approximation under UGC, and the best known general ratio is `O(log n · log log n)` (Even, Naor,
Schieber & Sudan, *Algorithmica* 20(2), 1998) `[S]`. So the division of labour is fixed: **report
cycles exactly, propose cut edges heuristically, never call a cut minimal.** The cheap standard
heuristic is Eades, Lin & Smyth's `GR` (*Inf. Process. Lett.* 47(6):319–323, 1993) `[S]` — `O(V+E)`,
leaving at most `m/2 − n/6` back edges. Graphviz's `tred -r` answers the adjacent question offline
(which edges are *redundant* rather than which are back edges) — `graph-tooling.md` §12.

**Published bound.** ArchUnit's metrics documentation states verbatim `[P]`:

> "for any non-trivial (n >= 5) acyclic graph of components the RACD is bound by 0.6"

So `RACD > 0.6` on a graph of 5 or more components is proof of a cycle, not a style opinion — and
`NCCD > 1.0` is the readable form of the same complaint. Neither is emitted by `graph.sh`; when
cycles matter, report `cycles[]` and `cycles[].shape` (see `arch-smells.md` §3) and note that the
Lakos numbers require a declared component partition the repo may not have.

---

## 4. Propagation cost and the visibility matrix

MacCormack, Rusnak & Baldwin, "Exploring the Structure of Complex Software Designs: An Empirical
Study of Open Source and Proprietary Code," *Management Science* 52(7), 2006.

```
V  = transitive closure of the direct-dependency matrix (the visibility matrix)
PC = (count of non-empty cells of V) / (N × N)
```

Read it as: *if I change one file at random, what fraction of the system can see the change.*
Self-visibility is included, so the floor is `1/N`, not `0`.

**Calibration, quoted `[P]`:**

> "from the 46 open source projects with more than 1000 files, 70% of them have PCs lower than 20%"

| Band | Reading | Source |
|---|---|---|
| `PC < 20%` | ordinary — where 70% of large open-source projects sit | MacCormack et al. 2006 `[P]` |
| `PC ≥ 20%` | worse than 70% of that sample; report it with the sample size caveat | same |
| `PC ≥ 50%` | half the system is downstream of a random file; a change cannot be reviewed locally | in-system reading, no published literal |

**Reading `V` as more than one number — the core/periphery split.** The same closure gives every
node a *visibility fan-in* `VFI` (how many files can reach it) and *visibility fan-out* `VFO` (how
many it can reach). The hidden-structure method (Baldwin, MacCormack & Rusnak) sorts nodes on
high/low `VFI × VFO` `[S]`:

| Class | VFI | VFO | Reading |
|---|---|---|---|
| **Core** | high | high | the real architecture, whatever the folders say |
| **Shared** | high | low | utilities, value types — reached by everything, reaches nothing |
| **Control** | low | high | orchestrators, entry points, wiring |
| **Peripheral** | low | low | leaves; the safe place to work |

Every member of an SCC has **identical** `VFI` and `VFO` — reachability cannot tell nodes inside a
cycle apart — so a large "core" is usually one tangle wearing many names. Report the SCC, not its
members. The high/low split is a rank cutoff in the method, not a literal; state the one you used.
Not computed: `graph.sh` emits no per-node visibility counts, only the aggregate below.

**Computed:** yes → `totals.propagation_cost`, as a fraction (`0.0714`, not `7.14%`). Above 3000
nodes the closure is skipped, the key is `null`, and the reason appears in `degraded[]` — the cost
is `O(V·E)` and the cap is deliberate. Node count is `totals.nodes`; quote both, because PC is
meaningless without `N` (a 12-file repo can hit 60% and be fine).

---

## 5. Decoupling Level

Mo, Cai, Kazman & Xiao, "Decoupling Level: A New Metric for Architectural Maintenance Complexity,"
ICSE 2016.

DL scores how well a system splits into **independently replaceable** modules, derived from the
design-rule hierarchy rather than from raw degree. Each independent module contributes a
size-weighted term; the sum is normalised to `[0,1]` and **higher is better** — the opposite
direction from `D` and `PC` `[S]`.

**The small-module cutoff is the part you must not lose.** Modules below **5 files** are not
credited proportionally, because a decomposition into hundreds of one-file "modules" would
otherwise score perfectly. The justification given is that people can comfortably process
approximately 5 chunks at a time `[P, paraphrase of the paper's Miller-derived argument]`.

**Computed:** no. It needs a design-rule hierarchy the repo does not declare, and the authors'
implementation (Titan) is not bundled. Do not report a DL number you did not compute with a tool
that implements the paper. What you *can* say offline: the count and sizes of independent modules,
i.e. the SCC-condensed DAG's source components with fewer than 5 files, straight out of `cycles[]`
and `nodes[]`. Report that as "module granularity," not as DL.

---

## 6. Class cohesion and coupling — LCOM, CBO

Chidamber & Kemerer, "A Metrics Suite for Object Oriented Design," *IEEE TSE* 20(6), 1994.

| Metric | Formula | Threshold | Computed |
|---|---|---|---|
| **LCOM1** (C&K) | `LCOM = max(0, |P| − |Q|)` where `P` = method pairs sharing **no** instance variable, `Q` = pairs sharing at least one | `0` for a cohesive class; unbounded and grows with method count, so it is not comparable across classes | no |
| **LCOM4** | number of **connected components** of the graph whose nodes are methods and whose edges join two methods that touch a common field or call one another | `1` = cohesive. `> 1` = the class is literally `n` classes sharing a name; the components are the split | reserved → `nodes[].metrics.lcom4` |
| **LCOM-HS** | `LCOM_HS = (m − (Σ_{j=1..a} μ(A_j)) / a) / (m − 1)` — `m` methods, `a` fields, `μ(A_j)` = number of methods accessing field `A_j` | practical range `[0,2]`; **above 1 is alarming** `[S]` (NDepend) | no |
| **CBO** | count of other classes to which a class is coupled — a class is coupled if it uses the other's methods or instance variables, in either direction, **inheritance excluded** | no literal in C&K; use this repo's top decile, and see `arch-smells.md` §8 for the vendor cutoffs (Designite `fanIn ≥ 20 ∧ fanOut ≥ 20`, NDepend ND1410) | reserved → `nodes[].metrics.cbo` |

**LCOM caveats that stop bad findings:**

- LCOM-HS and LCOM1 are unstable for small types; NDepend documents that they are not relevant for
  types with very few methods or fields `[S]`. Do not report LCOM on a 2-method class.
- `m = 1` makes LCOM-HS divide by zero. Undefined, not `0`.
- LCOM4 counts **only** intra-class edges. A class whose methods all delegate to one collaborator
  scores `1` and is still a Feature Envy case — that is a different smell, see `smells.md`.
- Getter/setter-only pairs inflate cohesion. State whether accessors were included.
- **The variant numbers collide.** LCOM3 is Li & Henry (1993) and LCOM4 is Hitz & Montazeri (1995),
  but Henderson-Sellers calls *his own* formula "LCOM3" `[S]` — so a tool printing "LCOM3" almost
  always means the `LCOM-HS` row above, not connected components. Tools that genuinely compute
  connected components: Aivosto (`LCOM4`), jPeek (`hitz95`), and SonarQube's `lcom4`, since removed
  as noise `[S]`. Read the tool's formula before comparing its number against this table.

The rest of the C&K suite — **WMC** (sum of method complexities), **DIT** (inheritance depth from
root), **NOC** (immediate children), **RFC** (methods plus methods invoked one level out) — are
`reserved → nodes[].metrics.{wmc,dit,noc,rfc}` and not emitted. The published number worth keeping
is `DIT > 6` for deep hierarchy, already tabulated in `arch-smells.md` §4.

**Do not quote the class-level threshold table** usually attributed to Lanza & Marinescu
(WMC 5/14/21, CBO 3/7/9). It circulates everywhere and no primary source for it could be reached
`[unverified]`. Every vendor number with a traceable rule ID is in `arch-smells.md` §8; quote those
instead.

---

## 7. Fan-in, fan-out, information flow

| Metric | Formula | Threshold | Source |
|---|---|---|---|
| **fan-in** | distinct in-neighbours | in-system top decile; also the input to hub rules in `arch-smells.md` §2 and §8 | Constantine & Yourdon `[S]` |
| **fan-out** | distinct out-neighbours | **≤ 7** per module as a design target | Card & Glass, *Measuring Software Design Quality* (1990) `[S]` |
| **IFC** (information flow complexity) | `IFC = length × (fan-in × fan-out)²` | no cutoff; rank only. Reported at `r = 0.95` against errors on a UNIX codebase — a single study, quote it that way | Henry & Kafura (1981) `[P]` |
| **IF4** | Shepperd's revision, dropping the `length` term after showing the original conflated size with structure | rank only | Shepperd (1990) `[S]` |
| **average degree** | `2|E| / |V|` | `> 5` is Designite's Dense Structure rule — do not restate it, cite `arch-smells.md` §4 | Designite `[S]` |

**Computed:** fan-in/fan-out yes → `nodes[].metrics.{fan_in,fan_out}`; average degree yes →
`totals.avg_degree`. IFC and IF4: no — both need a size term per node, and `nodes[].loc` is a file
count proxy, not the `length` of the original definition. If you compute `loc × (fan_in ×
fan_out)²` yourself, call it "an IFC-shaped ranking," not IFC.

The squared term is the whole point: a module with fan-in 10 and fan-out 10 is *100× worse* than
one with fan-in 1 and fan-out 10 by this measure. That is the arithmetic reason a broker in the
middle of a layered graph is the most expensive node in the repo.

---

## 8. Centrality and concentration — PageRank, betweenness, Gini

| Metric | Formula | Threshold | Computed |
|---|---|---|---|
| **PageRank** | `PR(v) = (1−d)/N + d · Σ_{u→v} PR(u)/outdeg(u)`, damping **`d = 0.85`** | in-system: this build normalises so the **mean is 1**, so `PR = 8` reads directly as "eight times the average node's importance." Report nodes at `≥ 5` | yes → `nodes[].metrics.pagerank` |
| **betweenness** | `C_B(v) = Σ_{s≠v≠t} σ_st(v) / σ_st` — fraction of shortest paths through `v` | rank only; no published cutoff. **High betweenness with low own `loc` = pure broker**; high betweenness *and* high fan both ways = hub-like, `arch-smells.md` §2 | yes → `nodes[].metrics.betweenness`, skipped above 1200 nodes with the reason in `degraded[]` |
| **Gini** | on values sorted ascending, `G = (2 · Σ_{i=1..n} i·x_i − (n+1) · Σ x_i) / (n · Σ x_i)`, range `[0,1]` | `0` = every node equal, `1` = one node holds everything. Used here on betweenness inside a tangle: `≥ 0.50` classifies the cycle as **multi-hub** | yes → `cycles[].shape_metrics.hub` |

`d = 0.85` is Brin & Page's original value `[P]` and is not tunable in this build. Direction is the
trap: run PageRank on the **reversed** graph to answer "who depends on me," which is the god-module
question; on the forward graph it answers "what do I depend on," which is much less interesting.
Say which direction you used. NDepend's TypeRank uses the same mean-1 normalisation `[S]`, so its
numbers are comparable in shape to these.

Centrality is also the published way to *order* findings: Arcan's Architectural Debt Index weights
each smell by the PageRank of the node carrying it, `ASIS = SeverityScore × PageRank` `[S]`. That is
the precedent for ranking by blast radius rather than by severity alone.

Brandes (2001) gives betweenness in `O(V·E)` unweighted `[P]`; the 1200-node cap exists because the
constant factor, not the asymptote, is what hurts. Freeman (1977) is the definition `[S]`.

---

## 9. Modularity and communities — a proposal, never a verdict

Newman & Girvan (2004): `Q = Σ_c [ L_c/m − (k_c / 2m)² ]` over communities `c`, with `L_c` edges
inside `c`, `k_c` the total degree of `c`, and `m` total edges. Louvain (Blondel et al. 2008) and
Leiden (Traag et al. 2019) are greedy optimisers of it; Leiden additionally guarantees connected
communities, which Louvain does not `[S]`.

**Three published results make `Q` unusable as a quality score for code:**

| Limitation | Statement | Source |
|---|---|---|
| **Resolution limit** | communities smaller than roughly `√(2L)` edges cannot be resolved by modularity maximisation, whatever the optimiser | Fortunato & Barthélemy (2007) `[P]` |
| **Degeneracy** | high-modularity partitions of the same graph are exponentially many and structurally very different, so "the best `Q`" is not a unique answer | Good, de Montjoye & Clauset (2010) `[S]` |
| **Code-specific gap** | detected communities in software reach `Q ≈ 0.55–0.75` while the developers' **own package structure** scores `Q ≈ 0.09–0.33` on the same graphs | Šubelj & Bajec `[P]` |

That last row is the one that ends the argument: a low-`Q` package layout is *normal*, so a low `Q`
is **never** a finding. Šubelj & Bajec's own prescription is to use detected communities to
**refine existing packages, never to introduce new labels** `[P, paraphrase]` — which is exactly
how `communities[].suggested_folder` must be read: as a proposal, attached to the folder it would
move *within*.

**Two consequences you act on.** (1) `√(2L)` is not abstract: at 20,000 dependency edges it is
`√40000 = 200` files `[derived]` from the bound above, so on a large repo modularity maximisation
will not propose *any* package smaller than that — which is why "modularity says merge these small
folders" is never usable. Leiden's CPM objective with an explicit `γ` is the published way around the
limit `[S]`. (2) MQ is a **sum**, not a mean: `CF_i = 2μ_i / (2μ_i + Σ_{j≠i}(ε_ij + ε_ji))` and
`MQ = Σ_i CF_i`, so `0 ≤ MQ ≤ k` for `k` clusters (Mancoridis et al., IWPC 1998; Mitchell &
Mancoridis, *IEEE TSE* 32(3), 2006) `[S]`. An MQ of 4 is not 400% of anything and is not comparable
to a score produced under the earlier bounded-by-1 definition.

The Bunch-family objectives (MQ, TurboMQ) have the mirror-image defect: Anquetil & Laval showed
their cohesion and coupling terms move mechanically with system growth, so scores are not
comparable across versions `[S]`. Their concrete case is the one to remember: across Eclipse
2.0.1 → 3.1 normalised cohesion *and* coupling both fell while raw `Ce` **rose in about 80% of
packages** `[S]`. Do not report MQ as a trend; trend raw `Ce` and SCC counts instead.

**Computed:** no. `communities[]`, `communities[].modularity_contribution` and
`totals.modularity_q` are `reserved` keys in `specs/graph-report.md`; the current `graph.sh` does
not emit them. Say "community detection not run" rather than eyeballing clusters from folder names.

---

## 10. Consolidated thresholds — every number with its source

| Number | Metric | Meaning | Source |
|---|---|---|---|
| `I = Ce/(Ca+Ce)` ∈ `[0,1]` | instability | definition, not a threshold | Martin 1994 `[S]` |
| `D = |A+I−1|` | distance | "as close to zero as possible"; report above `0.5` | Martin, *Clean Architecture* `[S]` + in-system floor |
| `/√2` | old `D` | 1994 form has range `[0,0.707]`; convert before comparing tools | Martin 1994 `[S]` |
| **0.6** | RACD | "for any non-trivial (n >= 5) acyclic graph of components the RACD is bound by 0.6" | ArchUnit docs `[P]` |
| **1.0** | NCCD | above = worse than a balanced binary tree of the same size | Lakos 1996 `[S]` |
| **20%** | propagation cost | 70% of the 46 open-source projects >1000 files sit below it | MacCormack et al. 2006 `[P]` |
| **50%** | propagation cost | half the system visible from a random file — local review impossible | in-system reading |
| **3000 nodes** | PC cap | closure is `O(V·E)`; above this the key is `null` + `degraded[]` | this skill |
| **5 files** | Decoupling Level | modules below this are not credited proportionally (~5 chunks of working memory) | Mo et al., ICSE 2016 `[P]` |
| **1** | LCOM4 | `1` = cohesive; `n` = the class is `n` classes | Hitz & Montazeri / LCOM4 `[S]` |
| **1** | LCOM-HS | above 1 is alarming; range in practice `[0,2]` | NDepend docs `[S]` |
| **6** | DIT | deeper hierarchy → design smell; full rule in `arch-smells.md` §4 | Designite `[S]` |
| **7** | fan-out | design target per module | Card & Glass 1990 `[S]` |
| **5** | average degree `2|E|/|V|` | Designite Dense Structure; rule in `arch-smells.md` §4 | Designite `[S]` |
| **0.95** | IFC correlation | `r` against errors, one UNIX codebase — quote with the caveat | Henry & Kafura 1981 `[P]` |
| **0.85** | PageRank damping | original constant, fixed in this build | Brin & Page 1998 `[P]` |
| **mean = 1** | PageRank scale | `PR = 8` means 8× the average node | this skill (NDepend TypeRank uses the same) `[S]` |
| **1200 nodes** | betweenness cap | Brandes `O(V·E)` with a large constant | this skill |
| **0.50** | Gini of betweenness in a tangle | at or above → cycle shape `multi-hub` | this skill, over Al-Mutawa's shape taxonomy |
| **`m/2 − n/6`** | feedback arc set | back edges the `GR` heuristic leaves; minimum FAS is NP-hard, so no cut you propose is minimal | Eades, Lin & Smyth 1993 `[S]` |
| **√(2L)** | modularity | smaller communities are unresolvable | Fortunato & Barthélemy 2007 `[P]` |
| **200 files** | modularity at 20,000 edges | the concrete reading of `√(2L)` — nothing smaller can be proposed | `[derived]` from Fortunato & Barthélemy 2007 |
| **`0 ≤ MQ ≤ k`** | MQ / TurboMQ | a sum over `k` clusters, not comparable to the bounded-by-1 1998 form | Mitchell & Mancoridis 2006 `[S]` |
| **~80%** | packages where raw `Ce` rose while normalised cohesion fell (Eclipse 2.0.1→3.1) | trend `Ce` and SCC counts, never normalised cohesion | Anquetil & Laval 2011 `[S]` |
| WMC 5/14/21, CBO 3/7/9 | class thresholds attributed to Lanza & Marinescu | **do not quote** — no primary source reachable | `[unverified]` |
| **0.09–0.33** | `Q` of real package structures | so low `Q` is **not** a finding | Šubelj & Bajec `[P]` |
| **2** | co-change count | do **not** restate — the co-change, churn and hotspot thresholds live in `arch-smells.md` §5 and are cited from there | see `arch-smells.md` |

---

## 11. What this build does not compute

Say the missing input, not "unknown."

| Metric | Missing input | What to report instead |
|---|---|---|
| CCD / ACD / NCCD / RACD | a declared component partition (folders are a guess) | `cycles[]` + `cycles[].shape` |
| Decoupling Level | a design-rule hierarchy, plus Titan | count and size of independent modules |
| LCOM (any variant), CBO, WMC, DIT, NOC, RFC | per-class member/field resolution; `reserved` keys only | file-level `fan_in`/`fan_out` and `loc` |
| modularity `Q`, communities | a community-detection pass; `reserved` keys only | folder structure as declared, unjudged |
| churn, hotspot, temporal coupling degree | `git log --numstat`; commands in `graph-tooling.md` §8 | run them, or say history was not read |
| IFC / IF4 | a true `length` per node | an "IFC-shaped ranking" over `loc`, labelled as such |
| VFI / VFO, core-periphery classes | per-node visibility counts; only the aggregate `propagation_cost` is emitted | derive them from the closure if it ran and state the rank cutoff, else say the classification was not computed |
