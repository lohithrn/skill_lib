---
name: md_bug-diagnosis
description: Diagnose a hard bug or a performance regression by building the feedback loop first — a single tight, deterministic, agent-runnable command that goes red on this exact symptom and green when it is fixed. Then reproduce and minimise, rank three to five falsifiable hypotheses before testing any of them, instrument one variable at a time behind a taggable prefix, and land the fix behind a regression test at a seam that can actually hold it. Enforces one gate above all others: no red-capable command that has already run means no hypothesis. Redacts every secret out of everything it shows.
when_to_use: Only when explicitly invoked as /md_bug-diagnosis. Never auto-trigger.
disable-model-invocation: true
argument-hint: "the symptom in the user's words — or [loop|repro|hypothesis|instrument|fix] to resume at a phase"
allowed-tools: Read, Grep, Glob, Write, Edit, TodoWrite, Agent, Bash
---

# /md_bug-diagnosis

One conflict to resolve: **do I have a signal that goes red on *this* bug?** Everything else in this
skill is mechanical once the answer is yes, and nothing in it works while the answer is no.

The two reference files hold the depth: `references/feedback-loop.md` is phase 1 and is the whole skill;
`references/hypotheses.md` is phases 3 through 6.

## The gate — read this first

**No red-capable command that you have already run means no hypothesis.** Not a theory, not a
suspected cause, not "it's probably the cache". If you catch yourself reading code to build a story
before that command exists, stop and go back to phase 1 — jumping to a hypothesis is the exact failure
this skill exists to prevent, and it is the reason hard bugs take days.

A command qualifies only when all four hold. The checklist is in `references/feedback-loop.md`
§The completion criterion, and it is quoted here because no phase may skip it:

- **Red-capable** — it drives the real bug code path and asserts the **user's exact symptom**, so it can
  go red now and green after the fix. "Runs without erroring" is not red-capable.
- **Deterministic** — same verdict every run. For a flaky bug, a pinned reproduction rate high enough
  to debug against.
- **Fast** — seconds. A 30-second flaky loop is barely better than nothing.
- **Agent-runnable** — you can run it unattended, and you have shown one invocation and its output.

## Redaction — before anything is shown

This skill shows commands, outputs, captured payloads and logs. **Redact every secret first**, writing
`<REDACTED>` in its place: tokens, keys, cookies, `Authorization` headers, connection strings,
customer identifiers. Build every loop against environment variables so the credential lives in the
environment and never in what you print. Captured traffic carries auth headers — quote only the lines
that carry the signal.

If the redacted output is not enough to diagnose the bug, **say so and ask**. Never widen what you show
to make your own job easier.

No credential is ever generated here. Never mint a certificate, key or keypair, and never propose one
as an auth mechanism — including "just to get the loop working".

## Route — six phases, in order

Skip a phase only with a stated reason. Announce the phase you are entering in one line.

| Phase | The question | Where the detail lives | Exit condition |
|---|---|---|---|
| **1. Loop** | what command goes red on this? | `references/feedback-loop.md` §The ladder | the four-part criterion above, with one invocation shown |
| **2. Repro + minimise** | is it *this* bug, and what is load-bearing? | §Minimise, same file | every remaining element is load-bearing; removing any one turns it green |
| **3. Hypothesise** | what are the 3–5 candidates? | `references/hypotheses.md` §Ranking | each one falsifiable, with its prediction written down, shown to the user before testing |
| **4. Instrument** | which prediction does this probe settle? | `references/hypotheses.md` §Probes | one variable changed, one hypothesis eliminated or confirmed |
| **5. Fix + regression test** | is there a seam that can hold the test? | `references/hypotheses.md` §The seam question | test written first and watched fail, then the fix, then watched pass |
| **6. Cleanup** | what did I leave behind? | `references/hypotheses.md` §Cleanup | every tagged probe removed, the original loop re-run green |

**Phase 1 gets disproportionate effort.** Be aggressive, be inventive, refuse to give up. Build the
right loop and the bug is most of the way fixed; skip it and no amount of reading code will save you.

## Non-negotiables

1. **Reproduce the user's symptom, not a nearby one.** A loop that goes red for a different reason
   produces a real fix to the wrong bug. Quote the symptom back before phase 2 and confirm they match.
2. **Minimise before hypothesising.** Every element you cut shrinks the hypothesis space in phase 3 and
   the repro becomes the regression test in phase 5. Cut one thing at a time, re-running after each.
3. **Three to five hypotheses, ranked, before testing any.** Generating one anchors you on the first
   plausible idea, and the first plausible idea is wrong often enough to cost a day.
4. **One variable per probe.** Two simultaneous changes make the result unattributable, and you will
   have to redo both.
5. **Tag every probe.** A unique prefix like `[DEBUG-a4f2]` on every temporary log or print, so phase 6
   cleanup is one grep. Untagged instrumentation survives into production; tagged instrumentation dies.
6. **Measure before fixing a performance problem.** Logs are the wrong tool for a regression in speed —
   establish a baseline number first, then bisect against it. `references/hypotheses.md` §Performance.
7. **No seam for the regression test is itself the finding.** Do not settle for a shallow test that
   cannot see the bug pattern; say the architecture is preventing the bug from being pinned down, and
   report that. A test giving false confidence is worse than a documented gap.
8. **Say what you could not do.** The loop you failed to build, the environment you could not reach,
   the hypothesis you could not test. Every report ends with this.

## Where this skill stops

- **It does not restructure.** A bug whose real cause is a structural defect ends with the fix plus a
  one-line note. The restructure is `/md_codegraph`, which needs the characterization tests first.
- **It does not review the fix against policy.** That is `/md_policy-code-review diff`.
- **It does not decide what a test should assert.** `md_codegraph/references/testing-hierarchy.md` §8
  owns that, and its §9 owns the three ways the regression test you are about to write could pass while
  proving nothing.
- **It never runs against a production system.** No live instrumentation, no shell on a running
  service, no query against a customer database. When the bug only reproduces there, say so and ask for
  a captured artifact instead — that is the phase 1 escape hatch, not an invitation.

## Checklist before saying done

- [ ] The loop command is named, was run, and its redacted output is shown
- [ ] The loop went red for the user's symptom, and they confirmed it is the right symptom
- [ ] The repro is minimal: every remaining element was shown to be load-bearing
- [ ] 3–5 ranked hypotheses were written with predictions, and the ranking was shown before testing
- [ ] Each probe mapped to one prediction and changed one variable
- [ ] The correct hypothesis is stated in the commit or PR body, so the next reader learns it
- [ ] A regression test exists at a seam that can see the bug — or its absence is reported as a finding
- [ ] Every `[DEBUG-...]` probe and every throwaway harness is gone, verified by grep
- [ ] The original, un-minimised loop was re-run and is green
- [ ] Nothing shown contains a secret, and nothing was generated as credentials
