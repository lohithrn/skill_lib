# Job — scan the Terraform and write the policy

This is the step the skill exists for. The engine ships a *static* analyzer
(`assets/tf_policy.py`) and it is best-effort: it has missed provider-implicit actions before — a data
source that reads tags needs `route53:ListTagsForResource`, which no resource block mentions. You do
better by actually reading the code, so you write the policy and pass it with `--policy-file`, which
the engine then uses verbatim.

Read the repo's Terraform **and** its deploy scripts and reason about what a CI `terraform apply` for
**this stage** actually calls.

## 1. Find the Terraform

Check `infra/terraform`, `terraform/`, `infrastructure/`, `deploy/terraform`, `iac`, `tf`, and any
per-stage subdirectory (`<dir>/<stage>`, `<dir>/environments/<stage>`, `<dir>/env/<stage>`). Read every
`.tf` file for:

- `resource "aws_*"` blocks — the write surface,
- `data "aws_*"` blocks — the read surface, which is where implicit actions hide,
- `backend "s3"` — the state backend,
- `provider` blocks and `variable`/`*.tfvars` defaults — region hints.

If nothing is found in the known directories, the engine's discovery falls back to directories inferred
from `terraform apply`/`init` invocations in scripts and CI, then to any `*.tf` anywhere, then to the
whole repo. Say which layer you used. Scanning the wrong directory produces a policy that is
least-privilege for code nobody deploys.

## 2. Reason about provider-implicit calls, not just the obvious CRUD

Think about what the AWS provider does under the hood for each resource:

| Pattern in the Terraform | Actions the apply really needs |
|---|---|
| `data "aws_route53_zone"` | `route53:GetHostedZone`, `route53:ListHostedZones`, **and** `route53:ListTagsForResource` |
| `aws_s3_bucket` | the full get **and** put of every sub-config the resource sets: website, policy, public-access block, versioning, CORS, encryption, logging, lifecycle, ownership controls, tagging |
| `backend "s3"` | `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` plus `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:DeleteItem`, `dynamodb:DescribeTable` for the lock table |
| any `data` source | the read/describe/list **and** the tag-read for that service |
| `aws_iam_role`, `aws_iam_policy`, … | IAM create/put actions, **gated on the permissions boundary** — see section 5 |

A missing implicit action does not fail at plan time. It fails halfway through a CI apply, with half the
stack created.

## 3. CloudFront ⇒ ACM read in us-east-1 (implicit, ARN-only certs count)

If the stack has an `aws_cloudfront_distribution` with a `viewer_certificate`, CloudFront reads the ACM
certificate during `CreateDistribution` and evaluates that read against **us-east-1** — *even when the
certificate is a raw ARN* (for example `var.certificate_arn`) with **no `aws_acm_certificate` resource
or data source** for a scanner to see. So:

- grant ACM read: `acm:DescribeCertificate`, `acm:ListCertificates`, `acm:GetCertificate`,
  `acm:ListTagsForCertificate`; and
- in the prod region guardrail, **add `us-east-1` to the allowed regions** alongside the stage region.

Exempting `acm:*` through `NotAction` is **not enough**: the validation runs with
`aws:RequestedRegion=us-east-1` and is denied unless us-east-1 is allowed. Skipping this yields the
misleading error `InvalidViewerCertificate: The specified SSL certificate doesn't exist...` when the
certificate is perfectly fine. Adding us-east-1 to the allowed set is exactly what unblocked the
CloudFront create on the prod frontend this rule came from.

See `assets/examples/README.md` and the redacted `assets/examples/example-cloudfront-*.json` pair for a
known-good policy and boundary.

## 4. Region — pick the stage's region, not the most common one

Determine the deploy region(s) for **this** stage by reading the code. Beta and prod usually differ:
`PROD_AWS_REGION` versus `BETA_AWS_REGION` in the pipeline YAML, or `*_prod.sh` versus `*_beta.sh`.
Prefer a region named on a line or in a file tied to the chosen stage, and drop a region tied to the
other stage. The engine's `detect_regions` does the same thing and weights a stage-matched hit **+10**,
so your answer and its answer should agree; if they do not, say why before applying.

For **prod**, add a region-deny guardrail: deny regional actions outside the stage's region(s), and
exempt the global services the policy actually grants (`cloudfront`, `route53`, `acm`, `iam`, `sts`)
through `NotAction`. If the stack grants no global service at all, use `"Action": "*"` instead — an
empty `NotAction` is invalid IAM and the whole document is rejected.

## 5. IAM management — the Option B boundary

If the Terraform creates IAM roles or policies, the deploy role needs IAM create/put actions, and they
**must** be gated on the permissions boundary:

```json
{
  "Sid": "IAMCreateOnlyWithBoundary",
  "Effect": "Allow",
  "Action": ["iam:CreateRole", "iam:PutRolePolicy", "..."],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "iam:PermissionsBoundary": "arn:aws:iam::<account-id>:policy/<repo>-<component>-<stage>-deploy-boundary"
    }
  }
}
```

Also write the matching boundary document. It is **self-referential** — it permits creating roles only
when they carry *this* boundary, so the ceiling propagates to grandchildren rather than stopping at
direct children — and it denies the escalation actions no deploy-created role should ever hold:
`iam:CreateUser`, `iam:DeleteUser`, `iam:CreateAccessKey`,
`iam:DeleteRolePermissionsBoundary`, `iam:PutUserPermissionsBoundary`, `iam:CreateSAMLProvider`,
`iam:CreateOpenIDConnectProvider`, `iam:UpdateAssumeRolePolicy`, `organizations:*`, `account:*`. An
explicit Deny always wins, which is what makes the ceiling real.

`references/naming-and-gates.md` carries the rest of the boundary discipline, including what the
boundary allows and why it is deliberately looser than the role policy.

## 6. Write the files and confirm

Write the policy to `/tmp/<repo>-<stage>-policy.json` in IAM policy language with
`"Version": "2012-10-17"`. When the Terraform creates IAM, write the boundary to
`/tmp/<repo>-<stage>-boundary.json`.

Show the user the policy you built, name the resource types it came from, and get an explicit
confirmation before step 3. Then return to `jobs/provision.md`.
