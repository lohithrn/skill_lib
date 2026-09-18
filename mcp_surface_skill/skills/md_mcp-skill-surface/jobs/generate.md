# Job: generate the MCP surface from an OpenAPI document

Read `references/layering.md` first if you have not. Then work these phases in order. Each phase has an
exit condition; do not start the next one until it holds.

Inputs you need before phase 1:

| Input | Required | If missing |
|---|---|---|
| The OpenAPI document for the service | yes | **stop.** Tools are generated from operations; without the document there is nothing to generate and hand-writing tools is forbidden |
| A working REST API behind it | yes | stop. The MCP surface adds no capability, it re-exposes one |
| The product's lowercase identifier for the URI scheme | yes | pick it once, with the owner — it is a breaking change later |
| The list of business tasks worth a skill | no | derive a first draft in phase 3, then have a human cut it |

---

## Phase 1 — inventory the operations

Read the OpenAPI document and build one row per operation. This table is the tool set; nothing is added
to it later by hand.

| Column | From |
|---|---|
| operation name | `operationId` — this becomes the tool name, unchanged |
| method + path template | the path item |
| path parameters | the operation's path parameters |
| query parameters | the operation's query parameters |
| headers the operation accepts | the operation's header parameters — an idempotency key, a request id |
| request body shape | per-property, or free-form (a whole-payload PATCH or PUT) |
| response envelope | the shared response schema, if the API has one |

**Exit:** every operation in the document has a row, and every row has an `operationId`. An operation
with no `operationId` cannot be named deterministically — fix the OpenAPI document, do not invent a name.

Flag any operation whose path carries a deployment prefix (a project, stage or region segment). Those
placeholders are resolved from configuration by the mapper and never appear in a tool's input schema —
`references/tool-generation.md` §2.

## Phase 2 — generate the tools

One module per row, each exposing exactly one tool value with the **10** fields from
`references/tool-generation.md` §1. Flatten path, query, header and body parameters into one input
object; record the mapping metadata that splits them back apart.

**Exit:** the tool registry, loaded, returns one tool per operation, sorted by name, and running the
generator twice produces no diff.

## Phase 3 — write the manifest

The manifest is the source of truth for skills. Shape and full field list in
`specs/skill-manifest.md`. One entry per skill: name, title, description, document path, tool list,
destructive flag.

Cut the skill list with a human before writing any document. The rule from
`references/skill-authoring.md` §2 is the filter: **one skill per business task**, named for the task.
A skill that wraps one tool and adds no ordering, no refusal and no confirmation gets deleted here,
where it costs nothing.

**Exit:** every manifest tool name appears in the phase 1 table. Every skill name is unique.

## Phase 4 — author the skill documents

One Markdown document per manifest entry, all **13** sections from `specs/skill-document.md`, with the
universal client instructions from `references/skill-authoring.md` §3 stated **in each document**.

Order of work inside one document, because it is the order that catches mistakes:

1. Purpose and the two use sections — *when to use* and *when not to use*. Write "when not to use"
   second, not last; it is what stops a read skill being used to mutate.
2. Required and optional inputs. Every required input maps to a required field of some tool in the list.
3. Tools used, by exact name.
4. The ordered workflow, numbered, one action per step, with validation steps before the first call.
5. Confirmation rules. For a read skill, write "none, this skill only reads" — an empty section reads
   like an oversight and invites someone to fill it in.
6. Validation rules, failure behaviour, expected final response.
7. For a destructive skill, the 8 rules from `references/skill-authoring.md` §4, and the two-confirmation
   sequence when the skill also touches local records.

**Exit:** every manifest document path resolves to a file, and every tool the document names is in the
manifest entry's tool list. A document naming a tool the manifest does not list is a workflow that
escapes the validation gate.

## Phase 5 — write the generator

One generator, in the service repo — `scripts/generate_surface.py` or whatever your repo's convention
is. It has **10** obligations:

1. Read the skill manifest.
2. Validate that every referenced tool name exists in the OpenAPI document.
3. Generate one prompt registration module per skill.
4. Generate the skill index.
5. Generate the resource registration.
6. Verify that every Markdown skill document exists.
7. **Fail the build** when a skill references a missing tool.
8. **Fail the build** when two skills share a name.
9. Produce deterministic output.
10. Never overwrite a hand-authored Markdown document unless explicitly asked.

Obligations 7 and 8 are the whole point. Without 7, the first symptom is a tool-not-found at run time,
mid-workflow, in front of a user, after the model has already performed the earlier steps — including
the irreversible ones. Without 8, one skill silently shadows another and the manifest still looks
complete.

**Exit:** deliberately break the manifest — point a skill at a tool that does not exist, then duplicate
a skill name — and confirm the build fails both times with a message naming the offender. A gate you
have not seen fire is not a gate.

## Phase 6 — wire the protocol surface

Implement or register the method set from `references/capability-model.md` §5, and declare all three
capabilities in the handshake. Compose the registries once, per `references/structure.md` §3.

Then, in order. **Step 0 is not optional and comes first** — read
`references/tool-generation.md` §7 before writing any of it:

0. **Authenticate.** One gate, in the entrypoint, before the method table — before `initialize`, before
   `tools/list`. Same authentication as the REST API. The caller's scope comes from the authenticated
   request, never from a tool argument, and no parameter belonging to a security scheme appears in any
   generated input schema. Skip this step and everything below it is an open proxy over your whole API,
   with `tools/list` publishing the map.
1. `initialize` returns three capabilities and a protocol version.
2. `tools/list` returns every operation.
3. `prompts/list` returns every skill.
4. `prompts/get` returns a rendered document — interpolating arguments per
   `references/skill-authoring.md` §11: value positions only, no Markdown structure, length-capped,
   declared names only.
5. `resources/list` includes the index URI.
6. `resources/read` returns the index as JSON and a document as Markdown, resolved against the loaded
   skill map and never the filesystem.
7. `tools/call` performs exactly one REST call and returns a mapped, redacted result.

**Exit, both halves:** an unauthenticated `initialize` and an unauthenticated `tools/list` are
**refused**, and a call naming a scope the caller does not hold is refused — *then* an authenticated
client connects, lists all three capability types, reads one skill, and completes one
tool call end to end.

## Phase 7 — package and test

Pack the artifact with the skill documents and the manifest inside it
(`references/structure.md` §5), then run the five test groups from `jobs/verify.md` §3.

**Exit:** every group passes, and the artifact's skill-document count equals the manifest's entry count.

---

## Report when done

Keep it to ≤25 lines:

1. Operations found, tools generated, skills authored, destructive skills marked.
2. Any operation you could not map, and why. Never a silent skip.
3. The two build gates, and the message each produced when you broke the manifest on purpose.
4. Which capabilities the handshake declares.
5. What is **not** covered: operations with no `operationId`, endpoints deliberately withheld from the
   MCP surface, and any skill a human cut in phase 3.

## What this job refuses

- **Hand-writing a tool.** No operation, no tool.
- **Registering a skill as a tool.** `references/layering.md` §3.
- **Regenerating a hand-authored skill document.**
- **Shipping with the build gates unproven.**
- **Putting a model, a planner or a tool-selection branch in the server.**
- **Shipping an endpoint with no pre-dispatch auth gate.** Phase 6, step 0.
- **Taking the caller's scope from a tool argument.** `references/tool-generation.md` §7.
- **Interpolating a prompt argument without stripping Markdown structure.**
  `references/skill-authoring.md` §11.
