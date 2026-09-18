# Migrating a consumer, in order

Five steps. The order exists to stop the app breaking *in the middle*, where you can neither run the
old code nor the new. Do not reorder them, and do not start step 3 with step 1 unfinished.

## Step 1 — fix the install first

The library no longer bundles every dependency. Install only what this consumer uses:

```bash
# Before: one install pulled in every optional dependency
pip install <LibraryName>

# After: pick the extras this consumer actually needs
pip install <LibraryName>                # base: the pure-Python core only
pip install "<LibraryName>[aws]"         # adds the AWS SDK
pip install "<LibraryName>[<domain>]"    # adds one domain's third-party clients
pip install "<LibraryName>[all]"         # every optional set
pip install "<LibraryName>[dev]"         # all, plus the test and lint tooling
```

**Why first:** with the extras missing, a consumer cannot tell "this import moved" from "this
dependency is gone". Both surface as `ModuleNotFoundError`, and they have opposite fixes. Fix the
install and the remaining errors are all real migration work.

Record in the map which feature needs which extra — a consumer should never have to bisect extras to
find out that token generation needs one and object storage needs another.

## Step 2 — hoist the environment reads to the consumer's entry point

The library no longer reads `os.environ`. Find every value the library used to resolve implicitly and
resolve it once, at startup, in the consumer:

```python
import os
from <package>.wiring import WiringConfig, DefaultWiring

config = WiringConfig(
    service_url=os.environ["<SERVICE_URL_VAR>"],
    api_key=os.environ["<API_KEY_VAR>"],
    api_secret=os.environ["<API_SECRET_VAR>"],
)
services = DefaultWiring(config).build()
```

**Why second:** every constructor you are about to touch in steps 3 and 4 takes a value that used to
come from the environment. Do this after the imports and you rewrite the same call site twice — once
to fix the import, again to supply the argument.

The composition root (`DefaultWiring` above, or whatever the library names it) is the shortcut for a
consumer that uses several services together: one config object in, a struct of wired services out.
Use it before hand-constructing five factories.

## Step 3 — replace the imports, one section at a time

Work the map section by section, not error by error. Within a section, fix every import before moving
on — a half-migrated section is the state in which two names for the same thing are both live.

The general shape of the map, which is worth knowing before you start:

| Old shape | Goes to |
|---|---|
| `<pkg>.commons.<anything>` | a dedicated domain module — one per subject |
| `<pkg>.<feature>_probes.*` (framework) | the core module for that framework |
| `<pkg>.<feature>_probes.<concrete>` | `extensions/` — concrete implementations move out of the core |
| `<pkg>.utils.*` | `extensions/` — the specific extension named in the map |
| `<pkg>.validator.*` | `extensions/` — but a backward-compatible shim usually exists, so this section can wait |

`commons` and `utils` are where every unowned symbol accumulated, which is why they produce the most
rows. Expect the largest section to be the one whose old module had the least specific name.

## Step 4 — adapt to the constructor-based APIs

This is the real work, and the map's before/after pairs are the reference for it. The single change
that dominates: **standalone functions became methods on injected instances.**

Mechanically, per call site:

1. Find the class the function became a method on.
2. Construct it **once**, at the same place you built the wiring config in step 2 — not per call.
3. Pass the values that used to come from the environment into the constructor.
4. Replace the call with the method, keeping the keyword arguments the map lists.

Constructing the instance inside the function that used to call the free function is the trap: it
looks like the smallest diff and it re-creates a client per request.

## Step 5 — run the tests, then remove the shims

In that order, never the reverse.

```
bash scripts/leftover_imports.sh --root . --prefix <old.package>.commons --prefix <old.package>.utils --text
```

Repeat `--prefix` for every old path in the map. Then:

- [ ] `violations` is **0** for every old prefix
- [ ] The consumer's own test suite is green **on the new paths**, not on shim-backed old ones
- [ ] The `degraded` notes were read, and any dynamic import the scanner cannot see was checked by
      hand
- [ ] Only then: drop the old imports that were still working through shims

A shim removed before the tests are green converts a migration into an outage, and the outage lands in
whichever consumer had not migrated yet.

## When it goes wrong

`references/troubleshooting.md` maps the errors you will actually see to their cause and fix. Check it
before assuming the map is wrong — four of the five common errors are the consumer's own step order.
