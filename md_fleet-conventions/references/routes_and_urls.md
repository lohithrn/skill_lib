# Routes, and the URLs a service calls out to

## The inbound shape

```
/<project_slug>/stage/{stage}/tenant/{tenant}/<methodname>/<paramName>/{paramValue}/...
```

Shapes seen across the fleet, with the identities replaced:

```
# newer repos: lowercased slug in the first segment, snake_case method name
/<projectslug>/stage/{stage}/tenant/{tenant}/create_scheduled_trigger/triggerName/{triggerName}
/<projectslug>/stage/{stage}/tenant/{tenant}/update_recurrence_occurrence/triggerName/{triggerName}/occurrenceDay/{occurrenceDay}
/<projectslug>/stage/{stage}/tenant/{tenant}/list_scheduled_triggers      # collection: no trailing param
/<projectslug>/stage/{stage}/tenant/{tenant}/mcp
/<projectslug>/stage/{stage}/tenant/{tenant}/login                        # the one route reachable without a token

# older repos: the repo name as-written in the first segment, camelCase method name
/<ServiceName>/stage/{stage}/tenant/{tenant}/send_email_by_template_name/jobId/{jobId}/templateName/{templateName}
/<ServiceName>/stage/{stage}/tenant/{tenant}/getJobSettingsByJobID/jobID/{jobId}
/<ServiceName>/stage/{stage}/tenant/{tenant}/CreateCallUserDataAlias/{identity}   # unnamed param — the older, worse form
```

Both generations exist. **Match the repo you are in**; do not convert one to the other in passing.

## Rules

- **Mandatory parameters go in the path. Optional parameters go in the query string.** No exceptions.
- Each path parameter is `/<paramName>/{paramValue}` — the name is spelled out, so a URL reads
  without a spec. The unnamed trailing form above is the older shape and is not copied forward.
- A collection route takes no trailing parameter; paging is query parameters (`page_size`,
  `forward_cursor`).
- **Update is `PUT`.** Create and delete are the only two operations that decide which entities
  exist; the unique name is the identity and is not editable. So there is no rename — a caller
  wanting a different name deletes and creates.
- **No hardcoded URL prefix anywhere in code.** Terraform is the only place the prefix is spelled:

```hcl
locals {
  # Every route hangs off this. project_slug comes from the repo folder name, so the
  # prefix is never spelled out; {stage} and {tenant} stay as path parameters.
  api_path_prefix = "/${var.project_slug}/stage/{stage}/tenant/{tenant}"
}
```

## Routes as one list, outputs generated from it

Declare `(path, http_method, function_name)` once as a `local` list, feed it to the `api_gateway`
module, and have `outputs.tf` generate the endpoint list from **the same list**. The printed URLs then
cannot drift from the deployed routes, and adding a route is one entry.

## The stage belongs to the deployment, not the request

This is the property most worth protecting, because the stage selects **which identity pool
authorizes the call**. A caller who could choose the stage could present a beta token against prod, or
mint a prod token from a beta page.

- The frontend proxy prepends the prefix **from its own environment variable**
  (`<SERVICE>_API_PATH_PREFIX`, wired by terraform). A missing one **fails loudly** rather than
  producing a prefix-less path and an unexplained 404.
- A browser that sends its own `/<slug>/stage/prod/...` has it appended **after** the deployment's
  prefix, so it resolves to no route rather than to prod.
- **There is no login-shaped exception.** `/login` gets the same prefix from the same variable as a
  list call, because that is the route that issues a token.
- Handlers compare the `{stage}` segment against their own `ENVIRONMENT`.
- The base URL is `rstrip`ped and the path `lstrip`ped, so neither a trailing nor a leading slash
  produces a double slash the API will not match.

## The tenant is in the path AND the header

Both, and the handler compares them. A proxy must **not** helpfully fill a missing
`AuthorizationTenant` from the path — that defeats exactly the check the comparison exists for.

## What survives the proxy hop

The proxy has **no identity of its own**; the caller's bearer token is the whole credential.

| Forwarded | Dropped |
|---|---|
| `authorization` (**byte for byte** — a JWT is signed; re-casing or trimming yields a token the API cannot verify) | `cookie` |
| `authorizationtenant` | `origin` |
| `authorizationregion` | `x-forwarded-for` |
| `content-type` | `host` (actively wrong once the URL changes) |
| | `content-length` (same) |

No SigV4 headers are attached: the frontend lambda's execution role can write its own logs and
nothing else, so compromising it yields nothing that can read data. All three auth headers are
required together — forwarding one and dropping the others is a 401 whose message blames the token.

Three urllib traps, worth a test each:

- **The method is stated, never inferred.** urllib infers POST from a body and GET from its absence,
  turning a PUT into a POST and a DELETE into a GET.
- **`b""` becomes `None`.** urllib reads empty bytes as "there is a body" and adds
  `Content-Length: 0` to a GET.
- **The query string is carried through uninterpreted.** Paging cursors are base64; parsing and
  rebuilding the query string is a way to corrupt one.

## MCP is a route, not a second implementation

**HTTP APIs are the primary interface.** `/mcp` hangs off the same prefix, behind the same auth gate,
and **translates tool calls into API Gateway events so both transports invoke the same handler**. MCP
is the alternative to the UI. An MCP tool that reimplemented a route would be two implementations to
keep in agreement, and they would disagree.

Keep it **stateless** — no sessions, no session id issued, nothing cached across invocations except
client builders and config readers keyed on configuration, so nothing can leak across tenants. When an
intermediary can supply routing headers (`Mcp-Method` / `Mcp-Name`) alongside a body, validate them
**against the body before dispatch**: two sources of truth for what is being called is the gap.

---

## Outbound URLs: `urls.{env}.yaml`, never per-URL env vars

1. Author `configuration/urls.beta.yaml` and `configuration/urls.prod.yaml`, key → URL template with
   `{stage}` / `{tenant}` / entity-id placeholders.
2. The deploy copies the env-appropriate file to `src/deployed_utilities_references/urls.yaml` and
   packages it in the zip.
3. Code calls `get_url("SOME_KEY")`, which **fails loudly** on a missing key.
4. `ENVIRONMENT` stays a terraform-wired env var and **must not default** — a missing `ENVIRONMENT`
   fails loudly rather than letting a prod lambda silently build beta URLs.

**Consequence of per-URL env vars instead:** every new callee is a terraform change in every caller,
and the environment blocks of ten lambdas become the place URLs actually live. The `md_service-blueprint`
skill ships the resolver this convention depends on, as a template.

Everything else the lambda needs — table names, pool ids, ARNs, prefixes — is composed in `main.tf`
from the terraform resources themselves. **Never hand-typed.**

The URL templates being per-environment is what makes the hostnames a deploy-time concern rather than
a code concern; the templating itself is only over `{stage}`, `{tenant}` and entity ids.
