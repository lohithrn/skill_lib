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
