# What a fleet looks like, and which repo to copy

Sanitized: the repos are private, so each row names the **role** a repo plays rather than the repo. Use
this to decide which existing repo to copy — and to know what a given repo does *not* yet demonstrate
before treating it as the reference. Every count below was measured by listing the repos, not
remembered.

## The canonical roles

### The reference service — `<org>/<ServiceName>`

**The most complete implementation, and the one to copy for anything new.** Multi-tenant scheduled work
on DynamoDB plus a scheduler, all lambdas, with a Lambda-Web-Adapter frontend. Uniquely demonstrates:

- `infra/terraform/naming.tf` — the only place names are composed
- `infra/aws_account_config.sh` — account-per-environment plus `assert_aws_account`
- `infra/deploy_entrypoint.sh` — one body behind four `z_` scripts, full-deploy and code-only modes
- the derive-from-folder rule across all three tiers (`src/commons/environment.py`,
  `test/terraform_naming.py`, `local_development/local_aws_configuration.py`)
- single-gate authorization with OR'd credentials (`src/commons/request_authorization.py`,
  `src/request_identity/`)
- the hardened `api_gateway` module — per-(path, method) config, no CORS, per-route lambda permission
- `src/commons/dynamo_json.py` — the explicit `Decimal` boundary
- the `role_slug` / `scheduler_slug` 64-character escape hatches
- a moto-backed `local_development/` harness that serves the **deployed** modules
- a stateless `/mcp` route alongside the HTTP routes
- recurrence as **projection, not materialisation**

### The original `api_gateway` module — `<org>/<ServiceName>`

The first generation of the module: OpenAPI `body` plus `data` sources plus
`put_rest_api_mode = "overwrite"` plus `prevent_destroy`, and the usage plan with quota and throttle.
Also the plain `infra/deploy_utils.sh` shape — init vars from `basename $(pwd)`, backend bucket
create-if-absent, `package_lambda`, init/plan/apply.

Does **not** have: `naming.tf`, `aws_account_config.sh`, `urls.yaml`, exit-code propagation. Its
`plan_terraform` passes `prefix=${PROJECT_NAME}-${environment}` — hyphenated and reversed, the older
convention. **Do not copy that part.**

### The lean service — `<org>/<ServiceName>`

The minimal layout: `src/lambda_api_handlers/` plus `src/utils/` plus `src/templates/`, one terraform
file per resource, `lambdas/` and `api_gateway/` modules. A good shape for a small service. No
`naming.tf`, no `urls.yaml`.

### The outbound-URL convention — two repos, `<org>/<ServiceName>`

`configuration/urls.{beta,prod}.yaml` plus `src/deployed_utilities_references/get_url_utility.py`. Read
one of these yaml files to see the route shape as **consumed** across the fleet — it is the best single
view of how services address each other. The second copy is the cross-check when the two disagree.

Note: the yaml holds per-service hostnames per environment. That is the current reality; the templating
is only over `{stage}`, `{tenant}` and entity ids.

### The UI theme — `<org>/<ServiceName>`

`frontend/app/globals.css` and nothing else. This repo is Docker/compose-based; do **not** copy its
infra shape into a lambda service.

## Everything else, by role

| Role a repo plays | Has | Read it for |
|---|---|---|
| the shared auth library | `z_build_and_publish_{beta,prod}.sh` | **the multi-tenant auth wheel every service's auth gate depends on** |
| the SSO / SAML end | infra, api_gateway, `saml_metadata/`, a local-env script | how the identity side is wired |
| per-environment dependency sets | infra, api_gateway, split `requirements_{beta,prod}.txt` | when beta and prod need different pins |
| the functional-test pattern | infra, api_gateway, postman, `z_setup_run_functional_tests.sh` | a suite that sets its own complete `PYTHONPATH` |
| API contracts | infra, frontend, `contracts/`, `spec/` | a `contracts/` directory worth copying for API contracts |
| frontend-only shapes | Vite/React plus infra | what a frontend repo carries and what it does not |
| the local override convention | `local_<ServiceName>.env` | where the gitignored per-repo override file came from |
| a service that vendors another | infra, api_gateway, `api_specifications/` | the shape of a second service in-tree |

Rows that carried nothing after sanitizing — the several repos whose only note was "standard shape" —
were deleted rather than shipped as placeholders.

## Convention spread (measured)

| Convention | Repos |
|---|---|
| `infra/deploy_utils.sh` | **10** |
| `infra/terraform/api_gateway/` module | **8** |
| `configuration/urls.{env}.yaml` | **2** |
| `infra/terraform/naming.tf` | **1** |
| `infra/aws_account_config.sh` | **1** |

**Read this as direction, not majority.** `naming.tf` and `aws_account_config.sh` are where the fleet is
going, and new repos get them. Do **not** retrofit an older repo unless asked — that is a sweeping change
to a working service, which working rule 2 forbids.

## Shared facts

- Company suffix: `<company>`, lowercased in every name.
- **Beta and prod resolve to the same AWS account today.** That is deliberate headroom: the
  per-environment lookup in `aws_account_config.sh` already exists, so splitting prod out later is a
  one-line change and not a re-plumbing. The account id itself lives in that one file and nowhere else.
- Regions: beta `us-west-2`; prod `us-west-1` in the repos that split. Expressed as
  `DEFAULT_DEPLOY_REGION` before sourcing the shared entrypoint, with `AWS_REGION` winning over both.
- Terraform state: one shared bucket, key `${PROJECT_NAME}/${environment}/terraform.tfstate`.
- `.terraform.lock.hcl` is **gitignored**. Decided; do not re-raise.
