# The engine, its flags, and the example policies

What each shipped module does, every flag the provisioner accepts, and where the known-good policy pairs
live. All paths are relative to this skill directory.

## The modules

`assets/create_deployment_role.py` is the entry point and the only module that talks to IAM. Everything
it can do without AWS is factored out so it can be unit-tested and dry-run:

| Module | Responsibility | AWS-free? |
|---|---|---|
| `create_deployment_role.py` | interview, authenticate, compare against live, apply, print | no |
| `provider_login.sh` | the SSO login and the IAM primitives, one place | no |
| `deployment_plan.py` | Terraform discovery, the naming triple, region merge, whole-plan assembly | yes |
| `tf_policy.py` | resource/data-source type → IAM action mapping, boundary generation, region guardrail | yes |
| `policy_compare.py` | live-vs-generated diff, per-`Sid` action sets | yes |
| `policy_merge.py` | the additive union and the list of what a reduction would remove | yes |
| `trust_policy.py` | who may assume the role | yes |
| `repo_source.py` | local folder versus remote URL, and the clone lifecycle | yes |
| `sso_config.py` | derive the SSO profile, start URL and region with **no** baked-in defaults | yes |

The AWS-free half is why `--dry-run` can produce and print the entire plan before authenticating, and why
`python3 assets/deployment_plan.py` works as its own CLI.

`sso_config.py` derives the SSO settings in this order: (1) an already-configured profile of that name,
(2) the repo's own deploy scripts, (3) unknown — ask the user. It carries no organisation's start URL and
no account id, and its test suite asserts that by **shape**: no concrete `<org>.awsapps.com` literal and
no 12-digit number may appear in the module. A baked-in default here silently points every repo at one
organisation, which is the bug that rule removed.

## Graceful degradation, and why the scan still matters

`tf_policy.py` maps common `aws_*` types to explicit action lists rather than `s3:*`, so the generated
policy is genuinely least-privilege for the types it knows. **Anything not in the table falls back to
`<service>:*` with a warning** — nothing is silently dropped, but nothing is tight either. That fallback
is the reason you read the Terraform yourself: the static analyzer cannot see provider-implicit calls at
all, and a `<service>:*` fallback is a wide grant that no one reviews later.

Run the tests before trusting a change to any of these modules:

```bash
python3 -m pytest assets -q
```

Eight test modules ship next to the code (`assets/test_*.py`), all offline.

## Every flag

| Flag | Effect |
|---|---|
| `--component` | `frontend` or `backend` |
| `--stage` | `beta` or `prod` |
| `--repo-name` | logical repo name used in resource naming |
| `--repo-path` | local checkout to scan; used in place and never deleted |
| `--repo-url` | remote repo to clone and scan instead; the clone is cleaned up afterwards |
| `--branch` | branch to check out after cloning `--repo-url` |
| `--user-name` | the IAM user CI assumes the role as |
| `--sso-profile` | the named profile for admin login. Required; `default` is refused |
| `--account` | expected account; defaults to the profile's verified account |
| `--region` / `--regions` | comma- or space-separated region list; detected regions are appended |
| `-y` / `--yes` | assume the default answer at each confirmation. Enables no reduction and no key creation |
| `--policy-file` | use this JSON permissions policy **verbatim**, bypassing the static analyzer |
| `--boundary-file` | use this JSON boundary verbatim; pairs with `--policy-file` |
| `--create-access-key` | mint a new CI access key. Off by default; explicit request plus confirmation only |
| `--allow-reduce` | permit removing live permissions. Off by default; still needs three confirmations |
| `--trust-root` | also trust the account root in the trust policy. Broadest escape hatch, off by default |
| `--dry-run` | plan, generate, authenticate, and show the live-vs-generated diff, then ask whether to apply |
| `--out-dir` | where the generated JSON is written; defaults to a fresh temp dir. Written in every mode |
| `--no-read-aws` | preview only: no login, no AWS calls. The printed JSON is unverified and cannot be applied |

`--dry-run` still reads AWS, read-only. `--no-read-aws` is the only mode that touches nothing, and its
output is explicitly labelled unverified — a preview compared against nothing is not a plan.

## The examples

`assets/examples/` holds eight redacted documents: four **policy + boundary pairs**, each the actual JSON
this workflow produced. `assets/examples/README.md` explains the placeholders (`<ACCOUNT_ID>`,
`<STAGE_REGION>`; `us-east-1` is left literal on purpose) and which pair to reach for.

Load the relevant pair into context before generating, so your output matches the proven shape. The
frontend/CloudFront pair is the one to read first: it is the stack the us-east-1 rule came from, and its
README carries that account of what went wrong and why the error message pointed at the wrong thing.

In every pair the boundary is a **superset** of the policy. If a generated pair ever violates that, the
boundary is not a ceiling and the apply will deny something the policy explicitly grants.
