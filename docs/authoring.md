# Authoring a skill in this repo

`README.md` §Layout says where files go and what the caps are. This says **how to write the prose so
an agent actually behaves**, and why this repo is shaped the way it is.

Every convention below is already visible in the twelve shipped skills; the point of writing it down is
that a convention nobody stated gets broken by the next skill. Where a rule here has a named source, it
is Pocock's `skills/engineering/writing-for-agents` and its `SKILL-MECHANICS.md`, adapted — the
divergences are marked, and they are deliberate.

---

## 1. The two loads

Two separate budgets, and they trade against each other:

- **Context load** falls on the model's window. Everything loaded competes for attention with the task,
  so an instruction that says nothing is not free — it is dilution.
- **Cognitive load** falls on the human, who has to remember the skill exists and reach for it.

Every skill here is `disable-model-invocation: true` with `when_to_use: Only when explicitly invoked`.
That is a deliberate choice of one budget over the other: **zero context load, paid entirely in
cognitive load.** Nothing enters the window until a slash command is typed, and in exchange the user
has to remember twelve commands.

Cognitive load is not a cost to eliminate. It is the price of the human deciding when a skill runs.
Model invocation is the opposite trade, and it is right only when the agent must reach the skill
**without being told** — a rule it has to apply mid-task, in a session nobody thought to prefix.

## 2. Router skills

The cure for cognitive load is not fewer skills, it is **one skill that names the others**. A router is
a user-invoked entry point holding exactly one conflict to resolve — *which thing does the user mean?*
— plus the table that answers it. No rule text.

`md_codegraph`, `md_policy-code-review` and `md_mcp-skill-surface` are all routers, and each says so in
its first paragraph. The shape:

| Layer | Holds | Loaded |
|---|---|---|
| `SKILL.md` | the conflict, the Route table, the gate, the non-negotiables, the fan-out contract | always, once invoked |
| `jobs/` | the phase-by-phase procedure for one mode | one per run |
| `references/` | rule text, thresholds, tables | on demand, by pointer |
| `specs/` | output contracts | when writing output |

**The 250-line router cap follows from this table, not from taste.** `SKILL.md` is the one file in
context for the whole run, so a line there costs more than a line anywhere else. When a router hits the
cap, the fix is almost never compression — it is that rule text leaked in from `references/`.

## 3. Progressive disclosure, and the branching test

Three tiers, in increasing cheapness: an **in-file step** (the agent reads it whether it needs it or
not), an **in-file reference** (a table it consults in place), a **disclosed reference** (a pointer to a
file it fetches only if it goes that way).

The test for which tier something belongs in is **branching**:

> **Inline what every branch needs. Push behind a pointer what only some branches reach.**

A `refactor`-only gate does not belong inline in a router four modes share; the 40-rule text does not
belong anywhere but `references/`. Conversely, a rule every mode must obey — the write gate, the global
bans — is inline even though it is long, because there is no branch that skips it.

**The one deliberate inversion:** `md_mcp-skill-surface/references/skill-authoring.md` requires each
*MCP prompt document* to restate its universal rules rather than point at a shared preamble. That is
correct there and stays: an MCP client fetches one document through `prompts/get` and **cannot follow a
pointer**, so a rule in a file the client never fetches is a rule that does not exist. Progressive
disclosure is a filesystem-agent technique. Do not import it across that boundary.

## 4. Context pointers

A pointer is **a reference plus the condition that fires it**. The condition is the load-bearing half:

- Weak — `See references/spec-policy.md for more.`
- Strong — `Asked to review against an issue this skill cannot read? references/spec-policy.md §Phase 0.`

The wording decides *when* the pointer fires, and firing is probabilistic. **A must-have behind a
weakly worded pointer is a variance bug**: it works in the sessions where the agent happened to follow
it, which is the worst failure shape to debug because it is not reproducible. If a pointer must always
fire, state the trigger; if what is behind it is non-negotiable, it belongs inline.

## 5. Leading words

A leading word is a compact concept the model already holds from pretraining, so naming it recruits
everything attached to it. The repo's load-bearing set: **seam · port · resolver · adapter · oracle ·
blast radius · hotspot · headroom · deferred conflict · characterization test · promotion threshold**.

Two rules:

- **Repeat it as a token, never as a sentence.** `the seam` in every relevant sentence; the definition
  once, in the reference that owns it. Re-explaining a leading word each time is the sentence form, and
  it pays context load to say what the token already said.
- **Prefer a word with priors over a coined one.** `seam` arrives with Feathers attached; a bespoke
  term arrives with nothing and has to be taught every session. Coin only when no existing word fits,
  and then define it once and hard — `deferred conflict` and `headroom` are ours, and each has exactly
  one defining passage.

## 6. Prompt the positive

Steering by prohibition has a cost most authors do not price: **naming the forbidden behaviour drags it
into context and makes it more available**, not less. `Never use a bare dict for the Context` puts bare
dicts in the window. `The Context is a frozen dataclass` puts frozen dataclasses there.

So the default is the positive form, stating the target rather than the trap.

**The exception, and it is large in this repo:** a prohibition earns its place as a **hard guardrail**,
where the ban *is* the content and no positive phrasing carries it. All of these stay exactly as they
are written:

- the global bans — machine-generated certs or keypairs as authorization, never `openssl` in a deploy
  path (`references/standing-doctrine.md` §2);
- the write gates — `review`/`diff` never edit the tree, never `push`/`checkout`/`stash`, never
  `codegraph-surgeon` from a read-only mode;
- the offline gates — never install a tool to reach a higher fitness tier, no network reference under
  `scripts/`;
- the safety rules in MCP skill documents — never invent an identifier, never bypass the API to hit the
  database. Their consequence (another tenant's data) *is* the instruction.

Even then, pair the ban with the positive target where one exists: *prefer SigV4* sits next to the cert
ban for a reason.

Everything else is a candidate for rewriting. The tell is that the positive form is obvious and
shorter: `Never printStackTrace()` → `Log through the configured logger so appenders see it.`

## 7. Pruning — what to delete

A skill document decays by accumulation. Five kinds of line to cut:

1. **No-ops.** An instruction the model already obeys by default pays load to say nothing. *Write
   clear code*, *be careful*, *think step by step* in a reasoning model. **The no-op test is
   model-relative and settled by running the document, not by arguing about it**: delete the line, run
   the skill, see whether behaviour moved. If it did not, it was a no-op on this model.
2. **Sediment.** A line added to fix one session's failure, still there three refactors later, now
   describing a phase that no longer exists. Every pointer to a renamed file is sediment.
3. **Restatement.** One fact, one home. A threshold repeated in a router *and* its reference will
   drift, and then the reader cannot tell which is authoritative.
4. **Cached environment.** The environment is itself a source of truth: a script's real flags, the
   tree's real layout. Prose restating it is a **cache**, and a cache earns its load only when the
   lookup is expensive. `install.sh discovers skills by globbing md_*/SKILL.md` is a cheap cache of an
   expensive read. A copied-out `--help` output is a stale one.
5. **Irrelevance.** Correct, live, and not needed for the job the skill does.

`tests/smoke.sh` catches kind 2 mechanically for scripts and flags, and nothing catches the rest.

## 8. Completion criteria have two jobs

Where a skill says "done", the criterion does two separate things, and most only do the first:

- **Clarity** resists **premature completion.** A fuzzy bound ("the report is complete") lets the agent
  stop early and truthfully claim it finished. Our verdict tables — `COMPLIANT`/`DRIFTING`/
  `NON-COMPLIANT`, `SPEC-MET`/`SPEC-DIVERGENT`/`SPEC-FAILED`/`SPEC-UNKNOWN` — and the
  `Checklist before saying done` blocks are the clarity side. Computed verdicts, not chosen ones.
- **Demand** drives **legwork.** A criterion an agent cannot satisfy by asserting forces it to go and
  measure. `Every number came from a command that ran; unmeasured metrics are in degraded` is a demand
  criterion. `Be thorough` is not.

When an agent stops early, sharpen the bound before adding steps after it. And note that hiding later
work to keep it from pulling focus only works across a **real context boundary** — a subagent or a
handoff. Steps listed inline are already in the window; the agent can see the finish line.

## 9. The caps

| File | Cap | Why |
|---|---|---|
| `md_*/SKILL.md` | 250 lines | the router is in context for the whole run (§2) |
| every other `md_*/**.md` | 600 lines | a reference is loaded whole, so its worst case is its length |

Both are enforced by `tests/smoke.sh` → `check_file_length_caps`. Hitting a cap is a design signal, not
a formatting problem: a router at 250 has rule text in it, and a reference at 600 is two references.

## 10. What a run leaves behind

A skill that writes leaves litter unless every path it writes has a named end. Five of the shipped
skills write into somebody else's tree: `md_codegraph` into `.codegraph/`, `md_policy-code-review`
into `.policy-review/` and `.out-of-scope/`, `md_python-library` a migration map, `md_deck-builder` an
unpacked OOXML tree, and `md_upsert-aws-deployment-role` a policy JSON. Only the last one already has
an end — it writes to `/tmp`, and that is the shape to copy whenever a file is spent the moment the
command reading it returns.

Everything else a skill writes is exactly one of two kinds. **The kind is a property of the file, not
of the mood the run finishes in:**

| Kind | Lives for | Exit |
|---|---|---|
| **scratch** | one run, against one commit sha | **deleted** by the run that made it |
| **durable** | until the thing it records changes | **committed**, through git, in the one documentation folder |

### Two exits, and ignoring is not one of them

A scratch directory is deleted at the end of the run, or — if what it holds turned out to be worth
keeping — it is **promoted**: committed like anything else a human would want to read next year.
Which of the two is a judgement made when the run ends and the content is known, not a policy fixed
in advance.

**`.gitignore` is the third door, and it is the wrong one.** Ignoring keeps the file *and* hides it:
the directory stops appearing in `git status`, so nobody is reminded it exists, and the next run
silently reads a `scope.json` measured against a commit that no longer exists — which
`md_policy-code-review` already calls out as the failure mode that poisons a report. Deletion closes
the loop that ignoring hides, and committing makes the value reviewable. There is no third outcome
worth having.

**This is a rule about a run's scratch, not about everything `.gitignore` is for.** A local config file
holding an account id, an SSO start URL or a profile name is ignored because committing it is the
defect — `md_register-sso-app/references/config-and-portability.md` is right to say so, and nothing
here changes it. The distinction is who the file is for: **scratch is the skill's own working state and
has to end; a local config is the operator's, and its whole job is to persist unshared.** Enforced by
`tests/smoke.sh` → `check_gitignore_is_not_an_exit`, which fires only on a skill's own artifact
directory.

### The disposition table is per skill, and it is stated before the run writes

One fact, one home (§7.3), so the rule above is stated only here. What each skill states for itself is
its own **disposition table** — every path it creates, and which kind that path is.
`md_codegraph/references/artifacts.md` and `md_policy-code-review/SKILL.md` §Artifacts are the two
worked examples. A path missing from its skill's table is exactly the defect this section exists to
catch: the file nobody deletes because nobody is sure it is safe to.

Three rules follow, and they are guardrails in the §6 sense — the ban *is* the content:

- **No intermediate `.md` at the root of somebody's repo.** A `MIGRATION.md`, `PLAN.md` or
  `REVIEW.md` dropped beside their `README.md` is the most expensive kind of litter, because it looks
  official. Durable prose goes in the repo's one documentation folder — `documentation/` in this
  house, per `md_policy-code-review/references/testing.md` — and scratch goes in the run's own dot
  directory or `/tmp`.
- **A spec that has been executed and verified is spent.** The restructure spec is the input to
  `apply`; once every slice is applied and `verify` is green, its claims live in the git history that
  proves them. Keep the report if the findings still teach something; the spec itself goes.
- **Never delete a durable artifact to tidy up.** `.out-of-scope/` is committed on purpose: a declined
  finding that dies with a directory gets re-reported forever. Deleting it is a regression, not
  cleanup.

### Cleanup is a phase, not a hope

`md_bug-diagnosis` is the model to copy, and it got there first: every probe carries a
`[DEBUG-a4f2]`-style tag **so that cleanup is one grep and cannot miss anything**, and phase 6 exists
only to run it. Tagging at write time is what makes the end of a run cheap. A skill whose cleanup step
is "remove any temporary files" has no cleanup step — it has a wish.

Enforced by `tests/smoke.sh` → `check_write_paths_declare_a_disposition`.

## 11. Semantics a run must not break

A skill that commits or publishes is editing two things: the tree, and the **record** of how the tree
got that way. The second is the one nobody notices being destroyed.

### The commit subject carries the why

Thirty commits reading `slice 3 step 2` are a history nobody can bisect, revert selectively, or review.
Every commit a skill makes uses a conventional subject and a body that says what the change *deletes*:

```
refactor(invoice): replace the tier if/elif with a resolver registry

Deletes the else at invoice_service.py:137 and the duplicate switch at
reporting/summary.py:31. Slice 3, step 2 of .codegraph/restructure.md.
```

- `type(scope): imperative summary` — `feat` · `fix` · `refactor` · `test` · `docs` · `chore` · `perf`.
  A `refactor` commit that changes behaviour is mislabelled, and that mislabelling is what makes a
  later `git bisect` lie.
- **The body names the slice and the spec, not just the step number.** The spec is scratch (§10) and
  will be deleted; the commit body is the only surviving record of which planned slice this was.
- A behaviour change hiding in a `refactor` commit is a finding in its own right.

### The version number is a promise about the API

`major.minor.patch`, and the rule is the consumer's, not the author's: **a change that breaks an import
a consumer has written is a major bump, however small the diff.** Moving a symbol between modules
breaks imports. So does narrowing an `__init__.py` export list. Both are major.

- A migration map exists because a major bump happened; publishing one without the other ships a break
  with no instructions (`md_python-library`).
- A new scaffold starts at `0.1.0`, not `1.0.0` — `1.0.0` is a claim that the API is stable, and a
  scaffolder cannot make that claim on the author's behalf (`md_create-git-template`).
- Never re-publish a version that already exists on the index. A consumer who pinned it gets different
  code under the same number, and no lockfile catches it.
