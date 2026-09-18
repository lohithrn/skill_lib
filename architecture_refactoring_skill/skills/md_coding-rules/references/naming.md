# Naming — folders, files, methods, and every other identifier

Answers: *what do I call this, and does the name still work when seen alone?*

Four rules: **1** and **2** name the tree, **7F** names methods, **36** extends the standard to every
identifier in the codebase.

---

### 1. Folder hierarchy and responsibility boundaries

Organize code into responsibility-based folders.

A codebase should prefer many focused modules over a few large modules.

Use folder boundaries to separate concepts such as:

- Application orchestration.
- Domain models.
- Interfaces.
- Implementations.
- Infrastructure adapters.
- Configuration.
- Dependency injection.
- Validators.
- Parsers.
- Builders.
- Handlers.
- Repositories.
- Services.

Avoid vague folders unless they are truly necessary:

- `utils`
- `helpers`
- `common`
- `misc`

If a folder contains unrelated concepts, split it.

**Consequence without it:** a vague folder is a magnet — unrelated concepts land in it because there
is no other obvious home, and the folder name stops predicting anything about its contents.

**Tests are not one of those folders.** The responsibility hierarchy above lives under `src/`, and
`src/` holds only what executes in production and what the deploy needs. Tests are a peer of `src/`,
not a child of it:

- `src/` — entrypoints, interfaces, implementations, adapters, configuration, DI, the running code.
- `tests/` — every test: unit, integration, contract, QE, load. Plus fixtures, stubs and recorded
  responses.
- `scripts/`, `local_development/` — generators, publish scripts, harnesses, experiments.

**Consequence without it:** a non-runtime file under `src/` ships in the artifact, so a test double
is one import away from a production code path and a recorded response carrying a real header lands
in your deploy. It also makes dead code undetectable: a module imported only by the test sitting
next to it looks live to every tool you own.

---

### 2. File and folder naming rule

Prefer explicit, responsibility-based file names inside clear responsibility-based folders.

A good path should communicate:

1. The domain subject.
2. The architectural role.
3. The concrete responsibility or implementation.

Preferred structure:

```text
payment/
  interfaces/
    payment_processor_interface.py
  processors/
    stripe_payment_processor.py
    paypal_payment_processor.py
```

This is better than vague short names such as:

```text
payment/
  interfaces/
    processor.py
  processors/
    stripe.py
    paypal.py
```

The folder hierarchy should provide context, but the file name should still be clear when seen alone
in an editor tab, import statement, search result, stack trace, or code review. **That five-context
test is the whole rule:** the folder is not visible in a stack trace.

Prefer file names that include the domain subject and role:

- `payment_processor_interface.py`
- `stripe_payment_processor.py`
- `paypal_payment_processor.py`
- `order_repository_interface.py`
- `postgres_order_repository.py`
- `user_validator_interface.py`
- `default_user_validator.py`
- `token_parser_interface.py`
- `lexical_token_parser.py`

Avoid vague file names unless they are completely obvious and extremely local:

- `processor.py`
- `handler.py`
- `service.py`
- `manager.py`
- `helper.py`
- `utils.py`
- `common.py`
- `base.py`
- `logic.py`

Good file names usually follow one of these patterns:

- `subject_role`
- `subject_action`
- `action_subject`
- `provider_subject_role`
- `subject_interface`
- `subject_implementation_role`

Use explicit names, but avoid bloated names.

Good:

- `stripe_payment_processor.py`

Too much:

- `stripe_external_payment_processor_implementation_for_payment_gateway_strategy.py`

The goal is clarity, not maximum length.

---

### 7F. Method names must be verbose enough to stand alone

A method name is the smallest piece of documentation a class has. If a reader can look at the name in
autocomplete or in a stack trace and immediately know what the method does, the name is doing its job.
If they have to read the body, the parameters, or the surrounding class, the name is failing — even if
the body is fine.

**Rules:**

- Prefer the **verb + noun** form: `find_entities`, `find_relationships`, `find_neighborhood`,
  `find_paths`, `answer`, `search`. Each tells the reader what happens and what is acted on. Bare
  verbs like `do`, `run`, `execute`, `handle`, `process`, `query` carry no information.
- **A method name should not need its parameter list to be understood.** If
  `find_paths(source, target, max_depth)` is clear without seeing the args, that's good. If
  `query(thing, kind, n)` requires reading the args to make sense, the name is doing too little work.
- **Prefer longer, fully-spelled names over short ambiguous ones.** `find_relationships` beats
  `rels`. `answer_natural_language_query` is fine if it removes ambiguity; `answer` is fine if context
  makes the audience obvious. Cheap autocomplete makes long names cost nothing.
- **Disambiguate when two operations share a verb.** `find_entities` vs `find_relationships` vs
  `find_neighborhood` vs `find_paths` — the noun is what makes them readable from a method list.
- **Do not optimize names for typing speed.** Code is read far more often than written, and IDE
  completion makes typing length irrelevant. A name that is harder to type but obvious to read is the
  right tradeoff.
- **Naming applies to private helpers too.** `_validate_int_range`, `_require_existing_directory`,
  `_resolve_artifact_path_kwarg`, `_load_artifact` — each describes its role precisely. `_check`,
  `_helper`, `_do_it` do not.
- **Self-describing names are the documentation.** If the name explains the method, you usually do
  not need a docstring. Reserve docstrings for *why* (non-obvious invariants or cross-cutting
  context), not *what*.

**Bad — vague verbs, abbreviations, parameter dependency:**

```python
class GraphToolCall:
    def query(self, kind, q, n=5): ...        # what kind? what does it do?
    def rels(self, s=None, t=None): ...       # cryptic, single-letter abbrevs
    def nbh(self, e, d=1): ...                # unreadable in autocomplete
    def run(self, s, t, m=3): ...             # "run" what?
```

**Good — verb + noun, full words, self-describing:**

```python
class GraphToolCall:
    def find_entities(self, query: str, limit: int = 10) -> dict: ...
    def find_relationships(self, *, source_query=None, target_query=None) -> dict: ...
    def find_neighborhood(self, entity_query: str, depth: int = 1) -> dict: ...
    def find_paths(self, source_query: str, target_query: str, max_depth: int = 3) -> dict: ...
```

A reader scanning the class header now knows the four operations the graph artifact supports without
reading any implementation.

**Why this matters:**

- A class header full of verb-only or abbreviated names tells the reader nothing. A class header of
  full verb-noun phrases tells the reader the entire capability set.
- Stack traces and logs become self-explanatory. `GraphToolCall.find_paths` in a traceback is
  informative; `GraphToolCall.run` is not.
- Refactors are safer when names are precise: `find_entities` only matches code that finds entities;
  `query` matches everything.

---

### 36. Names are descriptive 3–5 word phrases — clarity over brevity

Identifiers — variables, functions/methods, classes, modules/files, and folders — should be
descriptive multi-word phrases, **three to five words** joined by underscores (snake_case) or in
PascalCase for classes. This extends Rule 7F (verbose method names) to EVERY identifier.

Rules:

- **Prefer subject + object + predicate** (or verb + noun + qualifier). A name should read as a small
  phrase that explains itself without the surrounding code:
  `build_tenant_admin_and_tenant_creation_service`, `find_tenants_by_user_email`,
  `private_configuration_secret_name`, `TenantAdminAndTenantRemovalService`.
- **Three to five words is the sweet spot.** One- or two-word names are usually too terse for
  anything non-trivial (`svc`, `repo`, `data`, `do_it`); past five words it gets noisy. Aim for
  **3–5**; allow more only when it genuinely removes ambiguity.
- **No abbreviations or single letters** outside tiny, obvious loop indices. Spell it out:
  `membership_repository`, not `mem_repo`; `configuration`, not `cfg`.
- **A longer-but-clear name always beats a shorter-but-ambiguous one.** Code is read far more than
  written, and autocomplete makes length free. When in doubt, add the clarifying word.
- Applies to folders too (see Rules 1–2): `registration_services_user_tenant/` beats `services/`.
