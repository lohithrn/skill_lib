# Touchpoint 4 — Query the artifacts at run time

The tool-calling interface loads an artifact directory that already exists and exposes two methods:
`answer(...)` to query it and `about()` to describe it. It builds nothing.

## Usage

```python
from pathlib import Path
from <package>.tool_calling import <Domain>ToolCall
from <package>.configuration import ArtifactConfig
from <package>.dependency_injection import ConfigDependencyInjection

config = ArtifactConfig(
    input_dir=Path("raw_data"),
    category="<category>",
    bedrock_region="us-east-1",
    runtime_mode="bedrock",
    model_id="<bedrock-model-id>",
    embedding_model_id="amazon.titan-embed-text-v2:0",
    embedding_dim=1024,
)

tool = <Domain>ToolCall(
    artifact_directory=Path("/mnt/efs/<tenant>-<project>/<prefix>/<category>/<artifact-directory>"),
    configurations_and_constants=config,
    model_name="<bedrock-model-id>",
    dependency_injection=ConfigDependencyInjection.default(),
)

info = tool.about()                                      # inspect the artifact
result = tool.answer("<query>", mode="hybrid")            # query it
```

`embedding_dim=1024` must match the embedding model actually named in `embedding_model_id`. A
dimension that disagrees with the model does not raise on load — it raises, or worse returns
garbage, on the first vector comparison.

## The model-id constraint

**`model_name` at query time MUST equal the model id used at build time in touchpoint 3.** They
differ ⇒ `RuntimeError`, deliberately, at construction. This is not defensiveness: embeddings
written by one model and read by another return confidently ranked nonsense, and there is no
downstream signal that anything is wrong. An exception at startup is the cheapest possible failure.

## The three access modes

One artifact class, three wrappers, and the wrapper is chosen by *where the code runs*, never by a
flag a caller passes.

| Mode | Class | When | What it does |
|---|---|---|---|
| Direct build | `<Domain>Artifacts` | The build pipeline, local development | Constructor builds the artifacts locally |
| S3 cache | `S3ArtifactCacheDecorator` | CI/CD, shared builds | Downloads from the artifact bucket, builds only what is missing, uploads the result |
| EFS mount, read-only | `EFSMountDecorator` | Production (Lambda, ECS) | Reads from the mounted filesystem, writes nothing |

The tool-calling class **always uses the read-only mount decorator internally.** It expects artifacts
to already exist at the path it was given and fails if they do not. That refusal is the point: a
query path that can trigger a build will, one day, trigger a full extraction inside a request
timeout — and then again for every retry.

## The LLM adapter

For tool-use loops, the tool exposes an adapter that publishes its own schemas rather than making the
caller hand-write them:

```python
adapter = tool.llm_adapter

schemas = adapter.tools()               # generic function-calling schemas
bedrock_schemas = adapter.bedrock_tools()  # Bedrock converse format

result = adapter.call("<tool_name>", query="...", mode="hybrid")   # dispatch by name
```

`adapter.call(name, **kwargs)` is the same dispatch a model driver performs, which means the tool
loop and a direct call go through one code path. Two paths drift, and the one that drifts is always
the one only the model exercises.

## The tool-call base class

Every domain tool derives from a single `_tool_call_base.py` that owns:

- resolving the artifact directory and refusing a missing one,
- the model-id equality check above,
- `about()`, so every tool describes itself the same way,
- the adapter surface, so schemas are generated, not maintained by hand.

A domain adds `<domain>_tool_call.py`, `<domain>_tool_constants.py` and `<domain>_tool_schemas.py`
and nothing else. A tool that re-implements any of the four items above has forked the contract, and
the fork shows up as one tool whose `about()` reports a different shape.

## Loading from the manifest, not from arguments

A production caller should not be handed a mount path at all. It reads one:

```python
from <package>.resource_manifest import load

manifest = load()
artifact_dir = Path(manifest.mount_root) / category / artifact_directory
```

Passing the path in from configuration duplicates the manifest, and the duplicate is what goes stale
after a stage moves. See `specs/manifest-contract.md` for the full reader API.
