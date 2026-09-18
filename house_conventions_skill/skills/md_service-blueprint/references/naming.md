# The naming convention

The single most important structural rule in the house style.

## Every AWS resource is named

```
<prefix>_<resource_role>_<company>
```

| Part | Is | Comes from |
|---|---|---|
| `prefix` | `${environment}_${project_name}` | `project_name` is the **repo folder name** (`basename $(pwd)`), resolved at deploy time. Never hardcoded. |
| `resource_role` | the descriptive, specific middle in `snake_case`, including the resource **type word** | you, per resource — e.g. `universal_tenant_admin_cognito_pool`, `registrations_tenants_list`, `_topic`, `_secret`, `_web_acl` |
| `company` | the owning company, **lowercased** | `lower(var.company_name)`, from `COMPANY_NAME` in the deploy script |

## Composition happens in exactly one file

`infra/terraform/naming.tf` — a `locals {}` block with one entry per resource. Every resource `.tf`
references `local.<name>` and **never re-spells the prefix/suffix rule**.

**Consequence of spelling it twice:** changing the convention then means finding every copy of the
expression, and the copy that gets missed is the one that renames a live table on the next apply.

Start from `assets/naming.tf.template`.

## Rules of taste — bad names get called out every time

- **Descriptive and specific.** `<prefix>_users` / `<prefix>_tokens` / `<prefix>_data` are too thin —
  say what the resource holds and who owns it.
- **A "default" that is actually a fallback is named `fallback_*`, not `default_*`.** Calling it a
  default hides the fact that a fallback fired.
- **Name for the people or the purpose, not the mechanism.** `operation_admin_auth_users`, not
  `sigv4_role` or `cognito_login_lambda`: a mechanism in the name has to change when the mechanism does,
  and renaming a live resource means destroying it.
- **No cryptic abbreviations.** The name should read like a sentence fragment.

## The three 64-character namespaces

`prefix` is right for tables, functions, topics and queues. It overflows for names that carry **extra
segments on top of it**, and those namespaces cap at **64**:

| Namespace | Cap | Why it overflows | What it gets |
|---|---|---|---|
| IAM role name | **64** | carries a role-kind suffix **on top of** the function name | its own `var.role_slug` |
| scheduler schedule group | **64** | carries a **tenant** segment, user-supplied and unbounded | its own `var.scheduler_slug` |
| lambda function name | **64** | nothing extra — it fits | the **full** prefix, unshortened |

A lambda function name keeps the full prefix on purpose: a role is an internal identity, but a function
name is what the logs and the console show, and shortening the visible name to fit the invisible one's
cap is the wrong trade.

**The two slug variables may hold the same string today.** That is deliberate headroom — the two caps are
independent, and collapsing them into one variable means shortening one for the other's sake later.

### Assert the lengths at plan time

**IAM answers a too-long name at `terraform apply`, after a clean plan**, halfway through a deploy with
some resources created and some not. So the check has to be mechanical, in two places:

- a terraform `precondition` over the composed names, so a too-long name fails the **plan**;
- a unit test over every deployed environment, reading the role and function words out of `naming.tf`
  itself rather than restating them.

`assets/naming.tf.template` carries the `precondition` shape. Never a comment instead of an assertion:
the margin here is a handful of characters, and a comment does not fail a build.

### Runtime-composed names raise, never truncate

Where code composes a per-tenant name at runtime, overflow **raises** with the offending input named.
Truncating maps two tenants whose names differ only past the cut onto **one shared resource**, destroying
exactly the isolation a per-tenant resource exists to provide.
