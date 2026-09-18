---
name: md_mcp-skill-surface
description: Expose an existing REST/OpenAPI service as an MCP surface — one tool per OpenAPI operation, one prompt per skill, and every skill document served as a read-only resource under a productname://skills URI. Covers the five-layer split (skill, prompt, tool, REST API, implementation), argument and result mapping, the generated module layout, the skill-document contract, destructive-operation confirmation, credential handling, and the acceptance criteria and test matrix that prove the surface is complete. The MCP server holds no AI model.
when_to_use: When adding an MCP server in front of an existing REST/OpenAPI service, when writing or reviewing skill documents that MCP clients consume as prompts, or when auditing an MCP surface for the skills-are-not-tools rule.
allowed-tools: Read, Grep, Glob, Write, Edit, TodoWrite
---

# MCP surface over a REST service

A method for putting an MCP server in front of a service that already has an OpenAPI document and a
working REST API. It resolves one conflict — **which layer does this piece of behaviour belong to?**
— and everything else follows from the answer. Rule text lives in `references/`, the build procedure
in `jobs/`, the output contracts in `specs/`.

`<product>` is the service being exposed; `productname` is its lowercase identifier form, used in URI
schemes and module names. Substitute both throughout.

## The gate — read this first

**The MCP server contains no AI model.** If you find yourself adding one — a model call, a planner, a
"decide which tool to use" branch — you are building the client, not the server. Stop.

- The client's model reads a skill, discovers tools, and calls them. The server validates arguments,
  maps them to REST, and returns the mapped result. Nothing else.
- **A skill is never registered as an executable tool.** This is the single most common way this
  architecture is built wrong; `references/layering.md` §3 has the incorrect/correct pair.
- Every tool is backed by exactly one OpenAPI operation. No operation, no tool — you do not get to
  invent one because a workflow would read better with it.
- The MCP server calls the REST API over HTTP. It never reaches the database, the queue or an
  external target system directly. Bypassing the REST layer duplicates every validation, auth check
  and audit trail the API already owns, and the two copies drift within one release.
- Credentials for an external system are **tool arguments and nothing else** — never in a skill
  document, a prompt, a resource, a tool description, a summary or a log.
- **The MCP endpoint is authenticated before any dispatch, and the caller's scope comes from the
  authenticated request — never from a tool argument.** An MCP surface is a new front door onto an API
  that already exists; built without this, it is an open proxy in front of every operation you have,
  and `tools/list` publishes the map. `references/tool-generation.md` §7.
- **A rule written in a skill document is guidance to a cooperating model, not an access control.**
  Every scope rule exists twice: once as an instruction, once as an enforced check in the API.

## Route

| You are doing this | Read | Writes code? |
|---|---|---|
| Building the surface from an OpenAPI document | `jobs/generate.md` | yes, generated modules |
| Auditing or accepting an existing surface | `jobs/verify.md` | no, findings only |
| Writing or reviewing one skill document | `specs/skill-document.md` + `references/skill-authoring.md` | one `.md` |
| Deciding where a behaviour belongs | `references/layering.md` | no |

State which row you picked in one line before starting.

---

## The layering — the spine of the whole method

Five layers, each with one job. Full version with the request path in `references/layering.md`.

| Layer | Is | Contains |
|---|---|---|
| **Skill** | workflow instructions, in Markdown | when to use, ordered steps, confirmation rules |
| **MCP Prompt** | the protocol representation of a skill | the same document, retrievable over MCP |
| **MCP Tool** | one executable operation | schemas plus the REST mapping |
| **REST API** | the business API | validation, auth, business rules |
| **API implementation** | the actual operation | data access, external calls |

A skill does not execute code. It tells a model which tools to call, in what order, and what to
refuse. Delete the skill and the tools still work; delete the tools and the skill can do nothing.

## The three capabilities an MCP server must expose

Details, discovery methods and payload shapes in `references/capability-model.md`.

| Capability | Generated from | Discovered by | Retrieved by |
|---|---|---|---|
| **Tools** | OpenAPI operations, 1:1 | `tools/list` | `tools/call` |
| **Prompts** | skill documents, 1:1 | `prompts/list` | `prompts/get` |
| **Resources** | skill documents, plus one index | `resources/list` | `resources/read` |

Resource URIs are `productname://skills` for the index and `productname://skills/<skillName>` for one
document, MIME type `text/markdown`. Resources are read-only. A client that prefers to read
documentation rather than fetch a prompt uses these, and gets the same bytes.

---

## Non-negotiables

1. **Tool names match OpenAPI operation names exactly.** Rename in the mapping layer and the model is
   told about a `moveRecords` that no log line, no dashboard and no support engineer can find.
2. **All tools are generated, never hand-written.** A hand-edited tool drifts from its operation on
   the next API change and the schema starts lying to the model.
3. **A skill references only tools that exist.** The generator resolves every name in the manifest
   against the OpenAPI document and **fails the build** on a miss. Without that gate the first
   failure is a tool-not-found at run time, in front of a user, mid-workflow.
4. **Skill names are unique, lower snake case, and name the business task.** The name is the prompt
   name, the resource URI segment and the file name at once — a duplicate silently shadows a skill.
5. **One skill per business task.** Not one per tool, not one per endpoint. A skill that lists a
   single tool and adds no ordering, no confirmation and no refusal is a tool with extra steps.
6. **Every skill document carries all 13 sections** of `specs/skill-document.md`. The absent section
   is always the one that mattered: no "When not to use" is how a read skill gets used to mutate.
7. **Destructive skills require explicit human confirmation, obtained in that skill.** Never infer it
   from an earlier unrelated message, and never auto-set a `force` flag.
8. **Two destructive decisions need two confirmations.** Deleting from the external system and
   deleting the local record of that deletion are separate; one approval must never cover both.
9. **Never claim an operation succeeded without reading the tool result.** A model that narrates the
   call it made instead of the result it got reports success on a `FAILED` envelope.
10. **Distinguish stored state from live state.** Data read from your own stored export record is not
    proof that anything is still present in the external system. Say which one you read.
11. **Preserve identifiers exactly.** Row numbers, record ids, group ids, export ids — pass them
    through unmodified, never regenerate them, never renumber for readability.
12. **Redact before returning.** Authorization headers, API keys, tokens, passwords, cloud resource
    identifiers and raw stack traces never leave the mapping layer. `references/tool-generation.md` §5.
13. **Tool descriptions describe the operation; skills describe the workflow.** A tool description
    that says "call this after three other tools" is a skill leaking into a schema, and it is read
    out of order every time.
14. **Generation is deterministic.** Same manifest and same OpenAPI document ⇒ byte-identical output,
    or the diff is unreviewable and nobody will read it again.
15. **Never overwrite a hand-authored skill document.** The generator writes registration modules and
    indexes. Markdown is authored; regenerating over it destroys the only layer a human wrote.
16. **Treat every prompt argument as hostile text.** It is interpolated into a document a model then
    obeys. Values only, no Markdown structure, length-capped, declared names only — otherwise a caller
    appends a step to your workflow and the model cannot tell it from the ones you wrote.
    `references/skill-authoring.md` §11.
17. **Skill documents are static build artifacts.** Never assemble one at request time from stored or
    user-supplied data — that is indirect prompt injection with your own server delivering it.

---

## What this does NOT do

- **Does not register a skill as a tool.** A skill guides; a tool executes. If your `tools/list`
  contains something ending in `_skill`, that is the bug, not a naming quirk.
- **Does not put a model inside the MCP server.** No inference, no planning, no tool selection
  server-side. The client's model does that, which is why the skill is a document and not code.
- **Does not invent a tool that no OpenAPI operation backs.** A workflow that needs an operation the
  API does not have is an API change request, not a tool definition.
- **Does not put business logic in a skill.** Skills contain no executable code, no queries, and no
  arithmetic the API should be doing.
- **Does not create resources in the external system.** An export skill moves records into a dataset
  that already exists; it never claims to have created the destination dataset or the container holding it.
- **Does not delete an entire external dataset.** Deletion is scoped to the identities one stored
  export record names, and never to the container holding them.
- **Does not store or echo credentials.** Not in a resource, not in a prompt document, not in a
  summary, not in a log. Never mints a certificate or a keypair as an authorization mechanism.
- **Does not accept an unauthenticated MCP endpoint**, and does not let a caller choose its own tenant
  or account scope through a tool argument.
- **Does not choose an MCP SDK for you.** The layering and the contracts are the same whether you use
  an official SDK's decorators or hand-roll the JSON-RPC method set; `references/layering.md` §6
  gives the trade-off.

---

## Worked example — a neutral records service

Illustration only. Your surface has as many tools as your API has operations. Six tools:

| Tool | HTTP | Effect |
|---|---|---|
| `listGroups` | GET | read |
| `listRecordsByRange` | GET | read |
| `createBatchRecords` | POST | write, local |
| `exportRecordsToTarget` | POST | write, external system |
| `getExportData` | GET | read, stored export record |
| `deleteExportFromTarget` | DELETE | destructive, external system |

Four skills over those six tools, each named for the task and listing the tools it uses:

| Skill | Tools used | Destructive | Illustrates |
|---|---|---|---|
| `inspect_groups` | `listGroups` | no | read-only skill, pagination discipline |
| `create_records_in_group` | `createBatchRecords` | no | server-owned identifiers, per-item results |
| `export_records_to_target` | `listRecordsByRange`, `exportRecordsToTarget`, `getExportData` | no | preview, credentials, partial success |
| `reverse_export` | `getExportData`, `deleteExportFromTarget` | **yes** | scoped deletion, two confirmations |

The rule the table carries: **one skill per business task, named for the task, declaring its tools.**
The tool count and the domain are yours; that rule is not.

---

## Files — read the one you need

| File | Answers |
|---|---|
| `references/layering.md` | ★ the five layers, the request path, skills-are-not-tools, prompt vs tool separation |
| `references/capability-model.md` | what `tools/list`, `prompts/list` and `resources/list` must return, and the URI scheme |
| `references/tool-generation.md` | ★ one tool per operation, the 10 required fields, argument mapping, result mapping, redaction |
| `references/skill-authoring.md` | skill naming, the universal client instructions, destructive rules, credential rules, output rules |
| `references/structure.md` | the generated module layout and what each module is forbidden to import |
| `jobs/generate.md` | the build procedure, phase by phase, from an OpenAPI document to a running surface |
| `jobs/verify.md` | the 25 acceptance criteria and the five test groups that prove them |

Output contracts in `specs/`: `specs/skill-document.md` (the 13-section skill document, with a
template) · `specs/skill-manifest.md` (the manifest that drives generation).

---

## Checklist before saying done

- [ ] Every OpenAPI operation appears in `tools/list`, under its own operation name
- [ ] No entry in `tools/list` is a skill, and no skill document is executable
- [ ] Every skill in the manifest has a document, a prompt and a resource
- [ ] `prompts/list` returns every skill; `prompts/get` returns its document
- [ ] `resources/list` includes `productname://skills`; unknown skill URIs return not-found
- [ ] The build fails on a missing tool reference, a missing document, or a duplicate skill name
- [ ] Every destructive skill names its target, states what is and is not affected, and asks
- [ ] No credential appears in any document, resource, description, summary or log
- [ ] Regenerating twice produces no diff
- [ ] The server contains no AI model, and the report says so
