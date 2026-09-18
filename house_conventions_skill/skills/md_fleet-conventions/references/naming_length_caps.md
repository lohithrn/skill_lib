# AWS name-length caps and the slug escape hatches

Carried from the fleet's own measurements. The numbers here are the point of the file — do not round
them, and do not "simplify" the slug variables away.

## The caps that actually bite

| Namespace | Cap | When you find out |
|---|---|---|
| IAM role name | **64** | **`terraform apply`** — after a clean plan |
| IAM policy name | 128 | apply |
| Lambda function name | 64 | apply |
| EventBridge Scheduler schedule group | **64** | apply, or at runtime when the group is created by code |
| DynamoDB table / GSI name | 255 | rarely a problem |
| SNS topic name | 256 | rarely a problem |
| SQS queue name | 80 | apply |

The dangerous ones are IAM roles and schedule groups. **Both answer at apply time, not plan time**,
so a length problem survives every review and every `terraform plan` and then kills the deploy
halfway through — with some resources created and some not.

## Why one prefix is not enough

`prefix = "<environment>_<project_slug>"` is right for tables, functions, topics and queues. It
overflows for two namespaces because they carry *extra* segments on top of it:

- **IAM roles** carry a role-kind suffix *on top of* the function name they are derived from.
  Measured in the reference service: with the full prefix, **10 of 13** execution roles were over
  64, the worst at **78**, and the scheduler-invoke role at 67. Only **3** fit.
- **Schedule groups** carry a **tenant name** in the middle, which is user-supplied and unbounded.

So each gets its own variable:

```hcl
variable "scheduler_slug" {
  description = "Short slug used only for EventBridge Scheduler schedule-group names, which are capped at 64 characters and also carry a tenant segment."
  type        = string
  default     = "<short_project_slug>"
}

variable "role_slug" {
  description = "Short slug used only for IAM role names, which are capped at 64 characters and carry a role-kind suffix on top of the function name. Its own knob rather than a reuse of scheduler_slug: the two caps are independent, and shortening one for the other's sake is how a name gets cut in half."
  type        = string
  default     = "<short_project_slug>"
}
```

**They may hold the same value today.** That is deliberate headroom, not duplication — the two caps
are independent, and collapsing them means shortening one for the other's sake later.

```hcl
locals {
  prefix           = "${local.environment_lower}_${var.project_slug}"
  scheduler_prefix = "${local.environment_lower}_${var.scheduler_slug}"
  role_prefix      = "${local.environment_lower}_${var.role_slug}"
}
```

## What does NOT get shortened

**Lambda function names keep the full prefix.** A role is an internal identity; a function name is
what a listing, the logs and the console show. Shortening the visible name to fit the invisible one's
cap is the wrong trade. (Longest measured: **63** — it fits.)

## `_exec_role`, not `_execution_role`

Four characters, and they were needed: with `role_prefix` the longest execution role is **60**, and
the full word would put it at **65** against a cap of **64**. Keyed by the same word the function name
carries, so a role and its function are one entry read twice:

```hcl
lambda_execution_role_names = {
  for role_word in [
    "create_scheduled_trigger",
    # ... one per function
  ] : role_word => "${local.role_prefix}_${role_word}_${local.company_lower}_exec_role"
}
```

## Assert at plan time — do not trust a comment

The margin is thin on purpose, so the check has to be mechanical. Two places to do it:

**In terraform,** so a too-long name fails the plan:

```hcl
resource "null_resource" "assert_role_name_lengths" {
  lifecycle {
    precondition {
      condition     = alltrue([for n in values(local.lambda_execution_role_names) : length(n) <= 64])
      error_message = "An IAM role name exceeds 64 characters. Shorten var.role_slug."
    }
  }
}
```

**In the unit suite,** over every deployed environment, reading the role and function words out of
`naming.tf` itself rather than restating them:

```python
IAM_ROLE_NAME_MAXIMUM = 64
IAM_POLICY_NAME_MAXIMUM = 128
LAMBDA_FUNCTION_NAME_MAXIMUM = 64
DEPLOYED_ENVIRONMENTS = ("beta", "prod")
```

Worth also asserting **that the problem was real**, so nobody "simplifies" the slug away later:

```python
def test_the_full_project_slug_would_not_have_fit(self):
    longest = max(
        len(f"{prefix()}_{role_word}_{company()}_execution_role")
        for role_word in role_words()
    )
    self.assertGreater(longest, IAM_ROLE_NAME_MAXIMUM)
```

And that the role list and the function list are the same set:

```python
def test_naming_tf_lists_a_role_for_every_function(self):
    self.assertEqual(set(role_words()), set(lambda_function_words()))
```

## Runtime-composed names: raise, never truncate

Where code composes a name at runtime (a schedule group per tenant), overflow must **raise**:

```python
if len(group_name) > MAXIMUM_SCHEDULER_NAME_LENGTH:
    raise ValueError(f"tenant '{tenant_name}' needs a shorter name: ... {MAXIMUM_SCHEDULER_NAME_LENGTH}")
```

Truncating would map two tenants whose names differ only past the cut onto **one shared group** —
destroying exactly the isolation a group-per-tenant exists to provide. The error names whose input is
the problem, so it is actionable. Test the inclusive boundary too: an off-by-one rejects a legitimate
tenant name for no reason.
