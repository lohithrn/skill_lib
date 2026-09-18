# Graph tooling — the exact command per language, and the fallback when it is absent

Every command that produces an input `graph.sh` can consume, or that answers a question `graph.sh`
does not answer. Read `graph-metrics.md` for what the numbers mean and `arch-smells.md` for what
counts as a smell.

**Offline is a hard rule.** Naming a tool is allowed; *requiring* one is not. Every command below is
framed **use it if present, else fall back to the bundled script**. Nothing here installs a package,
resolves a registry, fetches a URL, contacts a license server, reads a credential, or generates a
key or a certificate. A tool that needs any of those is out of scope — say so and use the fallback.

**Presence check, every time:**

```sh
command -v TOOL >/dev/null 2>&1 || { echo "TOOL absent, using bundled scan"; }
```

For node tooling, `npx --no-install X` is the offline form: it runs `X` from `node_modules` if it is
already there and **fails instead of downloading** if it is not. Never plain `npx X`.

---

## 1. Read this before running anything

1. **Fidelity is part of the output.** Any fallback path must record what it could not see (§10).
   A graph without a fidelity note is not reviewable.
2. **The bundled scan is the floor, not the ceiling.** If a native resolver is present, its edges
   are more precise; say which produced the graph you are reporting.
3. **Never mix graphs.** Do not merge dependency-cruiser edges into a `graph.sh` run. Pick one
   producer per report, name it, and note the difference if you ran both.
4. **Package graph ≠ module graph.** `go mod graph`, `cargo tree`, `dotnet list package`,
   `npm ls` all describe *external dependencies*. None of them tells you anything about your own
   internal structure. Confusing the two is the most common wrong answer here.
5. **Vendor tools with licences** (NDepend, Structure101, Lattix, Arcan's commercial build) may be
   cited for their published rules — see `arch-smells.md` §8 — but must never be a required step.

---

## 2. The bundled fallback, and the file-listing lesson

```sh
bash skills/codegraph/scripts/graph.sh --root . --json > graph.json   # machine form
bash skills/codegraph/scripts/graph.sh --root . --text                # human form
bash skills/codegraph/scripts/graph.sh --root . --exclude 'vendor/**' --json
```

Pure stdlib, no network, no install. It walks the tree, parses imports per language, builds the
module graph, runs Tarjan, and emits the schema in `specs/graph-report.md`.

**How it enumerates files, and why the obvious version is wrong:**

```sh
git -C "$ROOT" ls-files -z --cached --others --exclude-standard
```

| Form | What it returns | Verdict |
|---|---|---|
| `git ls-files` | **tracked files only** | **wrong.** A repo with new, uncommitted source returns the committed set — often zero source files — and the graph comes back small, acyclic and "clean." This is a silent false negative, the worst failure mode a structure tool has |
| `git ls-files --others` | untracked only | wrong on its own |
| `git ls-files --cached --others --exclude-standard` | tracked **plus** untracked, with `.gitignore` still applied | **correct.** Sees work in progress without picking up `node_modules` or build output |
| `find . -type f` | everything | last resort only — `.gitignore` is not applied, so it drags in vendored trees. Must produce a fidelity note saying so |
| add `-z` | NUL-separated | required. Filenames legally contain spaces and newlines |

If the root is not a git repository, or git lists nothing under it, fall through to `find` **and
record that `.gitignore` was not applied**. `graph.sh` already does exactly this and writes the
reason into `degraded[]`.

---

## 3. Python

| Tool | Command | Produces |
|---|---|---|
| **grimp** | `python3 -c "import grimp,json; g=grimp.build_graph('mypkg'); print(json.dumps({m: sorted(g.find_modules_directly_imported_by(m)) for m in sorted(g.modules)}))" > deps.json` | true module graph, relative imports resolved |
| **grimp**, layer + cycle queries | `python3 -c "import grimp; g=grimp.build_graph('mypkg'); print(list(g.find_illegal_dependencies_for_layers(layers=('mypkg.web','mypkg.domain'))))"` | the illegal **routes** (heads, middle, tails), not a pass/fail. `g.nominate_cycle_breakers('mypkg')` returns an *approximate* minimum weighted feedback arc set — a suggestion, never a minimal cut (`graph-metrics.md` §3) |
| **import-linter** | `lint-imports --config .importlinter` · verbose: `lint-imports -v` | pass/fail against declared layer contracts |
| **pylint** | `pylint --output-format=json2 --disable=all --enable=cyclic-import mypkg` | one `R0401` per cycle, machine-readable (`json2` on recent pylint, `json` on older). The exit code is a **bitmask**, not a count: a cyclic-import breach is a refactor message, so `8` means "cycles found" and only `0` is clean |
| **pydeps** | `pydeps mypkg --show-deps --noshow --max-bacon 0 > deps.json` | JSON adjacency. Flag names drift between versions — run `pydeps --help` first. `-o out.svg` needs Graphviz |
| **bundled (default)** | `bash scripts/graph.sh --root . --json` | `stdlib ast` walk of `Import` / `ImportFrom`, relative levels resolved against the file's package |

**Fallback fidelity note:** the bundled scan resolves only what `ast` can see statically. It
deliberately **refuses single-component import tails**, so `import os.path` can never be mistaken
for a local `path.py`; the cost is that a legitimate flat-layout `import sibling` is left
unresolved and counted in `totals.unresolved_imports`. Report that count. Do not loosen the
resolver to make it smaller — see §9.

`import-linter` is a verifier, not a producer: it answers "did we break the declared layering," and
its five contract types are covered in `architecture.md`. Use it when a contract file already
exists; never author one as part of an analysis run.

---

## 4. TypeScript / JavaScript

| Tool | Command | Produces |
|---|---|---|
| **dependency-cruiser** | `npx --no-install depcruise --ts-config tsconfig.json --output-type json src > deps.json` | module graph with `tsconfig` `paths` aliases resolved |
| dependency-cruiser, validate | `npx --no-install depcruise --validate <config you ship> src` | rule violations, exit code non-zero on failure. **Never point `--validate` at the analysed repo's own `.dependency-cruiser.js`** — that file is JavaScript that node `require`s and RUNS, so it is arbitrary code execution from the tree you are reading. Use a config the skill or the fitness suite owns; in read-only analysis, skip this row entirely |
| dependency-cruiser, picture | `npx --no-install depcruise --output-type dot src \| dot -Tsvg > deps.svg` | needs Graphviz locally; skip if `command -v dot` fails |
| **madge** | `npx --no-install madge --json src > deps.json` · cycles only: `npx --no-install madge --circular --extensions ts,tsx src` | adjacency; `--circular` exits non-zero when cycles exist |
| **bundled** | `bash scripts/graph.sh --root . --json` | scans `import`/`export … from`/`require(...)` with literal specifiers |

**`--ts-config` alone still understates a TS graph.** dependency-cruiser's
`--ts-pre-compilation-deps` is **off by default** — checked in its own CLI option definition — and
without it every `import type` and interface-only import is missing from the graph, so a codebase
that leans on type-only imports comes back looking decoupled. Pass the flag, or record that
type-only edges were not collected.

**Fallback fidelity note:** the bundled scan does **not** read `tsconfig.json`, so `paths` aliases
(`@app/*`), `baseUrl`, and monorepo workspace links resolve as unknown rather than as edges. It also
cannot follow `require(variableName)` or `await import(`${dir}/x`)`. Both effects **understate**
coupling — the graph looks better than the code is, so never report a clean TS graph from the
fallback without the caveat. If `tsconfig.json` contains `paths` and dependency-cruiser is absent,
say the alias edges are missing and give the alias count.

---

## 5. Java / Kotlin

| Tool | Command | Produces |
|---|---|---|
| **jdeps** (ships with the JDK, nothing to install) | `jdeps -verbose:class -R -cp build/libs/app.jar build/libs/app.jar` | class-level edges, recursive |
| jdeps, package summary | `jdeps -summary build/classes/java/main` | package → package edges |
| jdeps, DOT out | `jdeps -dotoutput out/ -verbose:package build/libs/app.jar` | `.dot` per archive, feed to Graphviz |
| jdeps, keep intra-package | add `-filter:none` | otherwise same-package edges are dropped and cohesion looks perfect |
| **ArchUnit** (a test, not a CLI) | `gradle --offline test --tests '*ArchTest*'` · `mvn -o test -Dtest=ArchitectureTest` | layer/cycle rule verification, and **only** that: ArchUnit is assertion-only, exports no JSON, DOT or GraphML, and its PlantUML support is an *input* you hand-write — never plan to obtain a graph from it. `--offline` / `-o` are mandatory here. Prefer the SYSTEM `gradle` (`command -v gradle`) over `./gradlew`: the wrapper downloads the Gradle distribution named in the analysed repo's `gradle-wrapper.properties` **before** `--offline` is ever parsed, and `--offline` suppresses only *dependency* resolution. Running either also executes the target's build scripts, so this row belongs to apply/verify, never to read-only analysis |
| **bundled** | `bash scripts/graph.sh --root . --json` | `package` + `import` declarations from source |

**Fallback fidelity note:** the bundled scan reads source, not bytecode, so it misses everything the
compiler synthesises — lambdas, `record` accessors, generated builders — and it cannot see edges
created only by fully-qualified names used without an `import`. `import x.y.*` gives a package edge
with no class-level detail. jdeps needs **compiled output**; if `build/` or `target/` is absent and
you may not build, say "bytecode unavailable, source scan only."

Kotlin: jdeps works on the compiled classes exactly as for Java. On source only, expect to miss
`typealias`, extension functions resolved through implicit receivers, and `internal` visibility.

---

## 6. Go

| Tool | Command | Produces |
|---|---|---|
| **go list** (toolchain) | `GOFLAGS=-mod=readonly GOPROXY=off GOTOOLCHAIN=local GOWORK=off go list -deps -json ./... > deps.json` | full package metadata including `Imports`, `Deps`, `TestImports` |
| go list, terse edges | `GOFLAGS=-mod=readonly GOPROXY=off GOTOOLCHAIN=local GOWORK=off go list -f '{{.ImportPath}} {{join .Imports " "}}' ./...` | one line per package, ready for a two-column parse |
| offline safety | prefix with `GOFLAGS=-mod=readonly GOPROXY=off GOTOOLCHAIN=local GOWORK=off` | fails loudly instead of reaching a proxy. **Not `-mod=mod`** — that is the mode that lets the go command rewrite `go.mod` and FETCH the missing modules, which is the opposite of offline. `GOTOOLCHAIN=local` matters on an untrusted repo: a `toolchain` line in its `go.mod` otherwise makes go download and execute a different toolchain |
| **depguard** (via golangci-lint) | `golangci-lint run --disable-all -E depguard ./...` | violations of declared allow/deny import lists |
| **bundled** | `bash scripts/graph.sh --root . --json` | `import` blocks per file, packages as nodes |

**Go cannot have package import cycles** — the compiler rejects them, so an empty `cycles[]` on a
pure Go repo is the language working, not evidence of good design. Look instead at oversized
packages, `internal/` boundary crossings, and interface placement. `go mod graph` is the *module*
graph and answers a different question (§1.4).

**Fallback fidelity note:** the bundled scan treats a directory as a package and does not evaluate
build tags, so `//go:build` variants collapse into one node and `_test.go` imports may be counted
with production imports. Say which.

---

## 7. C#, Rust, and everything else

| Language | If present | Fallback and what it loses |
|---|---|---|
| **C#** | Roslyn-based analyzers already wired into the build: `dotnet build --no-restore` and read the analyzer output. NDepend has a console runner but is licensed — cite its rules (`arch-smells.md` §8), never require it | `graph.sh` scans `namespace` and `using` directives, giving namespace-level edges. Loses: implicit and `global using`, `partial class` members split across files, source generators (nothing exists on disk to scan), and everything resolved through the project's assembly references. `dotnet list package` is the external package tree, not your structure |
| **Rust** | `cargo modules --help` first (subcommand names have changed across releases), then the graph subcommand it reports, e.g. `cargo modules dependencies --package foo`. `cargo tree --offline` for the crate tree only | `graph.sh` scans `mod` declarations and `use crate::` / `super::` / `self::` paths. Loses: `#[cfg]`-gated modules, macro-generated items, `pub use` re-export chains (an edge to a facade instead of to the real definition) |
| **anything not parsed** | — | the file counts toward `totals.files` and `totals.loc` but produces no node. `languages` in the JSON lists what was recognised; diff it against the file extensions present and report the gap |

---

## 8. Git history — co-change, churn, hotspots

All local. No remote is contacted; nothing here needs a credential.

```sh
# 0. is this even a repo, and is the history complete?
git -C "$ROOT" rev-parse --show-toplevel
git -C "$ROOT" rev-parse --is-shallow-repository      # true => history truncated, note it

# 1. co-change pairs: commit boundary, then one line per file touched
git -C "$ROOT" log --no-merges -M --since='12 months ago' \
    --format='C%H' --numstat -- '*.py'

# 2. revisions per file, most-changed first
git -C "$ROOT" log --no-merges --since='12 months ago' --format='' --name-only \
  | grep -v '^$' | sort | uniq -c | sort -rn | head -20

# 3. churn: added+deleted lines per file over 90 days
git -C "$ROOT" log --no-merges --since='90 days ago' --format='' --numstat \
  | awk '$1 != "-" { c[$3] += $1 + $2 } END { for (f in c) print c[f], f }' \
  | sort -rn | head -20

# 4. ownership: who touches this file
git -C "$ROOT" shortlog -sn --no-merges -- path/to/file
```

**Parsing rules for `--numstat`:**

| Situation | What appears | Handling |
|---|---|---|
| commit boundary | the `C<sha>` line from `--format` | start a new file set; a set of size 1 contributes no pair |
| text change | `12\t3\tpath` | added, deleted, path |
| binary change | `-\t-\tpath` | counts as a revision, contributes **0** churn |
| rename (with `-M`) | `0\t0\told => new` or `a/{x => y}/f` | normalise to the new path before pairing, or the same file appears as two nodes |
| merge commit | — | excluded by `--no-merges`; including them double-counts every change |

**Metric shapes** (the *thresholds* are not restated here — every co-change, churn and hotspot
cutoff lives in `arch-smells.md` §5 and must be cited from there):

- **temporal coupling degree** `= 100 × shared_revisions / mean(revisions_a, revisions_b)`, the
  code-maat form. Requires a minimum revision count per file or two-commit files read as 100%.
- **hotspot** `= change frequency × complexity` (Tornhill). Offline, use revisions from command 2
  and a complexity proxy from `nodes[].metrics` or mean leading-whitespace depth. Say which proxy.
- **minor contributor** = a contributor below a small share of a file's commits (Bird et al.). Use
  the share stated in `arch-smells.md`; do not pick your own.

**History caveats that must reach the fidelity note:** shallow clone (`--is-shallow-repository`
true) truncates every count; squash-merge workflows collapse a whole branch into one commit so
co-change is systematically understated; a bulk reformat or a `mv` of a whole tree creates one
commit that pairs hundreds of unrelated files — check the top revision-count commits for a
suspiciously large file set before trusting any pair.

**Computed by `graph.sh`:** none of it. The history keys in `specs/graph-report.md`
(`churn_90d`, `hotspot`) are reserved and not emitted; run the commands above or state that history
was not read.

---

## 9. What each tool cannot see

Static resolution has a fixed set of blind spots. All of them make a graph look **better** than the
code is, so each one is a reason to soften a clean verdict, never to harden a dirty one.

| Blind spot | Example | Effect |
|---|---|---|
| **`sys.path` mutation + bare imports** | this skill's own `scripts/lib/*.py`: `sys.path.insert(...)` followed by `import graph_metrics`. The resolver deliberately refuses single-component tails (so `import os.path` never binds a local `path.py`), so these real edges are left unresolved and the skill **cannot fully analyse itself**. Decision on record: the resolver stays strict. Surfaced through `totals.unresolved_imports` and `fidelity` | missing internal edges; a real cycle can hide |
| **reflection** | `getattr(mod, name)`, `importlib.import_module(cfg["backend"])`, Java `Class.forName`, C# `Activator.CreateInstance` | edge exists only at runtime |
| **dynamic imports** | `require(pluginName)`, `await import(\`./locales/${lang}\`)` | whole directories invisible |
| **DI containers** | Spring component scan, `services.AddScoped<IFoo, Foo>()`, a Python container binding a protocol to an implementation | the concrete class shows **zero** fan-in and looks dead. Cross-check `ports[]` and `di-patterns.md` before calling anything unused |
| **service locators** | `Registry.get("mailer")` | coupling routed through a string key; the graph shows an edge to the registry, not to the target |
| **generated code** | protobuf stubs, OpenAPI clients, ORM models, source generators | either absent from the tree (nothing to parse) or present but with no author, inflating `loc` and creating fan-in nobody owns |
| **config-driven wiring** | entry points in `pyproject.toml`, Django `INSTALLED_APPS`, plugin manifests, route tables | the file is reachable only through data |
| **conditional compilation** | `#[cfg]`, `//go:build`, `#if DEBUG`, `partial class` | variants collapse into one node or vanish |

**Rule:** when a repo shows any of these, say "N edges are unresolved and the following mechanisms
are in use," list them, and downgrade the confidence of every *absence* claim — dead code, zero
fan-in, no cycles. Presence claims stay valid.

---

## 10. The fidelity note a fallback must record

Six fields. Missing any one makes the run unreviewable.

| Field | Example |
|---|---|
| **producer** | `bundled graph.sh AST scan` or `dependency-cruiser 16.x` |
| **why the fallback** | `depcruise absent (npx --no-install failed)` |
| **file enumeration** | `git ls-files --cached --others --exclude-standard` or `find (.gitignore NOT applied)` |
| **unresolved** | `totals.unresolved_imports = 34`, with the reason (single-component tails, missing tsconfig paths, …) |
| **caps hit** | contents of `degraded[]`, verbatim — betweenness skipped above 1200 nodes, closure above 3000 |
| **history depth** | `git log --since='12 months ago'`, shallow: no/yes; or `history not read` |

---

## 11. Other graphs of the same repo — what each answers and what it costs

The module graph is one projection of the code, not the code. Naming the others matters because
almost every question people bring to a "code graph" is answered at the cheapest level, and moving
up a level is a decision with a bill, not an upgrade.

| Graph | Nodes → edges | Answers | Cost, offline |
|---|---|---|---|
| **module / import** (this build) | files, packages → `imports` | cycles, layering, god packages, unstable dependencies | minutes; an AST-lite scan is enough |
| **call** | functions → `calls` | dead code, blast radius *inside* a module, broker functions | needs name resolution, and is unsound under dynamic dispatch (§9) |
| **inheritance / type** | classes → `extends`, `implements` | deep, wide or cyclic hierarchies; LSP suspects | cheap from the same AST; not built here |
| **PDG** (program dependence) | statements → data + control dependence | taint paths, and coupling through globals that no import reveals | a CFG plus reaching definitions per function — out of reach for a stdlib scan |
| **code property graph** | AST nodes → AST ∪ CFG ∪ PDG joined on statement nodes | "does an argument reaching this sink depend on a check that does not dominate it", as one traversal | Joern, one language front-end per language — name it in `degraded`, never run it |
| **ownership / co-change** | files, authors → `authored`, `changed-with` | knowledge silos, and coupling with no structural edge at all | `git log` only (§8) — the cheapest graph here and the one people skip |

**CPG** is Yamaguchi, Golde, Arp & Rieck, "Modeling and Discovering Vulnerabilities with Code
Property Graphs," IEEE S&P 2014; the contribution is the *join*, not the parsing. If a repo already
has Joern on the box, its export representations are `Ast,Cfg,Ddg,Cdg,Pdg,Cpg14,Cpg,All` and its
formats `Dot,Neo4jCsv,Graphml,Graphson` — enough to say in `degraded` that a better tool exists and
what it would have produced. This skill installs nothing.

**The call-graph precision ladder.** Pick a rung on purpose, because each costs more than the last
and the top rungs need whole-program closure: naive name matching → **CHA** (class hierarchy
analysis — every subtype of the declared receiver type) → **RTA** (rapid type analysis — CHA minus
types never instantiated anywhere) → **VTA** (variable type analysis) → points-to. A CHA answer and
a points-to answer disagree by design, so the rung is part of the result. Go's `callgraph` tool, when
it is already on `PATH`, exposes `-algo=static|cha|rta`; its `pta` mode was removed, so an old
command line fails rather than silently degrading.

**Budget heuristic, offered as a heuristic:** the module graph answers roughly 90% of architecture
questions at about 1% of the cost of a sound call graph. Those two figures are unattributed — no
study is being cited — and they are here to set expectations, not to be quoted in a finding. Build a
call graph when the question is blast radius *inside* a module; for cycles, layering and hubs the
module graph is not an approximation of the answer, it is the answer.

---

## 12. Graph algorithms already on the box, and the caps that truncate a picture

Graphviz is not only a layout engine — its CLI ships graph algorithms that answer questions
`graph.sh` does not. All local, nothing installed, no network. Guard each one (`command -v tred`) and
skip the whole section when Graphviz is absent.

| Command | What it gives you |
|---|---|
| `tred graph.dot > reduced.dot` | transitive reduction — the edges a reader actually needs to see |
| `tred -r graph.dot 2>&1 >/dev/null` | the **removed** edges, on stderr: that list *is* your redundant-dependency report. On a cyclic graph it also prints `warning: … has cycle(s), transitive reduction not unique` — heed it, the removed set is then one valid answer of several |
| `sccmap -s graph.dot` | one line, `N nodes, M edges, K strong components` — a cycle count without writing a Tarjan |
| `acyclic -n graph.dot` | no output; **exit 1 iff the graph has a cycle**. The cheapest gate here |
| `ccomps -x graph.dot` | splits into weakly connected components, one graph each — finds the orphaned island |
| `gvpr -f prog.gvpr graph.dot` | awk for graphs: filter or rewrite before layout |
| `unflatten -l3 graph.dot` | tames a wide fan-out before `dot` lays it out |

Behaviour above was checked against the Graphviz present in this environment. Engine choice: `dot`
for dependency graphs, because its layers **are** a levelization; `sfdp` or `neato` past roughly a
thousand nodes; `circo` when the cycle is the point.

**Render caps truncate silently, which is worse than an ugly picture.** Mermaid's documented defaults
are `maxTextSize` **50,000** characters and `maxEdges` **500**, and both sit in its `secure` array, so
a document cannot raise them through front-matter or a directive — only a host calling
`mermaid.initialize` can. Doxygen's `DOT_GRAPH_MAX_NODES` defaults to **50** and clips beyond it.
Working line: Mermaid for ≤ 60 nodes and ≤ 150 edges inside a document, DOT or SVG for anything real,
and when a graph is too large to draw, emit `graph.sh --text` instead. A truncated diagram with no
note that it was truncated is a false clean report.
