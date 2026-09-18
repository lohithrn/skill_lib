# House policy — `H1`–`H12`

The conventions in force across the service fleet: how things are named, how they are reached, how
they are configured, and how they are deployed. Every rule here was paid for by a failure, and the
number beside it is the number that failed.

**Sanitized on purpose.** Company, account and repository identifiers appear as `<company>`,
`<account-id>`, `<ServiceRepo>`. The rules are exact; the identities are not this file's business.
Where a rule says *match the closest existing repo*, read that repo — consistency with the fleet
beats this document where the two differ, and the report should say which one it followed.

Scope: applies to `*.tf`, `infra/`, deploy shell, and any source that composes a resource name, a
route, or a URL. A pure library with no infra in scope skips this group, and the report says so.

---

## H1 — `<prefix>_<resource_role>_<company>`

```
prefix        = "<environment_lower>_<project_slug>"
project_slug  = repo folder name, lowercased, non-alphanumerics -> "_"
company       = lower(var.company_name)
```

Composed in **exactly one file**, `infra/terraform/naming.tf`, as a `locals {}` block with one entry
per resource. Every other `.tf` references `local.<name>` and never re-spells the rule. A resource
name assembled inline in the resource block is the finding, even when the result is correct —
because the *next* one will not be.

**Taste rules, called out every time they are broken:**

- Specific, verbose, `snake_case`, **including the type word**:
  `fallback_trigger_notifications_topic`, `scheduled_triggers_by_last_updated_time`,
  `operation_admin_auth_users`. Never `_users`, `_tokens`, `_data`, `_info`.
- A fallback is named `fallback_*`, **never** `default_*`.
- Name for the **people or the purpose**, not the mechanism. `operation_admin_auth_users` — not
  `sigv4_role`, not `mfa_role`, not `cognito_login_lambda`. A mechanism in the name has to change
  when the mechanism does, and it never does get changed.
- No cryptic abbreviations. The name should read as a sentence fragment.

## H2 — Name-length caps, and the slug escape hatches

| Namespace | Cap | When you find out |
|---|---|---|
| IAM role name | **64** | **`terraform apply`** — after a clean plan |
| IAM policy name | 128 | apply |
| Lambda function name | 64 | apply |
| EventBridge Scheduler schedule group | **64** | apply, or at run time when code creates the group |
| SQS queue name | 80 | apply |
| DynamoDB table / GSI name | 255 | rarely bites |
| SNS topic name | 256 | rarely bites |

The dangerous two are **IAM roles** and **schedule groups**: both answer at *apply* time, not plan
time, so a length problem survives every review and every `plan`, then kills the deploy halfway
through.

One prefix is not enough, because two namespaces carry extra segments on top of it. Each gets **its
own slug variable** rather than a truncation of `prefix`:

| Variable | Applies to | Why it is separate |
|---|---|---|
| `var.role_slug` | IAM role names only | a role name carries a role-kind suffix **on top of** the function name |
| `var.scheduler_slug` | Scheduler schedule groups | the name also carries a **tenant** segment, user-supplied and unbounded |
| (none) | Lambda function names | keep the **full** prefix — a function name is what `ls`, the logs and the console show |

**They may hold the same value today. That is deliberate headroom, not duplication** — the two caps
are independent, and collapsing them means shortening one for the other's sake later. Suggesting they
be merged is an automatic non-suggestion (`specs/suggestion.md` §3).

Measured evidence for why the knobs exist, from the reference service: with the full prefix, **10 of
13** execution roles were over 64, the worst at **78**. `_exec_role` rather than `_execution_role`
was worth four characters — with the short slug the longest role was **60**, and the full word put it
at **65** against a cap of 64.

**Assert at plan time; never trust a comment.** Two places, both expected:

- In terraform, a `precondition` over `values(local.<names>)` so a too-long name fails the *plan*.
- In the unit suite, over every deployed environment, reading the role and function words out of
  `naming.tf` itself rather than restating them — plus a test asserting the problem was **real**
  (`the full slug would not have fit`), so nobody "simplifies" the slug away later, and a test that
  the role list and the function list are the same set.

**A name composed at run time raises, never truncates.** Truncating maps two tenants whose names
differ only past the cut onto **one shared group**, destroying exactly the isolation a
group-per-tenant exists to provide. The error names whose input is the problem. Test the inclusive
boundary: an off-by-one rejects a legitimate name for no reason.

## H3 — Route shape

```
/<project_slug>/stage/{stage}/tenant/{tenant}/<methodname>/<paramName>/{paramValue}/...
```

- **Mandatory parameters in the path, optional parameters in the query string.** Non-negotiable.
- `methodname` is the operation, matching the repo's existing case style.
- The path prefix is composed **once** in terraform (`local.<x>_api_path_prefix`) and never spelled
  in code.
- **The stage is a property of the deployment, not of the request.** A frontend proxy prepends the
  prefix from its own environment; a browser that sends its own `/stage/prod/...` gets it appended
  *after*, resolving to no route. This matters because the stage selects which identity pool
  authorizes the call.
- Handlers verify the `{stage}` segment against their own `ENVIRONMENT`.
- `{tenant}` appears in the **path AND the header**, and the handler compares them.
- Routes are declared as one `local` list of `(path, http_method, function_name)`, and `outputs.tf`
  generates the endpoint list from that same list, so the printed URLs cannot drift.
- HTTP is the primary interface. An MCP endpoint is **one more route on the same API** reached
  through the same gate, translating tool calls into gateway events so both transports run the
  *same* handler. An MCP tool is never a second implementation.
- No CORS, no `OPTIONS` route, where the browser talks to a frontend lambda that proxies: there is no
  preflight to answer, and an `OPTIONS` method with `authorization = NONE` is an unauthenticated
  route for nothing. One `lambda_permission` **per (method, path)**, so a function reachable by
  `POST /x` cannot be invoked through any other route.

## H4 — Outbound URLs live in `urls.{env}.yaml`, never in per-URL env vars

1. Author `configuration/urls.beta.yaml` and `configuration/urls.prod.yaml`: key → URL template with
   `{stage}` / `{tenant}` / `{id}` placeholders.
2. The deploy copies the env-appropriate file to `src/deployed_utilities_references/urls.yaml` and
   packages it in the zip.
3. Code calls `get_url("SOME_KEY")`, which **fails loudly** on a missing key.
4. `ENVIRONMENT` stays a terraform-wired env var and **must not default** — a missing `ENVIRONMENT`
   fails loudly rather than letting a prod lambda silently build beta URLs.

Everything else the lambda needs — table names, pool ids, ARNs, prefixes — is composed in `main.tf`
from the terraform resources themselves. **Never hand-typed.** A default on `ENVIRONMENT` is a
`blocker`: the failure it causes is a prod service quietly writing to beta.

## H5 — Nothing hardcoded; derive from the folder, in three tiers

The service name **is the repo folder name**, resolved once by the deploy:
`PROJECT_NAME="$(basename "$(pwd)")"`. Standing rule: *no derived name is ever hardcoded in regular
code, and test code should avoid it too.* Move the repo and everything adopts.

| Tier | Can it see the folder? | Mechanism |
|---|---|---|
| `src/` | **No** — a lambda runs from `/var/task` | **injected** by terraform as `PROJECT_NAME`, exactly like `ENVIRONMENT`; one reader that **raises** when absent |
| `test/` | yes | a naming helper that **parses terraform's own defaults** out of `variables.tf` and the deploy script rather than restating them |
| `local_development/` | yes | derives from the folder directly, reads slug defaults out of `variables.tf` |

**The one legitimate exception:** a test asserting that code *reads* a name from the environment must
pass deliberately **foreign** values (`prod_othersvc` / `othercorp`). Derived values would also pass
for a function that ignored the environment and rebuilt the name from its own constants. Such
literals carry a "these are on purpose, do not fix" comment, and flagging them is a non-suggestion.

Account ids live in exactly one file, `infra/aws_account_config.sh`. A second one anywhere is a
`blocker`.

## H6 — One authorization gate, OR'd credentials

- Every handler's **first statement** is the one authorization call, which calls exactly **one**
  function. **Commenting out that one function's body removes authorization from the whole
  application.** Nothing else raises a 401; no handler has a second condition of its own. A handler
  with its own extra auth branch is a `blocker` — it means the gate is no longer the gate.
- Two credentials, an **OR**, selected by the `Authorization` scheme so the two never contend and one
  refusal is never re-reported as the other's:
  - a bearer token (or Basic for m2m) scoped to one tenant, requiring the tenant and region headers;
  - **SigV4** over a signed identity call, permitted to act as any tenant — the company-administrator
    path, for someone fixing a customer's data with no tenant password. **The service never
    recalculates a signature; the cloud provider authenticates and we ask who signed.**
- The IAM role's **trust policy is the access list.** Adding a person is a tfvars entry, not code.
- *How* each credential is proven lives one-folder-per-strategy behind one interface, so a third way
  in is a new folder plus one table entry — the "exactly one gate" property survives.

**Global ban, above every rule here: never machine-generated certificates or keypairs as an
authorization mechanism.** No `openssl`/keytool minting in a deploy, connect or client flow; no such
material committed as an auth substitute. The only acceptable TLS is a CA-issued or
provider-managed certificate we did not generate, verified against the system trust store. Finding
one is a `blocker` regardless of what else the change does.

## H7 — Data conventions

- **Epoch milliseconds everywhere in the backend. Never ISO strings.** Including
  `last_updated_time`, which is mandatory on every row. The one argued exception: a map keyed by
  **local calendar day**, because keying by instant would orphan every override the moment the
  series' time-of-day changed. Values inside are still epoch ms.
- **DynamoDB: single-table, `getItem`/`putItem` first.** Partition key = tenant, range key = the
  entity's unique name. Names carry no spaces and must be unique; **create and delete are the only
  operations that decide which entities exist** — an update is a `PUT`, never a rename.
- **The `Decimal` boundary is explicit and converted once, at the boundary.** Reads come back as
  `decimal.Decimal`; `json.dumps` refuses it and comparison against a `float` is quietly wrong, and
  both failures surface far from the read. So: a plain-numbers pass on the way out of every read, a
  decimal-friendly pass on the way in, plus an encoder backstop at serialization time — so a
  delivery or a response is never where a type problem is discovered. A `Decimal` conversion done
  ad hoc at a call site is a `major`.
- **Every runtime-created per-tenant resource ships with a delete path**, and the destructive call
  lives in its own file whose whole subject is that danger.

## H8 — Compute: lambdas, and nothing else

Lambda only. **Never Lightsail, Docker, EC2 or Fargate** unless explicitly asked. A web frontend is
**one lambda** running a real HTTP server behind the Lambda Web Adapter **as a layer**, with the layer
version **pinned** — floating it changes the wrapper every request passes through on a re-apply. Set
the adapter's readiness path to a **real health path**, never the default `/`: `/` is the SPA
fallback and answers 200 with `index.html` even when the bundle is broken, reporting a broken deploy
as ready.

Cheapest thing that meets the need. Any RDS/Aurora/NAT/always-on compute is flagged with a cost
estimate and needs an explicit yes before it goes in.

## H9 — Code size limits (standing, all repos)

Every file **< 250 lines** · every method **< 25 lines** · nesting **≤ 2 levels** · verbose,
descriptive variable and class names in both `src/` and terraform. **There is a test enforcing the
file cap, not just a habit** — its absence is itself a `minor` under `G8`.

Where this and `G1` disagree — nesting 2 here, 1 there — apply the precedence rule in `SKILL.md`
§Precedence: depth 3+ is a `major` under both, depth 2 is a `minor` naming both numbers.

These thresholds are mandatory standards, not defaults. Apply every relevant rule as written. Do not
silently weaken a threshold, substitute a personal preference, or skip a rule because the existing
codebase already violates it. **Clearly identify any justified exception rather than inventing one** —
an exception carries the rule id, the `file:line`, the measured number, and why the alternative would
cost more clarity than it buys.

**Consequence without this:** an unstated exception is indistinguishable from an unnoticed violation,
so the next reviewer re-finds it and the one after that "fixes" it. A policy with negotiable numbers
is a style guide.

## H10 — Terraform comment discipline

Comments carry the **reasoning**: why a knob exists, what breaks without it, what was tried and
rejected. But **in any `.tf` file the comment lines must never outnumber the code lines.** Summarize
rather than delete — the reasoning is the valuable part, the length is not.

## H11 — Deploy gates: the deploy can never lie

`set -e` and `set -o pipefail`, then, in order:

1. Resolve `PROFILE` / `ENVIRONMENT` / `REGION` / `COMPANY_NAME` — every one a `:-` fallback with a
   working default, so a deploy is **one command** with no environment to set up first.
2. `PROJECT_NAME=$(basename $(pwd))`.
3. Source a gitignored `local_$(basename $(pwd)).env` **before** the defaults, so local overrides win
   and CI can supply the same variables directly. Never credentials in it.
4. **Log in inside the script** (SSO / assume-role). Never tell the user to run a login command
   first.
5. **Assert the resolved account matches the environment** — after login, **before any mutation**,
   hard-fail on mismatch, reading the one account config file.
6. **Run the full unit suite BEFORE building the zip.**
7. `create_tfvars` → derived `project_name`, `project_slug`, `environment`, `prefix`, `company_name`,
   region, profile. Everything derived; nothing hardcoded.
8. `terraform init` with a derived backend key `${PROJECT_NAME}/${environment}/terraform.tfstate`,
   then `plan`, then `apply`.
9. **Propagate `apply`'s exit code as the script's exit code.** A failed apply can never print
   success. This is a `blocker` when broken: the deploy reports green on a failure.
10. **Print the real resolved public URL** from outputs. Never a placeholder, never `xxxx`.

Two modes are worth having, sharing one body so PROD cannot drift from BETA (PROD is used least, so
PROD is what drifts): a **full deploy**, and a **code-only deploy** that pushes zips to functions
terraform already created and **refuses to run if they do not exist** — it can neither create, delete
nor re-wire anything.

The lock file stays gitignored. Decided; not a finding.

## H12 — Working rules (these come before any code)

1. **Never break existing users.** New features are additive. Call out **every** removed line that
   was not explicitly requested. A bug fix is not a revert; a refactor is not a rewrite.
2. **Surgical over sweeping.** Smallest change that solves it. No drive-by reformatting or renaming
   in the same change. Related changes go in clearly named files, not scattered.
3. **Confirm, don't hallucinate.** "X is the problem" requires having run, read or checked it. If
   unverified, the sentence says so.
4. **Nothing hardcoded.** Folder → service name; prefix → resource names; one file → account ids;
   `urls.yaml` → outbound URLs; secrets manager or env → secrets.
5. **Scripts are self-contained.** One command does login, build, test, deploy. Never "run this
   first".
6. **A deploy never lies** (`H11`).
7. **Cost-conscious by default.**
8. **Answer the question asked.** A yes/no or a number leads in one line.
9. **Judge against the system, not the snapshot.** A name or knob holding the loosest value, or the
   same value in every branch, is **deliberate headroom** — a feature. "You collapsed X into one
   value" is not a finding. A real finding breaks the system as designed or forecloses a path being
   kept open. When unsure whether something is intentional, **ask**.

Rules 1, 2 and 9 are the ones a review breaks most often. A suggestion that deletes a code path
nobody asked about violates rule 1 *in the review itself*, and is dropped.
