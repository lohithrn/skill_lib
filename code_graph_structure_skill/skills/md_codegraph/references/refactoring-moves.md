# Refactoring moves — safe slicing without a big-bang rewrite

The doctrine says what the structure must become. This file says how to get there **one revertable
step at a time**, with the suite green at every step. Every move below is named, sourced, and has a
declared rollback point. A restructure that cannot name its move and its rollback point is not a
slice — it is a rewrite wearing a slice's name.

**The definition that bounds all of it.** Refactoring is "a change made to the internal structure of
software to make it easier to understand and cheaper to modify **without changing its observable
behavior**" (Fowler, *Refactoring*, 1999; 2nd ed. 2018). Fowler's **Two Hats** (*Refactoring* ch. 2):
you are either adding function or refactoring, never both in one commit. `SKILL.md` non-negotiable 8
is that rule with a commit boundary on it.

---

## 1. The slice law — the invariant every move below preserves

| Rule | Why it is not negotiable |
|---|---|
| **Green before, green after** every slice *and* every step inside it | a red suite means you cannot distinguish your breakage from the pre-existing breakage |
| **Red ⇒ revert, never patch forward** | a patched-forward step has no known-good point behind it; the next failure has two causes |
| **Additive steps first, destructive step last and alone** | until the old path is deleted, rollback is "stop using the new thing", which costs nothing |
| **One slice = one commit = one revert** | `git revert <slice>` must leave a working tree (`specs/restructure-spec.md` §4) |
| **Characterization tests before touching untested code** | Feathers, *WELC* ch. 13: a characterization test asserts what the code *does*, bugs included — not what it should do |
| **Copy, do not rewrite, when extracting** | the body moves verbatim with its quirks; a "harmless" cleanup mid-move is a behaviour change with no test to catch it |

**Feathers' Legacy Code Change Algorithm** (*Working Effectively with Legacy Code*, Prentice Hall,
2004) is the order these rules imply: identify change points → find test points → **break
dependencies** → write tests → make the change and refactor. Steps 3 and 4 are the ones people skip,
and they are the ones this file is about. Feathers' framing, verbatim: "To me, legacy code is simply
code without tests."

---

## 2. Seams and enabling points — Feathers, *WELC* (2004)

> "A **seam** is a place where you can alter behavior in your program without editing in that place."
> "Every seam has an **enabling point**, a place where you can make the decision to use one behavior
> or another."

A seam with no enabling point is not usable. Finding the seam *is* the analysis; the enabling point
is where the composition root will eventually live.

| Seam type | Enabling point | Use when | Cost |
|---|---|---|---|
| **Preprocessing seam** | `#define` / build-time text substitution (C/C++ only) | no other seam exists and the code cannot be edited | invisible substitution; last resort |
| **Link seam** | the classpath / linker / module resolution order — swap the binary | you cannot change the source at all (vendored lib, generated code) | the swap is not visible in the source; document it or it is a trap |
| **Object seam** ★ | the **call site that supplies the object** — a constructor parameter | almost always, in any OO language | none. This is the seam the doctrine builds on |

**Object seams are the only kind this skill creates.** A port + constructor injection *is* an object
seam whose enabling point is the composition root. When `analyze` reports "no seam here", it means
the object is constructed inside the method that uses it (conflict **C11**, Control Freak §5.1.1).

### The four sprout/wrap moves — *WELC* ch. 6, "I Don't Have Much Time and I Have to Change It"

These are the moves for adding behaviour to code you cannot yet test. They are **additive**, so the
rollback point is "delete the new thing" in every case.

| Move | Mechanics | Use when | Rollback point |
|---|---|---|---|
| **Sprout Method** | write the new behaviour as a new, *tested* method; call it from one place in the untestable method | the new logic is separable and the host method cannot be brought under test today | delete the new method and its one call line |
| **Sprout Class** | the new behaviour becomes a new class, fully tested; the old method holds one instantiation and one call | the new logic needs its own state or dependencies, or the host class is untestable in-process | delete the class and its one call site |
| **Wrap Method** | rename the original method, create a new method with the *old* name that calls both the renamed original and the new behaviour | the new behaviour must run **every time** the old one does, and is not conditional on the old one's result | rename back, delete the wrapper |
| **Wrap Class** | a new class implementing the same interface, holding the original, adding behaviour around it (Decorator) | the new behaviour must apply at every call site, or must be composable/optional per environment | unwire the wrapper at the enabling point |

**Wrap Class is Decorator arriving by refactoring rather than by design** — the same shape
`doctrine.md` §4 mandates for retry/cache/log. Feathers' warning applies: Sprout Method leaves the
host method *worse* (one more line, still untested). It is a deliberate debt, and the port extraction
that removes it belongs in the spec as a later slice.

**Extract Interface** is Feathers' dependency-breaking move (*WELC* ch. 25), **not** in Fowler's
2nd-edition catalog. Cite it as Feathers. It is step 1 of almost every slice this skill writes:
declare the port, change nothing else, commit.

---

## 3. Branch by Abstraction — Fowler / Hammant

Fowler, *BranchByAbstraction* bliki (2014): a technique for making a large-scale change gradually,
so you can "release the system regularly while the change is still in-progress." Developed at length
by **Paul Hammant**, who attributes the coinage to **Stacy Curl**. The name is a deliberate pun: the
branch is in the *code*, expressed as an abstraction, not in version control.

**The five phases.** Each is a commit; the suite is green at every one.

| # | Phase | State of the system | Rollback |
|---|---|---|---|
| 1 | **Create the abstraction** over the flawed part — the port | new interface exists, nothing uses it | delete the interface |
| 2 | **Refactor clients to use the abstraction**, still backed by the old implementation | every caller goes through the port; behaviour identical | revert callers one file at a time |
| 3 | **Build the new implementation behind the abstraction**, not yet reachable | two resolvers exist; only the old one is wired | delete the new resolver |
| 4 | **Switch the enabling point** to the new implementation | new one runs; old one still compiles and is still tested | ★ **flip the wiring back — one line in the composition root** |
| 5 | **Delete the old implementation**, and the abstraction too if it was pure scaffolding | one implementation, or a real port with a real second answer | `git revert` this commit only |

**Phase 4 is the rollback point that matters.** Because the switch is one line of data at the
composition root, reverting a bad change is a config-shaped operation, not a code-shaped one — and
under a flag it is a runtime operation. That is the whole benefit.

**Why it beats a long-lived branch:** the abstraction stays on trunk, so every commit is integrated
and releasable; there is no accumulating merge, and no *semantic* conflict (code that merges cleanly
and is wrong); the new implementation is exercised by CI from the day it is created rather than the
day it merges; and the change can be shipped half-finished. A long-lived branch defers all of that
risk to one irreversible day. If phase 5 never happens, you have a port with two resolvers — which
is what the doctrine wants anyway.

**Distinguish from Feature Toggle** (Fowler/Hodgson): Branch by Abstraction chooses at the
*composition root, per deployable*; a toggle chooses at *runtime, per request*. The toggle is the one
place a conditional is deliberately kept, and it must be time-boxed and deleted.

---

## 4. Parallel Change / expand–migrate–contract — Danilo Sato (2011)

Named by **Danilo Sato** ("Parallel Change", 2011; ThoughtWorks). The move for changing a
**contract** — a signature, a field, a schema, a wire format, a file path — without a lockstep
update of every client. Three phases, and the phase names are the commit messages.

| # | Phase | What lands | Rollback |
|---|---|---|---|
| 1 | **Expand** | the new form is added **alongside** the old; both work; old callers untouched | delete the new form — nothing referenced it |
| 2 | **Migrate** | callers move to the new form, **one at a time, one commit each**; the old form may log a deprecation | revert the individual caller commit; the old form still works |
| 3 | **Contract** | the old form is deleted, once nothing references it | `git revert` — and this is the only phase where revert restores a *dependency*, so it goes last and alone |

Rules that make it safe:

- **Never write both forms from one caller.** Write through the new form; the old form reads from
  the same state or delegates to the new one. Two writers is how the two forms diverge.
- **The old form delegates to the new**, not the reverse. Then the new form has one implementation
  and the old is a shim with no logic to keep in sync.
- **Contract only when the reference count is zero**, proven by a search plus the type checker — not
  by belief. For a published API, the reference count includes clients you cannot grep;
  Hyrum's Law applies and the deprecation window is measured in releases.

This is the move behind **adding a Context field** (`doctrine.md` §6): expand the Context with the
new field defaulted, migrate the resolvers that care, contract nothing — the additive step alone is
often the whole change. It is also the correct move for a rename: `naming.md`'s renames are Parallel
Change with an alias in phase 1.

---

## 5. The Mikado Method — Ellnestam & Brolund (Manning, 2014)

Ola Ellnestam & Daniel Brolund, *The Mikado Method*. Named for the pick-up-sticks game: you want one
stick (the goal) and must remove the ones resting on it first, without disturbing the pile.

The method is the answer to "I started the change and it exploded into 40 files." It converts that
explosion into a **graph of prerequisites** you can attack from the leaves.

**The loop:**

1. **Write the goal** at the top of the graph — one sentence, the change you actually want.
2. **Try it, naively.** Make the change directly. Do not be careful; be fast.
3. **Read the errors** — compiler, type checker, test failures. Each one is a **prerequisite**, not a
   task to do now.
4. **Add each prerequisite as a node** below the node you were attempting, with an edge to it.
5. ★ **Revert to green.** `git checkout -- .` Discard the experiment entirely. The graph is the only
   artifact you keep from it.
6. **Pick a leaf** — a prerequisite with no prerequisites of its own — and do *that* as a real,
   tested, committed change.
7. Repeat. When a node's children are all done, retry the node. The goal is reachable when its
   prerequisites are all green.

**The rule that makes it work is step 5: revert, and write down what you learned.** The naive attempt
is an *experiment* whose output is knowledge, not code. Feathers' **Scratch Refactoring** (*WELC*) is
the same discipline for comprehension: refactor freely to understand the code, then throw it away.

**Why this skill uses it:** the Mikado graph *is* the slice-dependency graph in
`specs/restructure-spec.md` §4 (`Depends on slice 1, slice 2`). Leaves first, goal last — which is
also the slice-ordering algorithm: characterization tests → Contexts → leaf ports → cycles → hub.
A slice list with no dependency edges was not derived; it was guessed.

**Rollback point:** every one. The graph is built entirely from reverted work; the only committed
work is a finished leaf.

---

## 6. Strangler Fig at component scale — Fowler (2004)

Fowler, *StranglerApplication* bliki (2004), later renamed **StranglerFigApplication** after the
plant: "gradually create a new system around the edges of the old, letting it grow slowly over
several years until the old system is strangled." Published for whole-system replacement; it works
unchanged on **one component**, and that is the version a slice can execute.

| Step | Move | Rollback |
|---|---|---|
| 1 | **Put an interception point in front of the component** — a port, a facade, an HTTP route, a message handler. Everything goes through it; behaviour unchanged | delete the facade, restore direct calls |
| 2 | **Pick the smallest capability** the component owns and implement it behind the same port, in the new structure | delete the new resolver |
| 3 | **Route that one capability** to the new implementation, by data at the enabling point | ★ flip the route back — one line |
| 4 | Repeat 2–3, capability by capability. The old component shrinks; both are live and tested throughout | per capability |
| 5 | **Delete the old component** when its route table is empty | revert the deletion commit |

**Verify by traffic, not by reading.** A capability is migrated when the old path's counter reads
zero over a full business cycle — and `dead-code.md`'s deletion protocol still applies before the
delete: static absence of callers is not proof.

**Never the alternative.** Joel Spolsky, *Things You Should Never Do, Part I* (2000): the
rewrite-from-scratch fails because "It's harder to read code than to write it", so the old code looks
worse than it is and its accumulated bug fixes are silently discarded. Strangler Fig keeps the fixes
because it keeps the code running until it is provably unused.

---

## 7. Preparatory Refactoring — Fowler / Beck / Kerr

**Kent Beck** (2012): "for each desired change, make the change easy (warning: this may be hard),
then make the easy change."

Fowler's *PreparatoryRefactoring* bliki quotes **Jessica Kerr**'s analogy: "I want to go 100 miles
east but instead of just traipsing through the woods, I'm going to drive 20 miles north to the
highway and then I'm going to go 100 miles east at three times the speed I could have if I just went
straight there."

**How this skill applies it:** the port extraction is *not* the feature. It is the 20 miles north.
So:

- The preparatory refactoring is a **separate commit**, ideally a separate slice, and it changes no
  behaviour — the suite proves that by passing unchanged.
- It is justified by the *next* change, which must be named. An extraction with no named next change
  is Speculative Generality (`patterns.md` §7), not preparation.
- Fowler's companion timings from the same bliki family: **comprehension refactoring** (refactor to
  record what you just understood) and **litter-pickup refactoring** (the Boy Scout Rule, bounded).
  Both are legitimate; neither may ride along inside a behaviour commit.

---

## 8. Fowler mechanics for the moves this skill leans on

*Refactoring* 2nd ed. (Addison-Wesley, 2018). Mechanics are compressed; **"test" between every
numbered step is implied and mandatory** — that is what makes them mechanics rather than advice.

| Move | Mechanics, compressed | Role in CPRC | Rollback point |
|---|---|---|---|
| **Extract Function** | name the intent → copy the fragment into a new function → resolve locals into parameters, one out-value only → replace the fragment with a call → test → look for other fragments the new function subsumes | first move on every over-long method; produces the fragment a resolver will hold | inline it back |
| **Move Function** | inspect every element the function uses in its current scope → check for callers to move too → copy into the target, adapt → make the source a **delegating** call → test → redirect callers → delete the delegate | moves a resolver body to its own file; moves a decision to the data's owner (Feature Envy) | the delegate: while it exists, callers are unchanged |
| **Replace Conditional with Polymorphism** | create the class set / port → make a factory or registry that returns the right one → move one leg's body into one class, `return`ing → test → repeat per leg → the base/port method becomes abstract | ★ the doctrine's core move: legs → resolvers | each leg individually; the conditional shrinks one arm at a time and still compiles |
| **Replace Type Code with Subclasses** | self-encapsulate the type field → create one subclass per value with a factory → point callers at the factory → move type-dependent behaviour down, one method at a time → remove the type field | the move when the discriminant is a field on the object rather than an argument (**C10**) | the type field stays until the last behaviour has moved |
| **Introduce Parameter Object** | create the (immutable) class → add it as a parameter, unused → test → replace each original argument's use with the object's field, one at a time → remove the old parameters | ★ builds the Context. This is the only move that *creates* the headroom seam | the old parameters remain until the last one is unused |
| **Replace Constructor with Factory Function** | create a factory that calls the constructor → replace each `new` with the factory call, one at a time → narrow the constructor's visibility | the enabling point for a registry of factories; kills Control Freak `new` at call sites | the constructor stays public until the last call site moves |
| **Hide Delegate** | add a delegating method on the server → change each client from `a.b().c()` to `a.c()`, one at a time → remove the accessor if nothing else uses it | Demeter: stops callers navigating through a resolver's internals | the accessor stays until the last client moves |
| **Remove Middle Man** | add an accessor for the delegate → move each client to use it directly → delete the delegating methods | the inverse; the cure for a pass-through resolver / Lasagna layer | the delegating methods stay until unused |
| **Inline Function** | check it is not polymorphic → find all callers → replace each call with the body → test after **each** → delete the function | ★ the honest undo for over-application. Deleting a Poltergeist resolver is Inline Function + Inline Class | each caller independently |
| **Inline Class** | move the members to the absorbing class one at a time → point clients at the absorber → delete the emptied class | collapses a port whose single resolver never grew a sibling | the emptied class stays until the last member has moved |

**The pattern in every rollback column is the same:** the old path stays functional until the new one
carries all traffic. Any move whose first step deletes something is being done wrong.

---

## 9. Decision table — situation → move → rollback point

| The situation | The move | Rollback point |
|---|---|---|
| Untestable method, new behaviour must be added *now* | **Sprout Method / Sprout Class** (Feathers) | delete the new unit and its one call line |
| New behaviour must run at every existing call | **Wrap Method / Wrap Class** (Feathers) | rename back / unwire the decorator |
| An I/O client is constructed inside business logic (**C11**) | **Extract Interface** (Feathers ch. 25) → constructor-inject → object seam | the port is additive; nothing to undo but a file |
| One implementation must be replaced by a better one | **Branch by Abstraction** (Fowler/Hammant) | phase 4: flip one line at the composition root |
| A signature, field, schema, or path must change under N callers | **Parallel Change** (Sato) | the old form works until phase 3 |
| The change explodes into a tangle of prerequisites | **Mikado Method** (Ellnestam & Brolund) | every step — the experiments are reverted by rule |
| A whole component/service must be displaced | **Strangler Fig** (Fowler) | per capability: flip the route back |
| The feature is hard to add because the structure is wrong | **Preparatory Refactoring** (Beck/Fowler/Kerr) | it is its own commit and changes no behaviour |
| `if/elif/else` on a type or enum, in one place | **Replace Conditional with Polymorphism** | per leg; the conditional shrinks one arm at a time |
| Behaviour keyed off a mutable status field (**C10**) | **Replace Type Code with Subclasses** | the type field survives until the last behaviour moves |
| ≥4 parameters, or a data clump travelling together | **Introduce Parameter Object** → the Context | the old parameters stay until the last use is gone |
| Callers `new` a concrete resolver | **Replace Constructor with Factory Function** → registry | the constructor stays reachable |
| Callers navigate `a.b().c()` into a resolver | **Hide Delegate** | the accessor stays until the last client moves |
| A resolver that only forwards (pass-through / Poltergeist) | **Remove Middle Man**, then **Inline Function / Inline Class** | each caller independently |
| A port with one resolver, no boundary, no named second answer | **Inline Class** — undo it | the port file is the only casualty |
| The suite is red before you start | **stop.** No move is safe. Fix or characterize first | n/a — this is a refusal, per `jobs/apply.md` §4a |

---

## 10. Slice sizing — what is small enough to apply and verify in one pass

A slice is the unit of work **and** the unit of revert. It is correctly sized when **all** of these
hold:

| Dimension | Limit | Why |
|---|---|---|
| Files touched | **≤ 15** | above that a reviewer cannot hold the diff; and it is a codemod, so name the tool (`libcst`, `ts-morph`, `OpenRewrite`, `gofmt -r`, `comby`, `ast-grep`) and give it its own slice |
| Ports introduced | **1** | two ports in one slice means two independent reverts trapped in one commit |
| Steps | **≤ 8**, each a commit | the step list in `specs/restructure-spec.md` §4 is the plan; more than 8 means the slice is two slices |
| Oracle runtime | one full run you are willing to do **after every step** | if the suite takes 40 minutes, the slice is too coarse for the feedback loop it needs |
| Behaviour change | **zero** | mixing one in makes the revert a decision instead of a command |
| Prerequisites | all already **landed and green** | a slice that depends on an unlanded slice is a Mikado node whose children are not done |
| Destructive steps | **exactly one, last** | everything before it is additive, so rollback is free until the end |

**The green rule, stated once and enforced by `jobs/apply.md`:** the oracle — test suite,
`scripts/caps.sh`, `scripts/graph.sh --cycles`, the type checker, the linter — **passes before the
first step and after every step.** A step that leaves it red is reverted, reported, and the slice
stops. Not patched forward. Not "fixed in the next commit."

**Two more tests of a good slice:**

- **The measured-delta test.** The slice's `Green when` line names numbers (`invoice_service.py
  ≤ 250 lines`, `else in billing/ 9 → 0`, `cycles 4 → 3`). If you cannot state a measurable
  post-condition, the slice has no definition of done and cannot be verified in one pass.
- **The stranger test.** Another agent, or the same repo in a month, must be able to execute the
  slice from the spec alone — including the `← file.py:100-115` source ranges for every extracted
  resolver. If it needs re-derivation, the slice is under-specified regardless of its size.
