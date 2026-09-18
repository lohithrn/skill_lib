# Job: verify — prove the restructuring holds, by measurement

Phase 3 on a spec, phase 5 on applied code. **Read-only outside `.codegraph/`.** No source file is
edited, no commit made, no branch moved, no test rewritten. Output: `.codegraph/verify.md`,
`.codegraph/caps.after.json`, `.codegraph/graph.after.json`, and a ≤25-line summary. Claims come
from `.codegraph/restructure.md` §1, §3, §4 `Green when`, §5. Verdict arithmetic:
`../specs/graph-report.md` §4. Findings: `../specs/finding.md`.

**Fully offline.** Every number comes from the checkout, `git log`, and the two bundled scripts. No
URL fetched, no package installed, no vendor tool downloaded, no network call, no credential
handled, no certificate or key generated. A metric needing a tool the repo does not already have
goes under `degraded` — never estimated, never zeroed. **Nothing here is verified by reasoning:** a
claim whose command did not run is `UNVERIFIED`.

---

## Phase 5a — the gate. Refuse before measuring.

1. `.codegraph/restructure.md` and `.codegraph/graph.json` exist. No spec ⇒ no claims ⇒ nothing to
   verify: run `jobs/analyze.md` instead. `graph.json` is the **before** baseline every diff uses.
2. `git status` is clean — a dirty tree means the numbers belong to no commit. Print the sha under
   test (`git rev-parse HEAD`) and the baseline sha; two unrelated commits prove nothing.
3. `.codegraph/applied.md` lists ≥1 slice ⇒ **phase-5 mode**, verify the code. Absent ⇒
   **phase-3 mode**: check every claim is *measurable*, then hand to `jobs/refine.md`. Never mix
   modes in one report, and never print `PASS` in phase-3 mode.
4. `.codegraph/oracle.json` names a test command. If not, the whole run is `UNVERIFIED`.

---

## Phase 5b — re-run the deterministic scripts

Same flags, same root, same excludes as `jobs/analyze.md` phase 1b — different flags produce a diff
that is an artefact of the flags.

```bash
bash <skill-dir>/scripts/caps.sh  --json --root <path> > .codegraph/caps.after.json
bash <skill-dir>/scripts/graph.sh --json --root <path> > .codegraph/graph.after.json
```

`<skill-dir>` is the absolute path resolved in phase 0 and recorded in
`.codegraph/oracle.json` (`tools.caps.command` / `tools.graph.command` are the exact
strings). Substitute it; never run a command with an unexpanded `${...}` in it — a
shell that does not set the variable silently runs `bash /skills/…`.

1. Read `fidelity` and `degraded` from both. Before native + after degraded ⇒ **the diff is void**:
   say so, name the missing tool, do not install it, and do not assert a cycle count.
2. From `caps.after.json.totals` take `file_lines_major`, `method_lines_major`, `nesting_major`,
   `loop_body_major`, `else_major`, `params_major`, `public_members_major`, every `worst_*`. From
   `graph.after.json.totals` take `cycles`, `illegal_edges`, `ports`, `resolvers`,
   `composition_roots`, `contract_suites`, `ports_without_suite`, `ports_without_absent`,
   `avg_degree`, `propagation_cost`.
3. Write every delta as `before → after (claimed X → Y)` and report the **measured** one. A slice
   that promised `cycles 4→3` and delivered `4→4` did not succeed, whatever the tests say.

---

## Phase 5c — the machine gates

A gate with no command that ran is `UNVERIFIED`, never `PASS`.

| # | Gate | Measured by | Passes when |
|---|---|---|---|
| G1 | tests green | the repo's runner from `oracle.json` | exit 0 · 0 failures · 0 errors |
| G2 | types + linter clean | `mypy`/`tsc --noEmit`/`go vet` and the repo's linter, if present | exit 0 |
| G3 | caps | `caps.sh --json` | every `*_major` is 0, or matches §1's target |
| G4 | every port has `Absent` | `graph.after.json.totals.ports_without_absent` | `== 0` |
| G5 | every port has a contract suite | `totals.ports_without_suite` | `== 0` |
| G6 | every resolver registered | the spec's registration test, run | red for a missing resolver, green now |
| G7 | one composition root | `totals.composition_roots` | matches §1 |
| G8 | graph legality | `totals.cycles`, `totals.illegal_edges` | `cycles` match §1's target, usually `0`; `illegal_edges` **≤ before** and `0` inside the folders this slice claimed |
| G9 | `tests/fitness/` enforces every §5 claim | run the suite, count its tests | one test per §5 row, all green |
| G10 | the new tests bite | mutation tool from `oracle.json`, diff-scoped | above the repo's existing baseline |

- **G6 must be shown able to fail.** In a scratch copy drop one registry entry, run the test, confirm
  red, discard the copy. Green ⇒ not a registration test. `git status` stays clean afterwards.
- **G9 is a count.** For every §5 row name the test file and the assertion carrying it. A §5 claim
  with no test is a **blocker** `CG-TEST-<nnn>`: caps are not done until they are a test.
- **G10 is skipped, not faked** when no mutation tool is installed. Offline means no install.

**Never rewrite a contract suite, a fitness test, or a registration test to make a gate pass** —
that inverts the oracle. A resolver that cannot satisfy its contract means the port is wrong.

---

## Phase 5d — the over-application check

Mandatory, and invisible to G1–G10. Rules: `../references/arch-smells.md` §11 and `smells.md` §3.

| Smell | Measurement | Fails when |
|---|---|---|
| **Lasagna Code** | files touched by a one-field change, from §3 `Deletes` plus `git log --numstat` on the applied commits | >4 files for a trivial change |
| **Poltergeist** | resolver bodies, from `caps.after.json` violations per resolver file | a resolver forwards one call and adds nothing |
| **Speculative Generality** | `graph.after.json.ports[]` with `resolvers <= 1` | one resolver, no named second case, **and no I/O boundary** |
| **Zone of Uselessness** | node `abstractness` high + `instability` high | abstract and nothing depends on it |
| **Delegation depth** | longest port→resolver→port chain in `graph.after.json.edges` | depth rose and no conflict was removed |

**The rule that decides the job: a restructuring that raised delegation depth without removing a
conflict FAILED.** Count conflicts removed — `else_major` down, duplicate switch sites down,
`if x is None` sites down — against layers added. Second number moved and first did not ⇒ FAIL, and
the remedy is a revert. Adding a layer to fix a layer is the smell, not the fix.

### Deliberate headroom is not a failure

Never fail a gate, emit a finding, or propose a revert for these — full list `smells.md` §6.

1. A permissive default a future environment will tighten; env-scoped names sharing one value today;
   a mode knob with one mode; a per-stage resource pointing at one target for now.
2. **A single-resolver port at an I/O boundary** — testability alone justifies it, so it is exempt
   from the Speculative Generality row above and the report states the exemption.
3. Context fields nothing reads yet, when §3 named them as headroom; anything §6 recorded as
   `deferred-conflict`. A slice that silently closed one is a **deviation** — report it.

---

## Phase 5e — the verdict table

One row per claim. This table is the product of the job.

```markdown
| # | Claim (source) | Claimed | Measured | Command | Verdict |
|---|---|---|---|---|---|
| C1 | 0 cycles (§1)                | 4 → 0  | 4 → 0  | graph.sh --json            | PASS |
| C2 | 0 files over 250 (§1)        | 31 → 0 | 31 → 2 | caps.sh --json             | FAIL |
| C3 | every port has Absent (§3)   | 8 of 8 | 7 of 8 | graph.sh totals            | FAIL |
| C4 | mutation ≥70% on resolvers   | ≥70%   | —      | none installed             | UNVERIFIED |
```

1. Every row cites the spec section its claim came from. No source ⇒ not a claim. `Measured` is a
   number a command printed — never a word, never a range, never "as expected".
2. Three verdicts only: `PASS`, `FAIL`, `UNVERIFIED`. No `PARTIAL`, no `mostly`. Every finding ID
   in `.codegraph/report.md` gets a row — resolved, or carried forward with the reason. Count them;
   a missing ID is itself a `FAIL`.
3. The overall verdict is recomputed arithmetically from the two after-JSONs, never chosen.
   **One `FAIL` means the run failed.** Thirty `PASS` and one `FAIL` reports FAIL.

---

## Phase 5f — on failure: revert the slice, not the spec

1. Attribute the failing claim to **one slice**, using §4 and `.codegraph/applied.md`.
2. Revert that slice only: `git revert` its commits newest-first, exactly the range `applied.md`
   recorded. Additive-only steps may stay — §8 Rollback says which. **Never revert the whole spec
   because one slice missed.**
3. Re-run 5b and 5c. The reverted state must be green. Still red ⇒ the slice boundary was wrong:
   report a spec bug and re-run `jobs/spec.md` for that port. Never patch forward, never fix source
   while verifying. Append to `.codegraph/applied.md`: slice ID, the failed claim, the measured
   number, the revert commits. Then stop.

---

## Return to the conversation

≤25 lines, shaped like `../specs/graph-report.md` §3. Never paste the table or a JSON file.

```
CodeGraph verify: <repo> @ <sha> vs baseline <sha>   FAIL (2 of 4 claims)
Claims     4 · 1 PASS · 2 FAIL · 1 UNVERIFIED (no mutation tool installed)
Gates      tests 412 passed · mypy clean · caps 2 majors · fitness 7/7 green
Measured   cycles 4 → 0 · else 341 → 6 · files >250 31 → 2 · roots 3 → 1
Over-appl  delegation depth 2 → 2 · 0 poltergeists · 1 single-resolver port (I/O boundary, ok)
Headroom   14 deferred conflicts intact · none silently closed
Failed     C2 2 files still >250 (slice 6) · C3 TaxPolicy has no Absent resolver (slice 7)
Not covered ruby graph degraded · dynamic dispatch in plugins/ unresolvable
Next: revert slices 6 and 7, then /codegraph verify again   (full: .codegraph/verify.md)
```

---

## Refusals

- **Dirty tree, or two unrelated shas.** Hard stop; measurements must belong to a commit.
- **No test runner, or a claim with no command.** `UNVERIFIED`, never `PASS` — behaviour
  preservation must be measured before any graph claim counts.
- **Any request to edit source, a test, or a fitness rule to make a gate pass.** Refuse; the port
  or the slice is wrong.
