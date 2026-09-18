# Job: fitness — turn every structural claim into an executable test

Writes `tests/fitness/` only. **Adds test files; never edits production code.** No git state
changes beyond the new test files.

Input: `.codegraph/restructure.md` §5 (the fitness table), `.codegraph/graph.json`, `.codegraph/oracle.json`.
Output: one test file per claim, a runner entry, and a ≤25-line summary in the conversation.
Contracts: `../specs/restructure-spec.md` §5, `../specs/finding.md`.

**The rule this job exists to enforce: a cap that is not a test is a habit, and habits decay.**
Every number the spec claimed becomes a check that fails the build when it stops being true.

Fully offline. Every test written here runs from the checkout, the bundled scripts, and `git log`.
A test must never fetch a URL, install a package, or call a network service — a fitness test that
needs the network is not a fitness test.

---

## Phase 0 — establish what can actually be enforced

1. Read `.codegraph/oracle.json`. It says which of test runner, type checker, linter,
   `scripts/caps.sh`, `scripts/graph.sh` and a mutation tool actually run in this repo.
2. Read `.codegraph/restructure.md` §5 (shape in `../specs/restructure-spec.md` §5). Every row is
   a claim with an intended test file and tool.
   If there is no spec (the user ran `/md_codegraph fitness` standalone), derive the claim set from
   `.codegraph/graph.json`: current cycle count, current layer edges, current caps, current port
   list. **Claims derived this way pin today's state — say so; they are a ratchet, not a target.**
3. Decide the enforcement tier per claim, highest available wins:

| Tier | Mechanism | Use when |
|---|---|---|
| 1 | the repo's existing architecture linter (`import-linter`, `dependency-cruiser`, ArchUnit, `depguard`, `eslint-plugin-boundaries`) | it is already installed — a rule in a tool the team already runs is the cheapest gate to keep |
| 2 | a test that shells out to `scripts/graph.sh` / `scripts/caps.sh` and asserts on the JSON | no architecture linter, but the bundled scripts run |
| 3 | a pure-stdlib test that walks the source tree itself | neither of the above |

4. **Never install a tool to reach a higher tier.** Write the tier you got, and record the drop in
   the summary. An added dependency is a change to the build, and this job does not change builds.

---

## Phase 1 — write one test per claim

One file per claim, named for the claim, not for the mechanism. Each test file must state, in a
docstring or header comment: the claim, the spec row ID (`F1`…), the measured number at the time of
writing, and the file that will need editing when the claim legitimately changes.

The seven claim families and their canonical forms:

| Family | Claim | Assertion |
|---|---|---|
| **Acyclicity** | no cycles among the modules named in the target tree | `graph.json.cycles` is empty for that node set — or the linter's acyclic rule |
| **Layering** | layer A does not import layer B | forbidden-import rule, direction stated explicitly |
| **Isolation** | nothing outside the composition root imports `<resolvers dir>` | forbidden-import rule with the root as the only allowed importer |
| **Purity** | `utils/` imports nothing from `src/` | forbidden-import rule |
| **Port health** | every port has ≥1 resolver, an `Absent` resolver, a contract suite, and a registration test | walk the port list; assert each of the four |
| **Caps** | no file over the file cap, no folder over the fan-out cap, no method over the method cap, no nesting over the nesting cap | run `caps.sh`; assert `totals.*_major == 0` — including `totals.folder_files_major == 0` — **and** that the metric was measured at all (below) |
| **Test layering** | no test imports a higher test layer | walk `tests/`, assert the import direction |

Rules for the tests themselves:

1. **Assert on a number, not on a string.** `assert len(cycles) == 0`, not a message match.
2. **Fail with the offending list, not just a count.** A red fitness test must name the file that
   broke it, or nobody will fix it.
3. **No test may depend on another test's ordering** or on a prior run's artifact.
4. **Pin the cap values in one place** — read them from the same environment variables `caps.sh`
   uses (`CG_CAP_FILE`, `CG_CAP_FOLDER`, `CG_CAP_METHOD`, `CG_CAP_NESTING`, `CG_CAP_PARAMS`,
   `CG_CAP_PUBLIC`), and
   fall back to the documented defaults. Two sources of truth for a cap is a defect.
5. **Exclude what `scope.json` excluded** — vendored, generated, migrations, fixtures, build
   output. A fitness suite that fails on generated code gets disabled within a week.
6. **A claim that cannot be tested is not written as a weak test.** Record it as `UNVERIFIED` in
   the summary with the reason. A test that passes vacuously is worse than a missing test.
7. **A caps gate asserts coverage before it asserts zero.** `totals.method_lines_major == 0` is
   also true when no scanner ran: on Ruby, C# or PHP the key is absent, `.get(k, 0)` returns 0,
   and the gate is green forever. So the generated test must first assert
   `scanned.<language> > 0` for the repo's primary language and fail if `degraded[]` names it or
   `fidelity != "native"` — mechanism for rule 6, not a restatement of it. Two metrics are exempt
   from that guard because no language scanner produces them: `file_lines` and `folder_files` come
   from the file list itself, so the coverage assertion for both is `scanned.code > 0`. Do **not**
   gate `folder_files` on `scanned.folders > 0`: that number is legitimately 0 in a repo whose code
   is all `.tf` or all headers, which the cap excludes on purpose, and the test would then fail
   forever claiming a metric was unmeasured when it was correctly inapplicable. `scanned.folders == 0`
   with `scanned.code > 0` is the `UNVERIFIED` case of rule 6, not a red test.

---

## Phase 2 — the ratchet, for claims that cannot yet be met

Some claims are true of the target tree and false today. Those get a **ratchet test**, not a
skipped test:

1. Record today's measured value as the budget, in a single committed data file
   (`tests/fitness/budget.json`), one entry per claim.
2. The test asserts `measured <= budget`.
3. When a slice improves the number, the test lowers the budget in the same commit.
4. The budget may never rise. A commit that raises it is the finding.

State plainly in the summary which claims are ratchets and what their current budgets are. A
ratchet is honest; a `@skip` is a lie that passes.

---

## Phase 3 — wire it into the build

1. Register the suite with the repo's existing runner — a directory the runner already collects,
   not a new tool. `pytest tests/fitness`, `npm test -- tests/fitness`, `go test ./tests/fitness/...`,
   the existing JUnit source set.
2. **Registration is itself a test.** Add one check that the fitness directory is non-empty and is
   collected, so deleting the suite fails the build rather than silently passing it.
3. Do not add a CI workflow file unless the user asked. Report the one-line command they should add.

---

## Phase 4 — run it and report

1. Run the suite. Report the real pass/fail counts.
2. If a test fails on first run, that is either (a) a claim the slices have not delivered yet →
   convert it to a ratchet, or (b) a claim the spec got wrong → report it as a spec bug and stop.
   **Never weaken an assertion to make a first run green.**
3. Re-run `scripts/caps.sh` on the new test files. The fitness suite obeys the caps too.

Summary shape, ≤25 lines:

```
Fitness suite: tests/fitness/  (7 claims, tier 1×3 / tier 2×3 / tier 3×1)

| ID | Claim | Test | Status |
|----|-------|------|--------|
| F1 | no cycles among src modules   | test_no_cycles.py       | GREEN |
| F4 | every port has a contract     | test_contract_coverage.py| GREEN |
| F7 | caps: 250 lines/7 per folder/15/1 | test_caps.py       | RATCHET budget 3 |

UNVERIFIED: F6 (no test-layer oracle in this repo)
Next: add `pytest tests/fitness` to CI, then /md_codegraph verify
```

---

## Refusals

- **Editing production code to make a fitness test pass.** That is `jobs/apply.md`'s work, behind
  the approval gate. This job only writes tests.
- **Installing a tool, adding a dependency, or changing the build config** to reach a higher
  enforcement tier. Report the drop instead.
- **Weakening or skipping an assertion** so a first run is green. Ratchet or report.
- **Testing deliberate headroom.** A permissive default a future environment will tighten, an
  env-scoped name that shares one value today, a mode knob with one mode, a single-resolver port at
  an I/O boundary — these are `DEFERRED CONFLICT` entries in spec §6, not claims. Writing a test
  that forbids them **freezes the seam shut**, which is the opposite of the point. See
  `../references/smells.md` §6.
- **A test that reaches the network**, reads a credential, or generates a certificate or key.
  Never, in any language, for any reason.
- **A fitness test asserting on line-by-line file content.** Assert on structure and numbers;
  content assertions break on every rename and get deleted.

---

## Done checklist

- [ ] One test file per spec §5 row, or an explicit `UNVERIFIED` with a reason
- [ ] Every cap value read from the same place `caps.sh` reads it
- [ ] Every failing-today claim is a ratchet with a committed budget, not a skip
- [ ] The suite is collected by the runner the repo already uses
- [ ] Deleting the suite fails the build
- [ ] The suite itself passes the caps
- [ ] No test touches the network, a credential, or key material
- [ ] Deferred conflicts were left alone
- [ ] The conversation got the ≤25-line summary and one next action
