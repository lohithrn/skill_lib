# Dead code — delete it, but prove it first

Version control preserves history. **The working tree should preserve active truth**, not a museum.
Dead code costs on every read, every rename, every dependency bump, and every graph measurement —
an unused module still contributes edges, still inflates fan-out, and still hides in a cycle.

And: **static absence of callers is not proof of deadness.** Every language here has at least four
ways to reach code without a resolvable reference. This file is the protocol that keeps deletion
from becoming an outage.

---

## 1. What is deletable

| Kind | Signal | Confidence |
|---|---|---|
| unused import | linter (`F401`, `no-unused-vars`, `goimports`) | **certain** — delete without ceremony |
| unused local variable | linter (`F841`, `ineffassign`) | **certain** |
| unreachable statement | after `return`/`raise`/`break`; compiler or linter | **certain** |
| commented-out code | a block of syntax inside comments | **certain** — git has it |
| a branch whose condition is a constant | `if False`, a flag never set, a dead enum case | high |
| a private method with no in-file caller | scoped search is complete for truly private members | high |
| a duplicate implementation neither wired nor tested | not in the composition root, no test imports it | high |
| an orphan resolver | implements a port, absent from every registry | high — cross-check `port.json` |
| a public method/class with no caller | repo-wide search | **low — go to §2** |
| a whole module with fan-in 0 | `graph.json` | **low — go to §2** |
| speculative code for a future feature | no caller, no ticket | judgement — see §4 |

**A `# TODO` is not dead code and not debt.** It is a deferred-conflict marker. Record it, never
delete it (`specs/finding.md`).

---

## 2. The dynamic-usage safelist — check every line before deleting

Static analysis cannot see any of these. Search for the **name as a string**, not as an identifier.

**Entry points and manifests** — `pyproject.toml [project.scripts]`, `setup.py entry_points`,
`package.json` `bin`/`main`/`exports`/`scripts`, `Dockerfile` `CMD`/`ENTRYPOINT`, `Procfile`,
systemd units, Makefiles, CI workflow files, `main` functions, Lambda/Cloud Function handler
strings, cron definitions, k8s manifests.

**Reflection and dynamic import** — `getattr` · `importlib.import_module` · `__subclasses__()` ·
`globals()[name]` · `eval`/`exec` · `pickle` (unpickling instantiates by qualified name) ·
`require(variable)` · `import()` · `Class.forName` · Java/Kotlin annotation processors and
`ServiceLoader` (`META-INF/services`) · Spring component scanning · Go `reflect` and blank imports
`import _ "pkg"` (registers a driver purely for its `init()`).

**Framework and decorator registration** — route decorators, event/signal handlers, ORM model
discovery, Django/Alembic **migrations** (never delete, even superseded ones), Celery tasks, pytest
fixtures and `conftest.py`, `__init_subclass__`, DI container auto-registration, serializer
registries, admin registrations, feature-flag-gated paths.

**Config-driven dispatch** — a class path or handler name in YAML/JSON/TOML/env, a plugin
directory scanned at startup, a database row naming a strategy, a `settings.py` string reference.

**Language-specific traps** —
*Python:* `__all__`, `__getattr__` at module level, `TYPE_CHECKING` imports needed by string
annotations, Protocol/ABC conformance without an explicit base, doctests.
*TS/JS:* barrel `index.ts` re-exports, string-keyed dynamic access, JSX components referenced only
in templates, `sideEffects: false` interaction with polyfills, type-only usage that erases at
runtime, module-level side effects that matter even when nothing is imported.
*Java/Kotlin:* anything reflective, JNI, `@Keep`/ProGuard rules, JPA no-arg constructors, JSON
deserialization constructors, `equals`/`hashCode`/`toString` overrides.
*Go:* `init()` functions, blank imports, interface satisfaction (implicit — an "unused" method may
be the only reason a type satisfies a port), build tags (`//go:build`) hiding whole files from your
search, `cgo`, generated code.

**Outside the repo entirely** — a published library's public API, another service importing this
one, a notebook, an ops runbook, a dashboard query, a log-based alert, a customer integration.
For a library, **the public API is the contract**; unused-in-repo is expected, not dead.

---

## 3. The deletion protocol

1. **Establish the search surface.** Whole repo, not just `src/` — include config, templates, CI,
   infra, docs, and every non-code file type. `git grep -n '<name>'` on the *string*, then on the
   identifier.
2. **Walk §2** for the specific language and framework. Record which checks you ran; a deletion
   whose evidence is not written down is not reviewable.
3. **Prefer the tool** over grep: `vulture` (with a whitelist file), `deadcode`/`unimport`,
   `ts-prune` / `knip` / `ts-morph`, `depcheck` for packages, IDE "find usages", `deadcode` and
   `staticcheck U1000` for Go, `unused-code` inspections for Java. All of them have known false
   positives on §2 — the tool narrows the list, the protocol clears it.
4. **Runtime evidence beats static evidence** where it exists: coverage from the test suite plus
   coverage from production/staging (`coverage.py` in prod-lite, `--cover` builds,
   `go test -coverprofile`), APM traces, or a temporary log line at the top of the function shipped
   for one release cycle. For anything genuinely risky, this step is the answer.
5. **Deprecate before deleting** when the answer is still uncertain and the cost of being wrong is
   high: log a warning on entry, ship, wait one release, then delete when the log stays silent.
6. **Delete in its own commit**, listing the evidence in the message. Never bundled with a
   refactor — a reviewer must be able to revert the deletion alone.
7. **Re-run the graph.** Deleting a module changes fan-in/fan-out and may resolve or expose a cycle.
   Record the delta; that is the payoff being claimed.

**Unconfirmed ⇒ do not delete.** Report it as `SEVERITY minor`, with the symptom "no static caller
found; dynamic usage not ruled out" and the remedy "confirm with <the specific check that would
settle it>". A deletion the spec cannot justify is a bug, not a cleanup — and it is far more
expensive than the code it removes.

---

## 4. Speculative code, and where the doctrine differs from ordinary YAGNI

This is the one place the general rule "delete unused code" collides with the user's headroom rule,
and the distinction is precise:

| Not dead — leave it | Dead — delete it |
|---|---|
| an **unused field on a Context** that the spec documented as headroom | an unused field with no port reading it and no note explaining it |
| a **`BUILD_MODE`-style knob with one mode today** | a branch on a flag that no config or env can ever set |
| **env-scoped names sharing one value** | a duplicated function kept "in case we go back" |
| a **port with one resolver at an I/O boundary** — justified by testability | a `ThingInterface`/`DefaultThing` pair with no boundary and no second answer |
| an **`Absent`/Null resolver** never hit in practice — it is what makes the set total | an orphan resolver in no registry, and not the Absent one |
| a **documented deferred conflict** | commented-out code with a date in it |

The operative difference is **an intentional seam versus an abandoned attempt.** A seam is named,
documented, and reachable through the design. An abandoned attempt is unreferenced and unexplained.
When the two are indistinguishable from the code alone, **ask** — do not delete, and do not report
it as debt.

---

## 5. Dead branches in dispatch tables

The specific case where dead code and the doctrine meet, and the one part of parser/lexer cleanup
that generalises to any codebase.

Once a conflict is promoted, the registry becomes the inventory of live answers — which makes
deadness *measurable* for the first time:

- **A resolver in no registry** is either dead or an unregistered bug. The registration test tells
  you which: if it fails, the resolver was meant to be wired; if the resolver is genuinely obsolete,
  delete the file and its contract-suite subclass together.
- **A registry key no discriminant can produce** is dead. Enumerate the discriminant's domain — the
  enum, the sealed set, the DB column's distinct values — and diff it against the keys.
- **A token type, event name, command name, status, or format with no producer** is dead: nothing
  emits it, so nothing dispatches on it. Search producers, not consumers.
- **Duplicated parse/dispatch paths** — an old chain still present beside its registry replacement
  — are the residue of an incomplete migration. The spec's `Deletes:` line exists to prevent
  exactly this; if you find one, the previous slice was never finished.
- **Keep the `Absent`/default entry** always, even if unreachable today. It is what makes the set
  total and deletes the `else`; removing it reintroduces the branch.

Separate token/AST models from tokenizer, parser, and interpreter responsibilities when the logic is
still live (`architecture.md`). When it is not live, delete it whole — a half-removed grammar is
worse than either state.

---

## 6. Detection — what the `dead` dimension measures

| ID | Rule | Severity |
|---|---|---|
| D1 | unused import / variable / unreachable statement | minor, batched per file |
| D2 | commented-out code block ≥3 lines | minor |
| D3 | orphan resolver: implements a port, in no registry | **major** — bug or dead, and the registration test decides |
| D4 | registry key no discriminant can produce | major |
| D5 | module with fan-in 0 that is not an entry point | minor **and `suspicious`** until §2 is walked |
| D6 | duplicate implementation, unwired and untested | major |
| D7 | branch on a flag nothing can set | major |
| D8 | `*_old`, `*_v2`, `*_copy`, `*.bak` files | major — cross-check `naming.md` N8 |
| D9 | old dispatch chain still present beside its registry replacement | **blocker** — two sites will diverge silently |
| D10 | a dependency in the manifest that nothing imports | minor |

Every finding in this dimension carries an extra mandatory line beyond the seven fields:

```
EVIDENCE     searched: repo-wide string + identifier · config/templates/CI · §2 checks run:
             entry points, reflection, framework registration, config dispatch · coverage: 0 hits
             in 412 tests · verdict: safe to delete | suspicious
```

**A `dead` finding without an EVIDENCE line is dropped.** No exceptions — this is the dimension
where a wrong finding causes an outage rather than a bad review.
