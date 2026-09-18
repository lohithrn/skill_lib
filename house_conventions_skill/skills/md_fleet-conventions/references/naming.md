# Naming: `<prefix>_<resource_role>_<company>`

Every AWS resource in the fleet carries the same three-part name.

```
<prefix>_<resource_role>_<company>

prefix        = "<environment_lower>_<project_slug>"
project_slug  = repo folder name, lowercased, non-alphanumerics -> "_"
resource_role = the descriptive middle, snake_case, includes the type word
company       = lower(var.company_name)
```

Composed in **exactly one file**, `infra/terraform/naming.tf`, as a `locals {}` block with one entry
per resource. Every other `.tf` references `local.<name>` and never re-spells the rule.

```hcl
locals {
  # AWS resource names are case-sensitive; the convention requires the company
  # suffix lowercased regardless of how COMPANY_NAME is spelled.
  company_suffix = lower(var.company_name)

  scheduled_triggers_table_name = "${var.prefix}_scheduled_triggers_${local.company_suffix}"
  fallback_trigger_notifications_topic_name = "${var.prefix}_fallback_trigger_notifications_topic_${local.company_suffix}"
}
```

**Consequence of skipping the single file:** changing the convention then means finding every copy of
the prefix/suffix expression, and the one that gets missed is the one that renames a live table.

## Taste rules — these get called out every time they are broken

- **Specific, verbose, snake_case, and it includes the type word.**
  `fallback_trigger_notifications_topic`, `scheduled_triggers_by_last_updated_time`,
  `operation_admin_auth_users`. A name should read as a sentence fragment.
- **A fallback is `fallback_*`, never `default_*`.** A "default" that is actually the thing used when
  the real one is missing is a fallback, and calling it a default hides that a fallback fired.
- **Name for the people or the purpose, not the mechanism.** `operation_admin_auth_users` — not
  `sigv4_role`, not `mfa_role`, not `cognito_login_lambda`. A mechanism in the name has to change
  when the mechanism does, which means a rename of a live resource, which means a destroy.
- **No cryptic abbreviations.** The one exception is a length cap, and then only through the slug
  variables in `naming_length_caps.md` — never by hand-shortening one resource.

## Banned name shapes

| Shape | Why it is refused |
|---|---|
| `<prefix>_users`, `<prefix>_tokens`, `<prefix>_data` | too thin; say what it holds and who owns it |
| `default_*` for something that is a fallback | hides that a fallback fired |
| a mechanism word (`sigv4`, `mfa`, `cognito`, `jwt`) in a resource name | forces a rename when the mechanism changes |
| an abbreviation nobody outside the repo would expand | the console and the logs are read by people who did not write it |
| a hand-truncated name to fit a cap | the cap belongs to a slug variable, asserted at plan time |
| a name spelled inline in a resource `.tf` instead of read from `local.` | the convention now lives in two places |

## Derive from the folder — three tiers

The service name **is the repo folder name**, resolved once by the deploy:
`PROJECT_NAME="$(basename "$(pwd)")"`. Standing rule: *no derived name is ever hardcoded in regular
code, and test code should avoid it too.* Move the repo and everything adopts.

The three tiers differ because they can see different things:

| Tier | Can it see the folder? | Mechanism |
|---|---|---|
| `src/` | **No** — a lambda runs from `/var/task` | **Injected** by terraform as `PROJECT_NAME`, exactly like `ENVIRONMENT`. One reader (`commons.environment.service_name()`) which **raises** when absent |
| `test/` | Yes | A `terraform_naming.py` helper that **parses terraform's own defaults** out of `variables.tf` and the deploy script, rather than restating them |
| `local_development/` | Yes | Derives from the folder directly, reads slug defaults out of `variables.tf` |

**Why the reader raises instead of defaulting:** a default for `PROJECT_NAME` is a prod lambda that
silently composes beta resource names, and the failure surfaces as a missing table, far from the
cause.

**The one legitimate exception.** A test asserting that code *reads* a name from the environment must
pass deliberately **foreign** values (`prod_someslug` / `othercorp`). Derived values would also pass
for a function that ignored the environment and rebuilt the name from its own constants — the test
would prove nothing. Leave a "these literals are on purpose, do not fix" comment next to them, or the
next reader will helpfully replace them with the derived ones.

## Where the length caps take over

Three namespaces cap at 64 and carry extra segments on top of `prefix`, so they get their own slug
variables rather than a truncation of the name. Do not shorten anything by hand:
`naming_length_caps.md` has the cap table, the measured overflow evidence, and the plan-time
assertion that keeps the margin honest.
