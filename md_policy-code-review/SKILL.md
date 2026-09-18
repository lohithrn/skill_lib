---
name: md_policy-code-review
description: Review a codebase or a diff against the whole standing policy at once, and refactor to it when asked — the 40-rule architecture, dependency-injection and maintainability standard (hard caps, constructor injection, registries over branching, typed public APIs, dead-code safelist, the anti-overengineering brakes), CodeGraph structure (conflict→port→resolvers→context, one composition root, no cycles, tracebacks, contract suites), the house conventions (<prefix>_<resource_role>_<company> naming and its 64-char caps, route shape, nothing-hardcoded, one auth gate, epoch-ms data rules, deploy gates), ordinary change review (correctness, regressions, security, tests), and — on a diff — whether the change actually built what the spec asked, reported as a separate axis so a standards pass cannot mask a spec failure. Ships a deterministic linter for the countable rules. Emits suggestions with file:line and a named rule; edits only in refactor mode.
when_to_use: Only when explicitly invoked as /md_policy-code-review. Never auto-trigger.
disable-model-invocation: true
argument-hint: "nothing — or [review|diff|refactor] [path|git-ref] to force a mode"
allowed-tools: Read, Grep, Glob, Write, Edit, TodoWrite, Agent, Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(git rev-parse:*), Bash(git ls-files:*), Bash(git show:*), Bash(git add:*), Bash(git commit:*), Bash(mkdir:*), Bash(wc:*), Bash(awk:*), Bash(bash:*), Bash(python3:*)
---

# /md_policy-code-review

A router with one conflict to resolve: **which policy groups apply to what the user pointed at, and
what should change?** No rule text lives here — the rules are in `references/`, the phases in
`jobs/`, the output shape in `specs/`. Read the one you need.

## The gate — read this first

**`review` and `diff` never edit the tree.** Not once, not behind a flag, not "while I was in there".
`refactor` is the one mode that may, and only after its own gate clears.

- In `review`/`diff` the only writable location is `.policy-review/` in the analysed repo. Everything
  else is read. The **one** exception is `.out-of-scope/`, and only after the user answers yes to an
  explicit offer to record a declined finding — never on this skill's own initiative, never in the
  same breath as reporting it. `references/declined.md` §4 is the procedure.
- Never `push`, `checkout`, `stash`, branch, tag, or revert — in any mode. Never run a formatter, a
  codemod, or a linter's `--fix`. `git add`/`git commit` are for `refactor` mode only, per
  `jobs/refactor-workflow.md`.
- Never call a subagent that can write source **from `review`/`diff`**. If `codegraph-surgeon` is
  installed, it is out of bounds in those modes — they have no apply path to hand a slice to.
- In `review`/`diff` every output is a **suggestion**: what to change, where, why, and what it costs.
  The user applies it, or does not. `specs/suggestion.md` is the contract.
- **`refactor` may edit, and its gate is `references/architecture-standard.md` §The gate**: inspect the
  range (rule 22), produce the three-bucket plan including the do-not bucket (rule 23), preserve
  behaviour (rule 24). No inspection and no plan ⇒ no edit. Its report shape is
  `specs/review-output.md`.
- The `Bash` and `Edit` grants are wider than any single mode needs **on purpose**: measurement scripts
  live at paths only resolvable at run time, and one skill's frontmatter serves all four modes. What
  stops an edit in a review is this gate, not a missing tool — so state the mode you selected in your
  first line and hold to it.

## Route

Parse `$ARGUMENTS`. First token is the mode, rest is the target. An unrecognised first token is a
target, not an error. Read the one job file in that row and follow it; do not read the other.

| Invocation | Job file | Scope | Edits? |
|---|---|---|---|
| `/md_policy-code-review` | `jobs/diff.md` if the worktree is dirty or the branch is ahead, else `jobs/review.md` | the change, else the repo | no |
| `/md_policy-code-review review [path]` | `jobs/review.md` | whole tree at `path` (default: repo root) | no |
| `/md_policy-code-review diff [ref]` | `jobs/diff.md` | changed files vs `ref` (default: the merge base with the main branch) plus their direct importers | no |
| `/md_policy-code-review refactor [path]` | `jobs/refactor-workflow.md` | the area at `path`, restructured to group `R` | **yes**, after the gate |

State which case was found and the job it selected in one line before starting.

---

## The five policy groups — two axes

Every suggestion cites exactly one policy ID from one of these. The IDs are the contract between
this file, the report, and anyone arguing with a finding.

They sit on **two axes**: **Standards** (`R`/`G`/`H`/`C`) asks *is this code good?*; **Spec** (`S`,
diff-only) asks *did it build what was asked?* A change can pass one and fail the other, and **a
standards pass masks a spec failure** — code following all forty rules while implementing the wrong
feature reads as clean. Hence `S` never merges with the rest: §Precedence rule 0, and
`references/spec-policy.md` §Axis separation.

| Group | IDs | Owns | Reference |
|---|---|---|---|
| **Architecture** | `R1`–`R40` | the 40-rule standard: the three hard caps, responsibility-based naming, constructor injection with one composition root, registries instead of behaviour-selection branching, typed public APIs, localized constants modules, the dead-code safelist, the anti-overengineering brakes | `references/architecture-standard.md`, whose §Route indexes the per-topic rule files |
| **Structure** | `G1`–`G10` | hard caps, conflict→port→resolvers→context, composition root, cycles, layer rule, responsibility naming, tracebacks, contract suites, dead code, abstraction that pays | `references/graph-policy.md` |
| **House** | `H1`–`H12` | resource naming + its length caps, route shape, outbound URL config, nothing-hardcoded, one auth gate, data conventions, compute choice, code size, terraform comments, deploy gates, working rules | `references/house-policy.md` |
| **Change** | `C1`–`C6` | correctness, regressions, missing error handling, security and data handling, consistency with surrounding code, tests and docs the change owes | `references/change-policy.md` |
| **Spec** | `S1`–`S5` | ★ the second axis: requirements not delivered, behaviour nothing asked for, requirements implemented differently than specified, a spec that is itself wrong, and how anyone would know it works | `references/spec-policy.md` |

`review` runs Architecture + Structure + House and the parts of Change that do not need a diff; **`S`
cannot run** — there is no change to compare a spec to, and the report says `S not run (no diff)`.
`diff` runs Change first, then only the Architecture, Structure and House rules the changed lines can
actually break, then `S` against the spec source found in phase 0. `refactor` runs Architecture as the
standard it restructures to, with Structure as the measurement.

No spec source found ⇒ `S not run (no spec source found)`, stated out loud: a reader who assumes the
request was checked is worse off than one who knows it wasn't.

**Which groups apply to a file is decided by what the file is**, never by hope: `*.tf`, deploy
shell and `infra/` get House; source code gets Architecture + Structure; everything in the diff gets
Change. A Python service repo with a diff and a findable spec gets all five, and the report says so.
`S` is the exception: it is scoped by the *request*, not by file type.

---

## Precedence — when two policies disagree

Real conflicts exist between the groups. Resolve them here, once, rather than in each finding.
Rules 1 and 2 are not this skill's to trade away — they are the standing doctrine, stated in full in
`references/standing-doctrine.md`, and they outrank every group below **and** any convention a repo
has adopted locally. That file's third contract is the output contract, which shapes every report this
skill emits (see §Non-negotiables).

0. **The axes do not compete.** Everything numbered below orders findings *within* the standards axis.
   `S` is not in that order and is never traded against it. Two verdicts, two sections, two "worst
   finding" lines. Full rule, including the one cross-axis duplication this licenses:
   `references/spec-policy.md` §Axis separation.

1. **The global bans win outright.** Never machine-generated certificates or keypairs as an
   authorization mechanism (`H6`); prefer SigV4. No policy below can license one.
   Source: `references/standing-doctrine.md` §2.
2. **Headroom beats tidiness.** An env-scoped name holding one value today, a knob with one mode, a
   per-stage resource pointing at one target — deliberate seams, recorded as `deferred-conflict`,
   never billed as debt, never "simplified" (`G10`, `H12`, `R28`). When you cannot tell headroom from
   debt, **ask** — `references/standing-doctrine.md` §1.
3. **The stricter numeric cap is the one reported; the looser one is named in the same finding.**
   The groups genuinely differ on nesting: Structure caps it at **1** level measured from the
   method body, House at **2**. So depth 3+ is a breach under both and is a `major`; depth 2 is a
   `minor` that cites both numbers and says the repo may be holding the House line deliberately.
   Do not silently pick one and present it as the rule.
4. **`R` and `G` agree on the three caps — 250-line files, 25-line methods, 8-line loop bodies — so
   cite `G` for the measured number and `R` for the remedy.** Where only `R` covers a rule (public API
   discoverability, localized constants, the DI shapes in `references/data-and-wiring.md`), `R` rules
   alone and there is nothing to reconcile.
5. **The repo's own enforced convention beats all four** where it is actually enforced — a linter rule,
   a fitness test, a plan-time assertion. Say which gate enforces it instead of reporting it.
6. **`C` before `R`/`G`/`H` on a diff.** A correctness bug outranks every structural preference in the
   same file. A wrong answer that is beautifully factored is still wrong.

---

## Non-negotiables

1. **Read before ruling.** Never a suggestion from a filename or a grep hit. Open the range.
2. **Measure, don't estimate.** Every number came from a command that ran. A metric no tool
   produced is omitted and listed under `degraded` — never zeroed, never guessed.
3. **Every suggestion has all nine fields** of `specs/suggestion.md`. One with no CONSEQUENCE and
   no SUGGESTION is noise; drop it yourself rather than reporting it.
4. **Cite a rule, not a taste.** `LAW` names the policy ID *and* its source. "Best practice" is not
   a source, and "I would have named it differently" is not a finding.
5. **Suggest, never apply — except in `refactor`.** In `review`/`diff` every SUGGESTION is written as
   an unapplied proposal, and the report says in one line that nothing was changed.
6. **Say what you did not cover.** Languages degraded, directories skipped, groups not run,
   dynamic dispatch not statically resolvable. Every report ends with this.
7. **Never invent the repo's conventions.** Where the policy says "match the closest existing
   pattern", read the pattern first. Consistency with the tree beats the document, and a finding
   that fights a convention the repo follows everywhere is a question, not a suggestion.
8. **One suggestion, one location.** A suggestion needing more than 20 rendered lines is two
   suggestions.
9. **No threshold is quietly weakened.** Apply every relevant rule as written; name any exception you
   take with its rule number and reason. Group `R`'s own sixteen non-negotiables — responsibility
   decides a split, a file name must survive alone, dependencies arrive through the constructor,
   abstraction must pay for itself, simple code stays simple — are in
   `references/architecture-standard.md` §Non-negotiables and apply in every mode that runs `R`.
10. **Never re-report a decision the repo already recorded.** Read `.out-of-scope/` in phase 0 and
    match every candidate finding against it **by concept, not by string**. A match drops the finding
    and lists the concept once under `## Declined` with its file. Believe a recorded decision is now
    wrong? Say so in one line and **ask** — never re-emit the finding, never edit the file to agree
    with yourself. `references/declined.md` is the format and the procedure.

---

## Measurement — use a tool where one exists

Numbers come from commands. The order to try, per metric, is in `jobs/review.md` §2, and every
degradation lands in the report.

- **The countable `R` rules ship with this skill.** Run the bundled linter first, before reading a
  line of code:

  ```bash
  python3 scripts/architecture_lint.py --json <paths>     # or --changed for the dirty worktree
  ```

  It emits `{"findings": [...]}` — file, line, rule, severity, message — exits **1** when any finding
  is a `warning` (the three hard caps) and **0** otherwise. **Treat those findings as already-measured
  ground truth; do not re-count lines or re-eyeball sizes.** It is stdlib-only and never edits code.
  `python3 scripts/test_architecture_lint.py` proves its thresholds still match the prose.
- **Caps and the module graph.** If the `md_codegraph` skill is installed alongside this one, run its
  two measurement scripts, `caps.sh` and `graph.sh` (both take `--root PATH --json`, both emit
  JSON, both exit 0 on violations and 2 only when the scan could not run). Resolve the directory
  once, in phase 0, and record the absolute command in `.policy-review/oracle.json`. Not installed ⇒
  the bundled linter still covers the three caps, the vague names, one-member enums and module state;
  say `graph not measured` in the verdict line, and never claim a cycle count from a lexical sweep.
- **Name lengths.** Composed names are measured with `awk`, per the cap table in
  `references/house-policy.md` §2 — that check is arithmetic and never degrades.
- **The repo's own gates.** `pytest`/`npm test` are read for *what they enforce*, never run for a
  review: a review that executes the repo's test suite has started running its code.

**Rules are never fetched.** Every threshold this skill applies is in its own `references/`, so it
works from a checkout with no network and no sibling skill installed. Only the *graph* measurement is
borrowed, and only when it is already on disk.

---

## Fan-out contract

Heavy reading runs in subagents so bulk output never enters the conversation.

- One agent per policy group at most, launched **in a single message** so they run concurrently.
- **`S` runs as its own agent**, its prompt carrying the spec text plus `references/spec-policy.md` and
  nothing else. An agent holding both the spec and the architecture rules ranks one against the other —
  context isolation is the mechanism that keeps the axes independent.
- Every agent writes its artifact to `.policy-review/<group>.json` and returns **≤25 lines**:
  counts, the worst three locations, the single highest-leverage change. Bulk never returns as text.
- Only read-only agents. `general-purpose` with the group's reference file inlined is the default;
  `codegraph-inspector` and `codegraph-cartographer` are usable for `G` when installed, since
  neither can write outside its artifact directory. **Never `codegraph-surgeon`.**
- Cannot fan out (no `Agent` tool, or the parallel launch fails)? Run the groups **serially** in
  the order `C`, `H`, `R`, `G`, `S`, discarding each group's bulk before the next, and say
  `fan-out unavailable: ran N groups serially` in the verdict line.
- `refactor` does not fan out. One agent editing while another reads the same tree is how a plan and
  its application drift apart.
- The final message is the ≤25-line summary from `specs/suggestion.md` §5 plus one next action.
  Never paste the report.

---

## Artifacts

Two directories, opposite kinds, and the full table plus the end-of-run procedure is
`references/artifacts.md` — **read it before writing the first file, and again before finishing.**

- `.policy-review/` is **scratch**: `scope.json`, `oracle.json`, `<group>.json`, `spec.json`,
  `report.md`, all measured against one sha. `review`/`diff` write nothing else, anywhere. One from a
  different commit is stale and poisons the report: stop and ask.
- **Ending a run means disposing of it.** Promote every `deferred-conflict` into `.out-of-scope/`,
  commit `report.md` into `documentation/` if it still teaches something, then **delete
  `.policy-review/` and say so**. `.gitignore` is not a third exit: ignoring keeps the directory and
  hides it from `git status`, which is how a stale one survives to poison the next review.
- **`.out-of-scope/` is the opposite kind** — read every run, written only on an explicit yes,
  **committed**, and never tidied away. It is durable precisely because `.policy-review/` is not: a
  `deferred-conflict` recorded only there dies with the directory, so the same seam is re-reported
  forever. `references/declined.md`.

---

## Checklist before saying done

- [ ] The right job file was read, and only that one
- [ ] Which groups applied — and which did not — is stated, with the reason
- [ ] `scripts/architecture_lint.py` was run whenever group `R` applied, and its findings are folded in
- [ ] Every number came from a command that ran; unmeasured metrics are in `degraded`
- [ ] Every suggestion has nine fields, one policy ID, one location, and a real remedy
- [ ] Precedence conflicts were resolved per §Precedence, naming both numbers
- [ ] On a diff: the spec source is named or `S not run` says why; `S` got its own section and verdict
- [ ] `.out-of-scope/` was read, matched by concept, suppressions listed; nothing written without a yes
- [ ] Headroom is recorded as `deferred-conflict`, not reported as debt
- [ ] In `review`/`diff`: nothing outside `.policy-review/` was written, and the report says so
- [ ] `.policy-review/` was disposed of per `references/artifacts.md` — headroom promoted first, then
      deleted or committed, never left behind and never `.gitignore`d
- [ ] In `refactor`: the three-bucket plan came first, and the do-not bucket is populated by name
- [ ] The conversation got a ≤25-line summary, one next action, and what it does not cover
