# `.policy-review/` and `.out-of-scope/` — the two kinds, and how a run ends

This skill writes exactly two directories into the analysed repo, and they are opposite kinds. Getting
them the wrong way round is the only way this skill creates debt: delete the durable one and the same
seam is re-reported forever; keep the scratch one and every later report is measured against a commit
that has moved.

| Kind | Directory | Lives for | Exit |
|---|---|---|---|
| **scratch** | `.policy-review/` | one run, against one sha | **deleted** by the run that made it |
| **durable** | `.out-of-scope/` | until the decision changes | **committed**, and never tidied away |

## `.policy-review/` — scratch

Everything a `review` or `diff` writes lands here, and nothing else is written by those two modes:

| File | Contents |
|---|---|
| `.policy-review/scope.json` | languages, entry points, exclusions, which groups apply and why |
| `.policy-review/oracle.json` | the exact command behind every number, and whether it ran |
| `.policy-review/<group>.json` | one per group run: `R`, `G`, `H`, `C`, `S` |
| `.policy-review/spec.json` | the spec source, how it was found, and whether it was readable |
| `.policy-review/report.md` | the full report, section order per `specs/suggestion.md` §4 |

A `.policy-review/` from a different commit is stale and poisons the report: stop and ask.

## Ending a run

In order, and say in the summary which branch was taken:

1. **Promote the headroom first.** Every `deferred-conflict` the run recorded goes into
   `.out-of-scope/` on an explicit yes, and is committed. A seam recorded only in `.policy-review/`
   dies with the directory and gets re-reported on every future review — the whole reason
   `.out-of-scope/` exists (`references/declined.md`).
2. **Ask whether `report.md` is still useful.** Findings nobody has acted on are worth keeping;
   findings already fixed in the same session are not. If it is worth keeping it is **committed** into
   `documentation/`, subject `docs(review): record the <n>-finding policy review`. The other four
   files are never worth keeping — they are inputs to a report that has now been written.
3. **Delete `.policy-review/` and report the deletion in one line.** Never delete silently, and never
   delete on a mode that has not finished: a `diff` interrupted before `S` ran still holds the scope
   the next attempt needs.

**Never add `.policy-review/` to the repo's `.gitignore`.** Ignoring keeps the directory *and* hides
it — it stops appearing in `git status`, so nobody is reminded it is there, and the next run reads a
stale `scope.json` instead of stopping to ask. Scratch has two exits, deleted or committed, and there
is no third worth having.

## `.out-of-scope/` — durable, and not yours to tidy

Read every run, matched by concept rather than by line, written only on an explicit yes, and
**committed to the repo**. It is durable precisely because `.policy-review/` is not.

- **Deleting it is a regression, not cleanup.** A declined finding is a decision with a reason; the
  reason is what stops the next reviewer re-litigating it.
- It holds decisions, not measurements, so nothing in it is invalidated by a new commit — which is
  exactly the difference from every row in the scratch table above.
- Format, matching rules and what qualifies: `references/declined.md`.
