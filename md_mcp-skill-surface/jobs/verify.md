# Job: verify an MCP surface

Read-only. This job accepts or rejects a surface; it changes nothing. Use it to accept a build from
`jobs/generate.md`, or to audit a surface somebody else built.

**Read before ruling.** Never mark a criterion met from a file name or a grep hit. Open the range, or
call the method and read what came back.

---

## 1. How to run it

| Step | Do |
|---|---|
| 1 | Load the OpenAPI document and the skill manifest. These are the two sources of truth |
| 2 | Call `initialize`, `tools/list`, `prompts/list`, `resources/list` against the running surface, or load the registries directly if it is not deployed |
| 3 | Walk §2 in order. Each criterion is met, unmet, or **unverified** — never assumed |
| 4 | Run the five test groups in §3 and record which exist, not just which pass |
| 5 | Report per §5 |

A criterion you could not check is `unverified` with the reason. Marking it met because it "obviously
is" is how a surface ships with an undiscoverable skill.

---

## 2. The 25 acceptance criteria

The surface is complete when all 25 hold. The third column is what proves it — a command, a method
call, or a file comparison. Nothing is proven by inspection of intent.

### Tools

| # | Criterion | Proof |
|---|---|---|
| 1 | Every REST operation is exposed as an MCP tool | set difference: OpenAPI `operationId`s vs `tools/list` names, both directions, empty |
| 2 | Tool names exactly match API operation names | the same comparison, name for name |
| 3 | All tools are generated from OpenAPI | every module under the generated directory carries the generator header, and a regeneration produces no diff |
| 4 | MCP tools call the REST API over HTTP | exactly one module opens a connection; grep for it |
| 5 | Tool descriptions describe operations, not workflows | read each one: no ordering, no "after calling", no "then ask the user" |

### Skills, prompts, resources

| # | Criterion | Proof |
|---|---|---|
| 6 | Every skill in the manifest exists as Markdown | resolve every document path |
| 7 | Every skill is registered as an MCP prompt | manifest names vs `prompts/list` names, both directions |
| 8 | Every skill is exposed as an MCP resource | manifest names vs `resources/list` URIs |
| 9 | `prompts/list` returns all skills | call it, count it |
| 10 | `prompts/get` returns the requested skill instructions | call it for every skill; compare to the document |
| 11 | `resources/list` includes the skill index | the index URI is present in the listing |
| 12 | Skill resources use the `productname://skills/…` scheme | every URI matches the prefix; none is an HTTP URL or a file path |
| 13 | Skills contain no executable business logic | read every document: no code, no queries, no arithmetic the API should do |
| 14 | Skills reference only tools that exist | every tool name in every document and manifest entry resolves in `tools/list` |

### Gates

| # | Criterion | Proof |
|---|---|---|
| 15 | The build fails when a skill references a missing tool | break the manifest on purpose; watch it fail; restore |
| 16 | The build fails when two skills share a name | duplicate a name on purpose; watch it fail; restore |
| 17 | Skill registration and generated tool registration are covered by tests | the test files exist and are in the build, not just on disk |

### Safety

| # | Criterion | Proof |
|---|---|---|
| 18 | Destructive skills require explicit confirmation | every skill with the destructive flag has a confirmation section and a confirmation step in its workflow |
| 19 | Credentials are never stored in skills or resources | grep every document and every resource payload for credential field names; a test asserts it |
| 20 | Deletion skills never delete an entire external dataset | read each one: deletion is scoped to the identities a stored operation record names |
| 21 | A reversal skill uses separate confirmations for the external deletion and the local record | read the workflow: two confirmation steps, and the metadata flag defaults to off |

### Architecture

| # | Criterion | Proof |
|---|---|---|
| 22 | The MCP server contains no AI model | no model dependency in the artifact, no inference call, no tool-selection branch |
| 23 | The client's model interprets the skills | there is no server-side interpreter for a skill document; documents are returned, never executed |
| 24 | Skills never call the database or an external system directly | the server has no database client and no external-system SDK in its dependency set |
| 25 | Skills handle pagination, preserve identifiers, and distinguish stored from live state | read every read skill against `references/skill-authoring.md` §6 and §7 |

Criterion 22 is the one people fail without noticing, and it usually arrives as a helper "to pick the
right tool". That helper is a model, or a hard-coded orchestration nobody can change without a deploy.
Either way the layering is gone.

---

## 2b. Security checks the 25 criteria do not cover

The 25 above are the completeness list: they prove the surface exposes what it should. They do **not**
prove it is safe to expose. Run these as well, and treat any failure as a blocker — every one of them is
reachable by anyone who can reach the endpoint. Rules in `references/tool-generation.md` §7 and
`references/skill-authoring.md` §11.

| Check | Proof | Severity if it fails |
|---|---|---|
| The endpoint authenticates before any dispatch | call `initialize` and `tools/list` with no credential and with a bad one; both must be refused | **blocker** — an open proxy over the whole API |
| Auth is in one place, not per method | read the entrypoint: one gate, before the method table | **blocker** — the forgotten method is the way in |
| Caller scope comes from the authenticated request | call a scoped operation with someone else's tenant in the argument; it must be refused | **blocker** — cross-tenant read/write |
| Every scope rule is enforced in the API, not only stated in a document | for each "never invent an identifier" rule, name the server-side check | **blocker** — guidance is not a control |
| The server holds no credential outranking the caller's | read the configuration the server loads | **blocker** — privilege escalation by design |
| Prompt arguments cannot inject workflow steps | render a document with an argument containing a newline, a heading, a numbered list item and a code fence; none may survive as structure | **major** — a caller appends a step to your workflow |
| Arguments are length-capped and declared-names-only | render with an oversized argument and an undeclared one | **major** — refusals pushed out of attention |
| Documents are static artifacts | grep the registries for any request-time assembly from stored or caller data | **major** — indirect prompt injection |
| Resource URI resolution cannot traverse | read `productname://skills/../../etc/passwd` and equivalents; must be not-found, resolved against the loaded skill map only | **blocker** — arbitrary file read |
| Header forwarding is an allowlist | read the client: an explicit set, not pass-through | **major** — header injection through the narrow door |
| Redaction is a recursive walk, not a top-level key check | return a payload with a credential nested three levels down and in a list | **blocker** — secret in a client transcript |
| Errors carry no stack trace and no internal identifiers | force a mapper error and an upstream 500; read both responses | **major** — stack and inventory disclosure |
| No argument object is logged wholesale | grep every log call in the mapping path | **blocker** — credentials in logs, permanently |
| A destructive operation is authorized separately from a read | call a delete operation as a read-only caller; it must be refused by the **API**, not by a document | **blocker** — every reader is a deleter |
| Discovery is filtered to what the caller may call, or every listed tool is authorized per call | list tools as a low-privilege caller, then call one you should not hold | **major** — `tools/list` is a map of everything, and an unauthorized call must still fail closed |
| The outbound call cannot be redirected to another host | point an upstream stub at a `302` and at an absolute URL in a path argument | **major** — server-side request forgery, including instance metadata |
| The endpoint is rate-limited per caller | read the gateway or middleware configuration | **major** — one prompt-injected client can walk your whole dataset through `tools/call` |
| Unknown arguments are rejected | every tool's input schema sets `additionalProperties: false` | **minor** — silent scope changes |
| Path segments are URL-encoded | call with an identifier containing `/`, `..` and `%` | **major** — addresses a different resource |
| Required path and header parameters fail before the call | omit each one | **minor** — a request to a literal placeholder |
| An external-effect operation requires an idempotency key | read the schemas of every non-idempotent operation | **major** — a retry duplicates an external side effect |
| The artifact holds no secret and no environment configuration | list the packaged artifact | **blocker** — a secret that outlives every rotation |

**Do not run the traversal, injection or bad-credential probes against production.** Run them against a
deployment you own, and say in the report which environment answered.

---

## 3. The five test groups

A surface with all 25 criteria met and no tests will lose them on the next change. These are the groups;
the third column is what regression each one catches.

### Tool tests

| Test | Catches |
|---|---|
| `tools/list` contains every REST operation | an endpoint added without regenerating |
| `tools/call` maps arguments correctly — path, query, header, body, and the free-form body root | a mapping-metadata typo that silently drops a filter |
| Tool inputs match the OpenAPI schema | a schema that has drifted from the operation and now lies to the model |
| Tool outputs preserve the REST response | a mapper that flattens or renames fields, breaking every client that read them |

Add one more that is worth its weight: **a missing required path parameter fails before any HTTP call.**
Otherwise a request goes out to a literal `{groupId}` and the API's 404 is reported as "not found".

### Prompt tests

| Test | Catches |
|---|---|
| `prompts/list` contains every skill | a skill added to the manifest without registration |
| `prompts/get` returns valid content | a document that failed to package |
| Prompt arguments are interpolated safely | a placeholder that renders as an empty string, so an instruction loses its subject |
| Missing prompt arguments return structured errors | a half-rendered document — the refusals are usually at the end |
| A hostile argument cannot alter the document's structure — pass a value containing a numbered step, a heading, a list marker and a code fence, and assert the rendered document has the same step count, heading count and fence count as the source | an argument that arrives as an extra workflow step, which the model then performs with your tools |
| An undeclared argument name is rejected, and an over-long argument is rejected or truncated | a caller probing the renderer, and a flood that pushes your refusals out of the model's attention |

### Resource tests

| Test | Catches |
|---|---|
| `resources/list` includes the index URI | a client that cannot bootstrap without hard-coding the scheme |
| Skill resources return Markdown | a MIME type of `text/plain` or JSON, which some clients will not render |
| An unknown skill resource returns not-found | an empty read, which the model treats as "no instructions" and proceeds without them |
| Resources never expose credentials | the leak that survives longest, because resources are cached and logged |

### Skill validation tests

Six checks, all runnable offline against the manifest and the documents:

1. Every referenced tool exists.
2. Every Markdown document exists.
3. Skill names are unique.
4. Destructive flags are correct — every skill calling a delete operation is flagged.
5. Every destructive skill mentions confirmation.
6. Every skill handling external credentials mentions credential protection.

Checks 4–6 are text assertions over the documents. They feel crude and they are the ones that fire: a
document gets edited, the confirmation paragraph gets tightened out, and nothing else notices.

### Workflow tests

One end-to-end test per skill, driving the surface as a client would: read the skill, resolve its tools,
call them in the document's order, assert the final state.

Cover at minimum:

| Workflow | Asserts |
|---|---|
| A read workflow with pagination | the cursor round-trips and the second page differs from the first |
| A batch create | per-item results, and that the server allocated the identifiers |
| An export to an external system | preview, then the operation, then the stored record — and no credential in any output |
| Reading a stored operation record | that the output says it is stored state, not live state |
| A scoped deletion from an external system | that confirmation was required, and the container was not deleted |
| A reversal | that two separate confirmations were required, and that a partial failure stops before the local record is deleted |

The reversal test is the most valuable test in the suite. It is the only one that proves the
two-confirmation rule is real rather than aspirational.

---

## 4. Packaging check

| Check | Failure it prevents |
|---|---|
| The manifest is inside the deployed artifact | an empty `prompts/list` in production and a passing test suite locally |
| Every skill document is inside the artifact | `prompts/get` returning not-found for a skill that `prompts/list` advertised |
| The document count in the artifact equals the manifest entry count | one document silently excluded by a packaging glob |
| No credential material and no configuration secret is inside the artifact | a secret in a build output, which outlives every rotation |
| The artifact contains **no test, fixture, stub, recorded response or generator** — those live in `tests/` and at the repo root, never in `src/` (`references/structure.md`) | a test double reachable from a production import, and a recorded response carrying a real header into your deploy |
| Every module in the artifact is reached by an entrypoint or by another module in it | dead code you still patch, review and pay cold-start for |

---

## 5. Report

≤25 lines:

1. Criteria met / unmet / unverified, as three counts.
2. Every unmet criterion, by number, with the file or method call that shows it and one line on the
   consequence.
3. Every unverified criterion, by number, with why it could not be checked.
4. Test groups present, and any group missing entirely.
5. The single highest-leverage fix.
6. What this audit did **not** cover: operations excluded from the surface on purpose, workflows not
   exercised end to end, and anything you read but could not run.

Nothing was changed — say so in one line.
