---
name: md_coding-rules
description: The mandatory architectural code-review, dependency-injection, maintainability and refactoring standard — 40 numbered rules for reviewing, refactoring or writing a codebase where maintainability, encapsulation, DI, small files, small methods, interface-driven design, polymorphism and dead-code cleanup matter. Hard caps (250-line files, 25-line methods, 8-line loop bodies), responsibility-based folder and file naming, constructor injection with one composition root, registries instead of behaviour-selection branching, discoverable typed public APIs with no bare-string dispatch, localized `<predicate>_constants.py` modules, a dead-code safelist, and the anti-overengineering brakes that stop all of it becoming ceremony.
when_to_use: Any architectural code review, or reviewing, refactoring, or modifying a codebase for structure — or deciding whether an abstraction is worth writing.
argument-hint: "<optional path or area to review>"
allowed-tools: Read, Grep, Glob, Write, Edit, TodoWrite, Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(git ls-files:*), Bash(git add:*), Bash(git commit:*)
---

# Architectural Refactoring and Dependency Injection

The standing rule set. Use it when reviewing, refactoring, or modifying a codebase where
maintainability, encapsulation, dependency injection, small files, small methods, interface-driven
design, polymorphism, and dead-code cleanup are important.

The goal is a codebase that is easier to understand, easier to test, easier to extend, and easier to
safely change. **Look aggressively for architectural improvement opportunities, but avoid
over-engineering** — those are two rules, not one, and the second is enforced as hard as the first.

This file is a router. It carries the caps, the non-negotiables and the index. Every rule's text lives
in `references/`; the procedure lives in `jobs/refactor-workflow.md`; the report shape lives in
`specs/review-output.md`.

## The gate — read this first

**Read `references/doctrine.md` before ruling on anything.** It holds the promotion threshold (when a
branch becomes an interface) and the three brakes (rules 28–30). Without it this skill turns a
five-line mapping into five files, and every rule below reads as a mandate.

- **Inspect before editing.** Never emit a finding, or a rename, from a filename or a grep hit. Open
  the range and understand current behaviour, entry points and dependency flow (rule 22).
- **Plan before editing.** The plan has three buckets — definitely / suspicious / do-not — and the
  third is mandatory (rule 23).
- **Preserve behaviour.** Refactoring changes structure only, unless the user explicitly asked for a
  behaviour change. Public APIs, data formats and error behaviour are contracts even when undocumented
  (rule 24).
- **Never delete on suspicion.** Static absence of callers is not proof. Check the dynamic-usage
  safelist first; unconfirmed ⇒ mark **suspicious**, do not remove (rule 17).
- The write tools are granted because rules 24–25 apply edits. What stops an edit is this gate, not a
  missing tool: no inspection and no plan ⇒ no edit.

## Run the deterministic checker first

A handful of these rules are *countable*, and `scripts/architecture_lint.py` measures exactly those.
Run it before you read a line of code — from the skill directory, or by absolute path from anywhere:

```bash
python3 scripts/architecture_lint.py --json <paths>
```

| Argument | Effect |
|---|---|
| `paths` (positional) | files or directories to scan |
| `--changed` | scan the files changed in the git working tree instead |
| `--json` | emit `{"findings": [...]}` — file, line, rule, severity, message |
| neither flag | grouped human report; interactive prompt when no path is given |

Exit code: **1** if any finding is a `warning` (the three hard caps), **0** otherwise — `info` findings
never fail a run.

**Treat the JSON `findings` as already-measured ground truth. Do not re-count lines or re-eyeball
sizes.** Fold each finding into the report with its file, line and rule, then reason only on the
judgment-based rules.

| Measured mechanically — take the number as given | Judgment — nothing measures these for you |
|---|---|
| rule 3 file > **250** lines · rule 4 method > **25** · rule 5 loop body > **8** | which responsibility to split along (rule 7's eight-item list) |
| rules 1–2 vague file and folder names · rule 7F bare-verb method names | whether the replacement name is right (rules 2, 36) |
| one-member `(str, Enum)` · rule 21 module-level mutable assignments | DI and the composition root (8–12, 26–27), branching vs polymorphism (13–15), dead code (16–17), over-engineering (28–30), and everything in `references/public-api.md` and `references/data-and-wiring.md` |

**Consequence of re-measuring by eye:** you arrive at a different number than the checker for the same
file, the two disagree in review, and the finding gets argued about instead of fixed — which is how a
hard cap turns into a matter of taste. A count you did not measure is an estimate; say so.

The checker's messages cite rule numbers, not files: **3**, **4**, **5** and **21** are in
`references/laws.md`; **1**, **2** and **7F** in `references/naming.md`; the one-member-enum rule is
**7B** in `references/public-api.md` — its message says `rule 7A`, the upstream label, kept verbatim.
`architecture_lint.py` is the entry point and imports `scripts/lint_model.py` (every threshold and
vague-name set, in one place, so a limit change is a one-line edit) and
`scripts/python_structure_checks.py` (the AST checks). Run
`python3 scripts/test_architecture_lint.py` to prove the thresholds still match this prose — stdlib
only, no installer. The checker reports; it never edits code.

## How to apply these rules — no silent weakening

These are mandatory review standards, not defaults. When this skill is invoked, **apply every relevant
rule as written.** Do not silently weaken thresholds, substitute personal preferences, or skip a rule
because the existing codebase violates it. **Clearly identify any justified exception rather than
inventing one.**

Exceptions are legal and named: rules 3–5 allow a rare exception when splitting would reduce clarity,
rule 29 allows simple code to stay simple, and rule 28 lets you refuse an abstraction. Each of those is
a decision you *state*, with the rule number and the reason, in the report (`specs/review-output.md`).

**Consequence without this clause:** the **250**-line cap silently becomes "300 is fine here", the rule
set degrades into a style guide, and the review cannot be distinguished from taste.

## Route

| You are asking | Read |
|---|---|
| which numbers are already measured for me? | `scripts/architecture_lint.py` |
| is this branch a design problem? is this abstraction worth it? | `references/doctrine.md` |
| what do I call this file, folder, method, variable? | `references/naming.md` |
| how big may this be? what belongs in public? | `references/laws.md` |
| can a caller discover every operation from the signature? | `references/public-api.md` |
| who constructs this, and how is it wired? | `references/di-patterns.md` |
| may I delete this? | `references/dead-code.md` |
| what shape does a test take? what may be faked? | `references/testing.md` |
| errors, logging, async, types, import order, commits | `references/operational-rules.md` |
| writes, metadata, factories, cloud resource names | `references/data-and-wiring.md` |
| I am about to refactor — what order? | `jobs/refactor-workflow.md` |
| what must my report contain? | `specs/review-output.md` |

## Hard limits

Three measured caps. Each is a trigger to **inspect**, and the answer may be "this one stays" — a rare
exception is allowed when splitting would reduce clarity. Report every breach with `file:line` — all
three are measured by `scripts/architecture_lint.py`, so take its number rather than counting again.

| Limit | Hard | Resolution | Consequence of ignoring it |
|---|---|---|---|
| Source file | **250 lines** | split by responsibility, never randomly | nobody reads to the end, so the second half duplicates the first |
| Method | **25 lines** | extract a *named* method or a collaborator | the reader must simulate the method to know what it does |
| Loop body | **8 lines** | extract the body: loop shows repetition, method shows per-item behaviour | per-item and per-run work become indistinguishable |

Non-numeric limits with the same force: **one** composition root per library ·
**≥2** related values before an `Enum` earns its existence · **3–5** words in an identifier ·
**≤250** lines in the human code-reading document · **0** module-level mutable state ·
**0** uses of DynamoDB `update_item`.

Full text and the reasons: `references/laws.md`, `references/public-api.md`,
`references/di-patterns.md`, `references/data-and-wiring.md`.

## Non-negotiables

1. **Responsibility, not line count, decides a split.** A 250-line file split down the middle is worse
   than the original. Split along the eight responsibilities in `references/laws.md` §7.
2. **A file name must survive alone.** It has to make sense in an editor tab, an import statement, a
   search result, a stack trace, and a code review — none of which show the folder.
   `stripe_payment_processor.py`, never `stripe.py`. Banned: `utils` `helpers` `common` `misc` `base`
   `logic` `manager` `service` `handler` `processor` `helper` — this list is matched mechanically by
   `scripts/architecture_lint.py`, for file stems and for folder names.
3. **Dependencies arrive through the constructor.** Nothing in business logic constructs a repository,
   an HTTP client, a validator or a parser. A class's constructor is the truthful list of what it
   needs — a class that receives the whole DI object has no such list.
4. **One composition root decides which implementations run.** Business logic never chooses.
   Framework-native roots are fine; an *unidentified* root is not.
5. **Behaviour-selection branching is a smell, not an automatic violation.** Promote it only when a
   case carries substantial behaviour, cases will grow, cases are duplicated, cases need different
   dependencies, tests must swap them, or the branch hides provider infrastructure in business logic.
   None of those ⇒ leave the branch. A small stable mapping in the root is correct code.
6. **Guard clauses stay.** Null, empty, validation, permission, boundary and early-return checks are
   not the branching this skill hunts. Do not blindly replace every `if`.
7. **An operation is a typed method, never a string.** `tool.call("graph_neighborhood", …)` hides the
   operation from the type system, the IDE and the reader. String-keyed dispatch is allowed *only* as
   an adapter for a caller that genuinely passes strings, and it lives on a separate class.
8. **An enum must group ≥2 related values** — the checker flags every one-member `Enum`, `IntEnum` and
   `StrEnum` subclass. A one-member enum is ceremony; use a named constant plus a
   direct method. Reaching for one to "match" a sibling class is the tell — different surfaces are
   allowed different shapes, and forced symmetry hides real capability differences.
9. **Every meaningful string is a named constant, grouped by responsibility.** Env vars, headers, path
   params, attribute names, tool names, model ids — in a `<predicate>_constants.py` beside the code
   that owns it, never in a root-level god-file `constants.py`. **Tests reference the same constants**;
   a re-spelled literal in a test keeps passing while production breaks.
10. **No module-level mutable state.** Only imports, definitions, and narrowly scoped static constants
    in dedicated constant modules. Everything else arrives by constructor, DI object, setUp, or local.
    The checker flags every module-level `list`/`dict`/`set` bound to a non-`UPPER_CASE` name.
11. **Delete dead code; version control keeps history.** The active codebase preserves active truth —
    but not before the §17 safelist clears the deletion.
12. **Abstraction must pay for itself.** An interface, class, folder, registry or DI layer ships only
    if it removes real duplication, isolates real variation, improves testability, protects a real
    boundary, shrinks a large method or file, replaces a growing selection branch, separates
    infrastructure from business logic, or enables a real swap. `ThingInterface` + `DefaultThing` alone
    is a finding.
13. **Simple code stays simple.** Architectural purity is less important than practical clarity. Do not
    turn every small decision into a class.
14. **Extraction is only good if the name explains it.** `_do_stuff`, `_handle`, `_process`,
    `_execute`, `_finalize` move the reading cost instead of removing it — the checker flags those and
    the bare verbs `do`, `run`, `execute`, `handle`, `process`, `query` by name.
15. **Variants are additive.** Two provider or strategy variants users may want side by side each own
    their output path, metadata identity, tests and public wiring — so either can be extracted into its
    own library later without untangling the other. Collapse them into an either/or only when the
    business rule says only one can exist.
16. **Say what you deliberately did not do.** Every report carries the do-not bucket: the changes you
    rejected as over-engineering, and why. A report without it cannot be distinguished from one that
    never considered the question.

## Relationship to codegraph

`md_codegraph` is the descendant of this file: this states the rules, codegraph **measures** them at repo
scale. Where a rule here is a number — 250-line files, 25-line methods, 8-line loop bodies, one
composition root, cycles, swallowed exceptions — codegraph runs a script, emits `file:line` with the
measured value, and turns the claim into a fitness test. `scripts/architecture_lint.py` overlaps it on
the three caps and stops there: it is the pre-pass for one review, not a graph. Use this skill to decide what is right and to refactor;
use codegraph when you need the numbers proven rather than asserted. The rules in
`references/public-api.md` and `references/data-and-wiring.md` have no counterpart there.

## What this does NOT do

- **It measures the countable rules only.** `scripts/architecture_lint.py` emits `file:line` for the
  three caps, the vague names, one-member enums and module state. Every *other* number here is a
  threshold you check by reading, and no script in this skill emits a dependency graph, a cycle set or
  a coupling metric. A count you did not measure is an estimate — say so.
- **It does not authorize behaviour changes.** Structure only, unless the user asked.
- **It does not rule on correctness, security, or performance.** A god class full of correct logic is
  in scope; a race condition inside a 20-line method is not.
- **It is Python-shaped.** The caps, the folder layers and the branching rules are language-neutral;
  `(str, Enum)`, `Protocol`, `<predicate>_constants.py`, `config_dependency_injection.py` and the
  import-order rule are Python idioms. Translate them, and say that you did.
- **`references/data-and-wiring.md` is narrower than the rest.** Those five rules were written for one
  multi-tenant service against a key-value document store and an external identity provider. They are
  hard rules there and worked examples elsewhere — apply the shape, not the vendor.
- **It does not decide the plan for you.** The three buckets are a judgement, and rule 23 requires the
  third one to be populated by name.

## Checklist before saying done

- [ ] `scripts/architecture_lint.py` was run first, and every finding it returned is in the report
- [ ] The relevant files were opened, not grepped (rule 22)
- [ ] The plan named all three buckets, including what you refused to do (rule 23)
- [ ] Every breach reported with `file:line` and the measured number
- [ ] No threshold quietly relaxed — every exception taken is named with its rule number and reason
- [ ] Behaviour, public API, data formats and error behaviour unchanged unless asked (rule 24)
- [ ] Steps applied in the order in `jobs/refactor-workflow.md`, commits focused by responsibility
- [ ] Nothing deleted that the §17 safelist did not clear
- [ ] Every new abstraction named which of the nine benefits in rule 28 it delivers
- [ ] The report has all nine sections of `specs/review-output.md`, including reasoning and risk
