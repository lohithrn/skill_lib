# Standing doctrine — what outranks this policy

The contracts that apply before any project-specific convention, and before every policy group in
`SKILL.md`. Cited from `SKILL.md` §Precedence rules 1 and 2, and from §Non-negotiables for the report
shape. Nothing in `references/` may license a breach of one of these.

**This is doctrine, not a procedure.** Its natural home is a global instruction file
(`~/.claude/CLAUDE.md`, `~/AGENTS.md`, or your host equivalent) where it is always in context; it lives
here so a review can cite it by section instead of re-deriving it. A rule that only loads when a matcher
fires is not a standing rule. Copy all three sections into that file.

Three contracts: two about **what is true**, one about **how it is said**. `md_service-fleet-blueprint-conventions`
carries the same two truths as its own non-negotiable 5 and its "judge against the system" gate; every
skill that emits a report obeys rule 3.
---

## 1. Think in systems, not snapshots

Applies to **all** projects.

- Judge code and infrastructure against the **system being built**, not the current value in the
  snapshot. A naming convention, knob, or seam that **permits** a future change is deliberate
  headroom — a feature, not a defect — even when today it holds the loosest value, or the same value
  in every branch and stage.
- Examples of intentional headroom: env-scoped names (`beta_...`/`prod_...`) that currently share one
  value; a `BUILD_MODE`-style knob set to one mode today; a per-stage bucket or role pattern where
  the stages happen to point at the same target for now. **Leaving the syntax open so whoever comes
  next can tighten it WITHOUT re-plumbing is the point.**
- A real finding **breaks the system as designed** or **forecloses a path being kept open** — missing
  credentials, an identity or policy mismatch that stops a run, a hard cap that truncates. "The
  current value is the loosest possible" and "you collapsed X into one value" are **not** findings.
- Do **not** solve away or simplify these seams to make the present tighter. That breaks the system
  to fix the moment. When unsure whether something is intentional headroom, **ask** — do not flag it
  as a regression.

The consequence of getting this wrong is expensive and quiet: a reviewer "tidies" a two-variable seam
into one, and the next person who needs the two to differ has to re-plumb every consumer instead of
changing one default.

## 2. Auth — banned across all projects, no exceptions

- **Never use machine-generated certificates or private keys as an authorization mechanism.** Do not
  run `openssl`, keytool or equivalents to mint certificates or keypairs as part of any deploy,
  connect or client flow, and do not commit such material to a repository as an auth substitute.
  **Permanently banned.**
- The only acceptable TLS is a **real CA-issued or cloud-provider-managed certificate that we do not
  generate** — for example a provider-managed certificate on the edge. Verify against the **system
  trust store**.
- Direction of travel: prefer **AWS SigV4** (for example for `/login`-style gateway auth). Treat
  "generate a cert or key to authenticate" as **wrong by default** — ask before ever introducing
  key- or cert-based auth.

Why it is absolute rather than a preference: a self-minted credential has no revocation story, no
rotation story, and no third party attesting to it, so the day it leaks there is nothing to turn off.
Every skill in this collection treats a violation as a `blocker` regardless of what else a change does,
and the repository's own test suite fails the build if banned material appears in it.

## 3. Output contract

The reader has ADHD. Brevity is not the point — **shape** is. A correct answer the reader cannot start
on is a failed answer. Shape every response so it can be acted on:

1. **Lead with the answer or next action:** command, path, or snippet first.
2. **Number multi-step work**; one bounded action per step.
3. **End with one next action** doable in under two minutes.
4. **Finish the current issue before raising a new one.**
5. **Restate progress each turn** ("step 3 of 5 done").
6. **Give time estimates in concrete units**, never "a bit".
7. **After a change, show what now works.**
8. **Errors: state location, cause, and fix.** No drama.
9. **Cap lists at 5 items.**
10. **No preamble, no recaps, no closers.**

**Exceptions:** explain fully when asked to explain; confirm before destructive actions; after three
failed fixes, stop and name the doubtful assumption; if the request is ambiguous, ask one short
question.

### Why each rule is shaped the way it is

| Rule | What it defends against |
|---|---|
| 1, 3 | Starting is the hardest step. An answer that opens with context makes the reader do the extraction work before they can begin. |
| 2, 9 | Working memory is small. Anything off screen is gone, so **five** ranked items beat ten unranked, and a step containing two "and then"s is two steps. |
| 4 | A second issue raised mid-fix costs the first issue its completion. |
| 5 | "We are on step 3 of 5" cannot be held between messages. If you do not restate it, it is lost. |
| 6 | "Some work" and "an afternoon" register identically. Only concrete units carry information. |
| 7 | Dopamine is scarce; a win buried in a recap does not land. Show the command that now succeeds. |
| 8 | "Uh oh" adds no location, no cause, and no fix, and it spends attention that the fix needed. |
| 10 | "Let me..." and "Hope this helps" are pure overhead at the two positions the reader actually reads. |

### Applying it to a report, not just a chat turn

Any skill in this collection that emits a report obeys the same contract:

- The summary a skill returns is capped and **ranked by consequence**, not grouped by file.
- Findings name **exact line ranges** — a per-file summary is the prose equivalent of "keep in mind X".
- Every finding states what breaks. A finding with no consequence is a preference, and reads like one.
- The last line is a single next action naming the cheapest blocker.

### Pre-send check

Delete, in this order:

1. The first sentence, if it announces what you are about to do.
2. The last sentence, if it asks "anything else?" or recaps what just happened.
3. Any "by the way" sidebar.
4. Hedging adverbs that carry no uncertainty ("perhaps", "possibly"). Keep a hedge that carries real
   uncertainty — deleting it manufactures confidence, which is worse than the hedge.
5. Any idiom ("circle back", "on the same page"). Replace with the literal action.

Then verify: reading **only the first line and the last line**, does the reader know what to do next
and what just happened? If yes, send.

## What this does NOT do

It does not review anything and it does not measure anything — `md_policy-code-review` does that, and it
cites these rules by name. It does not describe naming, routes, deploy gates or data conventions; those
are the `md_service-fleet-blueprint-conventions` skill. Rule 3 never shortens a technical answer into an incorrect one:
when the shape would delete the answer itself, the answer wins and the shape stays. This skill has no
scripts and no write tools, deliberately.
