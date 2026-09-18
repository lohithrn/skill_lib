# Job — `diff`: review a change against the standing policy

Read-only. PR-sized: the changed lines, their enclosing functions, and the direct callers of anything
whose signature or behaviour moved. `C` runs first, because a correctness bug outranks every
structural preference in the same file.

This is the only mode that runs **both axes**: the standards groups (`C`, then the `R`/`G`/`H` rules the
change can break) and the spec group `S`, which asks the separate question of whether the change built
what was asked. They are never merged — `SKILL.md` §Precedence rule 0.

Target: `$ARGUMENTS` after the mode token — a git ref, then optionally a spec path.

---

## Phase 0 — Establish what changed

1. `git rev-parse --show-toplevel`, `git rev-parse --short HEAD`, `git status --porcelain`.
2. Pick the base, in this order, and **say which one was used**:
   1. the ref given as an argument;
   2. `git merge-base HEAD origin/main` (or `origin/master`, or the repo's default branch);
   3. `HEAD` itself, when the change is uncommitted worktree edits.
3. The file set:
   - `git diff --stat <base>` and `git diff --numstat <base>` for the shape;
   - `git diff --unified=8 <base>` for the content — **8 lines of context, not 3**, because a
     regression is usually in the line the change did not touch;
   - `git diff --name-status <base>` to separate `A`/`M`/`D`/`R`. A rename with edits is read as
     both.
   - Uncommitted work: the same commands without a base, plus `git status --porcelain` for untracked
     files, which a `git diff` will not show at all.
4. **Read the removed lines.** `C2` is the highest-value group here and it lives entirely in the `-`
   side of the hunks.
5. Direct importers: for each changed file, `Grep` the tree for imports of it, and read the call
   sites of any signature that moved. Cap this at the 20 highest fan-in files and say so if it binds.
6. Write `.policy-review/scope.json`: base and how it was chosen, files by status, added/removed
   counts, importers read, groups applying.

**Fail here, not inside two parallel agents.** Before anything fans out, confirm the base ref resolves
(`git rev-parse <base>`) and the diff is non-empty. A bad ref discovered by four subagents costs four
wasted runs and produces four confusing reports.

Nothing changed? Say so in one line and stop. Do not fall through to a whole-tree review.

---

## Phase 0b — The spec source, and the declined KB

Two reads that decide what phases 2 and 3 are allowed to say. Both happen before any finding exists.

1. **Find the spec**, per `references/spec-policy.md` §Phase 0 addition, stopping at the first hit: a
   path in `$ARGUMENTS` → a spec file in `docs/`, `specs/`, `.scratch/`, `adr/` matching the branch or
   changed area → the commit message bodies from `git log <base>..HEAD` → an unfetchable issue
   reference. Record which in `.policy-review/spec.json`, with its path and requirement count.
   - An issue number with no local text is a **degradation**: this skill has no network by design, so
     record `S degraded: issue #N referenced, not readable`, run `S` against the commit messages, and
     say so. Never guess what an issue said from its number.
   - Nothing found ⇒ `S` does not run. `S not run (no spec source found)` in Groups run, `SPEC-UNKNOWN`
     as the spec verdict. An absent spec is a fact about the change, not a finding against it.
2. **Read `.out-of-scope/`** if it exists — every file, per `references/declined.md` §2 — and record
   the concept count in `scope.json`. Every candidate finding in phase 3 is matched against it by
   concept, not by string.

Neither read is optional, and neither invents anything: no spec file is created, and `.out-of-scope/`
is never created unprompted.

---

## Phase 1 — Which groups, on which files

| File in the diff | Groups |
|---|---|
| source code | `C` then `G`, but only the `G` rules the changed lines can break |
| `*.tf`, deploy shell, `infra/`, `*_config.sh` | `C` then `H` |
| a composed name, route, or URL anywhere in source | `H` as well |
| docs, fixtures, lock files | `C6` only — and a lock-file diff is not a finding |
| every changed file the spec speaks to | `S` as well, scoped by the *request* rather than the file type |

`G` on a diff is **not** a tree audit: only caps the change breached or worsened, a conflict the
change added a third branch to, a cycle the change created, a new sideways edge, a port the change
added with no contract suite. A file that was already 300 lines and got one line added is
`pre-existing`, named once in the report, not billed to this change.

Measurement uses the same order as `jobs/review.md` §2, scoped to the changed files. Degradations
land in the report identically.

---

## Phase 2 — The change review itself (`C1`–`C6`)

Work `references/change-policy.md` in order. Per hunk, not per file:

1. **`C1` correctness** — for every changed function, name the inputs it can receive and find one it
   mishandles. Empty, null, zero, negative, one element, the maximum, the exact boundary, a
   duplicate, a unicode name. A `Break` CONSEQUENCE needs a reproducing input; without one it is
   `suspected` and `minor`.
2. **`C2` regressions** — every removed guard, `try`, timeout, validation, branch, default, env var
   and payload key. Every signature change against every caller found in phase 0.
3. **`C3` error handling** — new failure paths with no handler; a new `except` that swallows.
4. **`C4` security** — secrets, machine-generated certs or keypairs used as auth (`blocker`, always),
   injection, `verify=False`, an auth check after the work, a tenant id from the wrong source,
   wildcard IAM, PII in a log.
5. **`C5` / `C6` consistency and tests** — the existing helper the change re-implemented, by path;
   the test file and the case the change owes, by name.

**The recipe this group inherits, verbatim in spirit:** comment on **exact line ranges**, never
per-file summaries; **fewer, higher-signal** findings beat exhaustive ones; if two findings share one
cause, report the cause once at its site and list the other locations inside SYMPTOM; **do not modify
files.**

Heavy reading fans out per `SKILL.md` §Fan-out contract — one agent per group, single message,
`.policy-review/<group>.json` as the only writable path, ≤25 lines back. Serial fallback order is
`C`, `H`, `G`, `S`.

---

## Phase 2b — The spec review (`S1`–`S5`)

Runs **in the same fan-out message** as the standards groups, in its own agent, whose prompt carries the
spec text and `references/spec-policy.md` and nothing else. That isolation is the mechanism: an agent
holding both the spec and the architecture rules ranks one against the other, which §Precedence rule 0
forbids.

Enumerate the requirements first — number them, from the spec's own words — then walk the diff against
the list:

1. **`S1` gaps** — a requirement with no code. Say where you looked; `LOCATION` is the line the check
   belongs above, never the spec file.
2. **`S2` unrequested behaviour** — anything in the diff no requirement names. Check `.out-of-scope/`
   first: rejected behaviour now present is a `blocker` reversal, not creep. Tests are never creep.
3. **`S3` divergence** — present, plausible, wrong. Values, inverted conditions, right behaviour at the
   wrong time. Quote both sides. This is the group's most expensive finding.
4. **`S4` the spec is the problem** — contradictory or ambiguous requirements, a spec that changed after
   the code. Check the dates before blaming the author, and never pick a winner between two
   requirements: that is a person's call.
5. **`S5` observables** — a stated requirement with no test asserting it, or a test written from the
   code rather than the spec and therefore unable to fail.

Return the requirement roll-up — `met / gapped / divergent / untested` out of N — because that count is
what the spec verdict is computed from.

---

## Phase 3 — Merge, precedence, verdict

1. De-duplicate **within each axis, never across them**: one symptom, one suggestion, under the policy
   whose CONSEQUENCE is worse. A symptom that is both an `S3` divergence and a `C1` bug survives as two
   entries, each naming the other's ID — the documented exception, and the only one.
2. **Drop every finding matching a concept in `.out-of-scope/`** (`references/declined.md` §2), matched
   by concept rather than string. Each suppressed concept gets one line under `## Declined` with its
   file. A recorded decision you believe is now wrong is a one-line question, never a re-emitted
   finding.
3. Apply `SKILL.md` §Precedence — bans first, headroom untouched, the stricter cap reported with the
   looser one named, the repo's enforced gate instead of a finding, and **`C` above `G`/`H`** in the
   same file. All of that orders the standards axis only; `S` is not in it.
4. Separate **introduced** from **pre-existing**. This is the split the author actually needs: a
   pre-existing breach the change merely stood next to is listed once, under a `pre-existing` heading,
   and does not count toward the verdict.
5. Drop the automatic non-suggestions (`specs/suggestion.md` §3). A lock-file change, a formatting-only
   hunk the repo's formatter produced, and a comment rephrasing are not findings.
6. Every seam the change opens deliberately — an env-scoped name with one value, a knob with one mode,
   a Context field nothing reads yet — goes to **Deferred conflicts**. Never billed. Offer once to
   record confirmed headroom in `.out-of-scope/` so the next run does not re-ask; write nothing without
   a yes.
7. **Two verdicts** per `specs/suggestion.md` §6 — standards, computed over the **introduced** set only,
   and spec, computed from the requirement roll-up. Print both, always, even when one axis did not run.
   Never collapse them into one word.

---

## Phase 4 — Report and summary

1. `.policy-review/report.md`, section order per `specs/suggestion.md` §4, with these additions for
   this mode: the base ref and how it was chosen goes in **Groups run**, a `## Pre-existing` section
   sits after `## Change (C)`, and `## Spec (S)` follows it — its own section, never folded upward.
2. Return the ≤25-line summary of `specs/suggestion.md` §5, with the standards counts split
   `introduced / pre-existing`, **both verdicts**, and the worst finding **per axis**. One next action,
   naming the cheapest blocker on each axis that has one.
3. One line: nothing outside `.policy-review/` was written — or, if the user said yes to recording a
   declined finding, which `.out-of-scope/` file was written and that it belongs in their next commit.

## Refusals

- Asked to fix, apply, amend, or push: no. This skill has no apply path and never mutates git.
- Asked to approve or merge: no. It produces a verdict and suggestions; approving is a person's job.
- Asked to review a diff it cannot see (a ref that does not exist, a shallow clone with no merge
  base): say which command failed and ask for a base ref. Do not review `HEAD` and call it a diff.
- Asked to run the repo's tests to check the change: no. Read what they enforce; running them
  executes the code under review.
- Asked to review against an issue this skill cannot read (`#123`, a tracker URL): say so and ask for
  the text or a path. Run `S` degraded against the commit messages if there are any. **Never
  reconstruct a requirement from an issue number** — an invented spec produces `S` findings that are
  confidently wrong, which is worse than `SPEC-UNKNOWN`.
- Asked to write `.out-of-scope/` as part of the review itself: no. It is written only after an explicit
  yes to an explicit offer, and it is a tracked file in the user's repo.
