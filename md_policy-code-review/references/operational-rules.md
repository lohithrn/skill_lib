# Operational coding rules — errors, logging, async, types, imports, commits

Answers: *the six day-to-day questions that are not about structure.*

Six unnumbered rule blocks. They are as binding as the numbered ones; they are unnumbered because they
are not architecture, they are the mechanics that keep the architecture honest.

| Block | The rule in one line |
|---|---|
| Error handling | raise a type the caller can act on, and put the failing value in the message |
| Logging | a library never configures global logging and never `print`s |
| Async and concurrency | async is visible in the name; the knobs come from configuration |
| Type annotations | every public surface is annotated; `dict`/`Any` are not contracts |
| Import ordering | stdlib, third-party, local — and no import-time side effects |
| Git and pull requests | one responsibility per commit; risks named in the summary |

---

## Error handling

Use explicit domain or configuration errors when callers can act on the failure.

Prefer:

- `ValueError` for invalid constructor/configuration values.
- Custom exception classes for domain-specific failures that callers need to catch.
- Guard clauses near boundaries.
- Error messages that include the failing path, provider, category, or key.

Avoid swallowing exceptions, returning `None` for unexpected failures, or hiding provider errors behind
vague messages.

**Consequence of each:** a swallowed exception makes the failure appear as a wrong answer somewhere
else; a `None` return for an unexpected failure turns one bug into an unrelated `NoneType` crash three
frames away; a message without the failing key cannot be acted on without a debugger.

---

## Logging

Library code should not configure global logging.

Use module loggers or injected logger interfaces when logging is needed.

Do not use `print` in reusable library services except for existing CLI-style scripts being preserved
during migration. Prefer returning structured status or letting the CLI print.

**Consequence without it:** a library that calls `basicConfig` silently reconfigures the host
application's logging, and a library that `print`s writes into the host's stdout contract.

---

## Async and concurrency

Do not mix sync and async casually.

Async boundaries should be explicit in method names and tests. Avoid calling event-loop runners from
deep business logic unless the public API is intentionally synchronous and owns the boundary.

Concurrency settings such as worker counts, throttling, retry policy, and timeouts must come from
configuration or dependency injection.

**Consequence without it:** an `asyncio.run` buried in business logic fails the moment the caller
already has a running loop, and a hard-coded worker count cannot be tuned per deployment or set to 1
in tests.

---

## Type annotations

Public constructors, public methods, interface methods, and configuration objects should have type
annotations.

Use `Protocol` or abstract base classes for replaceable dependencies.

Avoid vague `dict` and `Any` in public APIs unless the data is truly unstructured; prefer dataclasses or
typed result models for stable contracts.

**Consequence without it:** a `dict` return is an undocumented contract — the keys are discoverable
only by reading the producer, and removing one is invisible to every caller until runtime. This is the
same failure as a string-keyed operation in `references/public-api.md` §7B.

---

## Import ordering

Order imports as:

1. Standard library.
2. Third-party packages.
3. Local package imports.

Avoid import-time side effects. Heavy optional provider imports may be placed inside the method that
uses them when the dependency is optional.

**Consequence without it:** import-time side effects make module load order significant, which is the
same defect as module-level mutable state (`references/laws.md` §21), and an unconditional heavy
provider import makes an optional dependency mandatory.

---

## Git and pull requests

Keep commits focused by responsibility.

Do not mix feature work, formatting churn, and unrelated refactors in one change unless the user asks.

Document behavior changes, test coverage, and provider/integration risks in PR summaries.

**Consequence without it:** a behaviour change hidden inside a formatting commit cannot be reviewed and
cannot be reverted on its own — which is the whole point of rule 25 in `jobs/refactor-workflow.md`.

### The subject line carries the type, and the type is a claim

Every commit `refactor` mode makes is `type(scope): imperative summary` — `feat` · `fix` · `refactor` ·
`test` · `docs` · `chore` · `perf` — with a body saying what the step *removed*:

```
refactor(billing): move tier selection behind a TierPolicy handler

Removes the if/elif at billing/invoice.py:88. Step 7 of the refactor plan;
behaviour pinned by tests/test_invoice.py, unchanged.
```

- **`refactor` is a promise that behaviour did not change**, and rule 24 is what makes it true. A
  behaviour change committed as `refactor` makes a later `git bisect` point at the wrong commit — the
  failure mode is not a style complaint, it is a wrong answer during an incident.
- One step of rule 25's order per commit. The step number in the body is what lets a reviewer read the
  sequence back without the plan document, which is scratch and will not survive
  (`references/artifacts.md`).
- Never amend or squash a step that is already pushed; a reviewer reading half a sequence sees a
  restructure that looks unmotivated.
