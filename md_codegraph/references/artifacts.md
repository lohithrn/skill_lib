# `.codegraph/` — what it holds, and how a run ends

Every path this skill writes is listed below with a **disposition**, and the last phase of a run takes
it. A path that is not in this table must not be written: the file nobody deletes, because nobody is
sure it is safe to, is the debt this file exists to prevent.

Two kinds, and the kind is a property of the file, not of the mood the run ends in:

- **scratch** — measured against one commit sha, spent when the phase that reads it returns. Deleted.
- **durable** — records a decision that outlives the run. Committed, through git, in the repo's
  `documentation/` folder.

## The table

| Path | Written by | Kind |
|---|---|---|
| `.codegraph/scope.json` | phase 0a (the answered scope), extended by phase 0 | scratch |
| `.codegraph/oracle.json` | phase 0 | scratch |
| `.codegraph/graph.raw.json` | `codegraph-cartographer` | scratch |
| `.codegraph/graph.dim.json` | `codegraph-cartographer` | scratch |
| `.codegraph/graph.json` | phase 1 merge | scratch |
| `.codegraph/caps.json` | `caps` dimension | scratch |
| `.codegraph/<dim>.json` · `.codegraph/<dim>.md` | one per `codegraph-inspector` | scratch |
| `.codegraph/report.md` | phase 1 | scratch, **promotable** |
| `.codegraph/restructure.md` | phase 2 | scratch — spent once every slice is applied and verified |
| `.codegraph/applied.md` | phase 4, appended per slice | scratch — superseded by the commit bodies |
| `.codegraph/verify.md` | phases 3 and 5 | scratch, **promotable** |
| `.codegraph/caps.after.json` · `.codegraph/graph.after.json` | phase 5 | scratch |

Nothing outside `.codegraph/` is written by `analyze`, `review`, `spec` or `verify`, and `tests/` plus
the source tree are the only things `fitness` and `apply` add to.

## Ending a run

The **last phase that runs** does this, in order, and says in its verdict line which branch it took:

1. **Promote the headroom first, before deleting anything.** Every `DEFERRED CONFLICT` in
   `report.md` is a decision not to promote a conflict *yet*, with a reason. Deleted, it is
   re-discovered and re-reported on every future run — the same failure `md_policy-code-review` keeps
   `.out-of-scope/` committed to avoid. Write each one into `documentation/` (or `.out-of-scope/`, if
   that repo already has one) and commit it. **This step is not optional and not conditional.**
2. **Ask whether anything else is still useful.** `report.md` and `verify.md` are the only two
   candidates: one holds findings nobody has acted on, the other holds the measured verdict for a
   restructure that is now in the history. If the user says either still teaches something, it is
   **committed** — moved to `documentation/`, with the semantic commit subject
   `docs(architecture): record the <n>-finding codegraph report`.
3. **Delete `.codegraph/` .** Everything left is a measurement of a commit sha that the applied slices
   have already moved past. Report the deletion in one line; never delete silently.

**Never add `.codegraph/` to the target repo's `.gitignore`.** Ignoring keeps the directory *and*
hides it: it stops appearing in `git status`, so nobody is reminded it is there, and the next run reads
a `scope.json` measured against a commit that no longer exists — a stale artifact poisons a report
exactly as surely as a wrong one. There are two exits, deleted or committed, and no third.

## Resuming is why the deletion is last, not per phase

Bare `/md_codegraph` resumes by reading `.codegraph/` — no spec ⇒ analyze, unchecked approval ⇒
re-print the gate, slices left ⇒ apply the next one. So the directory is the run's state machine and
**must survive between invocations**. Delete it only when the state machine has reached its end:

| Run ended at | Delete `.codegraph/`? |
|---|---|
| phase 1, findings reported, no spec asked for | yes — after step 1 above |
| phase 2, spec written, gate not approved | **no.** The spec is the pending question; deleting it discards the user's next decision |
| phase 4, slices left unapplied | **no.** `applied.md` is how the next run knows where it stopped |
| phase 5, every slice applied and verified | yes — the full three steps |
| any phase, `UNVERIFIED` because no oracle was found | yes, and say the verdict is unverified |

A run the user abandons leaves a stale directory behind, and that is the one case this contract does
not cover on its own: the next run detects the sha mismatch, says so, and asks. It never silently
measures against the old one.
