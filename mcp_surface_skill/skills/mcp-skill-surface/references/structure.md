# The generated module layout

The one question this file answers: **which file owns what, and what is each file forbidden to know?**

The layout is reusable as-is. Rename the root package for your product; keep everything below it.

## Where the tree lives: `src/` runs, `tests/` proves

Two top-level trees, and the split is a rule, not a preference:

```
<repo>/
├── src/
│   └── mcp_proxy/     the tree below — and NOTHING else
└── tests/
    ├── unit/          mappers, registries, the generator
    ├── integration/   the protocol surface against a stubbed API
    ├── contract/      tools vs the OpenAPI document; documents vs the manifest
    └── qe/            the end-to-end workflow tests from `jobs/verify.md` §3
```

| Rule | Consequence if broken |
|---|---|
| **`src/` holds only what executes in production and what the deploy needs.** The entrypoint, the mappers, the network client, the registries, the generated modules, the skill documents, the manifest | anything else in `src/` ships. A scratch script in the artifact is attack surface with no owner, and a test helper in `src/` means a test double is one import away from a production code path |
| **Every test lives under `tests/` — unit, integration, contract, QE, load.** None of them under `src/` | a `test_*.py` beside the module it tests gets packaged, imported and, once, executed against a real endpoint |
| **The generator is a build tool, not a runtime module.** It lives outside `src/` — `scripts/` or `tools/` at the repo root | a generator inside the artifact invites regeneration in production, against whatever OpenAPI document happens to be reachable |
| Fixtures, stubs and recorded responses live under `tests/`, never in the package | a recorded response usually contains a real header, and now it is in your deploy artifact |
| A module in `src/` that nothing in `src/` imports and no entrypoint reaches is **dead** — delete it | dead code in the artifact is dependency surface you still patch, review and pay cold-start for |

The test: list the artifact after packaging. Every file in it should be something a request touches, or
something the platform needs to start. If you cannot say which, it does not belong there.

## 1. The tree

```
src/mcp_proxy/
├── app.py                          entrypoint: transport in, protocol dispatch out
├── backend_client.py               the ONLY component that reaches the network
├── argument_mapper.py              flat MCP arguments -> path · query · headers · body
├── result_mapper.py                REST response -> MCP tool result, redacted
│
├── tools/
│   ├── generated/                  one module per OpenAPI operation, each exposing one TOOL
│   │   ├── list_groups.py
│   │   ├── list_records_by_range.py
│   │   ├── create_batch_records.py
│   │   ├── export_records_to_target.py
│   │   ├── get_export_data.py
│   │   └── delete_export_from_target.py
│   └── tool_registry.py            discovers every generated TOOL; backs tools/list + tools/call
│
├── skills/
│   ├── skill_registry.py           loads the manifest + the Markdown; backs prompts/list + prompts/get
│   ├── skill_resource_registry.py  backs resources/list + resources/read
│   │
│   ├── inspect_groups.md           hand-authored workflow documents
│   ├── create_records_in_group.md
│   ├── export_records_to_target.md
│   └── reverse_export.md
│
├── prompts/                        one generated registration module per skill
│   ├── inspect_groups.py
│   ├── create_records_in_group.py
│   ├── export_records_to_target.py
│   └── reverse_export.py
│
└── resources/
    ├── skill_index.py              serves productname://skills
    └── skill_document.py           serves productname://skills/<skillName>
```

Two more modules the tree implies and every real build needs:

| Module | Owns | Why it is separate |
|---|---|---|
| `tools/tool_definition.py` | the immutable tool shape: the descriptive fields plus the **5** REST mapping fields | the mappers depend on the *shape*, not on any tool; without it every generated module repeats the structure and a field rename touches all of them |
| `tools/common_schema.py` | the shared response-envelope output schema | your API returns one envelope shape; inlining it into every generated module means one place to fix per operation |

If you hand-roll the protocol rather than using an SDK, add one more: a dispatcher module holding the
method table and nothing else. Keeping it out of the entrypoint is what lets you test every protocol
method without constructing an HTTP event.

## 2. Ownership and forbidden knowledge

The value of the layout is the second column. A module that knows something in column three has
collapsed a layer.

| Module | Knows | Must **not** know |
|---|---|---|
| `app.py` | the transport (an HTTP event, stdio, a socket), auth, the dispatcher | any tool, any skill, any REST path |
| dispatcher | the MCP method names and which registry serves each | what any individual tool or skill does |
| `tool_registry.py` | that generated modules exist and expose a `TOOL` | any tool's schema or REST mapping |
| `tools/generated/*.py` | one operation: schemas + mapping metadata | any other tool, any skill, any workflow, the HTTP client |
| `argument_mapper.py` | how to split a flat argument object using mapping metadata | business rules, tool names, credentials |
| `backend_client.py` | the base URL, the header allowlist, timeouts, envelope parsing | tools, skills, mapping, redaction |
| `result_mapper.py` | the redaction list and the error rule | which tool produced the response |
| `skill_registry.py` | the manifest and the Markdown documents | tools, HTTP, the protocol transport |
| `skill_resource_registry.py` | the URI scheme and the MIME types | how a document was authored |
| `prompts/*.py` | one skill's name, title, description, tool list, argument names | the document's contents — it loads them |
| `resources/*.py` | how to render an index and one document | the manifest format |

Read the table as a dependency direction: **entrypoint → dispatcher → registries → definitions →
mappers → client.** No edge points back up. If a generated tool module imports the HTTP client, a schema
change and a network change are now the same commit.

## 3. Composition happens once

Build the registries and the mappers in **one** function in the entrypoint, pass them in by
constructor, and cache the assembled object for the process lifetime.

| Rule | Consequence if broken |
|---|---|
| One composition function, in the entrypoint | a registry constructed inside a handler re-imports and re-parses every generated module and every Markdown document on every request |
| Constructor injection only — no module-level singletons reached into from a handler | tests cannot substitute the HTTP client, so every protocol test needs a live API |
| Cache across invocations, build on first use | in a serverless runtime this is the difference between paying the load cost once per cold start and once per request |
| Nothing reads configuration except the composition function and the mapper's deployment placeholders | configuration read deep in the tree cannot be seen, overridden or tested |

## 4. Where generation stops and authoring begins

| Path | Generated | Hand-authored |
|---|---|---|
| `tools/generated/*.py` | ✅ every run | never |
| `prompts/*.py` | ✅ every run | never |
| the skill index | ✅ every run | never |
| the resource registration | ✅ every run | never |
| `skills/*.md` | ❌ | ✅ the workflow, by a human |
| the manifest | ❌ | ✅ the skill-to-tool mapping, by a human |
| `argument_mapper.py`, `result_mapper.py`, `backend_client.py`, the dispatcher | ❌ | ✅ written once, tested, then stable |

Every generated file carries a header saying it is generated and naming the generator. Without it, the
first person to find a wrong schema fixes the generated file, and their fix disappears at the next
build with no trace of why.

**The generator never writes over `skills/*.md`.** Those documents are the only artifact in the tree
that encodes human judgement about a workflow. Regenerating them replaces judgement with a template.

## 5. Packaging

The skill Markdown and the manifest must be **inside the deployed artifact**. A registry that resolves
them relative to a source checkout works locally and returns an empty prompt list in production.

Resolve in this order, and keep both paths:

1. The manifest packaged next to the skill documents inside the artifact.
2. Otherwise, the repository's contract directory — the local-checkout path.

Keeping both is not redundancy; it is what lets one loader serve a test run and a deploy without a
branch on an environment variable.

Assert it in the build: pack the artifact, then list the skill documents inside it and compare the count
to the manifest. `jobs/verify.md` §4 covers the check.
