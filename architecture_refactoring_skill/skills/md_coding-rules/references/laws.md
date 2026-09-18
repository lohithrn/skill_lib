# Laws — the numeric caps, encapsulation, and the global-state ban

Answers: *how big may this be, what belongs in public, and where may a value live?*

Six rules: **3**, **4**, **5** are the three measurable caps; **6** and **7** are the encapsulation
rules that decide what a split produces; **21** bans module-level mutable state.

## The caps at a glance

| Limit | Hard cap | Resolution |
|---|---|---|
| Source file length | **250 lines** | split by responsibility |
| Method length | **25 lines** | extract a *named* private method or a collaborator |
| Loop body length | **8 lines** | extract the body into a per-item method |

Every number below is a review trigger, not a formatting rule: the cap is the point at which you
**inspect**, and the answer may legitimately be "this one stays".

---

### 3. File size rule

No source file should exceed **250 lines**.

If a file is over 250 lines, inspect it for split opportunities.

Split by responsibility, not randomly.

Good reasons to split a file:

- It contains multiple classes with different responsibilities.
- It mixes orchestration, validation, persistence, parsing, and transformation.
- It contains both interfaces and several concrete implementations.
- It contains large private helper sections that deserve their own collaborator.
- It has unrelated logic grouped only because it was convenient.

Rare exceptions are allowed only when splitting would reduce clarity.

**Consequence without it:** nobody reads a 900-line file top to bottom, so its second half accretes
duplicates of its first half.

---

### 4. Method size rule

No method should exceed **25 lines**.

If a method is over 25 lines, inspect it for extraction opportunities.

Extract logic into private methods or collaborator classes when the extracted part has a clear
responsibility.

Do not create meaningless tiny methods with names like:

- `_do_stuff`
- `_handle`
- `_process`
- `_execute`
- `_finalize`

Method extraction is good only when the method name explains the responsibility. Extraction into a
name that says nothing moves the reading cost, it does not remove it. See `references/naming.md` §7F.

---

### 5. Loop body rule

If a `for` loop or `while` loop has more than **8 lines** inside the loop body, extract the loop body
into a separate method.

The loop should show repetition.

The extracted method should show the per-item behavior.

Prefer:

- `self._process_item(item)`
- `self._validate_record(record)`
- `self._map_token(token)`
- `self._dispatch_event(event)`

Avoid long inline loop workflows.

**Consequence without it:** the loop and the per-item work are read as one thing, so a reader cannot
tell which lines run once and which run *n* times — the usual home for an accidental O(n²).

---

## Encapsulation

### 6. Public and private method structure

Public methods should describe **what** a class does.

Private or protected-style methods should describe **how** the class does it.

A class should usually read like this:

1. Public orchestration method.
2. Private validation method.
3. Private transformation method.
4. Private execution method.
5. Private mapping or cleanup method.

Public methods should be minimal and meaningful.

Internal steps should be hidden unless they are part of the actual public contract.

**Consequence without it:** every internal step becomes a promise to callers, and the class can no
longer be reorganized without breaking someone.

---

### 7. Class responsibility rule

Each class should have one clear reason to change.

A class should not simultaneously:

- Validate input.
- Parse data.
- Save to a database.
- Call external APIs.
- Format responses.
- Send notifications.
- Select implementations.
- Own dependency wiring.

When a class has too many responsibilities, extract collaborators.

That eight-item list is the split checklist for rule 3: when a 250-line file has to be split, split it
along whichever of those eight it is doing at once. "Selects implementations" and "owns dependency
wiring" belong to the composition root instead — `references/di-patterns.md`.

---

### 21. Global state is prohibited

Do not add module-level mutable state or module-level configuration variables.

Allowed module-level values are limited to imports, class/function definitions, and narrowly scoped
static constants in dedicated constant/configuration modules when constructor injection is not the
right fit.

Business values, runtime configuration, provider choices, output paths, clients, and test fixtures
must be passed through constructors, dependency-injection objects, setup methods, or local variables.

**Consequence without it:** the value is set by whichever module imported first, tests leak state into
each other, and the dependency does not appear in any constructor — so nothing about the class
signature reveals it.

The constants exception is narrow and has its own rules: see `references/public-api.md` §7C for what
may live in a `<predicate>_constants.py` and what may not.
