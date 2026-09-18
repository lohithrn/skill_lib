# The seven-layer test hierarchy

Independent units first, then layers composed into a hierarchy where **a test at layer *n* may
not depend on any artifact, fixture, harness, environment, or double belonging to layer *n+1* or
above.** That rule is itself enforced at layer 4.

Layers 2 and 4 are the load-bearing additions. Neither appears in the published pyramid,
trophy, or honeycomb models, and both are what make a port-and-resolver codebase trustworthy.

---

## 0. Testability is a consequence of the composition root

A **seam** is a place where behaviour can be changed without editing in place; DI is how you
introduce one. Because nothing is composed except at the composition root, every class is
trivially constructible in a test with whatever collaborators the test chooses.

**The corollary is a blocker-severity rule:** if a test must reach into a DI container to build
its subject, the composition root has leaked and the unit is no longer independently testable.

Two supporting patterns:

- **Humble Object** (Meszaros) — "extract the logic into a separate easy-to-test component that
  is decoupled from its environment." What remains is "a very thin adapter layer that contains
  very little code," so thin that not testing it is a defensible choice. Variants: **Humble
  Dialog** (UI), **Humble Executable** (threads, processes, servers). This is how "untestable"
  becomes a design choice rather than a fact.
- **Ports & Adapters** (Cockburn) — "Create your application to work without either a UI or a
  database," so it "can equally be driven by users, programs, automated test or batch scripts."
  Ports come in two flavours: **primary/driving** and **secondary/driven**. His documented
  development sequence — the **sandwich** — is: test harness + in-memory DB → UI + in-memory DB
  → scripts + real DB → real users + real DB.
  **Sandwich rule: a component test drives one primary port and substitutes every secondary
  port. Nothing inside the hexagon is doubled.**
- **Nullables** (James Shore, *Testing Without Mocks*) — a `createNull()` factory returning an
  instance that "disables all external communication, but behaves normally in every other
  respect," plus **Embedded Stub** (stub the third-party library, not your own code), **Output
  Tracking**, **Narrow Integration Tests**, and **Paranoic Telemetry**. Worth adopting when you
  want sociable tests without a mocking framework; the cost is that doubles live in production
  code. Not the default here, but a legitimate alternative for a port with many resolvers.

---

## 1. Test doubles — the taxonomy, used correctly

| Double | Definition (Meszaros/Fowler) | Correct use here |
|---|---|---|
| **Dummy** | "objects are passed around but never actually used" | fill a Context field a resolver ignores |
| **Stub** | "provide canned answers to calls made during the test" | control an *indirect input*; force an error path |
| **Spy** | "stubs that also record some information based on how they were called" | observe *indirect outputs* with assertions in the test body |
| **Mock** | "pre-programmed with expectations which form a specification of the calls they are expected to receive" | only when call **count or order** is the requirement |
| **Fake** | "working implementations, but usually take some shortcut which makes them not suitable for production" | ★ the default replacement for a secondary port |

Only mocks do behaviour verification; the rest support state verification. A Spy does not fail
at the first deviation the way a Mock does. A Fake is not a control point — it just keeps
interactions self-consistent.

### Rules, with their sources

- **"Only mock types you own."** Freeman/Mackinnon/Pryce/Walnes, *Mock Roles, not Objects*
  (OOPSLA 2004), §4.1: "Programmers should not write mocks for fixed types, such as those
  defined by the runtime or external libraries. Instead they should write thin wrappers to
  implement the application abstractions in terms of the underlying infrastructure." Those thin
  wrappers are exactly this doctrine's adapters.
- Same paper, §4.5 **"Don't use mocks to test boundary objects"**; §4.7 **"Only mock your
  immediate neighbours"**; §5.4 — **"Complex mock setup for a test is actually a hint that
  there is a missing object in the design."** Treat elaborate mock setup as a **conflict
  detector**: it is telling you a port is missing.
- **Prefer the real implementation.** Use a real collaborator if it is fast, deterministic, and
  has simple dependencies. The all-mocks style does not scale, and stubbing leaks
  implementation details into tests, producing **change-detector tests**.
- **Never assert interactions with a stub** — that is overspecification. Verify only
  *state-changing* outbound calls (`send`, `write`, `publish`), never queries (`get`, `find`).
- **The managed/unmanaged rule** (Khorikov) is the cleanest decision procedure:
  *managed* dependency = out-of-process but fully under your control (your own database) → use
  the real thing; *unmanaged* = SMTP, message bus, third-party API → double it, because "the use
  of mocks cements the communication pattern," which is what backward compatibility requires.
  Rationale: "intra-system communications are implementation details; inter-system
  communications are not."
- **London vs Detroit, honestly.** Mockist tests localise failures better and drive interface
  discovery outside-in, but "mockist tests are... more coupled to the implementation of a
  method," and that coupling "interferes with refactoring." Classicist tests double as
  mini-integration tests and catch interaction errors mockist tests miss, at the cost of one bug
  reddening many tests. **Structure-insensitivity is the property mockist tests trade away** —
  and structure is exactly what this skill changes, so default classicist.

### Dependency categories — classify before choosing a double

§1 says *what* the doubles are. This says *which one this dependency gets*, which is the question that
actually comes up while designing a port. Classify every dependency of a module before deciding how it
is tested across its seam; the category, not taste, picks the double.

| # | Category | What it is | Test strategy across the seam | Does it need a port? |
|---|---|---|---|---|
| 1 | **In-process** | pure computation, in-memory state, no I/O | merge the modules and test through the new interface directly. No double at all | **no** — a port here is pure indirection |
| 2 | **Local-substitutable** | has a real local stand-in that runs in the suite: SQLite/PGLite for Postgres, an in-memory filesystem, a fake clock, moto/localstack | run the stand-in in the test suite and assert through the interface | **internal seam only** — not at the module's external interface |
| 3 | **Remote but owned** | your own service across a network: a sibling microservice, an internal API, a queue you publish to | define a **port** at the seam; the logic stays in one deep module, the transport is the adapter. In-memory adapter in tests, HTTP/gRPC/queue adapter in production | **yes** — the archetypal Ports & Adapters case |
| 4 | **True external** | a third party you do not control: Stripe, Twilio, Cognito, an LLM endpoint | inject it as a port; tests get a mock or a recorded-response adapter. Assert the request you send, not their behaviour | **yes**, always |

Two consequences worth stating, because both are commonly got wrong in the other direction:

- **Category 1 is the most common mistake.** Two pure modules with a Protocol between them is a
  shallow-module finding, not architecture. The doctrine's promotion threshold and the deletion test
  (`doctrine.md` §2) both refuse it; the category is a third way to see the same thing.
- **Category 3 is why "one deep module" and "deployed across a network" are compatible.** A service
  boundary is a deployment fact, not a design one. The logic can still live in one module with the
  transport injected — and if it does, the same contract suite runs in-process in milliseconds.

For categories 3 and 4 the port has **two** adapters from day one — production and test — so it never
trips the one-resolver brake. That is the honest reason a single-resolver port at an I/O boundary is
listed as *not a finding* throughout this skill: the double **is** the second adapter.

Source: the dependency-category split is from the deepening vocabulary in Pocock,
`skills/engineering/codebase-design` (`DEEPENING.md`); the doubles it selects are Meszaros' (§1).

---

## 2. The layers

| # | Layer | Scope | Doubles allowed | Budget | A failure means |
|---|---|---|---|---|---|
| 0 | **Static** | whole repo, no execution: types, lint, caps, `else` count | n/a | <30 s incremental | a banned construct entered, or a hard limit broke |
| 1 | **Unit** | one behaviour inside the hexagon | ports only; real value objects and real fast in-hexagon collaborators are **mandatory** | <100 ms each, suite <60 s | a domain rule is wrong — fix the code, not the test |
| 2 | **Contract** | one port × **every** resolver, one shared suite | none for the subject; each resolver runs for real, in memory where possible | <200 ms per resolver per case | a resolver is **not substitutable** (LSP violation) or a fake has drifted |
| 3 | **Component** | one hexagon end-to-end via one primary port | every secondary port substituted with a **contract-verified** fake; nothing inside the hexagon doubled | seconds each, suite <5 min | a use case is mis-wired or an application policy is wrong |
| 4 | **Fitness** | the dependency graph itself, plus the test-layering rule | n/a, no runtime | <60 s | structural erosion: a forbidden edge, a cycle, an unregistered resolver, a test reaching upward |
| 5 | **Integration** | one real adapter ↔ one real external system; provider contract verification | none for the subject; other collaborators still doubled ("narrow") | <5 min, containerised | serialisation, driver usage, or a consumer contract is broken |
| 6 | **E2E** | deployed system, critical journeys only | as few as possible | 15 min+, not in the inner loop | wiring/config/deploy is broken **and** a lower-layer test is missing |

**Sizes, enforced not annotated** (Google's small/medium/large): *small* runs in a single
process, no sleeping, no I/O, no blocking calls, ≤60 s; *medium* may span processes and threads
but reaches nothing beyond `localhost`, ≤300 s; *large* is multi-machine, ≤900 s+. Size is about
**resources**; scope is about **code paths**. A size annotation nobody polices is a comment.

**Ordering:** 0→2 on every save · 3→4 on every commit · 5 on every push · 6 per candidate build.

**Mix target:** roughly 80% narrow / 15% medium / 5% broad by test count. Named antipatterns:
the **ice cream cone** (mostly E2E) and the **hourglass** (many unit + many E2E, nothing between).

**Where the tests live:** all **7** layers live in one top-level `tests/` tree, one subdirectory
per layer, and **none of them under `src/`**. `src/` holds only what executes in production and
what the deploy needs; `tests/` holds every test, fixture, stub, recorded response and QE harness.
A `test_*` file beside the module it tests gets packaged and imported, which puts a double one
import away from a production path and hands you a green suite on a broken artifact. It also
corrupts every measurement in this skill: the test's imports become edges, so a module used only
by its own test reads as live. `references/doctrine.md` §9, consequence 6, is the same rule from
the graph's side.

---

## 3. Layer 2 in detail — why it exists

An interface is not a contract until there is **exactly one executable suite parameterised over
its implementations**, and **adding a resolver without registering it in that suite is a build
failure.** That is LSP enforced mechanically instead of asserted in review.

The rule for fakes: **a fake must have its own tests.** Write tests against the port and run
them against both the real resolver and the fake — that is what "contract test" means here.
Otherwise **fidelity** decays as the real implementation evolves. The team that owns the real
resolver owns its fake.

What layer 2 asserts, for every resolver identically:

- round-trip and idempotence properties
- ordering guarantees the port promises
- **error taxonomy** — the same violation raises the same error type from every resolver
- boundary inputs: empty, single, maximum, unicode, negative, zero, absent
- the Design-by-Contract algebra (below)
- fake-vs-real fidelity, where a fake exists

Concrete idioms per language: see `testing-contracts.md`.

### Not the same thing as consumer-driven contract testing

An in-process contract test is a *substitutability* check and runs in milliseconds with no
network — layer 2. **Pact**-style consumer-driven contract testing crosses a process boundary:
the consumer's test emits a pact file of interactions; provider verification replays them and
passes if each response "contains at least the data described," using **provider states** for
preconditions. Consumer side is layer 2-ish; **provider verification is layer 5** and runs on
the provider's pipeline. Fowler's separate point: a contract test against an external service
runs on "the rhythm of changes to the external service" and "shouldn't break the build like an
ordinary test failure."

---

## 4. Verifying LSP mechanically

**The rule.** Liskov & Wing's Subtype Requirement, verbatim: "Let φ(x) be a property provable
about objects x of type T. Then φ(y) should be true for objects y of type S where S is a subtype
of T." Signature compatibility is explicitly insufficient — "What is needed is a stronger
requirement that constrains the behavior of subtypes." The preserved classes are **invariants**
(true of all states) and **history properties** (true of all state sequences).

**The algebra** (Meyer, Design by Contract): subtypes may **only weaken preconditions** and
**only strengthen postconditions and invariants**. Plus the **history constraint**: added methods
must not enable state transitions the supertype forbids — mutable-Point-as-subtype-of-immutable-
Point is the canonical violation.

Mechanical consequences for layer 2:

- **A resolver that raises on input its port accepts is a failed contract test.** That is the
  LSP violation you wanted caught, and it is exactly what a `Refused Bequest` looks like at
  runtime.
- **A resolver that returns a weaker guarantee** (unsorted where the port promises sorted,
  nullable where the port promises total) fails the shared postcondition assertion.
- Python: `icontract` enforces the algebra by inheritance — postconditions are **conjoined**,
  invariants accumulate, preconditions are **disjoined** ("adding preconditions to a function in
  the child class weakens the preconditions"). Requires `icontract.DBC`/`DBCMeta`; without it
  inheritance of contracts is undefined behaviour. `__init__` is exempt from polymorphism.
- **Property-based testing is how you execute the contract over the whole input space.** Put the
  properties *in the shared suite* so every resolver inherits them: `hypothesis` (Python, with
  `RuleBasedStateMachine` + `@invariant` for history properties), `fast-check` (TS, with
  `fc.Command` model-based testing — run the *same* command list against every resolver with the
  *same* model; this is the highest-value LSP tool available), `jqwik` (Java — note its stated
  anti-AI-agent stance before adopting it in an agent-driven pipeline).
- **Metamorphic testing** covers ports with no oracle: assert relations across *multiple*
  executions rather than expected values. For a resolver set the highest-yield relation is
  cross-implementation: `A.f(ctx) ≡ B.f(ctx)` for all ctx where both claim to handle it.

---

## 5. Layer 4 — the graph as an executable test

Without layer 4, the doctrine's layer rule is a wish. **Architecture fitness functions** provide
"an objective integrity assessment of some architectural characteristic(s)."

What to assert, minimum set:

1. No cycles among modules.
2. No resolver imported outside the composition root and its registry.
3. No `domain`/inner layer importing an adapter/outer layer.
4. Every port has a registered contract suite; every resolver appears in it.
5. Utils import nothing from the project.
6. **No test at layer *n* imports an artifact of layer *n+1*.** (The cheapest high-value fitness
   function most codebases lack.)
7. Every hard limit from `laws.md` — file lines, method lines, nesting, `else` count.

Tooling, verified surface:

- **ArchUnit** (Java/Kotlin): `@AnalyzeClasses(packages="…")` + `@ArchTest static final ArchRule`.
  `Architectures.onionArchitecture()`, `layeredArchitecture()…whereLayer(…).mayOnlyBeAccessedByLayers(…)`,
  `slices().matching("com.app.(*)..").should().beFreeOfCycles()`. Legacy: `FreezingArchRule.freeze(rule)`
  baselines existing violations and fails only on new ones. Skipping uses `@ArchIgnore` —
  JUnit's `@Disabled` has no effect.
- **Import Linter** (Python): `lint-imports`, config in `pyproject.toml`/`.importlinter`.
  Five contract types: `forbidden`, `protected`, `layers`, `independence`, `acyclic_siblings`
  (there is **no** `modules` type). `layers` is listed higher→lower, enforces indirect chains,
  supports `containers`, `exhaustive`, `(optional)` layers, `a | b | c` for independent siblings
  and `a : b : c` for permissive; separators may not be mixed on one line. `*` = one module,
  `**` = subpackages.
- **dependency-cruiser** (JS/TS): `npx --no-install depcruise --init` — `--no-install` is not
  optional, because plain `npx X` FETCHES `X` from the registry when it is absent, which breaks
  the offline guarantee (see `graph-tooling.md` §1). Rules use `from`/`to` with
  `path`/`pathNot` — **regexes, not globs** — plus `circular`, `orphan`, `reachable`,
  `dependencyTypes`, `severity`. The `err` reporter's exit code equals the number of `error`
  violations, so it drops straight into CI. `--output-type baseline` + `--ignore-known` is the
  freeze equivalent.
- **TSArch**: `import "tsarch/dist/jest"` (no Vitest entrypoint exists — under Vitest call
  `await rule.check()` and assert manually). `filesOfProject().inFolder("domain").shouldNot().dependOnFiles().inFolder("adapters")`,
  `.should().beFreeOfCycles()`, and `slicesOfProject().definedBy('src/(**)/').should().adhereToDiagramInFile('docs/components.puml')`.
- **Go**: `depguard` in `golangci-lint`, plus a test walking `go list -deps` output.

---

## 6. Independence

- **Hermetic.** "A test should contain all of the information necessary to set up, execute, and
  tear down its environment." At service scale this means a *server in a box* — and it works
  only because "all connections to other servers are injected into the server at runtime using a
  suitable form of dependency injection." Hermeticity is a **consequence of the composition
  root**, which closes the loop with §0.
- **No shared mutable state, no ordering dependence.** Tests run in any order, frequently do,
  and that is what permits parallelism. Beck's desiderata: **Isolated** ("same results
  regardless of the order in which they are run"), **Deterministic**, **Specific**,
  **Structure-insensitive**, **Predictive**.
- **Rebuild starting state from scratch** rather than relying on teardown: a broken setup
  indicts the guilty test, a broken teardown reddens an innocent one.
- **Flake sources and treatments:** lack of isolation → rebuild state; asynchrony → "never use
  bare sleeps... use a callback or polling" with a distinct timeout exception; remote services →
  double plus periodic contract tests; time → **always wrap the clock** (and ban direct clock
  calls with a lint rule — in this doctrine the clock is a Context field); resource leaks → size
  the pool to 1 and throw on exhaustion so the *first* offending test fails.
- **Quarantine, time-boxed.** "Place any non-deterministic test in a quarantined area. (But fix
  quarantined tests quickly.)" Never a bare retry-3-times annotation without a bug. Scale of the
  problem, measured at Google: ~1.5% of test runs report flaky, ~16% of tests have some
  flakiness, ~84% of pass→fail transitions involve a flaky test.

---

## 7. Mutation testing — the only real check that the tests bite

Coverage "measures only which code is executed by your tests. It does not check that your tests
are actually able to detect faults."

- **Mutation score = detected / valid × 100**, where `detected = killed + timeout` and `valid`
  excludes compile/runtime errors.
- Tools: **PIT** (`mvn test-compile org.pitest:pitest-maven:mutationCoverage`, `mutationThreshold`
  fails the build) · **Stryker** (JS/TS/C#/Scala; `thresholds` default `{high: 80, low: 60,
  break: null}` — only `break` fails the build, and partial threshold objects are rejected) ·
  **mutmut** (`mutmut run`, `mutmut browse`; incremental — re-tests only mutants in changed
  functions).
- **Targets:** gate at **60–80% for domain code inside the hexagon**. Do **not** gate adapters,
  generated code, or Humble Objects — they are meant to be logic-free.
- **Do not chase a whole-repo score.** Google deliberately computes no whole-program mutation
  score and surfaces "at most a single mutant per line and 7 per file" during review, because
  "writing tests for those mutants would make the test suite worse, not better" —
  **unproductive mutants**. Reaching 0% survival is impossible since some mutants are
  behaviourally equivalent. Their empirical backing: a bug was coupled with a mutant in ~70% of
  cases, and in >90% of cases either all mutants on a line were killed or none was.
- **So: run mutation diff-scoped in CI, treat surviving mutants as review signal, gate only on a
  60% floor for domain code.**

---

## 8. What to assert at each layer

- **Static** — no assertion; the compiler and linter *are* the assertion. Fail on `any`,
  unchecked casts, missing exhaustiveness, `else`, and every hard limit.
- **Unit** — return values and observable state of one behaviour. Interaction assertions only on
  state-changing outbound calls.
- **Contract** — the port's invariants and postconditions, identically for every resolver.
- **Component** — use-case outcomes at the primary port, plus the *messages sent* to secondary
  ports (Output Tracking or spies). Never the hexagon's internals.
- **Fitness** — the graph, and the test-layering rule.
- **Integration** — serialisation/deserialisation fidelity and real driver behaviour. Write one
  "for all pieces of code where you either serialize or deserialize data." Plus **Paranoic
  Telemetry**: assert that each failure path logs and alerts, including hung requests.
- **E2E** — a handful of user-visible journeys and wiring correctness. Nothing about business
  rules a lower layer could assert.

**The redundancy rules:** (1) "If a higher-level test spots an error and there's no lower-level
test failing, you need to write a lower-level test." (2) "Push your tests as far down the
pyramid as you can." (3) Keep a higher test only for the increment of confidence it adds —
"beware of the sunk cost fallacy and hit the delete key." (4) Reproduce every bug in a
lower-layer test *before* fixing it.
