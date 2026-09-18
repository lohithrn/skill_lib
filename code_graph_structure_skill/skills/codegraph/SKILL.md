---
name: codegraph
description: Read a codebase as a dependency graph, then restructure it so every conflict becomes an interface, every interface has replaceable implementations wired at one composition root, and the folder tree IS the graph. Enforces hard caps (250-line files, 25-line methods, 1 nesting level, 8-line loop bodies, no else), responsibility-based file naming, traceback-bearing error handling, a contract-test suite per interface, and executable architecture-fitness tests.
when_to_use: Only when explicitly invoked as /codegraph. Never auto-trigger.
disable-model-invocation: true
argument-hint: "[analyze|spec|verify|apply|fitness|review] [path]"
allowed-tools: Read, Grep, Glob, TodoWrite, Agent, Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(git rev-parse:*), Bash(bash ${CLAUDE_SKILL_DIR}/scripts/*)
---

# /codegraph

A router. It resolves one conflict — **which job did the user ask for?** — and delegates. It
holds no job logic, no metric formulas, and no rule catalogs; those live in `jobs/`,
`references/`, and `specs/`. The skill is built the way it tells you to build.

Read `references/doctrine.md` before doing anything else. It is the transformation this whole
skill exists to perform.

---

## The gate — read this first

**Phase 2 is a hard stop.** Nothing on disk is edited until the user approves
`.codegraph/restructure.md`.

- `analyze`, `review`, `spec`, `verify` are **read-only** outside `.codegraph/`.
- `apply` requires an approved spec with a checked approval block. Without one it **refuses**,
  says what is missing, and runs `spec` instead.
- `apply` works one slice at a time. Tests green before and after every slice. A slice that
  leaves them red is **reverted, not patched forward**.
- Never `git commit`, `git push`, or branch without being asked. Never delete a file the spec
  does not list under `[deleted]`.

## Route

Parse `$ARGUMENTS`. First token is the job, rest is the path (default: repo root).
Read the one job file and follow it. Do not read the others.

| Invocation | Job file | Phases | Edits code? |
|---|---|---|---|
| `/codegraph` | `jobs/analyze.md` then `jobs/spec.md` | 0–2, stop at the gate | no |
| `/codegraph analyze [path]` | `jobs/analyze.md` | 0–1 | no |
| `/codegraph review [path]` | `jobs/analyze.md` (findings only, no graph artifacts) | 0–1 | no |
| `/codegraph spec [path]` | `jobs/spec.md` | 2 | no |
| `/codegraph verify` | `jobs/verify.md` | 3 | no |
| `/codegraph apply [slice\|all]` | `jobs/apply.md` | 4–5 | **yes, per approved slice** |
| `/codegraph fitness [path]` | `jobs/fitness.md` | writes layer-4 tests only | adds tests |

Unrecognised first token ⇒ treat the whole argument as a path and run the default route.
No arguments ⇒ default route on the repo root.

---

## The doctrine, in brief

Full version in `references/doctrine.md`. The short form:

> **Every conflict is an interface. Every interface has multiple implementations. Which one runs
> is decided by data, at the composition root — never by an `if` at the call site. Every
> implementation receives one immutable Context carrying the whole problem.**

1. **Conflict** — any point where more than one answer is possible. `if/elif/else` on a type or
   flag, a switch repeated in two files, `if x is None`, a boolean parameter, an env check, a
   `try/except` with a real alternative, two blocks differing in one operation.
2. **Port** — one interface per conflict, docstring states the conflict **as a question**,
   ≤3 methods, declared beside its caller (Separated Interface), not with its implementations.
3. **Resolvers** — one per answer, one per file, in a subfolder named for the port. Plus an
   `Absent`/Null resolver so the set is **total** — that is what deletes `else`.
4. **Selector** — the `if` moves once, into data: a registry map, a `handles(ctx)` chain, or a
   visitor. A residual `if` at the call site is a violation; a `match` in the registry is not.
5. **Context** — one frozen value object per conflict family, carrying every variable the problem
   needs *including ones nothing uses yet*. That is the headroom seam.
6. **Composition root** — one per deployable, the only place naming concrete resolvers.
   Constructor injection only. If a test touches the container, the root has leaked.
7. **Common utils** — pure, no I/O, zero project imports, a sink node in the graph.

**The layer rule:** layer *n* declares conflicts; layer *n+1* — a subfolder — resolves them.
Edges point down and inward. The folder tree therefore **is** the dependency graph, and the graph
is a testable predicate. Folders are question nodes, files are answer nodes, imports are edges.

**The promotion threshold matters as much as the doctrine.** Promote a conflict only when two
answers exist today, a second is named in a ticket, the branch crosses an I/O boundary, or the
same discriminant is switched on in ≥2 places. Otherwise record a `DEFERRED CONFLICT` and move
on. Over-application produces Lasagna Code and an interface farm — see `references/doctrine.md` §2.

---

## Hard limits

Machine-checked by `scripts/caps.sh`. Report every breach with `file:line` and the measured number.

| Limit | Warn | **Hard** | Resolution |
|---|---|---|---|
| File length | 200 | **250 lines** | split by responsibility; extract resolvers to a subfolder |
| Method length | 15 | **25 lines** | extract a *named* method, or promote the branch to a port |
| Nesting depth in a method | — | **1** | guard clauses, or extract the inner block to a named method |
| Loop body length | — | **8 lines** | extract the body: the loop shows repetition, the method shows per-item behaviour |
| `else` / `elif` | — | **0** outside a registry literal | registry, chain, or Null Object |
| Parameters | 3 | **4**, or 1 Context | introduce a Context |
| Methods per port | — | **3** | split the port (ISP) |
| Implementation hierarchy depth | — | **2** (port → resolver) | composition, not a third level |
| Module-graph cycles | — | **0** | invert the weakest edge behind a port |
| Public members per class | 5 | **7** | split by reason-to-change |
| Composition roots per deployable | — | **1** | merge the wiring |
| Ports without a contract suite | — | **0** | write the suite; add the registration test |
| Swallowed exceptions | — | **0** | log with traceback, or re-raise preserving the cause |

**Warn vs hard.** A warn breach is a **minor** finding, batched, never a slice of its own. A hard
breach is a **major** and must appear in the spec. Layer-4 fitness tests assert the **hard** column
only — a warn threshold that fails the build is a warn threshold nobody keeps.

Exempt from the `else` rule: a registry literal in the composition root, and an exhaustive match
over a sealed/ADT closed set where the compiler checks totality. Both are data, not control flow.

**Nesting is measured from the method body**, so `for` + `if` is depth 1 and legal; a third level is
not. Guard clauses that `return`/`raise` do not count as nesting — they remove it.

---

## Non-negotiables

1. **Read before ruling.** Never emit a finding from a filename or a grep hit alone. Open the range.
2. **The Iron Law of findings.** No finding without all seven fields of `specs/finding.md`. A
   finding without a consequence and a remedy is noise and is dropped.
3. **Headroom is not a defect.** "The current value is the loosest possible", "you collapsed X
   into one value", env-scoped names sharing a value, a mode knob with one mode today, a
   per-stage resource pointing at one target — these are deliberate seams. Record them as
   `DEFERRED CONFLICT`. Never simplify them away. When unsure whether a seam is intentional, ask.
4. **Measure, don't estimate.** Every number in a report came from a command that ran. A metric a
   tool could not produce is omitted and listed under `degraded`, never zeroed.
5. **The oracle rules.** Refinement is gated on the test suite, `caps.sh`, `graph.sh`, the type
   checker, and mutation score — never on self-assessment. No oracle for a dimension ⇒ report it
   once as `UNVERIFIED` and do not iterate on it. See `references/refine-loop.md` §1.
6. **Accept only if better.** Never take a revision that scores worse on the oracle. Return the
   best pass, not the last.
7. **Extract the interface before moving anything.** Always. Additive steps first. (*Extract
   Interface* is Feathers' dependency-breaking move, *WELC* ch.25 — it is **not** in Fowler's
   2nd-ed. catalog. Cite it correctly.)
8. **One slice, one commit, one revert.** Never mix a behaviour change with a refactoring.
9. **Characterization tests before touching untested code.** Pin current behaviour, including
   the bugs, then move it.
10. **Caps are tests, not habits.** The restructure is not done until `tests/fitness/` enforces
    every claim the spec made about the graph.
11. **Never rewrite a contract suite to make a resolver pass.** That inverts the oracle.
12. **Say what you did not do.** Every report ends with what it does not cover: languages
    degraded, directories skipped, dynamic dispatch not statically resolvable.
13. **A path must name its subject, its role, and its answer.** `payment/processors/
    stripe_payment_processor.py`, never `payment/processors/stripe.py`. The file name has to still
    make sense alone in an editor tab, an import line, a search result, and a stack trace. Banned
    as file or folder names: `utils` `helpers` `common` `misc` `base` `logic` `manager`.
    See `references/naming.md`.
14. **Every caught exception either logs a full traceback or re-raises with the cause attached.**
    A bare `except: pass`, a `catch (e) {}`, an ignored `err`, or a log line without the stack is a
    **blocker**. See `references/error-handling.md`.
15. **Never delete on suspicion.** Static absence of callers is not proof. Check the dynamic-usage
    safelist in `references/dead-code.md` first — entry points, reflection, plugin registries,
    config-driven dispatch, generated code, migrations. Unconfirmed ⇒ report as `suspicious`,
    do not remove.
16. **Abstraction must pay for itself.** An interface, folder, or registry ships only if it removes
    real duplication, isolates real variation, improves testability, protects a boundary, or kills
    a growing behaviour-selection branch. `ThingInterface` + `DefaultThing` with no second answer
    and no boundary is a **finding**, not an achievement.

---

## Fan-out contract

Heavy work runs in subagents so its tool output never enters this conversation.

- **One agent per analysis dimension, launched in parallel** in a single message:
  `graph` · `caps` · `cond` · `di` · `port` · `test` · `time` · `err` · `dead` · `name`.
- Every agent **writes its artifact to `.codegraph/`** and returns **≤25 lines**. Bulk never
  comes back as text.
- Findings are **claims** until an adversary confirms them. The adversary never sees the finder's
  reasoning. **1 CONFIRMED keeps a finding; 2 independent REFUTED drops it.**
- Bundled agents: `codegraph-cartographer` (graph), `codegraph-inspector` (one dimension),
  `codegraph-architect` (target tree), `codegraph-adversary` (attack), `codegraph-surgeon`
  (one slice). Use `general-purpose` with the job file inlined if the bundled agents are not
  installed.
- The final message to the user is the ≤25-line summary from `specs/graph-report.md` §3, plus
  one next action. Never paste a full report into the conversation.

---

## Scripts

Run them; do not read them. Both emit JSON on stdout.

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/caps.sh  --help
bash ${CLAUDE_SKILL_DIR}/scripts/graph.sh --help
```

`caps.sh` measures file lines, method lines, nesting depth, `else` count, and parameter counts.
`graph.sh` emits the module graph, cycles, and fan-in/out. Both degrade gracefully: they use
native tooling where present (`grimp`/`import-linter`, `dependency-cruiser`, `jdeps`,
`go list -deps`) and fall back to a ripgrep import scan otherwise, flagging the fidelity drop.

---

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
| `references/testing-hierarchy.md` | the 7 layers, doubles, LSP verification, mutation targets |
| `references/testing-contracts.md` | contract-suite code per language + registration-as-build-failure |
| `references/refactoring-moves.md` | safe slicing: seams, Branch by Abstraction, Parallel Change, Mikado |
| `references/language-idioms.md` | ports, registries, Contexts, roots, no-`else` idioms per language |
| `references/refine-loop.md` | the convergence loop, its stopping criteria, and why it is machine-gated |
| `specs/finding.md` | the finding contract — the Iron Law |
| `specs/graph-report.md` | the analyze output contract + the ≤25-line summary shape |
| `specs/restructure-spec.md` | the spec output contract — the phase-2 gate |

---

## Checklist before saying done

- [ ] The right job file was read, and only that one
- [ ] Every number in the output came from a command that ran
- [ ] Every finding has all seven fields and survived verification
- [ ] Headroom was recorded as `DEFERRED CONFLICT`, not reported as debt
- [ ] No file was edited before the approval block was checked
- [ ] Tests were green before and after every applied slice
- [ ] Every port in the result has an `Absent` resolver, a contract suite, and a registration test
- [ ] `tests/fitness/` enforces every graph claim the spec made
- [ ] The conversation got a ≤25-line summary and one next action — not a pasted report
- [ ] The report names what it does not cover
