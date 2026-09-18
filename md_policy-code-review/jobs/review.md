# Job — `review`: audit a whole tree against the standing policy

Read-only. Every phase below writes only inside `.policy-review/`. If a phase cannot measure
something, it records the degradation and continues — it never guesses a number and never edits.

Target: `$ARGUMENTS` after the mode token, default the repo root.

---

## Phase 0 — Scope, and what the tools are

1. `git rev-parse --show-toplevel` and `git rev-parse --short HEAD`. Not a repo? Continue with the
   given path and write `commit: none (not a git repo)` — the report needs a stamp either way.
2. `git ls-files` (or `Glob` outside a repo) → the file list. **Exclude** `.git/`,
   `node_modules/`, `venv/`, `.venv/`, `dist/`, `build/`, `target/`, `.terraform/`, `vendor/`,
   generated and minified files, and anything the repo's own ignore files exclude. Record the
   exclusions; a report that silently skipped half the tree is worse than no report.
3. Classify. This decides which groups run, and it is decided by **what the files are**:

   | Present | Group |
   |---|---|
   | source in any language | `G` structure |
   | `*.tf`, `infra/`, deploy shell, `*_config.sh` | `H` house |
   | always, on the file set the other groups already read | `C` change (the diff-free parts of `C1`, `C3`, `C4`, `C5`, `C6`) |

   A group with no matching files does not run, and the verdict says
   `verdict excludes H (no infra in scope)`. It never passes by default.
4. Resolve the measurement tools **once**, and record the absolute command for each in
   `.policy-review/oracle.json` with an `ok`/`absent` flag:
   - Look for the `md_codegraph` skill's `caps.sh` and `graph.sh` next to this skill — the sibling skill
     directory under the same plugin/skills root, then the host's skills directory. Probe with
     `--help` before trusting one. Absent, non-executable, or exit 2 ⇒ `absent`, and the fallbacks in
     §2 apply.
   - Look for a native graph tool the repo already depends on: `grimp`, `import-linter`,
     `dependency-cruiser`, `jdeps`, `go list`. Only if it is already in the repo's manifest.
   - Read the repo's linter config (`ruff.toml`, `.eslintrc*`, `pmd*.xml`, `setup.cfg`,
     `pyproject.toml`) for rules it **already enforces**. An enforced rule changes the finding into a
     note naming the gate (`SKILL.md` §Precedence rule 4).
5. **Read `.out-of-scope/`** if it is there — every file, per `references/declined.md` §2 — and record
   the concept count in `scope.json`. Phase 4 matches every candidate finding against it by concept,
   not by string. It is never created unprompted, and its absence is not a finding.
6. Write `.policy-review/scope.json`: languages with file counts, entry points, exclusions, groups
   applying and why, tool table, declined-concept count.
7. Print one line: target, commit, file count, groups, and which measurements are degraded. Include
   `S not run (no diff)` — this mode has no change to compare a spec to, so the spec verdict is
   `SPEC-UNKNOWN` and saying so is not optional.

A `.policy-review/` from another commit is stale — stop and ask before overwriting it. `.out-of-scope/`
is the opposite: durable, committed, and read on every run precisely because this directory is not.

---

## Phase 2 — Measurement order, per metric

Referenced from `SKILL.md` §Measurement. Try in order; the first that runs is the number, and the
one that ran is what `oracle.json` records. **A metric no command produced is printed as its
absence, never as `0`.**

| Metric | 1st | 2nd | 3rd | If none |
|---|---|---|---|---|
| File length | `md_codegraph` `caps.sh --json` | `wc -l` over the classified code files | — | never degrades |
| Method / loop-body length, nesting, `else` count, params, public members | `caps.sh --json` | `awk` per language on `def`/`function`/method starts, counting leading whitespace for depth | `Grep -n` per pattern, reading each hit | report `caps partially measured` and list the languages skipped |
| Module cycles, fan-in/out, layer edges | `graph.sh --json --cycles` | a native tool already in the repo's manifest | — | **`graph not measured`** in the verdict line. A lexical import sweep may report *edges*, and may never claim a cycle count. `0 edges with unresolved imports is a failed scan`, not an acyclic repo |
| Composed name lengths (`H2`) | `awk` over `naming.tf` `locals`, expanding `prefix`/slug defaults from `variables.tf` | — | — | arithmetic; never degrades |
| Hardcoded account ids, secrets | `Grep` for 12-digit runs and key patterns across the tree | — | — | never degrades |
| What the repo enforces | read the linter/fitness config | — | — | say `gates not read` |

Nesting is measured **from the method body**, so `for` + `if` is depth 1 (`G1`). File length is
measured on code files only.

Never run the repo's test suite, its deploy script, `terraform`, or any of its own entry points. A
review that executes the repo's code has stopped being a review.

---

## Phase 3 — Fan out, one agent per group

Launch the applicable groups **in a single message** so they run concurrently. Per
`SKILL.md` §Fan-out contract:

- Give each agent: the absolute repo root, the file list for its group, the absolute path to its
  reference file, the absolute path to `specs/suggestion.md`, the resolved commands from
  `oracle.json`, and `.policy-review/<group>.json` as its **only** writable path.
- Tell each agent in its prompt: **read-only, suggestions only, nine fields, no edits, no `git`
  mutation.** Read-only agent types only. Never `codegraph-surgeon`.
- Each returns **≤25 lines**: counts, the worst three locations, the one highest-leverage change.
- No `Agent` tool, or the launch fails? Run serially in the order `C`, `H`, `G`, discarding each
  group's bulk output before the next, and note `fan-out unavailable: ran N groups serially`.

What each group does with its file set:

| Group | Reads | Produces |
|---|---|---|
| `G` | every code file, `caps.sh`/`graph.sh` JSON | cap breaches with measured numbers, conflict sites worth promoting, composition roots found, cycles, sideways-edge folder pairs, ports without contract suites, misleading names |
| `H` | `*.tf`, deploy shell, `infra/`, and any source composing a name/route/URL | composed-name lengths against their caps, inline-composed names, hardcoded ids, `ENVIRONMENT` defaults, route shape, auth gate count, epoch-ms/`Decimal` boundaries, the 10 deploy gates |
| `C` | the same files, without a diff | unhandled inputs, swallowed exceptions, secrets, verification disabled, duplicated helpers, ports and branches with no test |

---

## Phase 4 — Merge, de-duplicate, resolve precedence

1. Load the three artifacts. **One symptom, one suggestion**: the same line reported by two groups is
   merged under the policy whose CONSEQUENCE is worse, with the other named inside `LAW`.
2. Apply `SKILL.md` §Precedence in order — bans, headroom, stricter cap with the looser one named,
   the repo's enforced gate, `C` over `G`/`H`.
3. Drop every automatic non-suggestion (`specs/suggestion.md` §3), **including every concept already
   recorded in `.out-of-scope/`** — matched by concept, not by string, and listed once under
   `## Declined` with its file. Move every seam to the **Deferred conflicts** inventory: recorded,
   never billed, never counted in the verdict. Offer once to make a confirmed seam durable in
   `.out-of-scope/`; write nothing without a yes (`references/declined.md` §4).
4. Drop any suggestion missing a field. Nine fields, or it does not ship. A deletion suggestion with
   no `EVIDENCE` is dropped or re-worded as `suspicious` per `G9`.
5. Collapse mass measurements into one finding each with the count and the worst location: illegal
   layer edges are a distance-to-target measurement, not N findings (`G5`).
6. Compute the verdict per `specs/suggestion.md` §6. **Computed, never chosen** — keep the
   arithmetic.

---

## Phase 5 — Report and summary

1. Write `.policy-review/report.md` in the exact section order of `specs/suggestion.md` §4. Sections
   with nothing to say print `none`, so absence is trustworthy. The **Cap table** carries every cap,
   its measured worst, and how many files are over — that table is what makes a re-run comparable.
2. Return the ≤25-line summary of `specs/suggestion.md` §5 to the conversation, plus one next action.
   Never paste the report.
3. State in one line that nothing outside `.policy-review/` was written.

## Refusals

- Asked to fix, apply, or "just do it": no. Point at the report and offer to write a slice plan into
  `.policy-review/` as text. Applying is another skill's job, and this one has no apply path.
- Asked to skip measurement and rule from experience: no. `SKILL.md` non-negotiable 2.
- Asked to review with no target and no repo: ask for a path. Do not scan the home directory.
- Asked to review a tree containing credentials: report them as `C4` blockers by **location**, never
  by value, and never copy a secret into `.policy-review/`.
