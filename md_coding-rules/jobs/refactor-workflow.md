# Job — the refactoring workflow

Four phases, in this order. Rules **22** (inspect), **23** (plan), **24** (preserve behaviour),
**25** (small steps). Do not start phase 2 before phase 1 is done; do not edit before phase 2 exists.

| Phase | Rule | Produces | Edits code? |
|---|---|---|---|
| 1. Inspect | 22 | an understanding of behaviour, entry points, dependency flow | no |
| 2. Plan | 23 | the three-bucket refactoring plan | no |
| 3. Preserve | 24 | the behaviour contract the edits must not break | no |
| 4. Apply | 25 | the 11 ordered steps | yes |

Phase 1 begins with the deterministic checker, not with reading: run `scripts/architecture_lint.py`
with `--json` over the scope and inspect what it flagged first. Its numbers are ground truth — SKILL.md
says why re-counting them by eye is a defect.

Output at the end follows `specs/review-output.md`.

---

### 22. Inspect before editing

Before making code changes, inspect the relevant files and understand:

- Current behavior.
- Entry points.
- Dependency flow.
- Existing abstractions.
- Existing tests.
- Hidden framework conventions.
- Dynamic usage risks.
- Branching patterns.
- Dead-code candidates.

Do not make mechanical changes without understanding the structure.

**Consequence without it:** a mechanical rename breaks a framework convention or a config-driven
dispatch that no call site mentions — see the safelist in `references/dead-code.md` §17.

---

### 23. Produce a refactoring plan

Before editing, create a concise plan.

The plan should identify:

- Files over **250** lines.
- Methods over **25** lines.
- Loop bodies over **8** lines.
- Vague file or folder names.
- Branching chains that select behavior.
- Dependencies created internally.
- Missing interfaces.
- Dead-code candidates.
- Lexical/parser cleanup opportunities.
- Dependency-injection changes.
- Risk areas.

The plan should distinguish between:

| Bucket | Meaning |
|---|---|
| **Definitely** | changes that should definitely be made |
| **Suspicious** | changes that are suspicious but need verification |
| **Do not** | changes that should not be made because they would over-engineer the code |

**The third bucket is not optional.** A plan with only the first bucket is how the anti-overengineering
rules get skipped — write down what you deliberately chose *not* to do, and why
(`references/doctrine.md` §28–30).

Thresholds live in `references/laws.md`; naming triggers in `references/naming.md`; branching triggers
in `references/doctrine.md`.

---

### 24. Preserve behavior

Refactoring must preserve behavior unless the user explicitly asks for behavior changes.

When possible:

- Keep public APIs stable.
- Keep existing tests passing.
- Add tests for extracted behavior.
- Use fake or mock implementations for injected interfaces.
- Avoid changing data formats unless requested.
- Avoid changing error behavior unless requested.

Error behaviour and data formats are contracts even when nothing documents them as one: a caller is
already catching that exception type. Test shape is in `references/testing.md`.

---

### 25. Refactor in small steps

Prefer incremental changes.

A good order is:

1. Remove obvious dead imports and dead local code.
2. Improve vague file or folder names when safe.
3. Extract long methods.
4. Extract long loop bodies.
5. Introduce interfaces at real boundaries.
6. Move concrete construction to dependency configuration.
7. Replace behavior-selection conditionals with strategies or handlers.
8. Split oversized files.
9. Clean up lexical/parser responsibilities.
10. Run or describe tests.
11. Summarize architectural improvements.

**The order is load-bearing.** Deletion comes first because everything after it is cheaper on a smaller
tree. Interfaces are introduced (step 5) *before* construction moves to the composition root (step 6),
and both come before conditionals are replaced (step 7) — because a strategy swap needs the interface
and the root to already exist. Splitting files (step 8) is late on purpose: methods and loop bodies are
already extracted, so the split lines are obvious.

Keep commits focused by responsibility, one step at a time — see the Git block in
`references/operational-rules.md`.
