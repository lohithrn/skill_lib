# `.out-of-scope/` — the declined-findings knowledge base

**The problem this solves: every deferred conflict this skill records today evaporates before the next
run.** `.policy-review/` is per-commit — `SKILL.md` §Artifacts says a directory from a different commit
is stale and poisons the report, so the correct handling is to discard it. Which means the headroom
inventory built in one review is gone by the next, and the same intentional seam gets re-reported
forever. The author answers "that's deliberate", the answer is written to a directory that is then
thrown away, and the next review asks again.

`.out-of-scope/` is the durable half. It lives **in the reviewed repo, committed to git**, and it is
the one thing this skill writes outside `.policy-review/` — and only with the maintainer's explicit
yes, per §Writing below.

Adapted from the triage recipe (Pocock, `skills/engineering/triage`, `OUT-OF-SCOPE.md`), which uses it
for rejected feature requests. Ours carries that plus two kinds that matter more here: **declined
findings** and **recorded headroom**.

---

## 1. What goes in it

| Kind | What it records | Written when |
|---|---|---|
| **declined-finding** | a suggestion this skill made, that the maintainer rejected on the merits | the maintainer says no to a real finding and the reason is durable |
| **headroom** | a seam deliberately left open — an env-scoped name with one value, a knob with one mode, a per-stage resource pointing at one target | a `deferred-conflict` is confirmed intentional by the author |
| **rejected-request** | a feature or refactor the repo decided against | a request is closed as out of scope |

One file per **concept**, never per finding. Three reviews that all flag the same single-resolver port
share one file. This is what makes lookup cheap and the directory readable.

**Not in it:** anything closed because it was *already done*. A built thing recorded as out of scope
poisons every future check — the next review reads "we rejected tenant routing", finds tenant routing
in the code, and reports a reversal that never happened. Point at where it lives instead.

Nor anything temporary. "Not this sprint" is a deferral; it belongs in the PR description. This
directory is for decisions expected to outlive the person who made them.

---

## 2. Reading it — phase 0, every mode, before any finding exists

`review` and `diff` both read every file in `.out-of-scope/` during phase 0, and record the count in
`scope.json`. Then, for each candidate finding, before it is emitted:

- **Match by concept, not by string.** "single-resolver port at the Cognito boundary" matches
  `speculative-ports.md`; "night theme" matches `dark-mode.md`. A grep for the finding's own words
  will miss almost every real match.
- **A match suppresses the finding.** It does not soften it, re-word it, or demote it to `minor`. The
  finding is dropped, and the concept is listed once in the report's `## Declined` section with its
  file — so the reader can see the review considered it and knows why it isn't billed.
- **A match on an `S2` scope-creep candidate inverts the finding.** Behaviour recorded as *rejected*
  and now present in the diff is a `blocker` reversal, not creep (`references/spec-policy.md` §S2).
  Cite the file and quote its reason.
- **Never re-litigate inside a review.** If you believe a recorded decision is now wrong — the
  constraint it cited is gone, the cap it avoided now binds — say so in one line under `## Declined`
  and ask. Do not re-emit the finding and do not edit the file to suit your own conclusion.

No `.out-of-scope/` directory ⇒ nothing to read, nothing to say. Its absence is not a finding, and
this skill never creates it unprompted.

---

## 3. File format

Prose, not a database row. Someone meeting this file for the first time should understand the decision
without finding the original discussion. Paragraphs and a code sketch beat a table.

```markdown
# Single-resolver ports at I/O boundaries

This repo deliberately keeps ports that have exactly one resolver where the seam sits on an
I/O boundary. Reviews should not report these as Speculative Generality.

## Why this is declined

The port is what makes the unit testable without the live service. `CognitoDirectory` has one
production resolver and will likely never have two — but the in-memory resolver in
`tests/doubles/` is what lets `tests/test_enrolment.py` run in milliseconds with no AWS
credentials. Collapsing the port would move 40 tests onto a network.

The promotion threshold in `references/graph-policy.md` already allows this ("the branch crosses
an I/O boundary"). This file exists because reviews kept reaching it from the
one-resolver-means-speculative direction instead.

```python
# The shape we keep, deliberately:
class CognitoDirectory(Protocol):       # one method, declared beside its caller
    def lookup(self, user_id: UserId) -> Directory | Absent: ...
```

## Applies to

- `identity/ports/directory.py` — and any port under `*/ports/` with a `tests/doubles/` sibling

## Prior findings

- PCR-G10-007, 2026-02-14 — declined by @lohithrn: "the double is the second resolver"
- PCR-R28-002, 2026-05-03 — declined, same reason
```

Required sections: the **title** (the concept, as a heading a browser of the directory understands),
**Why this is declined**, and **Prior findings** — the finding IDs, dates, and who declined them, so
the file accumulates weight rather than being rewritten.

`Applies to` is optional but does most of the work in practice: a path glob turns the file from prose
into something the next review can actually match against.

### Naming the file

Short kebab-case, naming the **concept**: `speculative-ports.md`, `dark-mode.md`,
`nesting-depth-two.md`, `hardcoded-region.md`. Recognisable from the directory listing without
opening it. Never `PCR-G10-007.md` — a finding ID names one run, not a concept, and the next reviewer
cannot tell what it covers.

### Writing the reason

Substantive and durable. Good reasons cite a technical constraint, a project-scope decision, or a
trade-off that was actually weighed:

- **Constraint** — "the rendering pipeline resolves one palette at build time; runtime switching needs
  a provider around the whole tree."
- **Scope** — "this project authors content; theming is a downstream consumer's concern."
- **Trade-off** — "collapsing the port would move 40 tests onto a network."

Bad reasons, all of which produce a file the next reviewer will reopen: "we don't want this", "too
busy", "the reviewer was wrong", and anything naming a person rather than a reason.

---

## 4. Writing to it

**This skill never writes here on its own initiative, and never in `review`/`diff` without being
asked.** The gate in `SKILL.md` §The gate stands: `.policy-review/` is the only path those modes write
unprompted. A declined decision is the maintainer's to record, so:

### The gate on offering at all

**Not every declined finding earns a file.** A directory of forty entries is read by nobody, and then
the suppression in §2 is silently matching against prose no one maintains. Offer only when all three
hold:

1. **The review will reach it again.** A policy rule genuinely points at this code, so the finding
   regenerates every run. A one-off judgement on a line that is about to be deleted does not.
2. **It is surprising without the reason.** A future reader looking at the code would ask "why is it
   like this?" If the shape reads as obviously correct on its own, the file is load with no signal.
3. **A real trade-off was weighed.** There were genuine alternatives and one was chosen for stated
   reasons. "We don't want that" is a preference, not a trade-off, and §3 §Writing the reason already
   rejects it.

Any one missing ⇒ do not offer. Say the finding is declined for this run and move on. The three-part
test is Pocock's gate for when a decision deserves an ADR (`skills/engineering/domain-modeling`,
`ADR-FORMAT.md`), with his first clause — *hard to reverse* — replaced by test 1: nothing here is hard
to reverse (§5 is one `rm`), so the cost this file buys down is **re-litigation**, not commitment.

1. The maintainer declines a finding, or confirms a `deferred-conflict` is intentional.
2. Check the three-part gate above. Fails it ⇒ stop here.
3. Offer, in one line: "record this in `.out-of-scope/speculative-ports.md` so future reviews skip it?"
3. On a yes, check for an existing file covering the concept.
   - **Exists** ⇒ append to `Prior findings`. Do not rewrite the reason; the original decision stands
     and its wording is the record.
   - **Does not** ⇒ create it with the concept name, the reason in the maintainer's own words, and the
     first `Prior findings` entry.
4. Say which file was written. It is a tracked file in their repo, so it belongs in their next commit
   and the report says so explicitly.

On a no, nothing is written. The finding stays declined for this run and will return next run — which
is the correct outcome, because an unrecorded decision is not a decision the next reader can find.

## 5. Reversing a decision

- Delete the file. The decision is no longer in force.
- Old findings are historical; nothing is re-opened and no report is amended.
- The finding that triggered the reconsideration proceeds through normal review.

A file that has been contradicted by the code — the rejected behaviour now ships — is not
automatically stale. It is either a reversal someone should know about (`S2`, `blocker`) or a decision
that changed without the record being updated. Surface it and ask which; never silently delete.
