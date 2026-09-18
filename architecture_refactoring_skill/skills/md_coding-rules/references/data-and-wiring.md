# Data and wiring hard rules — persistence, metadata, factories, resource naming

Answers: *how does a write happen, what does an endpoint accept, and what is this cloud resource
called?*

**These are hard rules for the codebase they govern. They are not stylistic suggestions.** They were
written for one multi-tenant service, so the mechanics are specific — a key-value document store, an
identity provider with custom attributes, a per-stage resource naming convention. Read them as the
concrete form the earlier rules take when the boundary is a cloud API instead of a Python module.

Five rules: **31** (GET+PUT only), **32** (arbitrary metadata accepted), **33** (no magic strings),
**34** (centralize object creation), **35** (every resource name is composed, never typed).

---

### 31. DynamoDB: GET + PUT only — never `update_item`

Never use DynamoDB `update_item` / `UpdateExpression` anywhere, for any table (private, public,
tenants, or any other), on any operation.

Every mutation — create AND update — is implemented as **GET → MERGE → PUT**:

1. **GET** the existing item (an empty dict when it does not exist yet).
2. **MERGE** the new values onto it in code, in this exact precedence order (each step overwrites the
   previous on key collision):
   1. the existing item (from the GET),
   2. the request **body**,
   3. the **query parameters**,
   4. the **path parameters**.

   So path parameters win over query parameters, which win over body, which win over what was already
   stored. Service-managed/immutable fields (e.g. `creator_time`, `user_id`) are applied last by the
   writer and are never taken from caller input.
3. **PUT** the whole merged item back.

A plain create is just this with an empty GET result. This is the only accepted shape for a DynamoDB
write in this codebase.

**The precedence order is the load-bearing part.** Four sources can supply the same key; without one
written-down order, two handlers resolve the collision differently and the stored item depends on which
endpoint wrote it. Service-managed fields being applied last is what makes them unspoofable — see
rule 32.

---

### 32. Arbitrary metadata is always accepted and persisted

When an endpoint accepts `metadata` (or any free-form blob), it must accept **any** JSON the caller
sends ("random junk" included) and persist it — flattened into columns for DynamoDB and/or into the
identity provider's `custom:metadata` attribute. Never reject metadata for having an unknown shape.

The ONLY thing rejected is a key that collides with a service-managed/reserved field (so callers cannot
spoof `creator_time`, `user_id`, etc.); that is a **400**.

**Consequence of validating metadata shape:** every new caller field becomes a service deployment, which
is the exact coupling a free-form blob exists to avoid. **Consequence of not rejecting reserved-key
collisions:** a caller sets its own `user_id` and the record's ownership is caller-controlled.

---

### 33. No magic strings — every meaningful string is a named constant

Treat every meaningful string as a magic value to be extracted: env var names, DynamoDB key/attribute
names, header names, path-parameter names, identity-provider attribute names, status keys, table/field
identifiers — none of them are inlined in business logic.

Put them in a localized `<predicate>_constants.py` next to the code that owns them (see rule 7C in
`references/public-api.md`). Tests reference the same constants, never re-spelled literals.

**Consequence without it:** an attribute name spelled two ways writes to two columns, and neither the
compiler nor the test suite says a word — the read simply returns nothing.

---

### 34. Centralize object creation (composition roots / factories)

Centralize the construction of objects as much as possible. Concrete collaborators (boto3
clients/resources, repositories, directories, registrars, services) are built in factory /
composition-root modules (`*_factory.py`), never constructed inside business logic or handlers.

Handlers and services receive their dependencies through constructors (rule 8 in
`references/di-patterns.md`) and ask a factory for a fully wired object. One place builds the object
graph; everything else depends on it.

---

### 35. Every cloud resource name is prefixed by stage + repo, optionally suffixed by company

Every provisioned resource (DynamoDB tables, identity pools, secrets, WAF ACLs, Lambdas, the API, etc.)
is named from a common convention — NEVER hardcoded and never ad-hoc:

```
<prefix>_<resource_role>[_<company>]
prefix  = "<environment>_<project_name>"   # project_name = the repo/folder name
company = lower(company_name)              # the owning company, lowercased
```

Rules:

- **`project_name` is the repo/folder name**, derived at deploy time (`basename $(pwd)`), never typed
  as a literal. It flows into `prefix`.
- **`environment` (stage)** is always the first part of the prefix (`beta_`, `prod_`). Every resource
  name — and every API URL — carries the stage.
- **Company suffix is optional per resource.** Some resources append the lowercased company
  (`_<company>`) as a suffix; others don't. Use it where the service convention calls for it; it is
  supplied at deploy time (`COMPANY_NAME`), never hardcoded.
- **Compose names in ONE place.** A single `naming.tf` `locals` block builds the full names; resource
  files reference those locals. Do not re-spell the prefix/suffix rule per resource.
- **Mind provider length limits** when composing (e.g. Lambda function names are capped at **64**
  chars — use `substr` on the prefix; identity pool names allow **128**).

Example (env `beta`, repo `<ServiceName>`, company `<company>`):
`beta_<ServiceName>_private_configuration_<company>`.

**The stage prefix is deliberate headroom, not duplication.** `beta_` and `prod_` names that today
point at similar resources are what lets one stage be tightened without re-plumbing the other. Do not
collapse them because they currently look the same. The **64**-char Lambda limit is the one that
actually bites: composed names cross it, and the failure is at apply time, not review time.
