# Change policy — `C1`–`C6`

Ordinary review of a change: is it correct, does it break anything that worked, is it safe, does it
match its neighbours, and does it carry the tests and docs it owes. This is the group that runs
**first** on a diff, because a correctness bug outranks every structural preference in the same file.

Copied in on purpose so this skill has no run-time dependency on any other review command. Adapted
from the change-review recipe: **comment on exact line ranges, not per-file summaries; fewer,
higher-signal findings beat exhaustive ones; and do not modify files.**

Scope: the changed lines, their enclosing function, and the direct callers of anything whose
signature or behaviour moved. Not the whole tree — that is `review` mode's job.

---

## C1 — Correctness on the change's own terms

Does the new code do what the change says it does, for every input it can actually receive?

Report:

- A path where the stated intent and the code disagree — quote both.
- An input the new code cannot handle: empty, `None`/null, zero, negative, one element, the maximum,
  a duplicate, a unicode name, a value at the exact boundary.
- An off-by-one on an inclusive/exclusive boundary. Cap checks are the usual site: a `>` where the
  rule says "at most" rejects a legal value for no reason.
- Wrong operator precedence, a comparison against the wrong unit (seconds vs epoch **milliseconds**),
  a mutable default argument, an integer division that was meant to be exact.
- An `async` call not awaited, a lock not released on the error path, an iterator consumed twice.

CONSEQUENCE must be a **Break**: input Q produces wrong output R, with the reproducing case. If you
cannot name the input, you have a suspicion, not a finding — say `suspected` and drop the severity to
`minor`.

## C2 — Regressions: what worked before and does not now

The most valuable finding in a diff, and the one a per-file reader misses.

Read the **removed** lines, not only the added ones. For every deletion or signature change:

- A removed branch, guard, `try`, timeout, retry, or validation. Name what it protected against.
- A renamed or re-typed parameter with a call site left on the old shape — search for every caller.
- A default value that changed, especially `None` → a concrete value or the reverse.
- A return type that widened or narrowed (`list` → generator, value → optional).
- Behaviour that moved earlier or later relative to a side effect: an ordering change is a regression
  even when both lines survive.
- Removed configuration, an env var no longer read, a key dropped from a payload a consumer reads.

**Call out every removed line that was not explicitly requested.** A bug fix is not a revert; a
refactor is not a rewrite. This is the working rule the review itself is most often used to violate.

## C3 — Error handling the change owes

- A new call that can fail with no handler, and no error boundary above it.
- A new `except`/`catch` that swallows: no stack, no re-raise, no defined fallback. `blocker` — the
  detailed rule is `G7`, cite that one when the file is source and this one when it is new in a diff.
- A new remote or subprocess call with no timeout, or a retry with no ceiling.
- An error message that names no input, no identifier and no next step, on a path a user reaches.
- A raised error caught by a broader `except` two frames up, so the specific type buys nothing.
- A partially-applied mutation with no compensating path: wrote row A, failed on row B, left both.

## C4 — Security and data handling

- A secret, token, password, private key, account id or connection string in the diff. `blocker`,
  and say **rotate it** — a committed secret is compromised even after the commit is amended.
- **Any machine-generated certificate or keypair used as an authorization mechanism**, or an
  `openssl`/keytool invocation in a deploy, connect or client flow. `blocker`, no exceptions, no
  flag: the only acceptable TLS is a CA-issued or provider-managed certificate we did not generate,
  verified against the system trust store. Prefer SigV4 for gateway auth.
- Interpolated SQL, shell or a path from request data; a `subprocess` with `shell=True` on a value
  from outside; deserialization of untrusted input (`pickle`, `yaml.load`, `eval`).
- Verification disabled: `verify=False`, a permissive host-name check, a pinned-off TLS setting.
- An authorization check added *after* the work it protects, skipped on one branch, or a handler with
  its own auth condition beside the one gate (`H6`).
- A tenant, user or account id taken from the body when the path and the token already carry it, or
  compared with the wrong one of the two.
- PII, a full token, or a whole request body written to a log.
- A new resource with a wildcard IAM action or resource; a bucket, queue or table made public.
- Input that reaches a name composed at run time with no length or character validation (`H2`).

## C5 — Consistency with what is already there

- The change does the same thing the neighbouring file already does, a second way. Name the existing
  helper and its path.
- A name that does not match the local convention: casing, the type word, `fallback_*` not
  `default_*`, purpose not mechanism (`H1`, `G6`).
- A hardcoded value the repo already derives — service name, account id, table name, URL (`H4`, `H5`).
- A new dependency where the repo already vendors an equivalent, or a new module in a folder whose
  siblings all do something else.
- Dead scaffolding the change leaves behind: a flag with one value now, a parameter no caller passes,
  a commented-out block. Handled under `G9` — never delete on suspicion, and the `EVIDENCE` field is
  mandatory.

**The repo's own convention beats this document.** Read the neighbour before ruling. A finding that
fights a pattern the tree follows everywhere is a question for the author, not a suggestion.

## C6 — Tests and docs the change owes

- A changed behaviour with no test that would have failed before it. Name the test file that should
  hold it and the case it should assert — not "add tests".
- A new branch, resolver or handler with no case covering it, and no registration test proving it is
  wired (`G8`).
- A test edited so it passes rather than because the contract changed. **Never rewrite a contract
  suite to make an implementation pass** — that inverts the oracle. This is a `blocker` when the
  edited assertion is the only thing that covered the changed line.
- A bug fixed with no regression test for the exact input that failed.
- A changed route, env var, deploy step or public signature not reflected in the README or the
  configuration file that documents it.
- A new plan-time or apply-time assumption with no assertion at plan time (`H2`).

Never run the repo's suite to decide this. Read what it enforces.

---

## How to report a `C` finding

Same nine fields as everything else (`specs/suggestion.md`), plus these habits from the recipe:

- **Exact ranges.** `handlers/create.py:88-94`, never `handlers/create.py`. A per-file summary is not
  a finding.
- **Fewer and higher signal.** Ten small notes bury the one blocker. If two findings share a cause,
  report the cause once at its site and list the other locations inside SYMPTOM.
- **Nothing is modified.** Every `C` finding is a proposal; the report says in one line that the tree
  was untouched.
- **Style the repo's own linter permits is not a finding**, and neither is a phrasing preference.
