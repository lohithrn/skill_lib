---
name: md_policy-code-review
description: Review a codebase or a diff against the whole standing policy at once — CodeGraph structure (hard caps, conflict→port→resolvers→context, one composition root, no cycles, tracebacks, contract suites), the house conventions (<prefix>_<resource_role>_<company> naming and its 64-char caps, route shape, nothing-hardcoded, one auth gate, epoch-ms data rules, deploy gates), and ordinary change review (correctness, regressions, security, tests). Emits suggestions with file:line and a named rule. Never edits the tree.
when_to_use: Only when explicitly invoked as /policy-code-review. Never auto-trigger.
disable-model-invocation: true
argument-hint: "nothing — or [review|diff] [path|git-ref] to force a mode"
allowed-tools: Read, Grep, Glob, Write, TodoWrite, Agent, Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(git rev-parse:*), Bash(git ls-files:*), Bash(git show:*), Bash(mkdir:*), Bash(wc:*), Bash(awk:*), Bash(bash:*)
---

# /policy-code-review

A router with one conflict to resolve: **which policy groups apply to what the user pointed at, and
what should change?** No rule text lives here — the rules are in `references/`, the phases in
`jobs/`, the output shape in `specs/`. Read the one you need.

## The gate — read this first

**This skill never edits the tree.** Not once, not behind a flag, not "while I was in there".

- The only writable location is `.policy-review/` in the analysed repo. Everything else is read.
- No `Edit` tool is granted at all. `Write` exists for the artifacts and for nothing else.
- Never `git add`, `commit`, `push`, `checkout`, `stash`, branch, tag, or revert. Never run a
  formatter, a codemod, or a linter's `--fix`.
- Never call a subagent that can write source. If `codegraph-surgeon` is installed, it is **out of
  bounds here** — this skill has no apply path to hand a slice to.
- Every output is a **suggestion**: what to change, where, why, and what it costs. The user applies
  it, or does not. `specs/suggestion.md` is the contract.
- The `Bash` grant is wider than the phases need **on purpose**: measurement scripts live at paths
  only resolvable at run time. What stops an edit is this gate, not a missing tool.

## Route

Parse `$ARGUMENTS`. First token is the mode, rest is the target. An unrecognised first token is a
target, not an error. Read the one job file in that row and follow it; do not read the other.

| Invocation | Job file | Scope | Edits? |
|---|---|---|---|
| `/policy-code-review` | `jobs/diff.md` if the worktree is dirty or the branch is ahead, else `jobs/review.md` | the change, else the repo | no |
| `/policy-code-review review [path]` | `jobs/review.md` | whole tree at `path` (default: repo root) | no |
| `/policy-code-review diff [ref]` | `jobs/diff.md` | changed files vs `ref` (default: the merge base with the main branch) plus their direct importers | no |

State which case was found and the job it selected in one line before starting.

---

## The three policy groups

Every suggestion cites exactly one policy ID from one of these. The IDs are the contract between
this file, the report, and anyone arguing with a finding.

| Group | IDs | Owns | Reference |
|---|---|---|---|
| **Structure** | `G1`–`G10` | hard caps, conflict→port→resolvers→context, composition root, cycles, layer rule, responsibility naming, tracebacks, contract suites, dead code, abstraction that pays | `references/graph-policy.md` |
| **House** | `H1`–`H12` | resource naming + its length caps, route shape, outbound URL config, nothing-hardcoded, one auth gate, data conventions, compute choice, code size, terraform comments, deploy gates, working rules | `references/house-policy.md` |
| **Change** | `C1`–`C6` | correctness, regressions, missing error handling, security and data handling, consistency with surrounding code, tests and docs the change owes | `references/change-policy.md` |

`review` runs Structure + House and the parts of Change that do not need a diff. `diff` runs Change
first, then only the Structure and House rules the changed lines can actually break.

**Which groups apply to a file is decided by what the file is**, never by hope: `*.tf`, deploy
shell and `infra/` get House; source code gets Structure; everything in the diff gets Change. A
Python service repo gets all three, and the report says so.

---

## Precedence — when two policies disagree

Real conflicts exist between the groups. Resolve them here, once, rather than in each finding.

1. **The global bans win outright.** Never machine-generated certificates or keypairs as an
   authorization mechanism (`H6`); prefer SigV4. No policy below can license one.
2. **Headroom beats tidiness.** An env-scoped name holding one value today, a knob with one mode, a
   per-stage resource pointing at one target — deliberate seams, recorded as `deferred-conflict`,
   never billed as debt, never "simplified" (`G10`, `H12`).
3. **The stricter numeric cap is the one reported; the looser one is named in the same finding.**
   The two groups genuinely differ on nesting: Structure caps it at **1** level measured from the
   method body, House at **2**. So depth 3+ is a breach under both and is a `major`; depth 2 is a
   `minor` that cites both numbers and says the repo may be holding the House line deliberately.
   Do not silently pick one and present it as the rule.
4. **The repo's own enforced convention beats both** where it is actually enforced — a linter rule,
   a fitness test, a plan-time assertion. Say which gate enforces it instead of reporting it.
5. **`C` before `G`/`H` on a diff.** A correctness bug outranks every structural preference in the
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
5. **Suggest, never apply.** Every SUGGESTION is written as an unapplied proposal, and the report
   says in one line that nothing was changed.
6. **Say what you did not cover.** Languages degraded, directories skipped, groups not run,
   dynamic dispatch not statically resolvable. Every report ends with this.
7. **Never invent the repo's conventions.** Where the policy says "match the closest existing
   pattern", read the pattern first. Consistency with the tree beats the document, and a finding
   that fights a convention the repo follows everywhere is a question, not a suggestion.
8. **One suggestion, one location.** A suggestion needing more than 20 rendered lines is two
   suggestions.

---

## Measurement — use a tool where one exists

Numbers come from commands. The order to try, per metric, is in `jobs/review.md` §2, and every
degradation lands in the report.

- **Caps and the module graph.** If the `md_codegraph` skill is installed alongside this one, run its
  two measurement scripts, `caps.sh` and `graph.sh` (both take `--root PATH --json`, both emit
  JSON, both exit 0 on violations and 2 only when the scan could not run). Resolve the directory
  once, in
  phase 0, and record the absolute command in `.policy-review/oracle.json`. Not installed ⇒ fall
  back to `wc -l`, `awk` and `grep` for the line-and-nesting caps, say `graph not measured` in the
  verdict line, and never claim a cycle count from a lexical sweep.
- **Name lengths.** Composed names are measured with `awk`, per the cap table in
  `references/house-policy.md` §2 — that check is arithmetic and never degrades.
- **The repo's own gates.** `pytest`/`npm test` are read for *what they enforce*, never run for a
  review: a review that executes the repo's test suite has started running its code.

**Rules are never fetched.** Every threshold this skill applies is in its own `references/`, so it
works from a checkout with no network and no sibling skill installed. Only the *measurement* is
borrowed, and only when it is already on disk.

---

## Fan-out contract

Heavy reading runs in subagents so bulk output never enters the conversation.

- One agent per policy group at most, launched **in a single message** so they run concurrently.
- Every agent writes its artifact to `.policy-review/<group>.json` and returns **≤25 lines**:
  counts, the worst three locations, the single highest-leverage change. Bulk never returns as text.
- Only read-only agents. `general-purpose` with the group's reference file inlined is the default;
  `codegraph-inspector` and `codegraph-cartographer` are usable for `G` when installed, since
  neither can write outside its artifact directory. **Never `codegraph-surgeon`.**
- Cannot fan out (no `Agent` tool, or the parallel launch fails)? Run the groups **serially** in
  the order `C`, `H`, `G`, discarding each group's bulk before the next, and say
  `fan-out unavailable: ran N groups serially` in the verdict line.
- The final message is the ≤25-line summary from `specs/suggestion.md` §5 plus one next action.
  Never paste the report.

---

## Artifacts

Everything lands in `.policy-review/` in the analysed repo, and nothing else is written:

| File | Contents |
|---|---|
| `.policy-review/scope.json` | languages, entry points, exclusions, which groups apply and why |
| `.policy-review/oracle.json` | the exact command behind every number, and whether it ran |
| `.policy-review/<group>.json` | one per group run: `G`, `H`, `C` |
| `.policy-review/report.md` | the full report, section order per `specs/suggestion.md` §4 |

A `.policy-review/` from a different commit is stale and poisons the report: stop and ask.

---

## Checklist before saying done

- [ ] The right job file was read, and only that one
- [ ] Which groups applied — and which did not — is stated, with the reason
- [ ] Every number came from a command that ran; unmeasured metrics are in `degraded`
- [ ] Every suggestion has nine fields, one policy ID, one location, and a real remedy
- [ ] Precedence conflicts were resolved per §Precedence, naming both numbers
- [ ] Headroom is recorded as `deferred-conflict`, not reported as debt
- [ ] Nothing outside `.policy-review/` was written, and the report says so
- [ ] The conversation got a ≤25-line summary, one next action, and what it does not cover
