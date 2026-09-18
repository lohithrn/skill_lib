# Job: spec — turn the graph into an executable plan

Phase 2. **Read-only outside `.codegraph/`.** No source file is edited. This job ends at the
approval gate and does not cross it, even if the user's original message asked for the
restructure — that is `apply`, and it needs a checked approval block.

Output: `.codegraph/restructure.md` against `../specs/restructure-spec.md`, plus a ≤25-line
summary. Nothing else.

---

## Phase 2a — load the graph, or refuse

1. Read `.codegraph/report.md` and `.codegraph/graph.json`.
2. Check `graph.json.root` and the sha in the report against `git rev-parse HEAD`.
   **A stale graph poisons every line of the spec.** If the sha differs, say so and re-run
   `analyze` — do not "adjust for" the drift.
3. If `.codegraph/` does not exist, run `jobs/analyze.md` first. Do not write a spec from a fresh
   read of the code; the spec's authority comes from measured numbers.
4. Read `.codegraph/oracle.json`. Every slice needs a real oracle command. A dimension marked
   `UNVERIFIED` may not produce a slice — its findings go to §7 Out of scope with the reason.

**Never widen scope here.** The spec covers exactly the findings in the report. A conflict you
notice while writing the spec goes back to `analyze`, not into a slice.

---

## Phase 2b — decide, per conflict, before designing anything

Walk the report's **Conflicts inventory** — every row, promoted or not. For each one apply the
promotion threshold from `../references/doctrine.md` §2 and record the decision:

| Decision | When | Where it lands |
|---|---|---|
| **promote** | ≥2 answers exist today · or a 2nd is named in a ticket · or the branch crosses an I/O boundary · or the same discriminant is switched on in ≥2 places | §3 as a port |
| **defer** | one real answer today, no named second | §6 as a deferred conflict |
| **collapse** | the branches differ only in a value, not behaviour | §4 as a data-table slice, no port |
| **type-out** | the case set is closed and the compiler can check totality | §4 as a sealed-type slice, no runtime dispatch |

`collapse` and `type-out` exist so the doctrine does not become an interface farm. A three-branch
`if` that returns three different constants is a **map**, not a port. A closed set the compiler
already checks exhaustively is **already correct** — `../references/architecture.md` §5. Converting
either into runtime dispatch is a regression, and the spec must say why it declined.

Print the promote/defer/collapse/type-out counts in the summary. A spec that promotes every
conflict it found has not applied the threshold and must be re-run.

---

## Phase 2c — fan out the design

Launch one `codegraph-architect` agent **per port cluster** (ports that share a Context or a
call site), in a single message. Each agent gets: the findings it owns, the relevant `graph.json`
nodes, `../references/doctrine.md`, `../references/patterns.md`, `../references/architecture.md`,
and `../specs/restructure-spec.md` §3.

Each agent returns **one §3 port subsection per port** — not prose, not options. Required in every
subsection, or the subsection is rejected and re-requested:

- the conflict **as a question**, in the user's domain words, not the code's
- the port file path and the full signature, ≤3 methods
- **Kind**: open set (registry) · closed set (sealed match) · boundary (single resolver)
- the pattern chosen, from `patterns.md`'s conflict→pattern table, **named**
- the expression-problem call: cases grow ⇒ resolvers; operations grow ⇒ sealed match or Visitor
- the Context type, its fields, and **which fields nothing uses yet and why they exist** —
  that is the headroom seam, and it is stated as intentional so no later reader deletes it
- the resolver table, every row citing `← source_file:start-end`
- the `Absent`/Null resolver — its absence is what leaves an `else` behind
- the contract-suite path and its assertion list (`../references/testing-contracts.md`)
- the registration test that fails the build when a resolver is unregistered
- **Deletes** — the exact ranges this port removes. A port that only adds is rejected.

In parallel, launch one agent for the **target tree** (§2), reading `graph.json.communities`.
The mismatch between detected communities and existing folders **is** the tree proposal; it is
not invented. Every line marked `[new]` needs a one-line reason; every `[moved from]` needs a
source; every `[deleted]` needs the finding ID that justifies it.

---

## Phase 2d — order the slices

Run the 7-step ordering algorithm in `../specs/restructure-spec.md` §4 verbatim. Then verify
mechanically, before writing §4:

1. Slice 1 is **characterization tests** for every hotspot a later slice touches. If the repo has
   no tests at all, slice 1 is the only slice this spec proposes, and §7 says so.
2. No slice touches >15 files. Split, or name the codemod tool.
3. Every slice has an **oracle command** that exists in `oracle.json` and a **revert**.
4. Every slice's first steps are **additive** — the port and the resolvers land before any caller
   changes. Deleting the old branch is always the last step of the slice.
5. Slice dependencies form a **DAG**. Compute it; a cycle in the slice order is a bug in the plan.
6. Every finding ID in the report appears in **exactly one** slice, or §6, or §7. Count it.

---

## Phase 2e — refine, machine-gated

Score the draft against the 8-criterion rubric in `../references/refine-loop.md` §6.
**Budget: 3 passes. Below 16/24, do not present — refine.**

Each pass:

1. Launch `codegraph-adversary` on the **draft spec**, one agent per slice, asking a single
   question: *what does this slice break that the oracle would not catch?* The adversary gets the
   slice and the code, never the architect's reasoning.
2. Score with the rubric. **Accept the revision only if it scores higher.** Keep the best pass,
   not the last — see `../references/refine-loop.md` §1 for why this is not optional.
3. Change **one** dimension per pass. Three simultaneous edits make the score unattributable.
4. Stop early on: no score change, an adversary finding you cannot answer, or 16/24 reached with
   every mechanical check in 2d passing.

Never refine by adding ports. The usual real improvement between passes is a **smaller** spec:
fewer slices, more deferrals, a tighter blast radius.

---

## Phase 2f — write it and stop

Write `.codegraph/restructure.md` in the exact 9-section order. Then run the mechanical checklist
at the end of `../specs/restructure-spec.md` and print its result. §9 Approval ships
**unchecked** — you never check it, and you never infer approval from an earlier message.

Return to the conversation, ≤25 lines:

```
CodeGraph spec: <repo> @ <sha>   ERODED → SOUND
Rubric     19/24 (pass 2 of 3 kept; pass 3 scored 17, discarded)
Conflicts  31 found → 8 promoted · 14 deferred · 6 collapsed to data · 3 already type-checked
Ports      8 · each with an Absent resolver, a contract suite, a registration test
Slices     9 · longest 12 files · slice 1 = characterization tests for 3 hotspots
Blast      87 files touched · 31 created · 4 deleted · no public API change
Deferred   14 seams recorded as intentional headroom — not work items
Not fixed  the reporting hub stays a hub; ruby graph was degraded (see §7)

Review: .codegraph/restructure.md — §2 tree, §3 port questions, §6 deferrals
Next:   check §9 Approval, then /codegraph apply <slices>
```

Then **stop.** Do not begin slice 1. Do not create files "to save a round trip". The gate is the
product of this job.

---

## Refusals

- **No approved spec is being requested here** — if the user asked for the restructure directly,
  write the spec, present it, and say plainly that `apply` needs §9 checked first.
- **No tests in the repo.** The spec proposes characterization tests and nothing else, and says
  why: restructuring unpinned behaviour is not a refactoring, it is a rewrite.
- **A finding with no oracle.** It goes to §7, not into a slice. Never plan a change whose success
  cannot be measured.
- **A degraded graph on the primary language.** The spec may not claim a cycle count, so it may
  not contain a cycle-breaking slice. Name the missing tool and its install command instead.
- **>15 ports in one spec.** Split by community and spec the highest-hotspot community first. A
  spec nobody will read is not a plan.
