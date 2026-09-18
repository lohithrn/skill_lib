# Doctrine — what to prefer, when to abstract, and when to stop

Answers: *is this branch a design problem, and is the abstraction I am about to write worth it?*

This is the whole philosophy plus the two brakes on it. Read it before any other reference: every
other file assumes the promotion rule and the anti-overengineering rules stated here.

---

## Core philosophy

Code should be organized around responsibilities, boundaries, and swappable behavior.

Prefer:

- Small files.
- Small methods.
- Clear class responsibilities.
- Constructor-based dependency injection.
- Injected callable/function references when they simplify utility behavior.
- Interfaces or protocols for replaceable behavior.
- Polymorphism instead of behavior-selection branching.
- Composition-root dependency wiring.
- Guard clauses instead of nested conditionals.
- Dead-code removal.
- Clear encapsulation of public and private behavior.
- Explicit responsibility-based file names.

Avoid:

- God classes.
- God files.
- Hidden dependencies.
- Concrete construction inside business logic.
- Large conditional chains.
- Deeply nested logic.
- Large loop bodies.
- Dead or speculative code.
- Vague utility dumping grounds.
- Abstraction for its own sake.

The goal is to make the codebase easier to understand, easier to test, easier to extend, and easier
to safely change. Look aggressively for architectural improvement opportunities, but avoid
over-engineering.

### Variants are additive, never either/or

When a system has multiple provider or strategy variants that users may want side by side, model them
as independent, additive variants. Do not collapse them into an either/or choice unless the business
rule truly says only one can exist. Each variant should own its output path, metadata identity, tests,
and public wiring so it can be extracted into a separate library later without entangling unrelated
variants.

**Consequence of collapsing them:** the extraction later is not a move, it is a rewrite — the two
variants share an output path and a metadata identity that has to be untangled first.

### Keep a companion scope document

A service with a hard boundary against a shared library or an external identity provider needs a
companion scope document that records what is **in scope** for the service and what is explicitly
**not its business**. Write the out-of-scope list down, by name, next to the in-scope list.

**Consequence without it:** the boundary is re-litigated on every ticket, and behaviour that belongs
to the library leaks into the service one "small exception" at a time.

---

## Branching and polymorphism

### 13. Avoid behavior-selection branching

Treat `elif`, `else-if`, and `switch`-style logic that selects behavior as a design smell, not an
automatic violation.

Behavior-selection branching usually means the code is choosing between different strategies,
providers, handlers, parsers, modes, exporters, importers, or workflows.

This should usually become:

- Polymorphism.
- Strategy classes.
- Handler classes.
- Registry-based dispatch.
- Injected implementation.
- Factory configured at the composition root.
- Interface-backed implementation swapping.

Branching based on these values is suspicious:

- Type.
- Mode.
- Provider.
- Status.
- Event name.
- Command name.
- Parser kind.
- Export format.
- Import format.
- Integration name.
- Workflow name.
- Operation name.

When this type of branching appears, inspect deeply for dependency-injection and polymorphism
opportunities.

Do not replace a small stable branch with a registry or interface hierarchy when the branch is
clearer.

Allowed simple mappings:

```python
if provider == "local":
    return LocalProvider()
if provider == "remote":
    return RemoteProvider()
raise ValueError(f"Unsupported provider: {provider}")
```

**Refactor toward polymorphism or a registry when:**

- Cases contain substantial behavior, not just construction or lookup.
- Cases are expected to grow.
- Cases are duplicated in multiple places.
- Cases require different dependencies.
- Tests need to swap implementations.
- The branch hides provider-specific infrastructure inside business logic.

That six-item list is the promotion threshold. None of it true ⇒ leave the branch alone.

**Consequence of promoting too early:** an interface farm — see rules 28–30 below. **Consequence of
promoting too late:** the same discriminant is switched on in three files and the fourth provider is
added to two of them.

---

### 14. Guard clauses are allowed

Do not blindly replace every `if` statement. Simple guard clauses are acceptable.

Allowed uses include:

- Null checks.
- Empty checks.
- Validation checks.
- Permission checks.
- Early returns.
- Error handling.
- Boundary checks.
- Defensive programming.
- Simple boolean decisions that do not select an implementation.

Prefer guard clauses over nested `else` blocks.

Avoid unnecessary `else` after `return`, `raise`, `continue`, or `break`.

**Consequence without this rule:** a reviewer who treats every `if` as a violation converts null
checks into strategy classes, and the null check becomes three files.

---

### 15. Replace conditional chains carefully

When replacing conditional chains, preserve behavior. Do not create unnecessary abstractions.

Use this decision rule:

| The branch… | Do this |
|---|---|
| chooses behavior | consider polymorphism or dependency injection |
| validates state | keep it simple |
| maps a small stable value | a dictionary or small mapper may be enough |
| contains large logic blocks | extract implementations |
| is expected to grow | use a registry or strategy pattern |
| has only one implementation and no meaningful variation | avoid premature abstraction |

---

## The brakes

### 28. Do not abstract without value

Do not introduce an interface, class, folder, registry, or dependency-injection layer unless it
provides at least one of these benefits:

- Removes real duplication.
- Isolates real behavior variation.
- Improves testability.
- Protects a meaningful boundary.
- Makes a large method smaller and clearer.
- Makes a large file more cohesive.
- Replaces a growing behavior-selection branch.
- Separates infrastructure from business logic.
- Enables a concrete implementation to be swapped.

If the abstraction does not provide value, do not create it.

---

### 29. Keep simple code simple

Simple validation logic can remain simple.

Simple guard clauses can remain simple.

Simple one-off transformations can remain simple.

Do not turn every small decision into a class. Do not replace readable code with unnecessary
indirection.

Architectural purity is less important than practical clarity.

---

### 30. Avoid interface explosion

Not every class needs an interface. Use interfaces for boundaries and variation points.

Avoid creating meaningless pairs such as:

- `ThingInterface`
- `DefaultThing`

unless there is a real reason.

A single concrete class is acceptable when it is not a boundary, not externally replaceable, and not
hard to test.

---

## Bad refactoring examples

Four named anti-patterns. Each is a *refactoring* that made the code worse.

### Bad: turning a small stable mapping into a framework

Do not replace this:

```python
if provider == "local":
    return LocalProvider(model_name)
if provider == "remote":
    return RemoteProvider(region, model_id)
raise ValueError(f"Unsupported provider: {provider}")
```

with five files, three interfaces, a registry, and a factory unless the mapping is growing,
duplicated, dependency-heavy, or hard to test.

Good refactor:

- Keep the small mapping in the composition root.
- Return interface-typed implementations.
- Move only provider-specific behavior into provider classes.

### Bad: interface for every class

Do not create:

```text
invoice_total_calculator_interface.py
default_invoice_total_calculator.py
```

when there is only one calculator, no external boundary, and no meaningful swap.

Good refactor:

- Keep one `InvoiceTotalCalculator`.
- Add an interface later if a second implementation or testing boundary appears.

### Bad: composition root everywhere

Do not pass `ConfigDependencyInjection` into every small service and let services pull dependencies
out of it.

Good refactor:

- Top-level wrappers may receive the dependency configuration.
- Lower-level services receive the specific interfaces they need.

This is the same failure as rule 11 in `references/di-patterns.md`, seen from the refactoring side.

### Bad: splitting a script into noise

Do not turn a readable 50-line one-off script into 12 files.

Good refactor:

- Extract only real responsibilities.
- Keep a script simple when it has no reusable domain behavior.
- Prefer one clear function over a fake layered architecture.

---

## Decision standard

Use this standard for every change.

A change is **good** when it makes the codebase:

- Easier to understand.
- Easier to test.
- Easier to modify.
- Easier to extend.
- Less coupled.
- More cohesive.
- Less branch-heavy.
- Less dependent on concrete implementations.
- Cleaner of dead or speculative code.
- Clearer from folder paths and file names.

A change is **bad** when it only makes the codebase:

- More abstract.
- More fragmented.
- More difficult to trace.
- More dependent on configuration magic.
- More mock-heavy.
- More ceremonial.
- More confusing for future maintainers.

The final goal is clean, practical architecture — not abstraction for abstraction's sake.
