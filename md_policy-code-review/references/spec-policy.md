# Spec policy — `S1`–`S5`

Every other group in this skill asks **"is this code good?"** This one asks a different question:
**did it build what was asked?** A change can satisfy all forty architecture rules, breach no cap,
carry its tests, and still implement the wrong feature. `R`/`G`/`H`/`C` cannot see that, because none
of them ever reads the request.

Adapted from the two-axis review recipe (Pocock, `skills/engineering/code-review`), whose one load-
bearing claim is worth restating: **a Standards pass masks a Spec fail.** Code that follows every
convention while implementing the wrong thing reads as clean in a four-group report. That is the
failure mode this group exists to catch, and it is why §Axis separation below forbids merging `S`
findings into the others.

Scope: the diff, against the request that caused it. This group is **diff-only** — `review` mode has
no change to compare a spec to, and must say `S not run (no diff)` rather than inventing a spec for
an existing tree.

---

## Phase 0 addition — find the spec, or say there isn't one

Before any `S` finding exists, name the spec source. In this order, stopping at the first hit:

1. **A path the user passed.** `/md_policy-code-review diff main docs/specs/tenant-routing.md` — the
   trailing non-ref argument is the spec.
2. **A spec file in the tree** matching the branch name or the changed area: `docs/`, `specs/`,
   `.scratch/`, `adr/`, `*.md` beside the changed package. Read the one, not all of them.
3. **The commit messages themselves.** `git log <base>..HEAD` bodies are a specification of intent —
   often the only one. A commit saying "cap retries at 3" *is* a requirement.
4. **An issue reference with no local text.** `#123`, `Closes #45`, `PROJ-88` in a commit message,
   with no file in the tree carrying its content.

Case 4 is a **degradation, not a spec.** This skill has no network and no issue-tracker access — its
`allowed-tools` grants `git` and nothing else, by design, so the rules it applies never depend on a
fetch. Record `S degraded: issue #123 referenced, not readable` in `oracle.json`, run `S` against the
commit messages alone, and say so in the report. Never guess what an issue said from its number.

No spec found at all ⇒ **`S` does not run.** Print `S not run (no spec source found)` in the Groups
run section and stop. An absent spec is a fact about the change, not a finding against it — but say
it out loud, because a reviewer who assumes a spec was checked is worse off than one who knows it
wasn't.

Whatever the source, quote it. **Every `S` finding carries the requirement's own words in LAW.** A
spec finding that paraphrases the spec is unfalsifiable.

---

## S1 — A requirement the diff does not deliver

The spec asked; the code does not do it.

Report:

- A requirement with no corresponding code anywhere in the diff. Name the requirement and say where
  you looked — the file that should have held it.
- A requirement implemented for one case and not its siblings: three of four enumerated states, two
  of three tenants, the happy path with the error path left open.
- A stated constraint with no enforcement: "reject names over 64 characters" with no check, "retry at
  most 3 times" with an unbounded loop, "idempotent" with no dedupe key.
- A requirement satisfied only by a `# TODO`, a stub that raises, or a function that returns a
  literal. A stub is not a partial implementation; it is an absent one with a name.

CONSEQUENCE is **Unmet requirement** — "the spec's line *N* asks for X; input Q takes the path that
does not do X." Name the input, or drop to `minor` and say `suspected`.

**A requirement explicitly deferred by the spec or the PR description is `deferred-conflict`,** not a
gap: "phase 2 handles the migration" is a plan, and billing it as a defect punishes the author for
being honest about scope.

## S2 — Behaviour nothing asked for

The code does more than the request. The harder half of this group, and the half a Standards review
structurally cannot find: unrequested work is often *well-built* unrequested work.

Report:

- A feature, flag, endpoint, table column or config key in the diff that no requirement mentions.
- A behaviour change bundled with the requested one: a rename, a reformat, a dependency bump, a
  refactor of a neighbouring module, "while I was in there".
- A generalisation the spec does not need — a port with one resolver, a parameter no caller passes, a
  strategy interface for a single strategy. This is Speculative Generality (`G10`, `R28`) reached
  from the other direction: not "is the abstraction paid for" but "did anyone ask for it".
- Widened scope in a signature: an argument added "for later", a return type made optional so a
  future case fits.

CONSEQUENCE is **Unrequested scope** — "N files changed for a requirement that named one; a reviewer
cannot tell which hunks implement the request." The real cost is review integrity and revert
granularity, not line count. Say that, not "the diff is large".

**Before reporting scope creep, check `.out-of-scope/`** (`references/declined.md`). A behaviour
recorded there as rejected and now appearing in the diff is not creep — it is a reversal, and it is a
`blocker`: someone rebuilt a thing the repo decided against. Cite the file.

**Not creep:** a change the requested one strictly requires (a new import, a call-site update, a
migration the schema change needs), and a test. Tests are never scope creep.

## S3 — Implemented, but not as specified

Present, plausible, wrong. The most expensive finding in this group, because it survives code review
and tests written from the same misreading.

Report:

- The spec's value and the code's value disagree: a different default, threshold, timeout, unit
  (seconds where the spec says **epoch milliseconds**), rounding rule, or sort order.
- The spec's condition, inverted or narrowed: `or` where it says "and", `>` where it says "at least",
  an early return that skips the case the spec singles out.
- The right behaviour at the wrong time: validation after the write, the notification before the
  commit, the audit entry on the success path only.
- The right behaviour in the wrong place: a rule the spec puts at the boundary implemented per call
  site, or the reverse. This one overlaps `G`/`R` — report it here when the *spec* named the location,
  and there when only the architecture did.
- An error case the spec specifies a response for, handled with a different status, message, or
  retryability than it asked.

CONSEQUENCE is **Divergence from spec** — quote both sides. This is the one `S` finding that is
frequently a `blocker`, and the severity comes from what the divergence does, not from the fact of
diverging.

## S4 — The spec is the problem

Sometimes the code is right and the request is not. Say so; the author cannot fix a requirement they
were handed.

Report:

- A requirement the diff *cannot* satisfy as written — it contradicts another requirement, an ADR, or
  a hard cap in `references/house-policy.md`. Name both, and do not pick a winner: that is a person's
  call.
- An ambiguous requirement the code resolved silently. The finding is the missing decision record,
  not the choice: `SUGGESTION` is "write it down in the ADR or the PR description", and `EFFORT` is
  `S`.
- A requirement contradicting a prior rejection in `.out-of-scope/`. Surface the file and ask; do not
  re-litigate it inside a review.
- A spec that changed after the code was written — the commit predates the requirement it supposedly
  implements. Check the dates before believing a mismatch is the author's fault.

`SEVERITY` here is `minor` or `deferred-conflict` almost always. `S4` is how the review stays honest
when the spec is wrong, and it must never be used to argue with a decision the maintainer already
made.

## S5 — How anyone would know it works

A requirement with no observable is a requirement no one can confirm later.

Report:

- A requirement with no test asserting it. Name the test file and the case, in the spec's own
  vocabulary — `test_rejects_name_over_64_chars`, not "add tests". Overlaps `C6`: cite `C6` when the
  *changed behaviour* is untested, `S5` when a *stated requirement* is.
- A test that asserts the implementation's behaviour rather than the spec's: written from the code,
  passing by construction, and unable to fail if the spec were misread. Quote the spec line the
  assertion should have used.
- A requirement about something a test cannot see — latency, cost, an alarm, a dashboard — with no
  metric, log line, or alert emitted. "p99 under 200ms" with nothing recording p99 is unverifiable.
- An acceptance criterion in the spec with no corresponding assertion anywhere. These are the cheapest
  tests in the change and the ones most often skipped.

---

## Axis separation — the rule that makes this group worth having

**`S` findings are reported in their own section and are never merged with, re-ranked against, or
traded off against `R`/`G`/`H`/`C`.** The two axes answer different questions, and one masking the
other is precisely the failure this group was added to prevent.

Concretely:

- The report has a `## Spec (S)` section of its own. `S` findings never appear under `## Change (C)`.
- The verdict line carries **two** readings — a standards verdict and a spec verdict — and neither
  overrides the other. `COMPLIANT / SPEC-DIVERGENT` is a real and common outcome, and it is the
  single most useful thing this skill can say about a change.
- The ≤25-line summary names the worst finding **within each axis**. It does not pick one overall
  winner; that is the re-ranking the separation exists to prevent.
- De-duplication in phase 3 runs *within* an axis, never across it. A symptom that is both an `S3`
  divergence and a `C1` correctness bug is reported **twice**, once per axis, with each entry naming
  the other's ID. This is the one documented exception to "one symptom, one suggestion" — because the
  author fixing a wrong threshold and the maintainer asking "did we build the right thing" are
  reading different sections.

The precedence order in `SKILL.md` §Precedence (`C` before `R`/`G`/`H`) is an ordering *inside* the
standards axis. It says nothing about `S`, and must not be extended to it.

---

## How to report an `S` finding

Nine fields as always (`specs/suggestion.md`), with two `S`-specific obligations:

- **`LAW` quotes the requirement.** Not "the spec requires idempotency" but `spec §3: "a repeated
  request with the same idempotency key must return the first response"` plus the source —
  `docs/specs/orders.md:41` or `commit a1b2c3d`. A requirement you cannot quote is one you inferred.
- **`LOCATION` for an `S1` gap is where the code should have been**, not the spec file. A missing
  requirement's location is `handlers/create.py:88` — the line the check belongs above. Point at the
  spec and the author cannot act on it.

And the habits the whole skill shares: exact ranges, fewer and higher signal, nothing applied.

## Automatic non-findings for `S`

In addition to `specs/suggestion.md` §3:

1. A requirement the spec defers by name. `deferred-conflict`, never a gap.
2. Tests, fixtures, and test helpers, as scope creep. Never.
3. A mechanical consequence of the requested change — a call-site update, an import, a lock file, a
   generated file, a migration the schema change needs.
4. A wording difference between the code and the spec that names the same behaviour. `S` is about
   behaviour, not vocabulary; naming lives in `H1`/`G6`/`R`.
5. The absence of a spec. That is a `degraded` line, not a finding.
6. A requirement already recorded as rejected in `.out-of-scope/`. Ask; do not review it.
