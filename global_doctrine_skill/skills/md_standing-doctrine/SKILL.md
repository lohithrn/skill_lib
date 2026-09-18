---
name: md_standing-doctrine
description: The two standing rules that apply to every project before any project-specific convention — judge code and infrastructure against the system being built rather than the value in today's snapshot, and never use machine-generated certificates or private keys as an authorization mechanism. Read this when reviewing, when tempted to simplify a seam, or when choosing how a caller authenticates.
when_to_use: Before any architecture review, any "let me simplify this", and any decision about how something authenticates.
allowed-tools: Read, Grep, Glob
---

# Standing doctrine

Two rules. They are not project conventions — they outrank project conventions, and every other skill
in this collection defers to them. `md_policy-code-review` encodes them as precedence rules 1 and 2;
`md_fleet-conventions` and `md_coding-rules` both cite them.

**This is doctrine, not a procedure.** It is installed as a skill so it can be read and cited, but its
natural home is a global instruction file (`~/.claude/CLAUDE.md`, `~/AGENTS.md`, or the equivalent for
your host) where it is always in context. Copy the two sections below into that file. A rule that only
loads when a matcher fires is not a standing rule.

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

## What this does NOT do

It does not review anything and it does not measure anything — `md_policy-code-review` does that, and it
cites these two rules by name. It does not describe naming, routes, deploy gates or data conventions;
those are the `md_fleet-conventions` skill. It has no scripts and no write tools, deliberately.
