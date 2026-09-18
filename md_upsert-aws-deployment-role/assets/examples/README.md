# Reference deployment-role policies

Complete, redacted example policy + boundary **pairs** — the actual JSON the
workflow produces — kept as few-shot context for the intelligent scan described
in this skill's `jobs/scan-terraform.md`. Load these into context before
generating so the
output matches the proven shape. Placeholders: `<ACCOUNT_ID>` and `<STAGE_REGION>`
(the stage's deploy region, e.g. `us-west-1`). `us-east-1` is left literal on
purpose — see the CloudFront rule below.

Each pair is a **role policy** (the least-privilege floor + read leeway) and its
**boundary** (the loose ceiling + escalation deny). The boundary is always a
superset of the policy.

## Files

Frontend / static site behind CloudFront (S3 + CloudFront + Route53 + ACM viewer
cert + S3/DynamoDB state backend), with a prod region guardrail:

- `example-cloudfront-frontend-prod-deploy-policy.json` — hand-curated, known-good.
- `example-cloudfront-frontend-prod-deploy-boundary.json` — its matching boundary.
- `example-frontend-cloudfront-prod-generated-{policy,boundary}.json` — the same
  archetype as produced deterministically by `deployment_plan.py`.

Backend service (Python service whose Terraform manages IAM roles ⇒ Option B
boundary gating), beta and prod:

- `example-backend-service-beta-deploy-{policy,boundary}.json`
- `example-backend-service-prod-deploy-{policy,boundary}.json` (adds the region
  guardrail)

## The CloudFront + ACM + us-east-1 lesson (why these exist)

A CloudFront distribution with a `viewer_certificate` makes CloudFront **read the
ACM cert during `CreateDistribution`**, and that read is evaluated against
**us-east-1** (where CloudFront's certs must live) — *even when the cert is passed
by raw ARN* (`var.certificate_arn`) with **no `aws_acm_certificate` resource or
data source** in the Terraform. A naive scanner sees no ACM usage, grants no
`acm:*`, and confines the region guardrail to the stage region. The result:

```
InvalidViewerCertificate: The specified SSL certificate doesn't exist,
isn't in us-east-1 region, isn't valid, or doesn't include a valid
certificate chain.
```

This error is **misleading** — the cert is fine. The real cause is the deploy
role being unable to read ACM in us-east-1. The fix (both applied in these
examples, and now automated in `../tf_policy.py`):

1. Grant ACM **read** (`acm:DescribeCertificate`, `ListCertificates`,
   `GetCertificate`, `ListTagsForCertificate`) whenever the stack has a
   CloudFront distribution — regardless of whether ACM appears in the TF.
2. In the prod region guardrail, include **`us-east-1`** in the allowed regions
   (alongside the stage region) whenever a CloudFront distribution is present.
   Exempting `acm:*` via `NotAction` alone is **not** sufficient — the cert
   validation is evaluated with `aws:RequestedRegion=us-east-1` and gets denied
   unless us-east-1 is allowed.

Both the deploy-role policy and the permissions boundary need the ACM allowance
(a boundary is a ceiling — if ACM isn't in it, granting it on the role has no
effect).
