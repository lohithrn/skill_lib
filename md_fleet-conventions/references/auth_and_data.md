# Authorization, and what the data rules are

## Authorization: one gate, OR'd credentials

- Every handler's **first statement** is `authorized_tenant(event)`, which calls exactly one
  function — `verify_authorization()`. **Commenting out that one function's body removes
  authorization from the whole application.** Nothing else raises a 401; no handler has a second
  condition of its own.
- **Consequence of a second condition anywhere:** the property above stops being true, and nobody can
  answer "what authorizes this route" by reading one file. Every audit becomes a survey.
- Two credentials, an **OR**, selected by the `Authorization` scheme so the two never contend and one's
  refusal is never re-reported as the other's:
  - `Bearer <jwt>` (or `Basic` for machine-to-machine) via the shared multi-tenant auth library,
    scoped to **one** tenant. Requires `Authorization`, `AuthorizationTenant`, `AuthorizationRegion`.
  - `AWS-SIGV4 <signed sts:GetCallerIdentity>`, permitted to act as **any** tenant — the
    company-administrator path, for someone fixing a customer's data with no tenant password.
    **The service never recalculates a signature; AWS authenticates and we ask who signed.**
- The IAM role's **trust policy is the access list**. Adding a person is a tfvars entry, not a code
  change, and removing one is the same entry deleted.
- *How* each credential is proven lives one-folder-per-strategy behind one interface, so a third way in
  is a new folder plus one table entry — the "exactly one gate" property survives the addition.

**The global ban outranks all of the above: never mint a certificate or a keypair as an authorization
mechanism.** The only acceptable TLS is a CA-issued or cloud-provider-managed certificate nobody here
generated, verified against the system trust store. Authorization direction is SigV4.

### Why the scheme selects, rather than trying both

Trying both and returning the last failure reports a SigV4 problem as a bad JWT, and the caller then
debugs the wrong credential. One scheme, one code path, one refusal message that names the credential
the caller actually sent.

---

## Data conventions

### Epoch milliseconds everywhere in the backend

**Never ISO strings.** Including `last_updated_time`, which is **mandatory on every row**. Integers
sort, compare and subtract without a parser; ISO strings do all three wrong at least once (offsets,
precision, the `Z` suffix) and the failure is a silently mis-ordered list.

The only exception seen so far, and it was argued for explicitly: an override map keyed by **local
calendar day**, because keying by instant would orphan every override the moment the series'
time-of-day changed. Values inside are still epoch ms.

### DynamoDB: single-table, `getItem`/`putItem` first

- Partition key = **tenant**. Range key = the entity's **unique name**.
- Names cannot contain spaces and must be unique.
- **Create and delete are the only operations that decide which entities exist.** An update is a
  `PUT`, never a rename. The name is the identity; renaming an identity is a create plus a delete
  pretending to be one write.
- Reach for a query or a scan only when a `getItem` cannot answer it, and add the GSI with a name that
  says what it is sorted by (`scheduled_triggers_by_last_updated_time`).

### The Decimal boundary is explicit, converted once, at the boundary

Reads come back as `decimal.Decimal`. `json.dumps` **refuses** it, and comparison against a `float` is
quietly wrong — and both failures surface far from the read. So:

| Direction | Call | Where |
|---|---|---|
| out of every read | `plain_numbers()` | immediately after the DynamoDB call |
| into every write | `decimal_friendly()` | immediately before the DynamoDB call |
| at serialization | a `DynamoNumberEncoder` backstop | the `json.dumps` in the response builder |

The backstop exists so that a delivery or an HTTP response is never the place a type problem is
discovered. Two conversions plus a backstop is cheap; a 500 in a webhook delivery is not.

### Runtime-created per-tenant AWS resources always ship with a delete path

If the code creates a schedule group, topic or pool **per tenant at runtime**, there is an API to
remove it, and the destructive call lives in **its own file whose whole subject is that danger**.

**Consequence of no delete path:** the account accumulates per-tenant resources for every tenant that
ever existed, and the first person to discover it is the one who hits an account limit during a
deploy. Putting the destructive call in its own file means a reviewer sees it as a change to *that*
file, not as three lines inside a create handler.

### Runtime-composed names raise rather than truncate

Covered in `naming_length_caps.md`, and it is a data rule as much as a naming one: truncation merges
two tenants onto one resource. The isolation the per-tenant resource exists to provide is the thing the
truncation silently removes.
