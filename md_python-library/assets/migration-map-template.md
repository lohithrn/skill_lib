# Migration map — `<LibraryName>`

> Copy this file into the library's own `documentation/` tree, fill it in, and delete the guidance
> lines marked `>`. The section order below is the order a consumer reads it in.

Use this document to understand how old import paths map to new ones after the refactoring. **Every**
import from the old structure has an entry here — a new path, a method, an instruction, or a removal
with a reason.

> Procedure first. Paste or link the five ordered steps here, before the tables. A map applied top to
> bottom breaks the app in the middle.

## Behavioural changes

> State these once. Do not repeat them per row.

1. **No environment variables.** Every value that was `os.getenv(...)` is a constructor parameter now;
   your entry point resolves the environment and passes values in.
2. **No free-form dicts in public APIs.** Inputs and outputs are frozen dataclasses.
3. **Constructor injection.** Nothing creates its own dependencies.
4. **Null-object implementations** ship in `<package>.noop` for testing.
5. **Backward-compatible shims** exist where noted, and are temporary.

## Extras

| Feature | Extra | Without it |
|---|---|---|
| Object storage, key-value config | `[aws]` | `ModuleNotFoundError` for the AWS SDK |
| `<domain>` clients and token generation | `[<domain>]` | `ModuleNotFoundError` for the `<domain>` client |
| Everything | `[all]` | — |
| Everything plus test/lint tooling | `[dev]` | — |

```bash
pip install "<LibraryName>[aws]"
```

---

## `<new.module.credentials>`

| Old Import | New Import |
|---|---|
| `from <pkg>.commons.credentials_lookup_utils import CredentialLookup` | `from <pkg>.credentials import DictionaryCredentialStore` |
| `from <pkg>.commons.credentials_lookup_utils import lookupCredentialsFromCache` | `from <pkg>.credentials import CredentialCache` |
| `from <pkg>.commons.check_credentials_utils import ...` | `from <pkg>.credentials import CredentialValidator` |

## `<new.module.clients>`

| Old Import | New Import |
|---|---|
| `from <pkg>.commons.client_fallback_utilities import get_<service>_client` | `from <pkg>.clients import ClientFactory` |
| `from <pkg>.commons.client_fallback_utilities import resolve_auth_hierarchy` | `from <pkg>.clients.auth_policy import PolicyFactory` |
| `from <pkg>.commons.auth_hierarchy_policy.base_policy import BaseAuthHierarchyPolicy` | `from <pkg>.clients.auth_policy import AuthPolicy` |
| `from <pkg>.commons.auth_hierarchy_policy.validation import get_region` | `from <pkg>.clients.auth_policy import validate_region_format` |

## `<new.module.config>`

| Old Import | New Import |
|---|---|
| `from <pkg>.commons.private_config.private_config import PrivateConfigReader` | `from <pkg>.config import KeyValueConfigReader` |
| `from <pkg>.commons.private_config.private_config import getPrivateConfigReader` | Construct `KeyValueConfigReader` directly |
| `from <pkg>.commons.private_config.private_config import getPrivateConfigReaderWithGroupPrefixAndProfile` | `KeyValueConfigReader(table_name, resource, tenant, group)` |

## `<new.module.validation>`

| Old Import | New Import |
|---|---|
| `from <pkg>.validator.schema_validator_util import validate_document_by_category` | `from <pkg>.extensions.payload_validation import validate_document_by_category` |
| `from <pkg>.validator.extractor import extractSessionInfo` | `from <pkg>.extensions.payload_validation import extractSessionInfo` |

> **Note:** the old `<pkg>.validator.*` paths still work via backward-compatible shims. They re-export
> from the new locations. Migrate at your own pace — the shims are temporary.

## `<new.module.testing>`

| Old Import | New Import |
|---|---|
| N/A (hand-written mocks) | `from <pkg>.noop import NoOpCredentialStore` |
| N/A (hand-written mocks) | `from <pkg>.noop import NoOpConfigReader` |

## Completely removed — no replacement

| Old Module | Reason |
|---|---|
| `commons.environment_guard` | Environment-variable checking is banned — the library no longer reads the environment |
| `commons.<provider>_utils` | Provider-specific — implement the `<Name>Provider` protocol instead |
| `commons.constants` (god-file) | Split into per-domain models, one per folder |
| `commons.utils` (god-file) | Split into typed models; the app-specific helpers moved to the app |
| `commons.thread_safe_dictionary` | Use the standard library's threading primitives |
| the dotenv dependency | Removed from core usage — no environment variables |

---

## Before → after

> One pair per calling-pattern change. Six to eight pairs is a large refactor; twenty means you are
> documenting the library instead of the migration.

### A free function became a method on an injected instance

```python
# BEFORE — standalone function, resolved its own configuration from the environment
from <pkg>.commons.client_fallback_utilities import get_<service>_client

client = get_<service>_client(credentials_dict)

# AFTER — a factory constructed once with explicit configuration and credentials
from <pkg>.clients import ClientFactory
from <pkg>.credentials.models import ClientConfig, CredentialsInput

factory = ClientFactory(
    config=ClientConfig(connect_timeout_seconds=5, read_timeout_seconds=10),
    credentials=CredentialsInput(
        access_key_id="<access-key-id>",
        secret_key="<secret-key>",
        region="us-west-2",
    ),
)

client = factory.create_client("<service>")
resource = factory.create_resource("<service>")
```

### A factory function became explicit construction

```python
# BEFORE — factory read the table name and tenant from the environment
from <pkg>.commons.private_config.private_config import getPrivateConfigReader

reader = getPrivateConfigReader()
config = reader.get_configuration("<SETTINGS_KEY>")

# AFTER — construct with the injected resource and explicit identity
from <pkg>.config import KeyValueConfigReader

reader = KeyValueConfigReader(
    table_name="<config-table>",
    resource=resource,
    tenant_name="<tenant>",
    default_group_name="<DEFAULT_GROUP>",
)
item = reader.get_configuration("<SETTINGS_KEY>")   # item.values is a dict[str, str]
```

### An ordering helper became a registered chain

```python
# BEFORE — free function that read remote config and resolved providers from the environment
from <pkg>.commons.services_sorted_setup import setup_sorted_fallback_with_remote_config

plugins = setup_sorted_fallback_with_remote_config(config_dict, identity)

# AFTER — register providers, then resolve in order
from <pkg>.resolution import OrderedFallbackChain, OrderedFallbackConfig

chain = OrderedFallbackChain(
    config=OrderedFallbackConfig(
        user_priority_order=["provider-a", "provider-b"],            # from your config or payload
        default_order=["provider-a", "provider-b", "provider-c"],
    )
)
chain.register_provider("provider-a", my_provider_a)
chain.register_provider("provider-b", my_provider_b)

ordered = chain.resolve_ordered_providers()
```

### A provider integration became a protocol you implement

```python
# BEFORE — the library owned the provider
from <pkg>.commons.<feature>_fallback_policy.resolver import resolve_<feature>
from <pkg>.commons.<feature>_fallback_policy.types import <Feature>Context

result = await resolve_<feature>(<Feature>Context(provider="<provider>", ...))

# AFTER — implement the protocol, inject it into the resolver
from <pkg>.<feature> import <Feature>FallbackResolver, <Feature>ResolutionInput

class MyProvider:
    def can_activate(self, context: <Feature>ResolutionInput) -> bool:
        return context.provider_name == "<provider>"

    async def create_and_start(self, context: <Feature>ResolutionInput):
        ...

resolver = <Feature>FallbackResolver(providers=[MyProvider()])
result = await resolver.resolve(<Feature>ResolutionInput(provider_name="<provider>", ...))
```

### The composition root, for a consumer using several services

```python
import os
from <pkg>.wiring import WiringConfig, DefaultWiring

config = WiringConfig(
    service_url=os.environ["<SERVICE_URL_VAR>"],
    api_key=os.environ["<API_KEY_VAR>"],
    api_secret=os.environ["<API_SECRET_VAR>"],
    storage_bucket=os.environ.get("<BUCKET_VAR>"),
)

services = DefaultWiring(config).build()
# services.token_generator, services.cleanup_coordinator, services.<name> — see the struct's fields
```

---

## Troubleshooting

> Fill in with this refactor's real errors. The generic five are in the skill's
> `references/troubleshooting.md`.

| Error | Cause | Fix |
|---|---|---|
| | | |
