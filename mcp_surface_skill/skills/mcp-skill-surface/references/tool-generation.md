# Generating tools, mapping arguments, mapping results

The one question this file answers: **how does one OpenAPI operation become one MCP tool, and how does
one `tools/call` become one REST call and back?**

## 1. One tool per operation, generated

| Rule | Consequence if broken |
|---|---|
| Every REST operation in the OpenAPI document is exposed as a tool | an operation with no tool is invisible to the client's model, and the model works around it by misusing a tool that is exposed |
| **Tool names match the operation names exactly** | a renamed tool cannot be traced from a client transcript to a log line to a dashboard metric; incident response stalls on vocabulary |
| All tools are generated from the OpenAPI document | a hand-written tool drifts on the next API change, and a schema that lies is worse than a missing schema — the model trusts it |
| No tool without an operation | a tool with no backing operation is an invented capability; the first call 404s in front of a user |
| One module per tool, one `TOOL` value per module | a registry that discovers tools by import needs exactly one obvious symbol; two tools per file makes the ordering of discovery matter |

Each generated tool carries **10** fields. The first **5** describe the tool; the last **5** are the
REST mapping.

| # | Field | Source | Purpose |
|---|---|---|---|
| 1 | `name` | `operationId` | identity, unchanged |
| 2 | `title` | summary | short human label |
| 3 | `description` | the operation description | tool selection by the model — operation behaviour only |
| 4 | `inputSchema` | parameters + request body, flattened | validation before any HTTP call |
| 5 | `outputSchema` | response schema, where the protocol version supports it | lets a client type the result |
| 6 | `httpMethod` | the operation's method | the REST call |
| 7 | path mapping | which flat arguments substitute into the path template | the REST call |
| 8 | query mapping | which flat arguments become query parameters | the REST call |
| 9 | body mapping | which flat arguments become body properties | the REST call |
| 10 | allowed header mapping | which flat arguments become which HTTP header | idempotency keys, request ids |

**The input schema is flat.** Path parameters, query parameters, allowed headers and body fields all
appear as sibling properties of one object, because that is what a model can fill in. The split back
into a real HTTP request is the mapper's job, driven by fields 7–10. A nested schema mirroring the HTTP
shape forces the model to know where each value lives in the protocol, and it guesses.

Set `additionalProperties: false` on the top-level input object. An unknown argument is a model
hallucinating a parameter, and silently dropping it means the call runs with the wrong scope.

**Two classes of OpenAPI parameter are excluded from the generated input schema.** Both are
security-critical, and a generator that flattens every declared parameter will include them:

| Excluded | Why | Consequence if included |
|---|---|---|
| Any parameter belonging to a **security scheme** — `Authorization`, an API key header, an auth cookie | the caller's credential is attached from the authenticated request context, by the one component that talks to the API | a caller — or a model reading a hostile transcript — supplies the credential the gateway trusts, as an ordinary tool argument. That is a second auth path into your API, and it puts a live secret into the argument object that must never be logged |
| Any **caller scope** identifier — tenant, account, workspace, organization | scope comes from the authenticated request, never from an argument | cross-tenant read and write. See §2 |

An operation whose OpenAPI document declares an auth parameter is not a reason to expose it; it is a
reason for the generator to know the document's security schemes and skip their parameters.

## 2. Argument mapping

The mapper performs **shape translation only** — no business logic, no external calls, no defaults
invented for missing values.

| Location | Rule | Consequence if broken |
|---|---|---|
| **Path** | substitute each declared path parameter; **URL-encode every segment value**; a missing one is a hard error before any HTTP call | an unencoded identifier containing `/` or `..` silently addresses a different resource; a missing one produces a request to a literal `{groupId}` |
| **Query** | forward **only** parameters explicitly supplied | a defaulted filter narrows a result set the human never asked to narrow, and the model reports a partial list as complete |
| **Headers** | map argument name to header name through the declared allowlist; a header argument that is `required` in the schema and absent is a hard error | a dropped idempotency key turns a retry into a duplicate external operation |
| **Body** | include only supplied body properties | sending explicit nulls overwrites stored fields on a PATCH |
| **Body root** | for free-form payloads (a PATCH or PUT body the API accepts whole), one argument's value **is** the entire body | mutually exclusive with per-property body mapping; supporting both at once makes the payload order-dependent |

**Deployment placeholders are not MCP arguments.** A path template often carries a shared prefix — a
project name, a deploy stage, a region segment — that belongs to the environment, not to the caller.
Resolve those from configuration in the mapper and keep them out of the input schema entirely. Exposing
them lets a client address another stage; hard-coding them means one build artifact per stage.

Keep the placeholder syntax in the path template even when a stage has only one value today. That is
the seam that lets the prefix vary later without re-plumbing every tool.

**The caller's scope is resolved the same way, and this is the security-critical case.** A tenant,
account, workspace or organization segment in a path template is filled from the **authenticated
request**, exactly like a deployment placeholder — never from a tool argument. Two acceptable shapes,
and one that is not:

| Shape | Verdict |
|---|---|
| The scope segment is resolved in the mapper from the authenticated request | **correct** — a caller cannot name a scope they do not hold |
| The scope segment is a path parameter, **and** the API authorizes it against the caller's identity on every request | **acceptable, and the check is mandatory** — this is the shape most existing REST APIs already have. Name the server-side check in your audit |
| The scope segment is a caller-supplied argument that the API trusts | **cross-tenant read and write.** The highest-severity mistake available in this architecture |

If your API already takes the scope in the path, you are in row two, and the whole safety of the MCP
surface rests on that authorization check existing. Verify it before you ship — do not assume it,
because the REST clients that came before may all have been trusted callers.

### Validation, in order

1. **Schema validation first** — types, `required`, enums, minima. Reject before mapping.
2. **Then the mapper's own hard errors** — a missing path parameter or a missing required header.
3. **Never** business validation. "This group belongs to another tenant" is the REST API's answer, and
   duplicating it in the mapper produces two rules that drift.

A rejected call returns a structured protocol error naming the offending argument. A generic "invalid
arguments" makes the model retry the same call with the same values.

## 3. Header forwarding

The MCP request carries caller headers. Forward **only an explicit allowlist** — authorization, a
request id, a tenant hint, an API key header the gateway expects — and drop everything else.

Consequence if you forward everything: client-supplied headers reach your API unfiltered, which is a
header-injection path straight through the layer whose whole job is to be the narrow door.

Consequence if you forward nothing: the REST API sees an unauthenticated call and the MCP server has
to hold a credential of its own, which is a second, weaker auth path into the same API.

## 4. The HTTP call

One `tools/call` is one HTTP request. Rules:

- **One component reaches the network** — the client that issues the REST call. Nothing else in the
  server opens a connection. Grep for it and there should be exactly one file.
- **Use the standard library HTTP client** where the runtime allows it. A serverless artifact that
  carries a third-party HTTP dependency for one GET is paying cold-start cost for convenience.
- **Set a timeout below the platform's own timeout.** No timeout means the platform kills the function
  and the client gets a transport error instead of a mapped one.
- **HTTP error statuses are results, not exceptions.** Read the error body, parse the envelope, map it.
  An exception here loses the API's own error code and message, which is the only thing that tells the
  model what to do next.
- **Tolerate a non-JSON body.** Wrap it rather than throwing: a gateway error page is a legitimate
  thing to receive and the client deserves to see what arrived.

### The outbound call is a request-forgery surface

The mapping layer takes model-supplied values and builds an HTTP request. Three rules keep that from
becoming a fetcher for arbitrary hosts:

- **The host and scheme come from configuration only.** No argument may influence either — not a base
  URL argument, not an absolute URL in a path parameter, not a scheme-relative value. Build the URL as
  configured base plus mapped path, and reject a mapped path that does not start with `/`.
- **Do not follow redirects.** A `302` from the upstream turns your one network component into a fetcher
  for any host the upstream names, including a cloud instance-metadata endpoint. Return the redirect as
  the result it is.
- **Cap the response size you read.** An unbounded read hands an arbitrarily large body to the mapper
  and then to a model. Cap it, and report truncation rather than silently returning a prefix.

## 5. Result mapping and redaction

The result mapper converts one HTTP response into one MCP tool result:

| Output field | Contents |
|---|---|
| `structuredContent` | the sanitized response envelope |
| `content` | one text block, the same envelope serialized with sorted keys |
| `isError` | `true` on HTTP ≥ 400, **or** when the envelope's own status says the operation failed |

Serialize the text block with **sorted keys**. Unsorted output makes two identical responses diff, and
every snapshot test in your suite becomes flaky for no reason.

### The redaction list

Strip these before returning, in the mapper, not in a skill instruction:

1. Authorization headers
2. API keys
3. Tokens
4. Passwords
5. Raw internal stack traces
6. Cloud resource identifiers (ARNs and equivalents)

Redaction is a **structural recursion over the whole payload** — strings, dicts, lists — not a
top-level key check. A credential nested three levels inside an echoed request object is still a
credential. Two failure modes worth naming:

- **A skill instruction cannot unsend bytes.** By the time a model is asked not to repeat a secret, the
  secret is already in the transcript, the client's history and the client's logs.
- **An echoed request is the usual leak.** APIs that return the request they processed will hand back
  the credential object you passed in. Sanitize the echo, and assert it in a test
  (`jobs/verify.md` §3, resource and tool tests).

## 6. Determinism

Generation must be reproducible: the same OpenAPI document and manifest produce byte-identical output.

| Requirement | Why |
|---|---|
| Sort schema keys and tool ordering | an unordered dump reorders on every run and the diff is unreviewable |
| Emit a "generated, do not edit" header naming the generator | without it someone hand-fixes a schema and the fix vanishes at the next run |
| Never write over a hand-authored Markdown skill document | the Markdown is the one layer a human wrote; regenerating it destroys the workflow |
| Fail, do not skip, on an unmappable operation | a silently skipped operation is a missing tool nobody notices until a workflow needs it |

A second run producing a diff is a bug in the generator, and it is worth a test of its own — run it
twice in the build and fail on any change.

## 7. The security boundary

An MCP surface is a **new, reachable front door onto an existing API**. Each rule below closes a hole
this architecture opens and that no other layer will close for you.

### The endpoint is authenticated, or it is an open proxy

| Rule | Consequence if broken |
|---|---|
| **The MCP endpoint carries the same authentication as the REST API**, checked in the entrypoint before any dispatch — before `initialize`, before `tools/list`, before anything | you have shipped an unauthenticated proxy in front of every operation in your OpenAPI document. `tools/list` alone hands a stranger your complete API surface, and `tools/call` executes it |
| Authentication runs once, in one place, and returns a protocol-shaped error on failure | an auth check per method means the one method somebody forgets is the way in |
| **The caller's scope — tenant, account, workspace — comes from the authenticated request, never from a tool argument** | a caller who can name a tenant in an argument can read every tenant. This is the highest-severity mistake available here |
| The MCP server holds **no credential of its own** that outranks the caller's | a server-held credential turns every authenticated caller into an authorized one, and makes the MCP path more powerful than the REST path it fronts |
| Prefer the platform's own request signing where it exists | it keeps a long-lived secret out of the client entirely |

Never mint a certificate or a keypair as an authorization mechanism for this endpoint. Where the
platform offers a managed certificate at the edge, that is the one to use.

### A skill instruction is not an access control

"Never invent a tenant identifier" belongs in every skill document — and it is **guidance to a
cooperating model, not a security control**. The model can be wrong, the client can be someone else's,
and the transcript can contain text an attacker wrote.

So every scope rule exists **twice**: as an instruction in the skill, and as an enforced check in the
REST API or the gateway. A rule that exists only in the document is unenforced; say so in the audit.
`jobs/verify.md` §2b is the checklist.

**This applies hardest to confirmation.** Every confirmation rule in every skill document protects a
*cooperating* client only. A hostile, buggy or prompt-injected client calls the delete tool directly and
no confirmation section anywhere in your surface will stop it. So a destructive operation needs a
server-side guard as well:

| Guard | Why the client-side rule is not enough |
|---|---|
| An explicit confirmation parameter the **API** requires, with no default | the API refuses a delete that no one confirmed, whatever the client did or did not display |
| A distinct scope or entitlement for delete operations | a caller who may read must not thereby be a caller who may delete |
| An audit record naming the caller, the target and the count | without it you cannot tell an authorized deletion from an injected one after the fact |
| A blast-radius limit enforced server-side — deletion scoped to identities a stored record names, never a container | a scope rule that lives only in prose is one hostile call away from deleting the container |

Asking the human still belongs in the skill — the human is on the client, and only the client can ask.
What must not live only in the skill is the **guard**.

### Untrusted text reaches a model through this surface

| Surface | Rule |
|---|---|
| Prompt arguments | caller-supplied — see `references/skill-authoring.md` §11 |
| Tool results | they come from your API, but may echo caller-supplied or third-party data; the model reads them as content, never as instructions |
| Resource documents | **static build artifacts only.** Never assemble a skill document from stored, tenant-supplied or fetched data at request time |

A document assembled at request time out of data a user controls is indirect prompt injection with your
own server as the delivery mechanism — and the client's model will act on it with your tools.

### Error and log hygiene

- **Return the API's own error code and message, never a raw internal stack trace.** A trace leaks
  module paths, dependency versions and sometimes argument values into a transcript that gets pasted
  into a ticket.
- **Never log a tool's argument object wholesale.** It is the one object that carries credentials by
  design. Log the tool name, the outcome and the identifiers — never the payload.
- **Keep internal resource identifiers out of errors.** They are inventory to an attacker and useless
  to the caller.
- Set the timeout below the platform's own, so a hung upstream produces your mapped error instead of
  the platform's — which tells the caller more about your stack than about their request.
- **A retry is a duplicate side effect** unless the operation carries an idempotency key. Retry in the
  client or the API, never in the mapping layer, and require the key on any operation with an external
  effect.
