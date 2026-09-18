# The MCP capability model

The one question this file answers: **what must the server return, for each of the three capability
types, and under what name?**

An MCP surface over a REST service exposes exactly **three** capability types. Declare all three in
the `initialize` handshake; a capability you do not declare is a capability the client will not ask
for, and the skills become invisible.

```
"capabilities": {
  "tools":     { "listChanged": false },
  "prompts":   { "listChanged": false },
  "resources": { "listChanged": false }
}
```

`listChanged: false` is honest for a generated surface: the set changes when you deploy, not while a
session is open. Declaring `true` and never sending the notification teaches clients to distrust it.

## 1. Tools — generated from OpenAPI operations

Tools **perform actual operations**. One tool per operation, named exactly as the operation is named.

| Method | Returns |
|---|---|
| `tools/list` | every tool, each with `name`, `title`, `description`, `inputSchema`, and `outputSchema` where the protocol version supports it |
| `tools/call` | `content` (a text block), `structuredContent` (the mapped envelope), `isError` |

Ordering is deterministic — sort by name — so two deploys of the same commit produce the same list and
a diff of `tools/list` output means something changed.

`isError` is set on a non-2xx HTTP status **or** a failure status inside the response envelope. A
service that returns 200 with `{"status": "FAILED"}` will otherwise be narrated as a success by the
client's model, which is the most expensive bug in this whole architecture. See
`references/tool-generation.md` §5.

Worked example: `listGroups`, `listRecordsByRange`, `createBatchRecords`, `exportRecordsToTarget`,
`getExportData`, `deleteExportFromTarget`. Your list is whatever your OpenAPI document contains.

## 2. Prompts — the protocol representation of skills

Prompts **represent skills**. Each prompt provides structured instructions for accomplishing one
workflow. A prompt executes nothing.

| Method | Returns |
|---|---|
| `prompts/list` | every skill: `name`, `title`, `description`, `arguments` |
| `prompts/get` | the rendered skill document for one `name` |

Rules that break something when dropped:

1. **`prompts/list` must contain every skill in the manifest.** A skill the client cannot discover is
   a document nobody reads, and the model falls back to calling tools in an order you never sanctioned.
2. **Prompt arguments are strings** unless the chosen official SDK and negotiated protocol version
   clearly support another prompt-argument type. Tool schemas keep their real JSON types — the
   constraint is on prompt arguments only.
3. **Every declared argument is interpolated, and an undeclared placeholder is left intact.** A
   placeholder that silently becomes an empty string produces an instruction like "validate the tenant
   " and the model invents a value to fill the hole.
4. **A missing required argument returns a structured protocol error**, not a half-rendered document.
   Half a workflow is more dangerous than none: the refusals are usually at the end.
5. **An unknown prompt name returns an error, never the nearest match.** Fuzzy resolution means a
   typo runs a different workflow than the one that was asked for.

Interpolation is a plain placeholder substitution over the Markdown — `{{tenantId}}` and friends. It
is not a template language: no conditionals, no loops, no includes. A skill document whose meaning
depends on a conditional is two skills.

## 3. Resources — skill documentation as read-only text

Resources expose the skill documentation as read-only text, for clients that prefer to **read** the
documentation directly rather than retrieve it as a prompt. Same bytes, different door.

| URI | Content | MIME type |
|---|---|---|
| `productname://skills` | the skill index | `application/json` |
| `productname://skills/<skillName>` | one skill document | `text/markdown` |

The index payload:

```json
{
  "skills": [
    {
      "name": "inspect_groups",
      "title": "Inspect Groups",
      "resourceUri": "productname://skills/inspect_groups"
    },
    {
      "name": "create_records_in_group",
      "title": "Create Records in Group",
      "resourceUri": "productname://skills/create_records_in_group"
    }
  ]
}
```

| Method | Returns |
|---|---|
| `resources/list` | the index resource, then one entry per skill document |
| `resources/read` | `{ "uri", "mimeType", "text" }` for the requested URI |

Rules:

1. **Resources are read-only.** No write, no subscribe-and-mutate. The document set changes by deploy.
2. **`resources/list` must include the index URI itself.** Without it a client has to guess the scheme
   to bootstrap, and guessing means hard-coding your product name in their code.
3. **An unknown skill URI returns not-found**, distinctly from an empty document. Empty reads as "this
   skill has no instructions", and the model proceeds without them.
4. **A URI that does not start with the skill prefix is not-found**, not a path traversal opportunity.
   Resolve the segment after the prefix against the loaded skill map only — never against the
   filesystem.
5. **No resource ever contains a credential.** Resources are cacheable, loggable and often persisted
   by clients. `references/skill-authoring.md` §5 is the full rule.

## 4. The URI scheme

`productname://skills/<skillName>` — three decisions, each with a reason:

| Decision | Reason |
|---|---|
| A custom scheme, not `file:` or an HTTP URL | the document has no location; it is a protocol object, and a location invites a client to fetch it out of band |
| `skills` as a fixed first segment | leaves room for `productname://openapi` or `productname://changelog` later without re-plumbing the resolver |
| the skill name as the last segment | the same string is the prompt name, the manifest key and the Markdown file stem, so there is exactly one identifier to get wrong |

Keep the scheme lowercase and stable. It appears in client configuration and in test assertions;
renaming it is a breaking change for every consumer.

## 5. The method map

The minimum set a surface over a REST service needs. Anything else is optional.

| Method | Delegates to | Notes |
|---|---|---|
| `initialize` | — | protocol version, server info, the three capabilities |
| `ping` | — | returns an empty result; keep it, health checks use it |
| `tools/list` | the tool registry | deterministically ordered |
| `tools/call` | tool registry → argument mapper → HTTP client → result mapper | one REST call |
| `prompts/list` | the skill registry | every manifest skill |
| `prompts/get` | the skill registry | renders the document |
| `resources/list` | the skill resource registry | index plus documents |
| `resources/read` | the skill resource registry | index JSON or one document |

An unrecognised method returns method-not-found. Silently returning an empty result makes a client
believe the capability exists and is empty, and nobody debugs an empty list as hard as an error.

## 6. Discovery order, from the client's side

Worth knowing because it tells you which failure a user actually sees first:

1. `initialize` — if `prompts` is not declared here, nothing below happens.
2. `prompts/list` or `resources/list` — the model learns which workflows exist.
3. `prompts/get` — the model reads one skill and now knows which tools it needs.
4. `tools/list` — the model resolves those names to schemas.
5. `tools/call` — execution, in the order the skill specified.

Step 3 naming a tool that step 4 does not return is the failure this architecture guards against
hardest, and it is why the generator validates manifest tool names against OpenAPI at build time
(`jobs/generate.md` phase 5).
