# Compute, code size, and the deploy gates

## Compute: lambdas, and nothing else

Lambda only. **Never Lightsail, never Docker, never EC2, never Fargate** unless explicitly asked.

A web frontend is **one lambda** running a real HTTP server behind the **AWS Lambda Web Adapter as a
layer** (`AWS_LAMBDA_EXEC_WRAPPER=/opt/bootstrap`), with two rules that are not optional:

| Rule | What breaks without it |
|---|---|
| the layer version is **pinned** | floating it changes the wrapper every request passes through, on a re-apply nobody associated with a wrapper change |
| `AWS_LWA_READINESS_CHECK_PATH` points at a **real health path**, not the adapter's default `/` | `/` is the SPA fallback and answers 200 with index.html even when the bundle is broken, so a broken deploy reports itself as ready |

**Cheapest thing that meets the need.** DynamoDB over Aurora/RDS. Lambda over always-on compute. A
function URL or API Gateway over standing up extra networking. Any RDS/Aurora/NAT/always-on gets
flagged with a monthly cost estimate and an explicit yes before it goes in.

## Code size limits (standing, all repos)

- Every file **< 250** lines
- Every method **< 25** lines
- No nesting **> 2** levels
- Verbose, descriptive variable and class names in both `src/` and terraform

There should be a **test** enforcing the file cap, not just a habit. A cap nothing measures is a cap
that has already been exceeded somewhere.

## Terraform comment discipline

Comments carry the *reasoning* — why a knob exists, what breaks without it, what was tried and
rejected. But **in any `.tf` file the comment lines must never outnumber the code lines.**

Summarize rather than delete: the reasoning is the valuable part, the length is not. A file that is
two-thirds prose stops being read as configuration, and the next person edits around the comments
instead of through them.

---

## The ten deploy gates (the deploy can never lie)

`set -e` and `set -o pipefail` first, then in order:

1. **Resolve `PROFILE` / `ENVIRONMENT` / `REGION` / `COMPANY_NAME`** — every one a `:-` fallback with a
   working default, so a deploy is **one command** with no environment to set up first.
2. **`PROJECT_NAME=$(basename $(pwd))`.** The folder name is the service name; nothing else decides it.
3. **Source a gitignored `local_$(basename $(pwd)).env` *before* the defaults**, so local overrides win
   and CI can supply the same variables directly. Never credentials in that file.
4. **Log in inside the script** (SSO or assume-role). Never tell the user to sign in first; a deploy
   that needs a prior command is a deploy someone runs half of.
5. **`assert_aws_account "$PROFILE" "$ENVIRONMENT"`** — hard-fail if the resolved account is not the one
   configured for this environment. After login, **before any mutation**. Single source of truth:
   `infra/aws_account_config.sh`; nothing else in the repo hardcodes an account id.
6. **Run the full unit suite BEFORE building the zip.** `set -e` then makes a failing test abort the
   deploy instead of shipping it.
7. **`create_tfvars`** → derived `project_name`, `project_slug`, `environment`, `prefix`,
   `company_name`, region, profile. Everything derived; nothing hardcoded.
8. **`terraform init`** with a derived backend key `${PROJECT_NAME}/${environment}/terraform.tfstate`,
   then `plan`, then `apply`.
9. **Propagate `apply`'s exit code as the script's exit code.** A failed apply can never print success.
10. **Print the real resolved public URL** from terraform outputs. Never a placeholder.

Each gate answers a specific lie a deploy can tell: gate 5 stops "deployed to beta" that went to prod,
gate 6 stops "tests pass" measured after the zip, gate 9 stops "deploy succeeded" after a failed apply,
gate 10 stops a URL nobody checked.

## Two modes, one body

Two modes are worth having, **sharing one body** so PROD cannot drift from BETA — PROD is the mode used
least, so it is the one that drifts:

| Mode | Does | Refuses |
|---|---|---|
| **full deploy** | login, assert, test, build, `init`/`plan`/`apply`, print URL | nothing |
| **code-only deploy** | pushes zips to functions terraform already created | runs at all if a target function does not exist; cannot create, delete or re-wire anything |

Most changes are Python or React, not infra, which is why the second mode pays for itself. Its refusal
is the safety property: a code-only deploy that could create a function is a full deploy with fewer
gates.

`.terraform.lock.hcl` **stays gitignored** — decided, do not re-raise.

## What the deploy must not do

- Ask the user to run anything first.
- Mutate before asserting the account.
- Build the zip before the tests run.
- Swallow `apply`'s exit code behind an `echo` or a `|| true`.
- Print a placeholder URL, an `xxxx`, or the URL from a previous run.
- Hardcode an account id, a bucket name or a service name anywhere except the one config file that
  owns it.
