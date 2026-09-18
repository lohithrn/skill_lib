# Dependency injection — constructors, interfaces, the composition root, registries

Answers: *who constructs this, and how does the class say what it needs?*

Seven rules: **8** (constructor injection), **9** (depend on interfaces), **10** (the root),
**11** (no service-locator misuse), **12** (layered packages, and callable vs interface),
**26** (centralize selection), **27** (registries).

The one-line version: **the composition root builds the object graph; every other class receives what
it needs through its constructor and never constructs a collaborator.**

---

### 8. Constructor injection is required

Dependencies must be injected through constructors.

Do not instantiate concrete dependencies inside business logic.

Avoid:

- Creating repositories inside services.
- Creating HTTP clients inside use cases.
- Creating validators inside handlers.
- Creating parsers inside orchestration logic.
- Importing concrete implementations deep inside business logic.

Prefer constructor-injected dependencies.

A class should clearly reveal its dependencies through its constructor.

Verbose constructor names are acceptable when they make dependency responsibilities obvious. Use one
naming convention per API. In Python, prefer explicit snake_case such as
`configurations_and_constants`, `dependency_injection`, `output_root`, and `category`. Do not expose
duplicate aliases for the same constructor concept.

**Consequence without it:** the dependency is invisible in the signature, so the class cannot be
tested without the real collaborator, and two aliases for one concept mean callers disagree about
which is canonical.

---

### 9. Depend on interfaces, not concrete implementations

When a dependency represents replaceable behavior, depend on an interface, protocol, or abstract base
class.

Use interfaces for:

- Repositories.
- External clients.
- Payment processors.
- Notification senders.
- Parsers.
- Tokenizers.
- Validators.
- Exporters.
- Importers.
- Event handlers.
- Strategy implementations.
- Provider-specific behavior.
- Mode-specific behavior.

Do not introduce an interface automatically for every class.

Create an interface when it protects a real boundary, supports testing, or enables meaningful
implementation swapping. Those three tests are the whole gate — see rule 30 in
`references/doctrine.md` for what happens when they are skipped.

---

### 10. Dependency configuration root

For layered Python libraries, dependency wiring should default to:

```text
config_dependency_injection.py
```

or inside a dependency-injection package that contains:

```text
config_dependency_injection.py
```

This file should contain the composition-root dependency class, usually named:

```text
ConfigDependencyInjection
```

This class is responsible for deciding which concrete implementations are used.

Business logic should not decide implementation choices.

Framework-native composition roots are allowed when the framework strongly expects them. Examples
include FastAPI dependency modules, Django settings/app configuration, CLI bootstrap modules, or
plugin manifests.

Even when using a framework-native root:

- Identify the composition root clearly.
- Keep implementation selection out of business logic.
- Keep constructor injection for core classes.
- Do not scatter provider/client construction across handlers or services.

**Consequence without one identified root:** there is no single place that answers "what runs in this
deployment?", so the answer is assembled by reading every handler.

---

### 11. Avoid service locator misuse

The dependency-injection configuration may be passed into top-level orchestration classes when
appropriate.

However, lower-level business classes should receive the specific interfaces they actually need.

Avoid passing the entire dependency configuration object into every class if that class only needs one
or two dependencies.

Bad architectural smell:

- A class receives `ConfigDependencyInjection`.
- The class pulls dependencies from it internally.
- The class hides what it really depends on.

Preferred pattern:

- The composition root builds the object graph.
- Each class receives explicit dependencies through its constructor.
- Dependencies are typed as interfaces where appropriate.

**Consequence without it:** every class depends on everything, so the constructor stops being a
truthful list of dependencies and rule 8 buys you nothing.

---

### 12. Explicit layered architecture preference

Prefer old-school, explicit, layered package structure for non-trivial libraries.

Good layers usually include:

| Layer | Holds |
|---|---|
| `configuration` | immutable configuration models and validation |
| `dependency_injection` | composition root and implementation selection |
| `interfaces` | protocols or abstract interfaces for replaceable boundaries |
| `services` | application orchestration with clear methods |
| `adapters` or provider folders | concrete external integrations |
| `models` or domain folders | data structures and domain concepts |
| `tests` | scenario tests plus utility support |

Core classes should depend on interfaces and constructor arguments, not concrete providers.

When a dependency is only one small operation, an injected callable may be clearer than a full
interface and implementation class.

**Prefer a callable for:**

- Small transformations.
- Clock/time providers.
- ID generators.
- Path resolvers.
- Retry/sleep functions.
- Lightweight parsing or formatting hooks.

**Prefer an interface/protocol for:**

- Multiple related operations.
- External clients.
- Stateful collaborators.
- Provider implementations.
- Behavior that needs a named contract across modules.

Methods should read like carefully named steps in a procedural story. Prefer a few beautiful,
intention-revealing methods over clever compressed logic.

Avoid anonymous generic layers such as `utils`, `helpers`, or `misc` unless the scope is tiny and
local.

---

## Composition rules

### 26. Centralize implementation selection

Implementation selection belongs in `config_dependency_injection.py`.

Do not scatter implementation selection across business logic.

The dependency config should build:

- Repositories.
- Services.
- Use cases.
- Handlers.
- Validators.
- Parsers.
- External clients.
- Strategy registries.
- Handler registries.
- Orchestrators.

---

### 27. Registry pattern

Use registries when many implementations are selected by key.

Good candidates:

- Event handlers.
- Command handlers.
- Exporters.
- Importers.
- Parsers.
- Provider integrations.
- Workflow handlers.
- Status handlers.

The registry should usually be created in the dependency configuration.

Business logic may ask the registry for the correct handler, but should not contain long conditional
chains.

**Consequence without it:** the key-to-handler mapping is re-spelled as an `elif` chain in every
caller — which is rule 13 in `references/doctrine.md`, arriving by a different door.

The factory-module form of rules 26 and 34 — `*_factory.py` modules for boto3 clients, repositories
and registrars — is in `references/data-and-wiring.md`.
