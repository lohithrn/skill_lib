# Output contract — a suggestion

**The Iron Law: nothing is reported unless it has all nine fields. A suggestion with no
CONSEQUENCE and no SUGGESTION is not a suggestion — it is noise, and it is dropped.**

Order is fixed. Fields are never omitted, never merged, never reordered.

```
ID           PCR-<GROUP><nn>-<nnn>          e.g. PCR-H02-004
POLICY       the one policy ID this cites — R1..R40 | G1..G10 | H1..H12 | C1..C6 | S1..S5
LOCATION     path/to/file.ext:startLine-endLine
SYMPTOM      what is literally in the code, in one sentence, no judgement
LAW          the named rule plus its source — "IAM role name cap 64 (AWS quota; house policy H2)"
CONSEQUENCE  what breaks, or what cannot change, because of it
SUGGESTION   the exact change, with real names and real paths — and it is NOT applied
EFFORT       S (under an hour) | M (under a day) | L (more than a day)
SEVERITY     blocker | major | minor | deferred-conflict
```

Two kinds carry a **mandatory tenth field**:

- **A suggestion to delete anything** — an `EVIDENCE` line listing the searches that ran and the
  dynamic-usage checks cleared (entry points, reflection, registries, config dispatch, generated
  code, migrations). Without it the suggestion is dropped: a wrong deletion causes an outage, not a
  bad review.
- **A naming suggestion** — SYMPTOM must state **how the name misleads a reader who sees it alone**,
  in a stack frame, an import line, a log line or the AWS console. "I would have named it
  differently" is not a finding.

---

## 1. Field rules

### ID
`PCR-` + the policy ID with a zero-padded number + a sequence, stable within a run. Referenced by
the report and by any verification verdict. Never reused.

### POLICY
Exactly one ID. A symptom that breaks two policies is reported once, under the one whose
CONSEQUENCE is worse, with the second named inside LAW. Two IDs in the POLICY field means the
suggestion has not been thought through.

**The one exception is across the two axes.** A symptom that is both a spec divergence and a standards
breach — a threshold that contradicts the spec *and* is a correctness bug — is reported **twice**, once
as `S` and once under the standards group, each naming the other's ID in LAW. De-duplication runs
within an axis, never across it (`references/spec-policy.md` §Axis separation). It still never means two
IDs in one POLICY field.

### LOCATION
**A line range, not a file.** `infra/terraform/naming.tf` is not a location. For a name-length
breach the location is the line that composes the name, not the resource that consumes it. If the
symptom spans files, pick the primary site and list the others inside SYMPTOM.

### SYMPTOM
What is literally there. No adjectives, no "messy", no "should". Include the measured number
whenever a cap is involved — `78 characters against a cap of 64`, `54 lines`, `3 nesting levels`,
`fan-in 31`. A reader must be able to verify the symptom without agreeing with the judgement.

### LAW
A **named** rule plus its source. Acceptable: a policy ID from this skill's `references/`, a
published rule with its book or paper (Fowler *Refactoring* 2nd ed., Martin *Clean Code* `G23`-style
codes, Bay *Object Calisthenics*, Page-Jones connascence, Seemann DI anti-patterns), an AWS service
quota, or a linter rule ID that already exists in the repo (`ruff TRY400`, PMD
`PreserveStackTrace`, `errcheck`, `eslint no-else-return`). Prefer the repo's own linter ID over a
bespoke rule when both apply.

"This violates SOLID" is not a law — say which letter and why. "Best practice" is not a source.

### CONSEQUENCE
The concrete failure predicted. One of these shapes, or the suggestion is dropped:

- **Fails at apply/deploy time** — "this name is 78 characters; `terraform apply` rejects it after a
  clean plan, halfway through the deploy."
- **Change amplification** — "adding a fifth tenant requires edits in N unrelated files."
- **Silent divergence** — "the two sites already disagree on the `None` case."
- **Silent corruption** — "two tenants whose names differ past the cut map onto one schedule group."
- **Untestable** — "this cannot be unit-tested without a live Cognito pool."
- **Invisible failure** — "the exception is swallowed, so the retry budget is spent with nothing in
  the log."
- **Foreclosed** — "the second region named in the ticket cannot be added without re-plumbing."
- **Break** — "input Q produces wrong output R", with a reproducing case.
- **Unmet requirement** — "the spec's line N asks for X; input Q takes the path that does not do X."
- **Unrequested scope** — "N files changed for a requirement that named one; a reviewer cannot tell
  which hunks implement the request." The cost is review integrity and revert granularity — never
  "the diff is large".
- **Divergence from spec** — "the spec says at most 3 retries; the loop has no ceiling", quoting both.

Aesthetics is not a consequence. If CONSEQUENCE would read "harder to read", drop it.

### SUGGESTION
The change, spelled out, and **explicitly unapplied**. Real names, real paths, no "consider
extracting an interface". A structural suggestion names the conflict as a question, the port file
and signature, the Context type and its fields, every resolver file, the selector and where it
lives, the contract-suite path, and what the change **deletes**. A naming suggestion gives the new
name and every call site that has to move with it. A `Deletes:` line is mandatory wherever
something is replaced: a suggestion that only adds is suspect.

### EFFORT
`S` under an hour · `M` under a day · `L` more than a day. Estimated from the number of files the
SUGGESTION touches and whether tests exist to cover them. This is what makes the report actionable
instead of merely correct: it is the field that decides what gets done today.

### SEVERITY

| Severity | Meaning | Report placement |
|---|---|---|
| **blocker** | fails at deploy or apply time, corrupts data, removes authorization, makes a unit untestable, or a graph cycle | first, always |
| **major** | change amplification across ≥2 files, or a hard cap breached by ≥2× | its own entry |
| **minor** | a single-site cap breach, local, no cross-file consequence | batched by file |
| **deferred-conflict** | a real seam deliberately left open | recorded, never fixed |

---

## 2. `deferred-conflict` — recording headroom without billing for it

Documented headroom. It appears in the inventory, never in the suggestion list, and never counts
toward the verdict.

```
ID           PCR-H01-019
POLICY       H1
LOCATION     infra/terraform/variables.tf:12-19
SYMPTOM      `scheduler_slug` and `role_slug` hold the same value, "cronsched".
LAW          — (none broken)
CONSEQUENCE  — (none; the two caps are independent and the seam permits shortening one alone)
SUGGESTION   none. Give them different values when one namespace's cap actually bites.
EFFORT       —
SEVERITY     deferred-conflict
```

## 3. Automatic non-suggestions — refuse to emit these

1. "The current value is the loosest possible."
2. "You collapsed X into one value" — env-scoped names sharing a value, a knob with one mode, a
   per-stage resource pointing at one target. All deliberate seams.
3. A single-implementation interface at an I/O boundary — justified by testability alone.
4. A registry `match`/`switch` in the composition root — data, not control flow.
5. An exhaustive match over a sealed set whose totality the compiler checks.
6. Duplication with fewer than three occurrences (Rule of Three).
7. A `# TODO` — a deferred-conflict marker, not debt.
8. Style the repo's own linter permits, unless a hard cap breaks.
9. A convention the repo follows everywhere that merely differs from this policy — ask instead.
10. Anything found only by pattern-matching a file name rather than reading the code.
11. A comment, a docstring or a variable name you would have phrased differently.
12. A concept already recorded in `.out-of-scope/` — matched by concept, not by string. Dropped from
    the suggestion list and named once under `## Declined` with its file (`references/declined.md`).
13. A requirement the spec defers by name, and a test as scope creep. Both are `S`-specific and both
    are never findings (`references/spec-policy.md` §Automatic non-findings).

---

## 4. The report — `.policy-review/report.md`, in this section order

Sections with nothing to say print `none`. Never dropped, so absence is trustworthy.

```
# Policy review — <target> @ <commit>

## Verdict            two lines — standards, then spec. Computed per §6, with the arithmetic
## Groups run         which of R/G/H/C/S ran, on what file set, and why the others did not
## Spec source        the spec, how it was found, whether it was readable — or why S did not run
## Measurement        every number's command, and whether it ran green — from oracle.json
## Structure (G)      suggestions, blockers first
## House (H)          suggestions, blockers first
## Change (C)         suggestions, blockers first
## Spec (S)           its own axis — never merged with the three above
## Cap table          | policy | cap | worst measured | files over | IDs |
## Deferred conflicts the headroom inventory — recorded, not billed
## Declined           concepts suppressed by .out-of-scope/, one line each with its file
## Nothing was applied one line, always present, naming .policy-review/ as the only write
## What this does NOT cover  languages degraded, paths excluded, groups skipped, dynamic dispatch
```

Order within a group: blockers → majors → minors (batched by file) → nothing else. Within a
severity, ascending EFFORT so the cheapest fix of equal severity is first.

`## Spec (S)` is ordered the same way but **ranked only against itself**. It is not folded into the
three sections above it and its findings do not compete with theirs for the blocker slots — the
sections are adjacent on the page and independent in the arithmetic.

## 5. The ≤25-line conversation summary

Exactly this shape, including the *absent* renderings. A number no tool produced is printed as the
absence, never as a zero.

```
Policy review: <repo> — standards DRIFTING · spec SPEC-DIVERGENT. Nothing was changed.
           2 blockers, 9 majors, 17 minors (standards) · 1 blocker, 3 majors (spec)

Groups     G structure (412 files) · H house (31 .tf + 6 shell) · C change (diff of 14 files)
           S spec (docs/specs/tenant-routing.md, 11 requirements)
Structure  8 files >250 · 22 methods >25 · 14 nests >1 (3 also >2) · 96 `else` · 0 cycles (native)
House      3 IAM role names over 64 (worst 78) · 2 hardcoded account ids · urls.yaml absent
Change     1 unhandled None path · 3 swallowed exceptions · 0 new tests for 14 changed files
Spec       9/11 requirements met · 1 divergent (retry ceiling) · 2 unrequested files · 4 untested
Caps       graph measured with codegraph scripts · name lengths by awk · history not read
Declined   speculative-ports.md suppressed 2 (PCR-G10, PCR-R28)

Worst on each axis — not ranked against each other
standards  PCR-H02-001 blocker S  naming.tf:41 role name 78 chars — apply fails; add var.role_slug
spec       PCR-S03-001 blocker S  client.py:54 retries uncapped; spec §4 "at most 3 attempts"

Next 2 (standards)
1  PCR-C01-002 blocker S  handlers/create.py:88 tenant compared before auth gate returns
2  PCR-G07-004 major  M  commons/dynamo.py:120 except: pass — 3 swallowed, no stack in logs

Full: .policy-review/report.md
Next: fix both blockers (one per axis, both S), then re-run /md_policy-code-review diff
```

**Never print one overall "worst finding" across the axes.** That single line is the re-ranking the
separation exists to prevent: it is how a spec failure disappears behind a cap breach. One worst per
axis, labelled, even when one axis is clean — `spec: none` is information.

## 6. Verdict thresholds

**Two verdicts, computed independently.** Neither overrides the other, and they are always printed as
a pair even when one axis did not run.

### Standards verdict — from `R`/`G`/`H`/`C`

| Verdict | Condition |
|---|---|
| **COMPLIANT** | 0 blockers · 0 cycles · <5% of files over any cap · every composed name under its AWS cap |
| **DRIFTING** | ≤2 blockers · <20% of files over a cap · no name over its cap |
| **NON-COMPLIANT** | anything worse, or any name that would fail at apply time |

### Spec verdict — from `S` alone

| Verdict | Condition |
|---|---|
| **SPEC-MET** | every requirement delivered as specified · 0 `S3` divergences · no unrequested behaviour |
| **SPEC-DIVERGENT** | ≥1 `S1` gap, `S2` unrequested behaviour, or `S3` divergence, none of them a blocker |
| **SPEC-FAILED** | any `S` blocker — a requirement inverted, a rejected behaviour rebuilt, a specified constraint unenforced |
| **SPEC-UNKNOWN** | `S` did not run: no diff, or no spec source found. Say which |

`COMPLIANT / SPEC-FAILED` and `NON-COMPLIANT / SPEC-MET` are both real, common, and the most useful
thing this skill says about a change. **Never collapse the pair into one word**, and never let a clean
standards verdict imply the change did the right thing.

Verdicts are computed, never chosen. Print the arithmetic if asked. A group that did not run cannot
contribute to a verdict: say `verdict excludes H (no infra in scope)` rather than passing it by
default — and `SPEC-UNKNOWN` is the honest reading of an unfindable spec, never `SPEC-MET`.
