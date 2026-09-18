# Phase 1 — the feedback loop, and phase 2 — minimising

This file is the skill. Phases 3 through 6 (`references/hypotheses.md`) are mechanical consumers of what
you build here: bisection, hypothesis-testing and instrumentation all just spend the signal a loop
produces. Without one they are guesswork wearing a procedure.

Spend disproportionate effort here. A loop is a **product**: build it, then improve it.

---

## The ladder — ten ways to construct one, in rough order of preference

Work down until one is achievable. Higher is better because it is cheaper to run and closer to the
code, not because it is more rigorous.

1. **A failing test** at whatever seam reaches the bug — unit, contract, component, integration, end to
   end. Which seam is a real decision: `md_codegraph/references/testing-hierarchy.md` §2 is the layer
   map, and §9 §Agree the seams is why you name it out loud before writing it.
2. **A scripted request against a locally running dev server.** Local only — this skill never points a
   loop at a deployed environment.
3. **A CLI invocation with a fixture input**, diffing its output against a known-good recorded output.
4. **A headless browser script** driving the UI and asserting on the DOM, the console, or the request
   log. Only when the symptom is genuinely in the browser.
5. **Replay a captured trace.** Save one real payload, event log or request to disk and push it through
   the code path in isolation. This is also the escape hatch when the bug lives somewhere you cannot
   reach: ask the user for the artifact, redacted.
6. **A throwaway harness.** The smallest subset of the system that reaches the bug — one module, its
   dependencies substituted — driven by a single function call.
7. **A property or fuzz loop.** For "sometimes the output is wrong": run a few thousand generated inputs
   and look for the failure shape. Record the seed.
8. **A bisection harness.** When the bug appeared between two known states — a commit, a dataset
   version, a dependency version — automate "put the system in state X, check, report" so
   `git bisect run` can drive it. The harness must exit non-zero on the bug and zero otherwise.
9. **A differential loop.** Push the same input through two versions or two configurations and diff the
   outputs. Often the fastest route when "it worked last week".
10. **A human in the loop, driven by a script.** Last resort, when a person must click something. Write
    the script so it prompts for the one manual action, captures what comes back, and loops — the human
    is a step inside the loop, not a replacement for it.

**Prefer 1–3.** Anything from 4 down is slower, flakier, or harder to hand to the next person, and its
only justification is that the ones above it were not reachable.

---

## Tightening

Once you have *a* loop, make it a *tight* one. Three axes, and each pays for itself many times over
across phases 3 and 4:

- **Faster.** Cache the setup, skip unrelated initialisation, narrow the test scope to the one case.
  You will run this command dozens of times.
- **Sharper.** Assert the specific symptom, not "it did not crash". A loop that goes red for three
  different reasons cannot eliminate a hypothesis.
- **More deterministic.** Pin the clock, seed the random source, isolate the filesystem, substitute the
  network, fix the ordering. Every non-determinism you remove is a hypothesis you no longer have to
  test.

A two-second deterministic loop changes what is possible. A thirty-second flaky one does not.

## Non-deterministic bugs

The goal is not a clean reproduction — it is a **higher reproduction rate**. Loop the trigger a hundred
times, run copies in parallel, add load, narrow the timing window, inject deliberate delays at the
suspected race. **A bug that reproduces half the time is debuggable; one percent is not**, so keep
raising the rate until it is, and state the rate you reached.

## The completion criterion

Phase 1 is done when you can name **one command**, that you have **already run at least once**, and show
its invocation and redacted output. All four must hold:

- [ ] **Red-capable** — drives the real bug code path and asserts the user's exact symptom. It can go
      red on *this* bug and green once fixed. Not "the suite passes"; it must be able to catch this bug.
- [ ] **Deterministic** — the same verdict every run, or a pinned high reproduction rate.
- [ ] **Fast** — seconds, not minutes.
- [ ] **Agent-runnable** — runs unattended; a human appears only as a scripted step inside it.

Miss any one and phase 1 is not finished. Say which one is missing rather than proceeding.

## When you genuinely cannot build one

Stop and say so explicitly. Do **not** proceed to hypothesise — an untested theory presented
confidently is the single most expensive output this skill can produce.

List what you tried, then ask for exactly one of:

1. access to an environment where it reproduces;
2. a redacted captured artifact — a request log, a log dump, a core dump, a screen recording with
   timestamps;
3. permission to add temporary instrumentation to a non-production environment.

---

## Phase 2 — reproduce, then minimise

Run the loop. Watch it go red as the bug appears. Then confirm three things before touching phase 3:

- [ ] The failure is the one **the user described**, not a different failure that happens to live
      nearby. Wrong bug, wrong fix, and the original report reopens.
- [ ] It reproduces across several runs — or at the rate you pinned.
- [ ] The exact symptom is captured verbatim (the error text, the wrong value, the timing number) so
      phase 5 can prove the fix addressed it.

### Minimise

Shrink the red scenario to the **smallest one that still goes red**. Cut inputs, callers, configuration,
data and steps **one at a time**, re-running the loop after each cut, keeping only what stays
load-bearing.

Two reasons this is not optional. It shrinks the hypothesis space in phase 3 — fewer moving parts left
to suspect — and the minimal case *is* the regression test in phase 5, already written.

Done when **every remaining element is load-bearing**: removing any one of them turns the loop green.
Say the count you started with and the count you finished with.

Do not enter phase 3 until you have both reproduced and minimised.
