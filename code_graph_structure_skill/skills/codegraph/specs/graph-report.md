# Output contract — the graph report

Two artifacts per analysis run, written to `.codegraph/`. Nothing else is produced by phase 1.

| Artifact | Purpose | Consumer |
|---|---|---|
| `.codegraph/graph.json` | machine-readable graph + metrics | phases 2–5, the fitness tests, diffing runs |
| `.codegraph/report.md` | human-readable findings | the user, at the phase-2 gate |

The orchestrator returns **≤ 25 lines** to the conversation. Bulk stays on disk.

---

## 1. `graph.json` schema

```jsonc
{
  "schema": "codegraph/1",
  "generated_at": "2026-09-17T00:00:00Z",
  "root": "/abs/path/to/repo",
  // `files` AND `nodes`, because in Go they differ: one node is a package of several files.
  "languages": [{"name": "python", "files": 412, "nodes": 412, "loc": 38104,
                 "tooling": "ast", "fidelity": "native"}],
  "nodes": [
    {
      "id": "billing.invoice_service",       // module path, language-normalised
      "kind": "module",                      // module | package | class | port | resolver | util | root | test
      "path": "src/billing/invoice_service.py",
      "loc": 214,
      "layer": 2,                            // folder depth from the nearest composition root
      "role": "service",                     // port | resolver | registry | context | root | util | adapter | service | test | unknown
      "metrics": {
        "fan_in": 7, "fan_out": 12,
        "instability": 0.63,                 // I = Ce / (Ca + Ce)
        "abstractness": 0.0,                 // A = abstract types / total types
        "distance": 0.37,                    // D = |A + I - 1|
        "wmc": 41, "cbo": 12, "rfc": 55, "dit": 1, "noc": 0, "lcom4": 3,
        "max_method_lines": 54, "max_nesting": 4, "else_count": 9,
        "cyclomatic_max": 17, "cognitive_max": 31,
        "betweenness": 0.081, "pagerank": 0.019,
        "churn_90d": 34, "hotspot": 0.71     // change frequency x complexity, normalised 0-1
      },
      "violations": ["CG-CAPS-003", "CG-COND-007"]
    }
  ],
  "edges": [
    {"from": "billing.invoice_service", "to": "reporting.summary",
     "kind": "import",                       // import | call | inherit | implement | instantiate | co-change
     "weight": 3,                            // occurrences, or co-change count
     "legal": false,                         // per the layer rule
     "reason": "sideways edge between sibling resolvers"}
  ],
  "cycles": [
    {"scc": ["billing.invoice", "reporting.summary", "billing.tax"],
     "weakest_edge": {"from": "reporting.summary", "to": "billing.tax", "weight": 1},
     "break_with": "invert behind port ReportsTax (DIP)"}
  ],
  "communities": [
    {"id": 0, "label": "billing", "members": ["..."], "modularity_contribution": 0.21,
     "matches_folder": false, "suggested_folder": "src/billing"}
  ],
  "layers": {"declared": ["domain", "application", "adapters"],
             "violations": [{"from": "domain.pricing", "to": "adapters.postgres",
                             "count": 4, "rule": "dependency rule: inward only"}]},
  "ports": [
    {"port": "billing.DiscountPolicy", "methods": 1, "resolvers": 3,
     "has_absent_resolver": false, "contract_suite": null,
     "imported_outside_root": ["reporting.summary"]}
  ],
  "hub_like": [
    {"node": "billing.util.helpers", "fan_in": 41, "fan_out": 38,
     "median_fan_in": 3, "median_fan_out": 4,   // the thresholds it beat, so the claim is checkable
     "ratio_ok": true}                          // |fan_in - fan_out| <= (fan_in + fan_out) / 4
  ],
  "totals": {
    "nodes": 412, "edges": 1204,
    "files": 412, "loc": 38104,
    "illegal_edges": 17,                        // edges with legal:false
    "unresolved_imports": 88,                   // import targets no node matched
    "utils": 9, "avg_degree": 5.8,
    "ports_without_absent": 4,
    // caps.sh keys are `<metric>_minor` (over target) and `<metric>_major` (over hard), plus
    // `worst_<metric>`. Copy them verbatim: the name carries the severity, so a gate can assert
    // `*_major == 0` without knowing which metrics exist. Never `files_over_250` — that spells a
    // threshold into a key name, and CG_CAP_FILE is meant to move it.
    "file_lines_minor": 31, "file_lines_major": 12, "worst_file_lines": 612,
    "method_lines_minor": 208, "method_lines_major": 74, "worst_method_lines": 141,
    "nesting_major": 96, "worst_nesting": 6,
    "loop_body_major": 42, "worst_loop_body": 35,
    "else_major": 341,
    "params_minor": 30, "params_major": 9, "worst_params": 7,
    "public_members_minor": 14, "public_members_major": 5, "worst_public_members": 19,
    // Every caps key is `<metric>_<severity>`, with no exception for these three: the emitted
    // spellings are `unparseable_minor`, `exempt_without_reason_major`, `unbalanced_braces_minor`.
    // A gate keyed on the bare metric name reads "not measured" forever.
    "unparseable_minor": 0, "exempt_without_reason_major": 0, "unbalanced_braces_minor": 0,
    "swallowed_exceptions": 12, "logs_without_stack": 38, "missing_timeouts": 5,
    "error_boundaries": 0, "orphan_resolvers_dead": 2, "banned_names": 7,
    "cycles": 4, "propagation_cost": 0.19,   // propagation_cost is omitted above 3000 nodes
    // "modularity_q" is RESERVED and emitted by nothing in this build (graph-metrics.md §9).
    // Shown here only so a reader does not add it: a Q value no tool printed is a fabrication.
    "ports": 6, "resolvers": 14, "orphan_resolvers": 2,
    "composition_roots": 3, "container_uses_in_tests": 11,
    "contract_suites": 1, "ports_without_suite": 5
  },
  // string[], not objects. One sentence per caveat, each naming what is missing from THIS run.
  // A consumer indexing `entry["reason"]` raises TypeError, so do not document it as a shape.
  "degraded": ["ruby: no native tooling; lexical import graph only",
               "betweenness omitted: 1841 nodes > 1200-node cap"]
}
```

**Rules.** Every metric that appears must have been *measured* — no estimates, no
"approximately". A metric a tool could not produce is **omitted**, not zeroed, and the reason
goes in `degraded`. `legal` on an edge is computed from the layer rule, never guessed.

`totals` is a **union across dimensions**, not one tool's output. `scripts/graph.sh --json`
fills the structural keys; `scripts/caps.sh --json` fills the cap keys; the remaining
dimensions fill theirs, and the orchestrator merges. So a key listed above being absent from
any single tool's output is expected and correct — read the key you need, and treat a key that
is missing entirely as *not measured*, never as zero. Consumers must key off names, never off
position or count: this block is open, and a dimension added later adds keys here without any
existing consumer changing.

---

## 2. `report.md` structure

Fixed section order. Sections with nothing to say are printed with `none` — never dropped, so a
reader can trust the absence.

```markdown
# CodeGraph report — <repo> @ <git sha>

## Verdict
<one line: SOUND | DRIFTING | ERODED>  ·  <n> blockers, <n> majors, <n> minors
<one line on the single highest-leverage change>

## Shape
- languages, files, LOC, and which tooling produced the graph (native vs degraded)
- entry points and composition roots found
- test runner, existing linters, existing caps already enforced

## The graph
- ASCII adjacency by layer, ≤40 lines, deepest-first
- cycles: every SCC listed with its weakest edge and the port that breaks it
- top 5 by betweenness, top 5 by fan-in, top 5 by fan-out
- illegal edges: **the top 5 source-folder → target-folder pairs, each with its count and its share
  of `totals.illegal_edges`**, then the raw total. Never a per-edge list. On a repo that has not
  been restructured yet, almost every cross-folder edge is sideways and therefore illegal
  (`../references/doctrine.md` §9), so `3518 of 3593` is a **distance-to-target measurement, not
  3518 findings** — say which folder pair carries the mass, because that is the first slice.
- Instability/Abstractness scatter read: who is in the Zone of Pain, who in the Zone of Uselessness
- communities detected vs folders that exist — the mismatch list IS the folder proposal, **when a
  partition was computed**. This build computes none (`../references/graph-metrics.md` §9:
  `communities[]` and `totals.modularity_q` are reserved keys, not emitted), so unless a native
  tool supplied a partition this section prints `community detection not run` and the folder
  proposal is derived instead from `nodes[].layer`, `nodes[].role` and directory grouping, read
  against `edges[].legal`. Never print a Q value that no tool produced.

## Hard limits
| metric | warn | hard | worst | over warn | over hard | files |
(one row per limit; the counts link to finding IDs. Warn breaches are minors, hard are majors.)

## Failure handling
- swallowed exceptions, logs without a stack, lost causes — counts and the worst file
- missing timeouts on remote calls, and whether a global error boundary exists per deployable
- resilience decorators found, and whether their nesting order is correct (timeout innermost)

## Dead code
| kind | count | verdict |
Split into `safe to delete` (evidence cleared) and `suspicious` (dynamic usage not ruled out).
Never merged — the second list is not a work list.

## Naming
Banned names, ports named after their first implementation, and paths that would be ambiguous in a
stack frame. Consistent repo conventions are excluded and that exclusion is stated.

## Conflicts inventory
| # | location | discriminant | branches | repeated at | promote? | why |
Every detected conflict, including the ones NOT promoted, with the threshold reason.

## Findings
(per ../specs/finding.md, blockers → majors → minors)

## Deferred conflicts
(the headroom inventory; recorded, not billed)

## Test hierarchy status
| layer | present? | count | gap |
Ports without a contract suite are listed by name — this is usually the biggest gap.

## What this report does NOT cover
Explicit list: languages degraded, directories excluded, dynamic dispatch not statically
resolvable, generated code skipped.
```

---

## 3. The ≤25-line conversation summary

Exactly this shape — including the *absent* renderings. Three numbers here are conditional and a
run that does not have them must say so rather than print the example's value: `propagation cost`
is omitted above the 3000-node cap (`propagation cost n/a (>3000 nodes)`), community detection is
not computed at all (`community detection not run`), and `churn`/`hotspot` need the git pass in
`../references/graph-tooling.md` §8 (`history not read`). Copying a number from this template is
the failure `graph-report.md` §1 warns about: a missing key is *not measured*, never zero.

```
CodeGraph: <repo> — ERODED. 3 blockers, 11 majors, 24 minors.

Graph      412 files / 38.1k LOC / python+ts (native tooling)
           4 cycles · propagation cost 0.19 · community detection not run
           hub: billing.invoice_service (fan-in 7, fan-out 12, betweenness 0.081)
Caps       31 files >250 · 74 methods >25 (208 >15) · 96 nests >1 · 42 loops >8 · 341 `else`
Errors     12 swallowed · 38 logs without a stack · 5 missing timeouts · 0 error boundaries
Ports      6 ports / 14 resolvers · 2 orphaned · 5 ports have no contract suite
Roots      3 composition roots (expected 1) · 11 tests build via the container
Dead       9 safe to delete · 4 suspicious (dynamic usage unresolved)
Hotspot    history not read (no git pass in this build; see graph-tooling.md §8 to run it)

Top 3
1  CG-GRAPH-001 blocker  billing↔reporting↔tax cycle — break at reporting→tax behind ReportsTax
2  CG-DI-002    blocker  domain/pricing constructs PostgresRepo directly — untestable
3  CG-COND-007  major    tier switch repeated in 2 files — promote to DiscountPolicy

Full: .codegraph/report.md · .codegraph/graph.json
Next: /codegraph spec   (writes the restructure spec; still no edits)
```

---

## 4. Verdict thresholds

| Verdict | Condition |
|---|---|
| **SOUND** | 0 cycles · 0 blockers · <5% of files over any cap · every port has a contract suite |
| **DRIFTING** | ≤2 cycles · ≤2 blockers · <20% of files over a cap |
| **ERODED** | anything worse |

Verdicts are computed, never chosen. Print the arithmetic if asked.

---

## 5. Determinism

Two runs on the same commit must produce byte-identical `graph.json` except `generated_at`.
That means: sort every array by a stable key, never embed absolute paths inside `nodes`/`edges`
(only in `root`), round floats to 3 decimals, and never include timing data. A non-deterministic
graph cannot be diffed, and diffing runs is how phase 5 proves the restructure worked.
