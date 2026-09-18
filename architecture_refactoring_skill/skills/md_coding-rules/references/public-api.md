# Public API surface — discoverability, clean primary interfaces, no magic strings

Answers: *what does the caller see when they open this class, and can they discover every operation
from the signature alone?*

Three rules: **7B** (operations are typed methods, not strings), **7E** (optional protocols leave the
primary class), **7C** (no hard-coded strings — localize constants, prefer enums). They share one
premise: **a signature is documentation, and a string is not part of a signature.**

---

### 7B. Public APIs must be discoverable

Public classes that callers will use programmatically must be inspectable from their signature alone.
A developer reading the class header, its method list, or its constructor must be able to discover
what operations exist, what arguments each takes, and what each returns — without reading the
implementation, JSON schemas, or string tables.

**Rules:**

- Every supported operation must be a **direct, named method** on the class with typed parameters and
  a typed return. Methods are how callers invoke behavior.
- **Never use bare strings to select behavior** in the primary client-facing API. A method signature
  like `tool.call("graph_neighborhood", entity_query="x")` hides the operation name and its arguments
  from the type system, the IDE, and the reader.
- When an operation has a small fixed set of valid values (modes, kinds, tool names, formats), use an
  `Enum` (or `Literal`) — not a free-form string. The enum becomes a discoverability surface:
  `RerankerProvider.LOCAL` shows up in autocomplete; `"local"` does not.
- Enums backing string contracts should subclass `(str, Enum)` so that JSON serialization and external
  dispatch still work without callers having to convert.
- **An enum must group at least two related values.** A single-member enum is pure ceremony —
  `class FooTool(str, Enum): ONLY = "foo"` adds no discoverability and no type safety beyond a named
  constant. When there is exactly one valid value, expose it as a localized module-level constant
  (`FOO_TOOL_NAME = "foo"`) and a direct method (`def do_foo(...)`); do **not** wrap it in a one-member
  enum.
- **The threshold is ≥2 related values.** Vector search has one operation: one method, one constant.
  Graph traversal has four operations: four methods grouped under one `GraphTool` enum. The reranker
  has two providers: one `RerankerProvider` enum. A retrieval surface with five modes: one mode enum
  with five members, not five loose constants — the cap on an enum is cohesion, not count. Apply this
  rule strictly — ceremony for symmetry across classes is a code smell.
- **If you find yourself reaching for a one-member enum just to "match" the shape of another class,
  stop.** Different surface areas are allowed to have different shapes. Force-fitting a 1-member enum
  onto a class with a single operation is exactly the Java/C# anti-pattern of "every class needs an
  interface". It does not.
- A `call(name, **kwargs)` style entry point is acceptable **only as an adapter for an external caller
  that genuinely passes strings** — for example, an LLM tool-call dispatcher receiving a tool name from
  a model output. Even then, the underlying operations must also be exposed as direct methods so Python
  clients never have to use the string-keyed entry point.
- The `call` adapter, when present, must accept the typed enum in addition to the string form, so
  internal Python callers can use the enum and stay type-checked.
- **Do not co-locate the string-keyed adapter on the primary client class.** If the primary class is
  `XToolCall` with direct methods like `search()` or `answer()`, a reader scanning that class for
  "what can I do with this?" should see those methods and only those methods. `tools()`,
  `bedrock_tools()`, and `call()` belong on a separate adapter object reachable through a single
  property (e.g. `tool.llm_adapter`) — not on the primary signature. Keep the LLM-protocol surface
  optional and out of sight unless the caller actually needs it.

**Bad — operations hidden behind strings:**

```python
result = tool.call("graph_neighborhood", entity_query="brand", depth=2)
```

A reader has no way to know `"graph_neighborhood"` is a valid name, what arguments it expects, or what
it returns, without reading source or docs.

**Good — direct methods with typed parameters:**

```python
result = tool.find_neighborhood(entity_query="brand", depth=2)
```

Or, when the caller is an LLM dispatcher that genuinely receives a tool name as a string at runtime,
the same operation is still reachable through the enum-typed adapter:

```python
result = tool.llm_adapter.call(GraphTool.NEIGHBORHOOD, entity_query="brand", depth=2)
```

The string-based form remains only for the LLM tool-call boundary; Python clients use the direct
methods.

**Why this matters:**

- IDEs and type checkers can navigate, complete, and validate direct methods. They cannot do any of
  that for `call("some_string", **opaque_kwargs)`.
- New consumers of the library can read the class definition and immediately know its capabilities.
  They do not have to discover hidden tool names by grepping.
- Refactors that rename or remove an operation surface as type errors at every call site, instead of
  producing runtime `Unknown tool` errors at the worst possible time.

---

### 7E. Primary interfaces must be clean — push optional protocols to a separate layer

A class a reader opens for the first time should be **a short, scannable list of the operations it
offers**. If the same class also exposes generic protocol plumbing (string-keyed dispatch, schema
enumeration, framework adapters), the reader has to mentally filter "what does this thing actually
do?" out of "what's framework boilerplate?" That filter is not free — and on a class with five
methods, only one of which is the real operation, it is the difference between an obvious API and a
confusing one.

**Rules:**

- The primary client class for a feature exposes **only the direct typed operations** callers want to
  perform. Nothing else. If a reader scans the class header and sees `search`, they know exactly what
  the class is for. If they also see `tools`, `bedrock_tools`, `call`, `_bindings`, `_lookup_binding`,
  the answer becomes "I'm not sure — read the docs."
- **Optional protocol adapters live in a separate class** reachable through a single property on the
  primary class (e.g. `tool.llm_adapter`). Examples: an LLM tool-use adapter (`tools()`,
  `bedrock_tools()`, `call(name, **kwargs)`), a CLI argparse adapter, an HTTP request router. Each of
  these is a *different audience* — model runtimes, shells, web frameworks — and each deserves its own
  type so its surface does not pollute the primary class signature.
- **The composite-property pattern beats both co-location and standalone factories.** Co-locating
  (`tool.tools()`, `tool.call()`) clutters the primary surface. A standalone `build_*_adapter(tool)`
  factory creates a second public type with no added value. A single `@property`
  (`tool.llm_adapter`) on the primary class keeps the adapter reachable when needed and invisible
  otherwise — one object total, surfaces split by audience.
- **Verbose, self-describing method names beat short generic ones.** `search`, `find_entities`,
  `find_relationships`, `find_neighborhood`, `find_paths`, `answer` all tell the reader the operation.
  A method called `query`, `do`, `run`, `execute`, or `handle` does not. When in doubt, pick the longer
  name; cheap autocomplete removes any cost.
- **Less is more in a primary interface.** A class with one direct method (`answer`) is finished. Do
  not add `tools()`, `bedrock_tools()`, `call()`, `bindings()` "to be consistent with sibling
  classes." A 1-method client is a feature, not a bug — it signals that the class does exactly one
  thing.
- **Symmetry across classes is not a goal.** If `VectorToolCall` has one method and `GraphToolCall`
  has four, that asymmetry is *information* about the underlying capabilities. Forcing every class
  through the same protocol shell hides that signal.

**Bad — primary class mixes operation methods with protocol plumbing:**

```python
class RerankerToolCall:
    def __init__(self, ...): ...
    def rerank(self, query, candidates): ...         # the actual operation
    def tools(self) -> list[dict]: ...               # LLM protocol — different audience
    def bedrock_tools(self) -> list[dict]: ...       # LLM protocol — different audience
    def call(self, tool_name, **kwargs): ...         # LLM protocol — different audience
    def _bindings(self): ...                         # framework hook
    def _lookup_binding(self, name): ...             # framework hook
```

A reader asking "what does RerankerToolCall do?" sees seven methods and has to read the implementation
to learn the answer is "it reranks candidates."

**Good — primary class shows only the direct method; the adapter is composite-hidden:**

```python
class RerankerToolCall:
    """Reranks candidate chunks against a query."""
    def __init__(self, ...): ...
    def rerank(self, query: str, candidates: list[dict]) -> dict: ...

    @property
    def llm_adapter(self) -> LlmAdapter:           # composite, hidden
        return LlmAdapter(self.ERROR_CLASS, self._tool_bindings())

# The adapter class owns the LLM protocol surface — once, generically, for any tool-call:
class LlmAdapter:
    def tools(self) -> list[dict]: ...
    def bedrock_tools(self) -> list[dict]: ...
    def call(self, name, **kwargs) -> dict: ...
```

A reader of `RerankerToolCall` sees one method (`rerank`) and learns the class's purpose in one line. A
reader wiring an LLM tool-use loop reaches for `tool.llm_adapter.call(...)` and finds the protocol
surface there. One object, two audiences, no second public type.

**Why this matters:**

- A 1-line, 1-method class header is self-documenting. A 7-method header is not.
- Optional protocols change independently. The Bedrock Converse schema and an MCP adapter are
  different consumers that may evolve at a different cadence than the primary operations. Keeping them
  in separate classes means a change to one does not touch the other.
- New consumers learn the library by reading the primary class. They do not learn it by reading
  framework hooks they will never call.
- Symmetry-driven design produces ceremony. Capability-driven design produces APIs that match what the
  underlying system can actually do.

---

### 7C. No hard-coded strings — localize constants and prefer enums

String literals scattered through the code are silent landmines. They duplicate, drift, type-check as
`str`, and rename only with `grep`. Treat every meaningful string the same way you treat numeric magic
values: **extract it, name it, group it with its peers**.

**Rules:**

- Avoid inlining meaningful strings in business logic. "Meaningful" = anything that identifies a tool,
  mode, provider, kind, route, file name, key, header, env var, artifact name, model id, default
  category, or any value the program compares, branches on, or persists. Keep one-off literals local
  when extraction would only restate the line.
- Fixed sets should usually become `Enum`s. If a value comes from a known finite set (modes,
  providers, kinds, statuses, formats, tool names), prefer an `Enum` — preferably `(str, Enum)` so JSON
  serialization remains transparent. Use constants instead when the set has one value or when an enum
  would add ceremony without improving correctness.
- **Open-ended strings become localized constants.** Values that are not from a fixed set (default
  paths, header names, fallback model ids, well-known sub-directory names) live as module-level
  constants in a constants module dedicated to that concept.
- **Group constants by responsibility, not into a global dumping ground.** Use predicate-named files
  such as `<predicate>_constants.py`. Examples:
  - `vector_search_constants.py`
  - `bedrock_model_constants.py`
  - `reranker_provider_constants.py`
  - `s3_artifact_path_constants.py`
- Do not grow a god-file `constants.py` at the package root that holds every unrelated literal. If a
  repo already has a shared constants module, add to it only when the value is genuinely cross-cutting;
  otherwise keep constants near the owning code.
- **Folder hierarchy applies to constants too.** Put constants files inside the same
  responsibility-based folder as the code that owns them. Vector constants belong inside the vector
  package. Mount-related constants belong inside the mount package. Do not promote constants to a
  root-level folder unless they are genuinely shared across multiple top-level domains. When several
  constants files relate to the same area, group them in a `constants/` sub-folder under that area.
- Consider abstracting repeated string-shaped concepts behind small types. A category name, a model id,
  an artifact path, a tool name — when these flow through many functions, introduce a small dataclass,
  named tuple, or wrapper type so the type system can distinguish them from arbitrary `str`. A
  `ModelId` parameter cannot be confused with a `Category`; two `str` parameters can.
- **Tests count too.** Test fixtures should reference enum members and constants from the same module
  the production code uses, not re-spell the strings. If a test hard-codes `"vector_search"`, a rename
  of the enum member silently keeps the test passing while production breaks.

**Bad — strings inlined and duplicated:**

```python
if provider == "bedrock":
    ...
return {"name": "rerank", "default_provider": "local"}
```

**Good — enum + constants module:**

```python
# reranker/reranker_provider_constants.py
from enum import Enum

class RerankerProvider(str, Enum):
    LOCAL = "local"
    BEDROCK = "bedrock"

DEFAULT_RERANKER_PROVIDER = RerankerProvider.LOCAL
```

```python
# reranker/reranker_tool_constants.py
RERANKER_TOOL_NAME = "rerank"
```

```python
# elsewhere in the package
if provider is RerankerProvider.BEDROCK:
    ...
return {
    "name": RERANKER_TOOL_NAME,
    "default_provider": DEFAULT_RERANKER_PROVIDER.value,
}
```

**Why this matters:**

- A rename of an enum member surfaces quickly through imports, tests, and static typing when those
  checks are enabled. A rename of a string literal can silently leave stale call sites alive.
- Localized constant files become a discoverable index of vocabulary: a new contributor reading
  `reranker_provider_constants.py` sees every valid provider at once.
- Open-ended literals stop multiplying. When the same `"X-Trace-Id"` header appears in three modules, a
  single `HEADER_TRACE_ID` constant prevents one of them from drifting to `"x-trace-id"`.
- Domain-typed wrappers stop the typical `str, str, str` argument-order bug at compile time.

**Allowed exceptions:**

- One-off literal in a single test assertion that documents an expected value.
- String passed once to a third-party API where extracting it would only restate the call site.
- Single-use strings in script-level CLI bootstrap where extraction adds no value.

If a literal crosses a boundary, drives branching, or is repeated, extract it. If it is single-use and
obvious, keep the code simple.

The hard-rules version of this, for a service where env var names, table attributes, headers and
identity-provider attribute names are all strings, is rule 33 in
`references/data-and-wiring.md`.
