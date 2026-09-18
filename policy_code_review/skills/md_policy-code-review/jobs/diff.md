# Job — `diff`: review a change against the standing policy

Read-only. PR-sized: the changed lines, their enclosing functions, and the direct callers of anything
whose signature or behaviour moved. `C` runs first, because a correctness bug outranks every
structural preference in the same file.

Target: `$ARGUMENTS` after the mode token — a git ref, default the merge base with the main branch.

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

Nothing changed? Say so in one line and stop. Do not fall through to a whole-tree review.

---

## Phase 1 — Which groups, on which files

| File in the diff | Groups |
|---|---|
| source code | `C` then `G`, but only the `G` rules the changed lines can break |
| `*.tf`, deploy shell, `infra/`, `*_config.sh` | `C` then `H` |
| a composed name, route, or URL anywhere in source | `H` as well |
| docs, fixtures, lock files | `C6` only — and a lock-file diff is not a finding |

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
`C`, `H`, `G`.

---

## Phase 3 — Merge, precedence, verdict

1. De-duplicate: one symptom, one suggestion, under the policy whose CONSEQUENCE is worse.
2. Apply `SKILL.md` §Precedence — bans first, headroom untouched, the stricter cap reported with the
   looser one named, the repo's enforced gate instead of a finding, and **`C` above `G`/`H`** in the
   same file.
3. Separate **introduced** from **pre-existing**. This is the split the author actually needs: a
   pre-existing breach the change merely stood next to is listed once, under a `pre-existing` heading,
   and does not count toward the verdict.
4. Drop the automatic non-suggestions (`specs/suggestion.md` §3). A lock-file change, a formatting-only
   hunk the repo's formatter produced, and a comment rephrasing are not findings.
5. Every seam the change opens deliberately — an env-scoped name with one value, a knob with one mode,
   a Context field nothing reads yet — goes to **Deferred conflicts**. Never billed.
6. Verdict per `specs/suggestion.md` §6, computed over the **introduced** set only, and say so.

---

## Phase 4 — Report and summary

1. `.policy-review/report.md`, section order per `specs/suggestion.md` §4, with two additions for
   this mode: the base ref and how it was chosen goes in **Groups run**, and a `## Pre-existing`
   section sits after `## Change (C)`.
2. Return the ≤25-line summary of `specs/suggestion.md` §5, with the counts split
   `introduced / pre-existing`, plus one next action naming the cheapest blocker.
3. One line: nothing outside `.policy-review/` was written.

## Refusals

- Asked to fix, apply, amend, or push: no. This skill has no apply path and never mutates git.
- Asked to approve or merge: no. It produces a verdict and suggestions; approving is a person's job.
- Asked to review a diff it cannot see (a ref that does not exist, a shallow clone with no merge
  base): say which command failed and ask for a base ref. Do not review `HEAD` and call it a diff.
- Asked to run the repo's tests to check the change: no. Read what they enforce; running them
  executes the code under review.
