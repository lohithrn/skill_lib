---
name: md_codegraph
description: Read a codebase as a dependency graph, then restructure it so every conflict becomes an interface, every interface has replaceable implementations wired at one composition root, and the folder tree IS the graph. Enforces hard caps (250-line files, 25-line methods, 1 nesting level, 8-line loop bodies, no else), responsibility-based file naming, traceback-bearing error handling, a contract-test suite per interface, and executable architecture-fitness tests.
when_to_use: Only when explicitly invoked as /md_codegraph. Never auto-trigger.
disable-model-invocation: true
argument-hint: "nothing — or [analyze|spec|verify|apply|fitness|review] [path] to force a phase"
allowed-tools: Read, Grep, Glob, Write, Edit, TodoWrite, Agent, Bash(mkdir:*), Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(git rev-parse:*), Bash(git ls-files:*), Bash(git add:*), Bash(git commit:*), Bash(git checkout:*), Bash(git switch:*), Bash(git revert:*), Bash(bash ${CLAUDE_SKILL_DIR}/scripts/*)
---

# /md_codegraph

A router. It resolves one conflict — **which job did the user ask for?** — and delegates. No job
logic, no metric formulas, no rule catalogs: those live in `jobs/`, `references/` and `specs/`. The
skill is built the way it tells you to build; read `references/doctrine.md` first.

## The gate — read this first

**Phase 2 is a hard stop.** Nothing on disk is edited until the user approves
`.codegraph/restructure.md`.

- `analyze`, `review`, `spec`, `verify` are **read-only** outside `.codegraph/`.
- `apply` requires an approved spec with a checked approval block. Without one it **refuses**, says
  what is missing, and runs `spec` instead. It works one slice at a time, tests green before and
  after each, and a slice that leaves them red is **reverted, not patched forward**.
- Never `git push`, open a PR, merge, tag, or rebase. Never commit to `main`/`master`. Never delete
  a file the spec does not list under `[deleted]`.
- The tool grant is **wider than the read-only phases on purpose**: `apply` writes source and
  `fitness` writes tests. What stops an edit is this gate, not a missing tool.

## Route

Parse `$ARGUMENTS`. First token is the job, rest is the path (default: repo root). Read the one
job file in that row and follow it; do not read the others. The default route is the single
exception — two files, `analyze.md` then `spec.md`, in that order and never interleaved.

| Invocation | Job file | Phases | Edits code? |
|---|---|---|---|
| `/md_codegraph` (no argument) | whatever `.codegraph/` says is next — see below | 0–5 as reached | only past an approved gate |
| `/md_codegraph analyze [path]` | `jobs/analyze.md` | 0–1 | no |
| `/md_codegraph review [path]` | `jobs/analyze.md` (findings only, no graph artifacts) | 0–1 | no |
| `/md_codegraph spec [path]` | `jobs/spec.md` | 2 | no |
| `/md_codegraph verify` | `jobs/verify.md` | 3 | no |
| `/md_codegraph apply [slice\|all]` | `jobs/apply.md` | 4–5 | **yes, per approved slice** |
| `/md_codegraph fitness [path]` | `jobs/fitness.md` | writes layer-4 tests only | adds tests |

**No argument is the whole interface: bare `/md_codegraph` resumes.** Read `.codegraph/` first — no
spec ⇒ analyze then spec · unchecked approval block ⇒ re-print the gate and stop · approved spec with
slices left ⇒ apply the next one, naming it · all slices applied ⇒ verify. State which case was found
and the job it selected in one line before starting. A job token overrides that choice; an
unrecognised first token is a path, not an error.

---

## The doctrine, in brief

Full version in `references/doctrine.md`. The short form:
> **Every conflict is an interface. Every interface has multiple implementations. Which one runs
> is decided by data, at the composition root — never by an `if` at the call site. Every
> implementation receives one immutable Context carrying the whole problem.**

1. **Conflict** — any point with more than one possible answer: `if/elif/else` on a type or flag, a
   switch repeated in two files, `if x is None`, a boolean parameter, an env check.
2. **Port** — one interface per conflict, ≤3 methods, docstring states the conflict **as a
   question**, declared beside its caller (Separated Interface), never with its implementations.
3. **Resolvers** — one per answer, one per file, in a subfolder named for the port, plus an
   `Absent`/Null resolver so the set is **total**. Totality is what deletes `else`.
4. **Selector** — the `if` moves once, into data: a registry map, a `handles(ctx)` chain, or a
   visitor. A residual `if` at the call site is a violation; a `match` in the registry is not.
5. **Context** — one frozen value object per conflict family, carrying every variable the problem needs
   *including ones nothing uses yet*. That is the headroom seam.
6. **Composition root** — one per deployable, the only place naming concrete resolvers,
   constructor injection only. If a test touches the container, the root has leaked.
7. **Common utils** — pure, no I/O, zero project imports, a sink node in the graph.

**The layer rule:** layer *n* declares conflicts; layer *n+1* — a subfolder — resolves them. Edges
point down and inward, so the folder tree **is** the dependency graph and the graph is a testable
predicate: folders are question nodes, files are answer nodes, imports are edges.

**The promotion threshold matters as much as the doctrine.** Promote a conflict only when two answers
exist today, a second is named in a ticket, the branch crosses an I/O boundary, or the same
discriminant is switched on in ≥2 places. Otherwise record a `DEFERRED CONFLICT` and move on:
over-application produces an interface farm (`references/doctrine.md` §2).

---

## Hard limits

Machine-checked by `scripts/caps.sh` — `--help` prints the live defaults, every one overridable by
its `CG_CAP_*` env var. Report every breach with `file:line` and the measured number.

| Limit | Warn | **Hard** | Resolution |
|---|---|---|---|
| File length | 200 | **250 lines** | split by responsibility; extract resolvers to a subfolder |
| Method length | 15 | **25 lines** | extract a *named* method, or promote the branch to a port |
| Nesting depth in a method | — | **1** | guard clauses, or extract the inner block to a named method |
| Loop body length | — | **8 lines** | extract the body: the loop shows repetition, the method shows per-item behaviour |
| `else` / `elif` | — | **0** outside a registry literal | registry, chain, or Null Object |
| Parameters | 3 | **4**, or 1 Context | introduce a Context |
| Public members per class | 5 | **7** | split by reason-to-change |

Hard too, measured by another dimension, not `caps.sh`: **3** methods per port and hierarchy depth
**2** (`port`) · **0** module-graph cycles, from `graph.sh` (`graph`) · **1** composition root per
deployable (`di`) · **0** ports without a contract suite (`test`) · **0** swallowed exceptions
(`err`). A fitness test asserts each against the tool that emits it.

**Warn vs hard.** A warn breach is a **minor**, batched, never its own slice; a hard breach is a
**major** and must appear in the spec. Fitness tests assert the **hard** column only (`*_major`).

Exempt from the `else` rule: a registry literal in the composition root, and an exhaustive match over
a sealed/ADT set the compiler checks. Both are data. **Nesting is measured from the method body**, so
`for` + `if` is depth 1 and legal, a third level is not, and a guard clause removes nesting.

**File length is measured on code files only** — the cap is a claim about how much *code* one file
may hold, and firing it on a README teaches a reader to ignore the tool. Prose: `SPEC.md` §10.

**A breach may be declared exempt in the source** with `# codegraph:exempt <metrics> -- <reason>`
above the declaration — or, for `file_lines`, in the first 20 lines of the file, since a file has no
declaration. Seam, not hole: it must name each metric and carry a reason, a reasonless one suppresses
nothing and is reported as `exempt_without_reason`, and the breach is still printed with
`"severity": "exempt"`. The bar is a **citation**. Mechanism: `references/laws.md` §8.

---

## Non-negotiables

1. **Read before ruling.** Never emit a finding from a filename or a grep hit alone. Open the range.
2. **The Iron Law of findings.** No finding without all seven fields of `specs/finding.md`; one with no
   consequence and no remedy is noise and is dropped.
3. **Headroom is not a defect.** "The current value is the loosest possible", "you collapsed X into
   one value", env-scoped names sharing a value, a mode knob with one mode, a per-stage resource
   pointing at one target — deliberate seams. Record as `DEFERRED CONFLICT`, never simplify away,
   and when unsure whether a seam is intentional, ask.
4. **Measure, don't estimate.** Every number came from a command that ran; a metric no tool produced
   is omitted and listed under `degraded`, never zeroed.
5. **The oracle rules.** Refinement is gated on the suite, `caps.sh`, `graph.sh`, the type checker
   and mutation score — never self-assessment. No oracle ⇒ report the dimension once as
   `UNVERIFIED` and do not iterate. `specs/oracle.md`, `references/refine-loop.md` §1.
6. **Accept only if better.** Never take a revision that scores worse on the oracle; return the
   best pass, not the last.
7. **Extract the interface before moving anything.** Additive steps first. (*Extract Interface* is
   Feathers' move, *WELC* ch.25 — **not** in Fowler's 2nd-ed. catalog. Cite it correctly.)
8. **One slice, one commit, one revert.** Never mix a behaviour change with a refactoring.
9. **Characterization tests before touching untested code.** Pin current behaviour, bugs included,
   then move it.
10. **Caps are tests, not habits.** Not done until `tests/fitness/` enforces every claim the spec
    made about the graph.
11. **Never rewrite a contract suite to make a resolver pass.** That inverts the oracle.
12. **Say what you did not do.** Every report ends with what it does not cover: languages
    degraded, directories skipped, dynamic dispatch not statically resolvable.
13. **A path names its subject, its role, and its answer.** `payment/processors/stripe_payment_processor.py`,
    never `.../stripe.py` — it must still make sense alone in an editor tab, an import line and a
    stack trace. Banned names: `utils` `helpers` `common` `misc` `base` `logic` `manager`.
14. **Every caught exception either logs a full traceback or re-raises with the cause attached.**
    A bare `except: pass`, a `catch (e) {}`, an ignored `err`, or a log line without the stack is a
    **blocker**. See `references/error-handling.md`.
15. **Never delete on suspicion.** Static absence of callers is not proof. Check the dynamic-usage
    safelist in `references/dead-code.md` first — entry points, reflection, plugin registries,
    config dispatch, generated code, migrations. Unconfirmed ⇒ `suspicious`, not removed.
16. **Abstraction must pay for itself.** An interface, folder or registry ships only if it removes real
    duplication, isolates real variation, improves testability, protects a boundary, or kills a
    growing selection branch. `ThingInterface` + `DefaultThing` alone is a **finding**.

## Fan-out contract

Heavy work runs in subagents so its tool output never enters this conversation.

- **One agent per analysis dimension, launched in parallel** in a single message:
  `graph` · `caps` · `cond` · `di` · `port` · `test` · `time` · `err` · `dead` · `name`.
- Every agent **writes its artifact to `.codegraph/`** and returns **≤25 lines**; bulk never returns as text.
- Findings are **claims** until an adversary confirms them, and it never sees the finder's
  reasoning. **1 CONFIRMED keeps a finding; 2 independent REFUTED drops it.**
- Bundled agents: `codegraph-cartographer` (graph), `codegraph-inspector` (one dimension),
  `codegraph-architect` (target tree), `codegraph-adversary` (attack), `codegraph-surgeon` (one slice).
  Not installed ⇒ `general-purpose` with the job file inlined.
- **Cannot fan out** (no `Agent` tool, or parallel launch fails)? Run the dimensions **serially in
  this order** — `caps`, `graph`, `err`, `cond`, then the rest — one at a time, discarding each
  dimension's bulk output before the next, and say `fan-out unavailable: ran N dimensions
  serially` in the verdict line. Fewer dimensions honestly reported beats a pipeline that
  refuses to start; the four named first are the ones with a script or a grep behind them.
- The final message is the ≤25-line summary from `specs/graph-report.md` §3 plus one next action.
  Never paste a full report into the conversation.

## Scripts

Run them; do not read them. Both take `--root PATH` and emit JSON on stdout (`--text` for humans).
A violation or a cycle is **data**: exit 0. Exit 2 means the scan could not run — the only case
where the output must not be read as a result. A path is an option value, never a positional.

**Resolve the skill directory once, in phase 0, and record the ABSOLUTE command in
`.codegraph/oracle.json`.** Try `${CLAUDE_SKILL_DIR}`, then the directory holding this
`SKILL.md`; first one with a `scripts/caps.sh` wins. Later phases
and subagents run the recorded string — an unexpanded `${...}` becomes `bash /scripts/…` elsewhere.

Start with `bash <skill-dir>/scripts/caps.sh --help` and the same for `graph.sh`.

| Script | Emits | Contract |
|---|---|---|
| `scripts/caps.sh` | file lines, method lines, nesting, loop bodies, `else`, params, public members | `codegraph-caps/1` |
| `scripts/graph.sh` | nodes, edges, cycles (Tarjan) + shape, fan-in/out, I/A/D, PageRank, propagation cost, port health | `specs/graph-report.md` |
| `scripts/graph.sh --cycles` | the cycle slice of the same artifact, `--json` or `--text` | same, projected |

`--cycles` answers the refine loop's one question, "did this slice remove the cycle?" — a
**projection, never a second measurement**, carrying `fidelity`/`degraded` through.

**Fidelity is reported, never assumed.** Python is AST-exact and Go uses `go list` when the toolchain
and a `go.mod` are present; TypeScript/JS and Java/Kotlin are a **lexical import sweep**, so aliases
beyond `@/`, wildcard imports and same-package references are not edges. Every caveat lands in
`degraded`, every unmeasurable metric is **omitted, not zeroed**, a lexical graph may not claim "0
cycles" without saying so in the verdict line, and **0 edges with unresolved imports is a failed
scan, not an acyclic repo** — the scripts say so themselves in `degraded`.

Dependency set: `python3`, `awk`, `grep`, `git`. Nothing is installed, nothing is fetched.

## References — read the one you need, do not inline them wholesale

| File | For |
|---|---|
| `references/doctrine.md` | ★ the CPRC transformation, the promotion threshold, when it goes wrong |
| `references/laws.md` | SOLID, Object Calisthenics, connascence, GRASP, Demeter, every numeric cap and its source |
| `references/architecture.md` | DDD, hexagonal/onion/clean compared, parse-don't-validate, illegal states, the expression problem |
| `references/naming.md` | responsibility-based paths, the banned-name list, rename safety |
| `references/error-handling.md` | tracebacks, never-swallow, error boundaries, resilience decorators, per-language idioms |
| `references/dead-code.md` | the deletion protocol and the dynamic-usage safelist |
| `references/patterns.md` | GoF + modern patterns, and the **conflict → pattern decision table** |
| `references/di-patterns.md` | DI taxonomy, composition root, the named anti-patterns |
| `references/graph-metrics.md` | formulas and thresholds: I, A, D, LCOM, CBO, centrality, propagation cost |
| `references/graph-tooling.md` | exact commands per language, including git co-change |
| `references/smells.md` | Fowler's 24, Clean Code's codes, architecture smells, and what is NOT a finding |
| `references/arch-smells.md` | ★ the published architecture-smell rules with their exact numbers, cycle shapes, name-collision table, offline computability matrix |
| `references/testing-hierarchy.md` | the 7 layers, doubles, LSP verification, mutation targets |
| `references/testing-contracts.md` | contract-suite code per language + registration-as-build-failure |
| `references/refactoring-moves.md` | safe slicing: seams, Branch by Abstraction, Parallel Change, Mikado |
| `references/language-idioms.md` | ports, registries, Contexts, roots, no-`else` idioms per language |
| `references/refine-loop.md` | the convergence loop, its stopping criteria, and why it is machine-gated |

Output contracts in `specs/`: `finding.md` (the Iron Law) · `oracle.md` (what command proves a claim,
per dimension) · `graph-report.md` (analyze output + the ≤25-line summary) · `restructure-spec.md`
(the phase-2 gate).

## Checklist before saying done

- [ ] The right job file was read, and only that one
- [ ] Every number in the output came from a command that ran
- [ ] Every finding has all seven fields and survived verification
- [ ] Headroom was recorded as `DEFERRED CONFLICT`, not reported as debt
- [ ] No file was edited before the approval block was checked
- [ ] Tests were green before and after every applied slice
- [ ] Every port has an `Absent` resolver, a contract suite and a registration test
- [ ] `tests/fitness/` enforces every graph claim the spec made
- [ ] The conversation got a ≤25-line summary, one next action, and what it does not cover
