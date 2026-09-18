# Job: apply — execute one slice, then stop

Phases 4–5. **This is the only job that edits source.** It runs one slice at a time, proves the
oracle green before and after each, and reverts rather than patching forward.

Input: an approved `.codegraph/restructure.md`. Output: edited source, one commit per step, and a
≤25-line summary per slice.

---

## Phase 4a — the gate. Refuse before you read any code.

Check, in this order, and stop at the first failure:

1. `.codegraph/restructure.md` exists.
2. Its sha matches `git rev-parse HEAD`. **A spec written against a different commit is void** —
   line ranges have moved. Re-run `spec`.
3. §9 Approval has **every box checked** and names slices.
4. The requested slice is in that list. `/codegraph apply all` means the listed slices, in order —
   never every slice in the file.
5. `git status` is clean. Never begin a slice on a dirty tree; revert stops working.
6. The oracle command from `oracle.json` **runs and passes right now**. If the suite is already
   red, stop: you cannot tell your breakage from the existing breakage.

On failure, print exactly what is missing and run `jobs/spec.md` instead. Do not "proceed
carefully". Do not check the approval boxes yourself, and do not treat an approving sentence in
chat as §9 — the checked file is the authorisation.

**Branch first.** If on the default branch, create `codegraph/<slice-name>` before the first edit.
Never commit to `main`/`master`. Never `push`. Never open a PR unless asked.

---

## Phase 4b — execute the slice, step by step

Each numbered step in the slice's `Steps` list is **one commit**. Per step:

1. Make only that step's edits. Nothing opportunistic — no renames, no import tidying, no "while
   I'm here". A step that touches a file the step does not name is wrong.
2. **Copy, do not rewrite.** When extracting a resolver from `← file.py:100-115`, the body moves
   verbatim, including the quirks. Behaviour changes are a different slice, and the
   characterization tests from slice 1 exist precisely to catch a "harmless" cleanup.
3. Run the oracle: the test suite, then `scripts/caps.sh --json --root <touched path>` (the path
   is an option value, never a positional — a positional argument exits 2 and step 4 would read
   that as red), then
   `scripts/graph.sh --cycles` if the step claims a graph change.
4. Green ⇒ commit with the slice ID and step number in the subject. Red ⇒ **revert the step**
   (`git checkout -- .` for an uncommitted step), report the failure, and stop the slice.
5. Update the TodoWrite item. One step in progress at a time.

**The order inside a slice is not negotiable.** Port first, resolvers second, contract suite and
registration test third — and both must **fail** before the registry exists, or they are not
tests. Registry fourth. Callers fifth. The old branch is deleted **last**, and only after every
caller points at the registry.

Delete only what the spec lists. A file the spec does not mark `[deleted]` stays, even if it looks
dead — `graph.json` is a static graph and dynamic dispatch may still reach it.

---

## Phase 4c — write the code to the hard limits

Every file this job creates must pass `caps.sh` when it is written, not after a cleanup pass.

| Writing | Rule |
|---|---|
| a port | ≤3 methods · docstring is the conflict **as a question** · no imports from resolvers |
| a resolver | one file, one answer · takes the Context, nothing else · no `else` · nesting within `caps.sh`'s hard cap (default 1) |
| the Absent resolver | returns the neutral value or raises the port's declared error type — never `None` bare |
| a Context | frozen/immutable · no methods with logic · carries the unused headroom fields the spec named, with the comment the spec gave |
| a registry | the one place a `match`/map over the discriminant is legal · exhaustive · Absent as default |
| the composition root | the only file naming concrete resolvers · constructor injection only |
| a common util | pure · zero project imports · no I/O |

Language-specific idioms — the exact syntax for frozen Contexts, protocol/interface declaration,
registries, and no-`else` control flow in Python, TypeScript, Java/Kotlin, and Go — are in
`../references/language-idioms.md`. Contract-suite scaffolding per language, including the pytest
`python_classes` prefix trap and the JUnit `@TestInstance(PER_CLASS)` requirement, is in
`../references/testing-contracts.md`. Read the section for the language you are writing; do not
improvise the harness.

**Never edit a contract suite to make a resolver pass.** That inverts the oracle. If a resolver
cannot satisfy the contract, the port is wrong — stop the slice and say so.

---

## Phase 4d — after every slice

1. Full oracle, not just the touched paths: suite · type checker · linter · `caps.sh` on the whole
   scope · `graph.sh --cycles`.
2. Diff the graph: `graph.sh --json > .codegraph/graph.after.json`, and compare the slice's
   `Green when` numbers against the measured ones. **Report the measured delta, not the intended
   one.** A slice that promised `cycles 4→3` and delivered `4→4` did not succeed, whatever the
   tests say.
3. If the slice was meant to delete an `else` chain and `caps.sh` still counts it, the slice is
   incomplete. Finish it or revert it.
4. Append the result to `.codegraph/applied.md`: slice ID, commits, measured deltas, anything
   deviated from the spec and why.

Then return ≤25 lines and stop:

```
Slice 3 of 9 applied — DiscountPolicy port extracted
Commits    7 (a1b2c3d..e4f5g6h) on codegraph/discount-policy
Oracle     pytest 412 passed · mypy clean · caps.sh 0 breaches in src/billing
Measured   invoice_service.py 214 → 96 lines · else in billing/ 9 → 0 · cycles 4 → 3
Deviation  none
Next: /codegraph apply 4   (Context for the tax family)
```

**Do not chain into the next slice** unless the user asked for `all`. Even then, stop on the first
red oracle and report.

---

## Phase 5 — prove it, once every approved slice is in

1. Run `jobs/fitness.md` to write `tests/fitness/` — every claim §5 of the spec made becomes an
   executable test. **The caps are not done until they are a test.**
2. Run `jobs/verify.md` for the final report: graph before vs after, every finding ID resolved or
   explicitly carried forward, the fitness suite green.
3. Mutation score on the new resolvers if a mutation tool is in `oracle.json`. A resolver whose
   contract suite kills no mutants has a contract suite that asserts nothing.

---

## Refusals

- **Unchecked §9, stale sha, or dirty tree.** Covered above; these are hard stops.
- **Untested code in the slice's blast radius.** Slice 1 exists for this. Never restructure
  unpinned behaviour because the spec is approved — say the characterization tests are missing.
- **A step that requires a behaviour change to work.** Stop. That is a spec bug, not an edit
  decision. Report it and re-run `spec` for that port.
- **A cap breach you cannot fix inside the slice.** Report it as a finding for the next analyze
  run rather than growing the slice to fix it.
- **`git push`, a PR, a merge, a tag, or a rebase.** Never, unless explicitly asked in that turn.
