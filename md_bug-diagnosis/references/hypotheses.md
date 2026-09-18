# Phases 3–6 — hypothesise, instrument, fix, clean up

Everything here consumes the loop from `references/feedback-loop.md`. If that loop does not exist, or
is not red-capable, nothing in this file works — it produces confident theories instead of causes, and
a confident wrong theory costs more than no theory.

---

## Phase 3 — ranking

Generate **three to five hypotheses before testing any of them.** Generating one anchors you on the
first plausible idea, and you then spend the session confirming it rather than testing it.

Each one must be **falsifiable**, which means it states its own prediction:

> If `<X>` is the cause, then `<changing Y>` makes the bug disappear, or `<changing Z>` makes it worse.

**No prediction means it is a vibe, not a hypothesis.** Sharpen it until it predicts something, or drop
it. "Something's wrong with the caching" predicts nothing. "If the cache key omits the tenant, then
requesting as a second tenant returns the first tenant's row" predicts something you can test in one
probe.

Rank them by expected information gained per unit of effort, not by likelihood alone: a cheap probe that
eliminates two hypotheses beats an expensive one that confirms the most likely.

**Show the ranked list to the user before testing anything.** They re-rank it instantly more often than
not — "we deployed a change to number three yesterday", "we already ruled out number one". It is the
cheapest checkpoint in the whole skill. Do not block on it: if nobody answers, proceed with your
ranking and say you did.

---

## Phase 4 — probes

Every probe maps to **one specific prediction** from phase 3, and changes **one variable**. A probe
that does not eliminate or confirm a named hypothesis is not a probe, it is looking around.

Tool preference:

1. **A debugger or a REPL**, where the environment supports it. One breakpoint beats ten log lines,
   and it answers questions you had not thought to log.
2. **Targeted logging at the boundary that distinguishes two hypotheses.** Not the boundary nearest the
   symptom — the one where the candidates disagree.
3. Never "log everything and grep". It produces volume, not signal, and it buries the one line that
   mattered.

**Tag every probe with a unique prefix** — `[DEBUG-a4f2]`, generated once per session. Then phase 6
cleanup is a single grep and cannot miss anything. Untagged instrumentation is how a debug print reaches
production.

State after each probe: which hypothesis it eliminated, which it promoted, and what is left.

### Performance

For a regression in speed, logs are usually the wrong instrument. The order is:

1. **Establish a baseline measurement** — a timing harness around the suspect path, a profiler run, the
   database's own query plan, a counter of calls made. A number, recorded.
2. **Bisect against that number**, by code version, by input size, by configuration. Halve the search
   space per measurement.
3. Only then reason about cause.

**Measure first, fix second.** A performance fix with no before-number is a guess with a diff attached,
and the usual outcome is a real change to something that was never the bottleneck.

---

## Phase 5 — the fix, and the regression test

Write the regression test **before the fix** — but only if there is a **correct seam** for it.

### The seam question

A correct seam is one where the test exercises the **real bug pattern as it occurs at the call site**. A
test that reaches the code but not the condition is worse than nothing: it locks in a green light for a
bug that can still happen.

Two shapes of wrong seam:

- A single-caller unit test for a bug that needs two callers interleaving.
- A unit test that cannot reproduce the chain — the ordering, the shared state, the second request —
  that actually triggered it.

**If no correct seam exists, that itself is the finding.** State it plainly: the architecture is
preventing this bug from being pinned down. Name the seam that would be needed and what stands in the
way. That is a structural finding, and it belongs in the report even though this skill does not act on
it — `/md_codegraph` does, and it will want the characterization tests first.

Before writing the test, check it can fail for the right reason:
`md_codegraph/references/testing-hierarchy.md` §9 names the three ways a test passes while proving
nothing, and a regression test derived from a minimised repro is especially exposed to the first of them.

### The sequence, when a seam exists

1. Turn the **minimised** repro from phase 2 into a failing test at that seam.
2. Run it. **Watch it fail**, and read the failure to confirm it fails for the bug's reason.
3. Apply the fix — the smallest change that addresses the confirmed cause, not the cause plus three
   tidy-ups.
4. Run the test. Watch it pass.
5. Re-run the **phase 1 loop against the original, un-minimised scenario.** The minimal case passing is
   not evidence the reported bug is gone.

---

## Phase 6 — cleanup

Required before saying done. Every line is a thing that has shipped by accident before:

- [ ] The original reproduction no longer reproduces — the phase 1 loop was re-run, un-minimised, green
- [ ] The regression test passes, **or** the absence of a correct seam is written down as a finding
- [ ] Every `[DEBUG-...]` probe is removed, verified by grepping the prefix
- [ ] Every throwaway harness is deleted, or moved somewhere unmistakably marked as debug scaffolding
- [ ] Nothing left behind contains a secret, a captured payload, or a customer identifier
- [ ] **The hypothesis that turned out correct is stated in the commit or PR body**, with the one piece
      of evidence that settled it

The last line is the one that gets skipped and the one that pays. The next person to debug this area
inherits either a diff or an explanation, and only one of those tells them where to look.
