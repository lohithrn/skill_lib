# The layering

The one question this file answers: **which layer does a piece of behaviour belong to?** Every other
rule in this skill is downstream of the answer.

## 1. The five layers

| Layer | Definition | Artifact | Owns |
|---|---|---|---|
| **Skill** | workflow instructions | `skills/<name>.md` | when to use, ordered steps, refusals, confirmation |
| **MCP Prompt** | the protocol representation of the skill | `prompts/<name>.py` | name, title, description, arguments |
| **MCP Tool** | one executable operation | `tools/generated/<snake_name>.py` | input/output schema, REST mapping |
| **REST API** | the business API | the existing service | validation, auth, business rules, audit |
| **API implementation** | the actual operation | the existing handlers | data access, external system calls |

The skill and the prompt are the **same content** in two forms: one is a file a human edits, the other
is that file delivered over the protocol. If they can disagree, you have two sources of truth and the
one the client reads is the one nobody reviewed.

**The MCP server contains no AI model.** It validates, maps, calls, and maps back. All reasoning
happens in the client, whose model is the only thing in the system that reads a skill.

## 2. The request path

```
Human
  │
  ▼
MCP client + AI model
  │
  ├── reads a <product> skill          (prompts/get or resources/read)
  ├── discovers <product> tools        (tools/list)
  └── calls the required tools         (tools/call)
        │
        ▼
<product> MCP server
  │
  ├── validates tool arguments         (against the generated input schema)
  ├── maps arguments to REST           (path · query · headers · body)
  └── calls the <product> REST API     (HTTP, one call per tools/call)
        │
        ▼
<product> API implementation
  │
  └── data access, external system calls, business rules
```

Two properties of this path are load-bearing:

- **A skill does not execute code.** It cannot. It is text handed to a model. Everything a skill
  "does" happens because the model chose to call a tool the skill named.
- **One `tools/call` is one REST call.** A tool that fans out to three endpoints hides a workflow
  inside a schema, and the client can no longer sequence, retry or confirm the middle step. Sequencing
  belongs in the skill, where a human can read it.

## 3. Skills are not tools

The hardest rule in this document, and the one worth the most. **Do not register a skill as an
executable tool.**

Incorrect — a skill exposed through `tools/list`:

```
Tool: export_records_skill
```

Correct — a skill exposed as a prompt, declaring the tools it orchestrates:

```
Skill prompt: export_records_to_target
Uses tools:   listGroups
              listRecordsByRange
              exportRecordsToTarget
              getExportData
```

Why it matters, concretely:

| If a skill is a tool | Consequence |
|---|---|
| The client calls it and waits for a result | There is no result — a skill has no implementation, so the call either errors or returns instructions the model was not expecting in a result slot |
| The server must interpret the workflow | You have just put a model in the server, or a hard-coded orchestration nobody can change without a deploy |
| Confirmation happens server-side, or not at all | The human is on the client. A server-side "are you sure" reaches nobody |
| Tool selection degrades | The model now sees two kinds of thing in one list and picks the coarse one, skipping every validation step the skill specified |

The test is mechanical: **anything in `tools/list` must be backed by exactly one OpenAPI operation.**
A name ending in `_skill` in a tool list is the bug.

## 4. Prompt and tool separation

The same business capability is described twice, at two altitudes. Neither copy may contain the
other's content.

| | Tool `exportRecordsToTarget` | Skill `export_records_to_target` |
|---|---|---|
| Defines | inputs, output, REST mapping, operation description | when to preview rows, when to ask for confirmation |
| Defines | argument types and constraints | how to interpret partial success |
| Defines | the HTTP method and path | how to report the export id |
| Defines | which fields are required | what the external dataset must already contain |
| Never contains | ordering, confirmation, multi-step guidance | code, queries, schemas, HTTP details |

**Operation behaviour belongs in tool descriptions. Workflow instructions belong in skills.** Mixing
them is not a style problem: the model reads tool descriptions during selection, out of order and out
of context, so ordering advice placed there is applied at the wrong moment.

## 5. Tool description requirements

A description must help a model pick the right tool **without embedding a skill**.

Good:

> Move records in a tenant-global row range, restricted to their current group, into an existing
> external target dataset.

Bad:

> Use this tool after calling three other tools and then ask the user…

The good one names the operation, its scope and its precondition in one sentence. The bad one is a
workflow, will be read during selection rather than during execution, and describes steps the model
has no way to verify it performed.

## 6. Protocol plumbing: SDK decorators or a hand-rolled method set

Both are legitimate. The layering is identical either way; only the registration syntax differs.

| | Official SDK | Hand-rolled JSON-RPC |
|---|---|---|
| Registration | a decorator per prompt and tool | a registry object per capability type |
| Method set | supplied | you implement `initialize`, `ping`, `tools/list`, `tools/call`, `prompts/list`, `prompts/get`, `resources/list`, `resources/read` |
| Argument types | constrained by the SDK — **prompt arguments must be strings** unless the SDK and negotiated protocol version clearly support another type | your choice, and therefore your bug |
| Cost | a dependency in the deploy artifact | ~150 lines of dispatch you own and must test |
| Best when | a general-purpose server | a constrained runtime where the dependency does not fit, or a serverless function behind an HTTP gateway |

**Tool input schemas keep their real JSON types in both cases.** The string-argument constraint is a
prompt-argument constraint only; applying it to tool schemas throws away the validation that stops the
model sending a row number as a sentence.

If you hand-roll, the dispatcher is the only place that knows the protocol, and it delegates every
method to a registry — see `references/structure.md` §2. If you use an SDK, the registration module
per skill is a decorated function that loads the document and returns it; the loader is still the
single source of truth.

## 7. Where does this behaviour belong?

Use this table before writing anything. The wrong answer is always "the server".

| Behaviour | Layer | Why not elsewhere |
|---|---|---|
| "Call A, then B, then report" | Skill | the server would need to plan; the client already has a model |
| "Ask the human before deleting" | Skill | the human is attached to the client — but the **guard** that enforces it is in the API, because a hostile client asks nobody. `references/tool-generation.md` §7 |
| "Reject a row range where start > end" | Tool schema **and** skill | the schema is the hard gate; the skill explains it so the model asks instead of failing |
| "Normalize the target system's name to uppercase" | Skill instruction + REST API | the mapping layer may not silently rewrite values a human supplied |
| "Generate the record id" | API implementation | a client-generated id is a duplicate key waiting to happen |
| "Retry on a 429" | MCP client or the REST API | a retry inside the mapping layer double-charges an external operation |
| "Strip credentials from the response" | Result mapper | it is the last place before the wire; a skill instruction cannot unsend bytes |
| "Decide which of two lookup tools to use" | Skill | it depends on what the human supplied, which only the client knows |
| "Fail the build on a missing tool reference" | Generator | run time is too late; see `jobs/generate.md` phase 5 |

## 8. What the layering buys you

- **The API stays the contract.** Every MCP call lands on an endpoint that already validates, already
  authorizes and already audits. Nothing gets a second, weaker path in.
- **Skills change without a deploy of the API.** They are Markdown; the workflow layer moves at the
  speed of review, not of release.
- **The tool surface is derivable.** Since tools are generated from OpenAPI, adding an endpoint adds a
  tool for free, and removing one removes the tool rather than leaving a schema that lies.
- **Refusals are auditable.** They are sentences in a document, in version control, next to the
  workflow they constrain — not conditions buried in a handler.
