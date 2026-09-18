# The four repo types, their tokens, and the conventions they encode

Reference for `md_create-git-template`. Paths are relative to the skill directory; every template file is
stored with a trailing `.tmpl` that the engine strips on copy, so the names below are what the scaffolded
repo receives.

## What each type ships

| Type | Files | Deploy target | Shape |
|---|---|---|---|
| `frontend` | **17** | S3 + CloudFront + Route53 | `infra/terraform/{main,s3,cloudfront,route53,outputs,variables}.tf`, `infra/{provider_login,utils,terraform_utils,setup_dependency}.sh`, `z_deploy_beta_from_local.sh`, `z_run_locally.sh`, the two `z_setup_s3_create_deploy_*.sh`, a pipeline, `README.md`, `TOKENS.md` |
| `frontend_lib` | **11** | S3 tarball publish | `package.json`, `infra/{provider_login,utils,z_clean,z_run_local_tests}.sh`, `z_build_and_publish_{beta,prod}.sh`, `z_deploy_beta_from_local.sh`, a pipeline, `README.md`, `TOKENS.md` |
| `backend_service` | **21** | Terraform-managed compute, container image | `infra/terraform/{main,naming,outputs,variables}.tf` plus `infra/terraform/lambdas/`, `infra/{aws_account_config,deploy_utils,provider_login}.sh`, `Dockerfile`, `requirements_{beta,prod}.txt`, the `z_setup_deploy_*` and functional-test scripts, a pipeline, `.gitignore`, `README.md`, `TOKENS.md` |
| `backend_lib` | **12** | S3 wheel publish | `setup.py`, `project_constants.sh`, `infra/{provider_login,utils,z_clean,z_run_local_tests}.sh`, `z_build_and_publish_{beta,prod}.sh`, `z_deploy_beta_from_local.sh`, a pipeline, `README.md`, `TOKENS.md` |

**61** files in total. `TOKENS.md` is template metadata and is the one file **not** copied into the
scaffolded repo — read it during the interview, then leave it behind.

## The shared tokens

The same token name means the same thing in all four templates. Read the chosen type's own `TOKENS.md`
for the authoritative list; this is the summary.

| Token | Meaning | Default |
|---|---|---|
| `__PROJECT_NAME__` | logical repo/project name; also the throwaway CLI profile name | the repo name |
| `__TENANT_NAME__` | branding and labels only — names nothing persisted | `acme` |
| `__TENANT_NAME_UPPER__` | uppercase form, used only where a literal identifier is required (the CI variable group name and the secret env-var prefix) | derived |
| `__DEPLOYMENT_TENANT_PROFILE__` | the persisted-resource identity | **none** |
| `__AWS_ACCOUNT_ID__` | the 12-digit account the repo deploys into | the verified account |
| `__SSO_START_URL__` | IAM Identity Center start URL for local deploys | **none** |
| `__SSO_REGION__` | region of the Identity Center portal | `us-east-1` |
| `__DEPLOY_REGION_BETA__` | region beta deploys into | `us-west-2` |
| `__DEPLOY_REGION_PROD__` | region prod deploys into | `us-west-1` |
| `__GITHUB_ORG__` / `__GITHUB_REPO__` | repository metadata | parsed from the remote |

Per-type tokens, asked for only when that template uses them:

| Token | Types | Meaning |
|---|---|---|
| `__DOMAIN_NAME__` | `frontend` | apex domain; the subdomains are derived in-shell |
| `__CERTIFICATE_ARN_BETA__` / `__CERTIFICATE_ARN_PROD__` | `frontend` | ACM certificate ARNs in **us-east-1**, because CloudFront reads them there |
| `__PACKAGE_NAME__` | `frontend_lib`, `backend_lib` | the published package or import name |
| `__PACKAGE_S3_BUCKET_BETA__` / `__PACKAGE_S3_BUCKET_PROD__` | `frontend_lib`, `backend_lib` | the publish buckets — persisted, owned by `deployment_tenant_profile` |
| `__ECR_REPO_NAME__` | `backend_service` | container image repository name |
| `__BACKEND_DEPLOY_ROLE_NAME__` | `backend_service` | the role CI assumes to deploy. The convention-based default is `<project>-<component>-beta-deploy-role`, which is exactly what the `md_upsert-aws-deployment-role` skill creates |

Substitution is **longest token first**, so `__TENANT_NAME_UPPER__` is never corrupted by
`__TENANT_NAME__` having been replaced inside it. Reversing that order produces a value like
`acme_UPPER__`, which is a valid-looking string and therefore the worst kind of wrong.

## Deliberately not tokenised

- **The shared CI deployment image** in the pipeline (`DOCKER_IMAGE`) — it is the build agent container,
  the same for every repo, not a per-repo knob.
- **The Dockerfile base image** (`python:3.12-slim`) — a standard public base; change it only when the
  service needs a different runtime.

Leaving these literal is the point: a token nobody varies is a question nobody should be asked.

## The identity model the templates are built around

Three names, three jobs. Conflating them is the failure these templates exist to prevent.

1. **`temporary_aws_profile_name`** (value: the project name) — a **throwaway** credentials pointer,
   exported as `AWS_PROFILE`, created and deleted per run. The assumed-role session is written into it.
   It **must never name a persisted resource**, because its value can change between runs. Locally its
   source is the folder-named SSO profile; in CI it is the static base credentials that assume the deploy
   role.
2. **`deployment_tenant_profile`** (`__DEPLOYMENT_TENANT_PROFILE__`) — the **persisted-resource
   identity**. It names the Terraform state bucket (`terraform-<env>-<deployment_tenant_profile>-state`)
   and the lowercased suffix on every Terraform resource name. It is deliberately independent of the CLI
   and login profiles so a local deploy and a CI deploy read and write the **same** state. It has **no
   default**: the deploy scripts print to stderr and `exit 1` before any AWS action if it is empty or
   still holds the placeholder. A default would split the state in two the first time someone renamed a
   folder.
3. **`tenant_name`** (`__TENANT_NAME__`) — branding only: the venv name, labels, the CI variable group.
   It names nothing persisted.

Account ids are never hardcoded outside `infra/aws_account_config.sh` in `backend_service`, and
`assert_aws_account` gates every deploy against the account the environment maps to. A deploy that runs
in the wrong account is not a deploy, it is an incident.

## The `naming.tf` convention

`backend_service/infra/terraform/naming.tf` is the origin of the convention the house documentation
describes: every resource is named

```
<prefix>_<resource_role>_<deployment_tenant_profile>
```

- `prefix` = `${environment}_${project_name}`, derived from the repo folder name at deploy time and never
  hardcoded;
- `resource_role` = the per-resource descriptive middle (`service`, `queue`, `table`);
- the suffix = `lower(var.deployment_tenant_profile)`, the same identity that names the state bucket.
  It is lowercased in one place because AWS resource names are case-sensitive and the deploy script may
  spell the profile with capitals.

The composition lives in `locals` in that one file, and each resource file references the local rather
than re-spelling the rule. That is why a change to the naming convention is a one-file change. Add one
local per resource you own; do not inline the prefix and suffix at the resource.

## The CI credentials the scaffolding expects

The publish and deploy scripts read the CI base credentials from the environment; the pipeline maps them
from its variable group. They are **not** tokenised and **not** written into the repo — the scaffolded
tree contains no credential material at all, which is what makes it safe to commit immediately after
scaffolding. The env-var names follow `<TENANT_UPPER>_<STAGE>_<COMPONENT>_AWS_ACCESS_KEY` and its secret
counterpart.

Optional runtime overrides need no edit: `DEPLOY_ROLE_ARN`, `DEPLOY_ROLE_NAME`, `DEPLOY_ACCOUNT_ID` for
the CI assume-role target, and `AWS_SSO_PROFILE`, `SSO_START_URL`, `SSO_REGION`, `EXPECTED_ACCOUNT`,
`DEPLOY_REGION` for a local deploy. Those seams are why one template serves every stage without a fork.
