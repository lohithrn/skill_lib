# Job: analyze — build the graph, find the conflicts

Phases 0–1. **Read-only outside `.codegraph/`.** No file is edited. No git state changes.

Output: `.codegraph/graph.json`, `.codegraph/report.md`, and a ≤25-line summary in the
conversation. Contracts: `../specs/graph-report.md` and `../specs/finding.md`.

---

## Phase 0 — scope, cheaply

Before spending a single agent, establish the ground truth. One `Bash` batch, one `Glob`.

1. **Languages and size.** `scc` or `tokei` if present, else `git ls-files | awk -F. '{print $NF}' | sort | uniq -c | sort -rn`.
2. **Entry points.** `main.*`, `__main__.py`, `cmd/*/main.go`, `Application.java`, `index.ts`,
   `Dockerfile` CMD, `pyproject.toml [project.scripts]`, `package.json` `bin`/`scripts.start`.
3. **Existing composition roots.** Grep for container setup, `wire()`, `@Configuration`,
   `createApp`, `AppModule`, `fx.New`, `wire.Build`.
4. **Test runner and existing gates.** `pytest.ini`/`pyproject`, `package.json` test script,
   `pom.xml`/`build.gradle`, `go.mod`. Which linters already run, and **which caps they already
   enforce** — never report a violation of a cap the repo already polices differently without
   saying so.
5. **Oracle inventory.** Write `.codegraph/oracle.json` in the shape of `../specs/oracle.md`:
   which of test suite, type checker, linter, `caps.sh`, `graph.sh`, mutation tool actually run
   here, each with its **exact command**, whether it ran green, and its baseline output. Nine
   later steps execute those strings verbatim, so the key names are a contract, not a suggestion.
   Dimensions whose tool list is empty are reported once as `UNVERIFIED` and never iterated on.
6. **Exclusions.** Vendored code, generated code, migrations, fixtures, `node_modules`, build
   output. List them; they go in the report's "does NOT cover" section.

Write `.codegraph/scope.json`. If the repo is >5k files, ask which subtree to analyze before
fanning out — a whole-monorepo graph is rarely the question being asked.

---

## Phase 1 — fan out, one agent per dimension

Launch **all** dimension agents **in a single message** so they run concurrently. Each one:

- receives `.codegraph/scope.json` and the path to its reference file,
- writes its own artifact to `.codegraph/<dim>.json` **and** `.codegraph/<dim>.md`,
- returns **≤25 lines** — never a finding list, never file contents.

| Dim | Agent | Reads | Hunts | Artifact |
|---|---|---|---|---|
| `graph` | `codegraph-cartographer` | `graph-tooling.md`, `graph-metrics.md` | cycles, hubs, fan-in/out, I/A/D, centrality, communities vs folders, layer violations | `graph.dim.json` |
| `caps` | `codegraph-inspector` | `laws.md` | file lines, method lines (15 warn / 25 hard), nesting >1, loop bodies >8, `else`, params, public members, hierarchy depth | `caps.json` |
| `cond` | `codegraph-inspector` | `doctrine.md` §1, `patterns.md` | every conflict C1–C14, with discriminant, branch count, and repeat sites | `cond.json` |
| `di` | `codegraph-inspector` | `di-patterns.md` | Control Freak, Service Locator, Ambient Context, Bastard Injection, field injection, multiple roots, container-in-tests | `di.json` |
| `port` | `codegraph-inspector` | `doctrine.md` §3, `smells.md` | fat ports, ports declared with implementations, missing Absent resolvers, orphan resolvers, Refused Bequest, deep hierarchies | `port.json` |
| `test` | `codegraph-inspector` | `testing-hierarchy.md`, `testing-contracts.md` | ports without a contract suite, unregistered resolvers, layer bleed, mock overuse, missing fitness tests | `test.json` |
| `time` | `codegraph-inspector` | `graph-tooling.md` §git | co-change coupling with no static edge, hotspots (churn × complexity) | `time.json` |
| `err` | `codegraph-inspector` | `error-handling.md` §7 | E1–E10: swallowed exceptions, logs without a stack, lost causes, missing timeouts, no error boundary, unbounded retry | `err.json` |
| `dead` | `codegraph-inspector` | `dead-code.md` | D1–D10: orphan resolvers, unreachable registry keys, fan-in-0 modules, duplicate unwired implementations, old chains beside their replacements | `dead.json` |
| `name` | `codegraph-inspector` | `naming.md` §7 | N1–N8: banned names, role-only or answer-only file names, ports named after their first implementation, `Base*` with shared state | `name.json` |

**Do not** run these sequentially. **Do not** run a dimension whose oracle is absent — record it
as `UNVERIFIED` in the report and skip it.

Three dimensions have extra rules their agent must be told:

- **`err`** — prefer an existing linter's rule ID as the LAW field (`ruff TRY400`, PMD
  `PreserveStackTrace`, `errcheck`) over a bespoke finding. E1/E2/E6/E7 are **blockers**: each one
  means a real failure is invisible or unbounded.
- **`dead`** — every finding needs the `EVIDENCE` line. **Never propose a deletion; propose a
  verified deletion or a `suspicious` marker.** Walk the §2 dynamic-usage safelist for the actual
  language and framework, and say which checks ran.
- **`name`** — report only names that mislead a reader seeing them alone. The repo's own consistent
  convention is **not** a finding, and neither is idiomatic brevity in Go or a framework-mandated
  file name.

### What every dimension agent is told

Verbatim requirements to include in each agent's prompt:

- "Run the measurement. Do not estimate. Every number you report came from a command that ran."
- "Open the line range before ruling on it. A grep hit is not a finding."
- "Emit findings only in the format of `specs/finding.md`. Seven fields. A finding without a
  CONSEQUENCE and a REMEDY is dropped — drop it yourself rather than reporting it."
- "Deliberate headroom is not a defect. Env-scoped names sharing one value, a mode knob with one
  mode today, a per-stage resource pointing at one target, a permissive default a future stage
  will tighten — record these as SEVERITY `deferred-conflict` with no LAW and no CONSEQUENCE.
  Never report them as debt."
- "Check `specs/finding.md` §'Automatic non-findings' before you emit anything."
- "Write your full output to `.codegraph/<dim>.md` and `.codegraph/<dim>.json`. Return at most 25
  lines: counts, the worst three locations, and the single highest-leverage change."

---

## Phase 1b — measure with the scripts, not by reading code

```bash
bash <skill-dir>/scripts/caps.sh  --json --root <path>  > .codegraph/caps.json
bash <skill-dir>/scripts/graph.sh --json --root <path>  > .codegraph/graph.raw.json
```

`<skill-dir>` is the absolute path resolved in phase 0 and recorded in
`.codegraph/oracle.json` (`tools.caps.command` / `tools.graph.command` are the exact
strings). Substitute it; never run a command with an unexpanded `${...}` in it — a
shell that does not set the variable silently runs `bash /skills/…`.

Native tooling, per language, when installed — see `references/graph-tooling.md` for exact flags:
`grimp`/`lint-imports`/`pydeps` · `depcruise --output-type json` · `jdeps -dotoutput` ·
`GOFLAGS=-mod=readonly GOPROXY=off GOTOOLCHAIN=local go list -deps -json` ·
`git log --numstat` for churn and co-change. The go prefix is not optional: without it the command
resolves modules from the network.

If native tooling is missing, the scripts fall back to a lexical import sweep (`grep`/`awk`, no
extra tooling — ripgrep is not a dependency and is never installed) and set
`"fidelity": "degraded"`. **Report the degradation in the verdict line.** A degraded graph may not
be used to claim "0 cycles."

---

## Phase 1c — merge and verify

1. Merge every `<dim>.json` — including the cartographer's `graph.dim.json` — into
   `.codegraph/graph.json` per the schema in
   `../specs/graph-report.md` §1. Sort every array by a stable key. Round floats to 3 decimals.
   Two runs on one commit must differ only in `generated_at`.
2. **Verify the findings before writing the report.** Launch `codegraph-adversary` agents in
   parallel, one per blocker and per major, each receiving *only* the finding and the code — never
   the finder's reasoning. Schema and thresholds: `../references/refine-loop.md` §4.
   **1 CONFIRMED keeps it. 2 independent REFUTED drops it. 2 UNCLEAR downgrades to minor.**
3. **Calibration check.** If an adversary panel refutes ≥50% of one dimension's findings, that
   detector is miscalibrated. Stop verifying it, tighten its threshold, re-run it once, and say so
   in the report. Do not spend the budget arguing.
4. Compute the verdict arithmetically (`../specs/graph-report.md` §4). Never choose it.

---

## Phase 1d — write the report

`.codegraph/report.md`, exact section order from `../specs/graph-report.md` §2. Sections with
nothing to say print `none` — never dropped, so absence is trustworthy.

Two sections carry most of the value and are usually skipped by lesser reports:

- **Conflicts inventory** — *every* conflict found, including the ones **not** promoted, each with
  the threshold reason. This is what makes the spec reviewable: the reader can see what was
  considered and declined.
- **Communities vs folders** — the detected module communities next to the folders that exist. The
  mismatch list *is* the folder proposal that phase 2 turns into a target tree. No bundled script
  computes a partition, so with no native tool this section reads `community detection not run` and
  the grouping comes from `nodes[].layer`/`nodes[].role` plus `edges[].legal`; name which. Printing
  a fabricated community list or a `modularity Q` value is a blocker-severity error, because
  `../references/graph-metrics.md` §9 then compares real folders against invented ones.

Order findings: blockers → majors → minors (batched by file) → deferred-conflict inventory last
under its own heading. Within a severity, descending `change-amplification × hotspot`.

---

## Return to the conversation

Exactly the shape in `../specs/graph-report.md` §3 — ≤25 lines. Then one next action:

```
Next: /md_codegraph spec   (writes the restructure spec; still no edits)
```

**Never paste the report.** Never paste `graph.json`. Never list more than the top three findings.

---

## `review` mode

`/md_codegraph review [path]` is this job with three changes: no `graph.json` is written (only
`report.md`), the `time` and `port` dimensions are skipped unless the path is a whole package, and
the output stops at findings — no communities, no folder proposal, no next-action pointing at
`spec`. Use it for a PR-sized diff. If the target is a diff, scope every dimension to the changed
files plus their direct importers, and say so in the report.

**`review` ends the run, so it also disposes of `.codegraph/`** — `../references/artifacts.md`
§Ending a run. Nothing downstream is going to read these measurements: there is no spec to write and
no slice to apply, so the per-dimension JSON is spent the moment the report is written. Promote the
deferred conflicts, offer `report.md`, delete the rest. An `analyze` that the user is taking on to
`spec` keeps the directory — that is the state machine, not litter.

---

## Refusals

- **A repo with no tests.** Say so in the verdict line and mark every slice-bearing finding as
  requiring characterization tests first. Do not propose restructuring untested code as if it were
  safe.
- **A degraded graph on the primary language.** Report what you can, name the missing tool and its
  install command, and do not assert cycle counts.
- **A path outside the repo, or a `.codegraph/` that already exists from a different commit.**
  Stop and ask; a stale graph silently poisons every later phase.
