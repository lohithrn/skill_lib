# Every resource a service creates, and what its name must obey

One row per AWS resource kind a fleet service actually owns. Cited from `SKILL.md` §Route and
§The non-negotiables. Use it two ways:

- **build arc** — the checklist of what `naming.tf` needs a `locals` entry for, and which terraform
  file it lands in.
- **review arc** — the list to walk a repo against. A resource that exists in the tree but has no row
  here is either a resource this file has not caught up with, or a resource nobody named on purpose.
  Say which, do not guess.

**Applies to** is the column that decides whether a breach is a finding. `all code` means the rule
holds in every repo including the ones that predate the convention. `new only` means existing repos
are **grandfathered and never retrofitted** — working rule 2. A finding against a `new only` row in a
five-year-old service is noise, and reporting it burns the reviewer's credibility on the rows that
matter.

## The catalog

| Resource | Terraform file | `naming.tf` local | Name | Cap | Cap answers at | Applies to |
|---|---|---|---|---|---|---|
| DynamoDB table | `dynamodb_<name>.tf` | `<role>_table_name` | `<prefix>_<resource_role>_<company>` | 255 | plan | new only |
| DynamoDB GSI | same file as its table | `<role>_index_name` | `<resource_role>_by_<key>` | 255 | plan | new only |
| Lambda function | `lambdas/` module | `<role>_function_name` | **full** `prefix` — never shortened | **64** | **apply** | all code |
| IAM execution role | `lambdas/` module | `lambda_execution_role_names[<word>]` | `<role_prefix>_<word>_<company>_exec_role` | **64** | **apply** | all code |
| IAM policy | with its role | `<role>_policy_name` | `<prefix>_<resource_role>_<company>` | 128 | apply | new only |
| EventBridge Scheduler group | `scheduler_*.tf`, or composed at runtime | `scheduler_prefix` + tenant | `<scheduler_prefix>_<tenant>_...` | **64** | **apply, or runtime** | all code |
| SNS topic | `sns_<name>.tf` | `<role>_topic_name` | `<prefix>_<resource_role>_topic_<company>` | 256 | plan | new only |
| SQS queue | `sqs_<name>.tf` | `<role>_queue_name` | `<prefix>_<resource_role>_queue_<company>` | 80 | apply | new only |
| Secrets Manager secret | `secret_manager_<name>.tf` | `<role>_secret_name` | `<prefix>_<resource_role>_secret_<company>` | 512 | plan | new only |
| Cognito user pool | `cognito_<name>.tf` | `<role>_pool_name` | `<prefix>_<resource_role>_pool_<company>` | 128 | plan | new only |
| WAF web ACL | `waf_api_gateway.tf` | `<role>_web_acl_name` | `<prefix>_<resource_role>_web_acl_<company>` | 128 | plan | new only |
| API Gateway REST API | `api_gateway/` module | `<role>_api_name` | `<prefix>_<resource_role>_api_<company>` | 1024 | plan | new only |
| CloudWatch log group | **none — AWS derives it** | none | `/aws/lambda/<function_name>` | 512 | never | all code |
| Lambda Web Adapter layer | `lambdas/` module | none — AWS-published ARN | not ours; **version pinned** | — | — | all code |
| Terraform state object | `main.tf` `backend "s3"` | none | key `${PROJECT_NAME}/${environment}/terraform.tfstate` | — | — | all code |

The three rows in bold-cap territory — lambda function, IAM role, scheduler group — are the whole
reason the slug variables exist. `references/naming_length_caps.md` has the measured overflow
evidence, the two slug variables and the plan-time assertion; do not re-derive them here.

## The two rows that are not decided

Say "not decided in this fleet" rather than inventing an answer:

- **S3 buckets.** The `_` convention **cannot** apply: an S3 bucket name is globally unique, 3–63
  characters, lowercase letters, digits, hyphens and dots only — no underscores. Terraform state uses
  one shared bucket with a per-service *key*, so the question has not been forced. A service that
  needs its own bucket needs a decision first; the closest existing hyphenated pattern in the
  organization is `{tenant}-{project}-{stage}`, which is a different convention, not this one.
- **Custom domains and ACM certificates.** The `custom_domain/` module exists in the layout but no
  naming rule was recorded for it. Whatever is decided, **the certificate is CA-issued or
  provider-managed** — never minted locally. That is non-negotiable 5 and it is not open.

## What every row shares

1. **The name is composed in `naming.tf` and nowhere else** (`new only`). Every other `.tf` reads
   `local.<name>`. A name spelled inline is the convention living in two places.
2. **One terraform file per resource, named for the resource** (`new only`). `dynamodb_private_configuration.tf`
   holds the `private_configuration` table. A resource whose file you cannot guess is a resource
   nobody finds when it misbehaves.
3. **The lambda environment is composed in `main.tf` locals from the resources themselves**
   (`all code`) — never a hand-typed table name, pool id or secret ARN. A hand-typed ARN is correct
   until the resource is replaced.
4. **Nothing here is created by hand in the console** (`all code`). A resource that exists only in an
   account is a resource the next `apply` does not know about.
5. **Every runtime-created per-tenant resource has a delete path** (`all code`). A group created per
   tenant and never removed is a quota exhausted six months later, in prod, by success.

## How to walk a repo against this table

Review arc, in order — the first two are the ones that find real problems:

1. `grep -c 'local\.' infra/terraform/*.tf` against the count of `resource "` blocks. A resource block
   with no `local.` reference is spelling a name inline.
2. For every entry in `naming.tf`, check the composed length against its cap row above. Arithmetic,
   never an estimate — `awk '{print length($0), $0}'` on the resolved names.
3. Any resource kind in the tree with **no row here**: name it in the report as uncatalogued rather
   than ruling on it.
4. Any `new only` breach in a repo that predates `naming.tf`: record it as grandfathered, not as a
   finding. Say which repo, and say you did not retrofit it.
