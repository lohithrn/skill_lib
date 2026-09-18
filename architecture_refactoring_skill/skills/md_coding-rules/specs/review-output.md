# Output contract — the review checklist and what the report must contain

Two halves. The **checklist** is what you run against the code. The **output expectations** are what
the report must contain when you are done. Neither is optional; a report missing a section is
incomplete, not brief.

---

## Review checklist

When reviewing code, check the following:

**Size and shape** — `references/laws.md`

- [ ] Does any file exceed **250** lines?
- [ ] Does any method exceed **25** lines?
- [ ] Does any loop body exceed **8** lines?
- [ ] Are classes exposing too many public methods?
- [ ] Are private methods hiding internal implementation details clearly?

**Naming** — `references/naming.md`

- [ ] Are file and folder names explicit enough?
- [ ] Would a file name still make sense in an editor tab, import statement, search result, stack
      trace, or code review?
- [ ] Are utility/helper modules becoming dumping grounds?

**Branching** — `references/doctrine.md`

- [ ] Are there large `if` / `elif` / `else` or `switch` chains?
- [ ] Do conditionals select behavior that should be polymorphic?

**Dependency injection** — `references/di-patterns.md`

- [ ] Are dependencies constructed inside business logic?
- [ ] Are implementation choices centralized in `config_dependency_injection.py`?
- [ ] Are dependencies injected through constructors?
- [ ] Are interfaces used at meaningful boundaries?

**Public API surface** — `references/public-api.md`

- [ ] Are public operations exposed as **direct typed methods** rather than dispatched through bare
      strings? Is every fixed-set parameter a typed `Enum` instead of a string?
- [ ] Does every enum group **two or more related values**? Single-member enums must be deleted in
      favor of a named constant + direct method.
- [ ] Are meaningful string literals **localized in `<predicate>_constants.py` modules** next to the
      domain they govern, instead of inlined or dumped into a global `constants.py`?
- [ ] Are repeated string-shaped concepts (category, model id, tool name, header) protected by a small
      wrapper type so the type system distinguishes them from arbitrary `str`?

**Dead code** — `references/dead-code.md`

- [ ] Are there dead classes, methods, variables, imports, or branches?
- [ ] Is lexical/parser/tokenization code still active and useful?
- [ ] Is any code kept only because it might be useful later?

**The brakes** — `references/doctrine.md`, `references/testing.md`

- [ ] Would the proposed refactor improve clarity, or just add ceremony?
- [ ] Can the code be tested with fake or mock dependencies?
- [ ] Is the behavior preserved?

The last three are the ones that get skipped under time pressure, and they are the ones that decide
whether the review made the codebase better or merely more abstract.

---

## Output expectations

When applying this skill, provide:

1. A concise architectural assessment.
2. A refactoring plan.
3. Specific files or areas to change.
4. Naming improvements when unclear names exist.
5. The reasoning for dependency-injection or polymorphism changes.
6. The reasoning for any code deletion.
7. Any risk or uncertainty.
8. The final code changes, when editing is requested.
9. A summary of what improved.

**Do not only say that code is bad.**

Explain what structural issue exists and how to fix it.

### Exceptions must be named, never taken silently

Every rule you did not apply is a line in the report: the rule number, the file, and why the exception
is justified. **Clearly identify any justified exception rather than inventing one** — do not weaken a
threshold, substitute a preference, or skip a rule because the existing codebase already violates it.

The three legitimate sources of an exception, each of which still has to be stated:

| Exception | Granted by | What the report must say |
|---|---|---|
| a file, method or loop body stays over cap | rules 3–5, "rare exceptions… only when splitting would reduce clarity" | the measured number and why splitting would cost clarity |
| a branch, validation or transformation stays simple | rule 29 | which of the promotion criteria in rule 13 it fails |
| an abstraction is refused | rule 28 | which of the nine benefits it would not have delivered |

**Consequence without this section:** an unstated exception is indistinguishable from an unnoticed
violation, so the next reviewer re-finds it and the one after that "fixes" it.

Items **5**, **6** and **7** are the ones that make the report reviewable. A dependency-injection
change without its reasoning cannot be argued with; a deletion without its reasoning cannot be
audited against the safelist in `references/dead-code.md`; and an unstated uncertainty is a claim the
reader will take as certain.
