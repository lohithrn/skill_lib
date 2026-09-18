# Deploy discipline, and the URL/config convention

## What every deploy script must do, in order

The reference implementations are `assets/z_setup_deploy.sh.template` (the entrypoint) and
`assets/deploy_utils.sh.template` (the helpers). The required sequence:

1. **`set -e` and `set -o pipefail`.** Fail fast, and fail on the failing member of a pipeline rather
   than on the last one.
2. **Resolve `PROFILE`, `ENVIRONMENT`, `REGION`, `COMPANY_NAME`** — all overridable via the environment,
   all with sane defaults, so a deploy is one command with nothing to set up first. Then
   `PROJECT_NAME=$(basename $(pwd))`.
3. **`source infra/provider_login.sh` and sign in *inside* the script** (SSO or assume-role). Never ask
   the user to sign in first: a deploy that needs a prior command is a deploy somebody runs half of.
4. **`assert_aws_account "$PROFILE" "$ENVIRONMENT"`** — hard-fail if the resolved account is not the
   account configured for this environment in `aws_account_config.sh`. This runs **after** login and
   **before any mutation**. Without it, "deployed to beta" and "deployed to prod" are indistinguishable
   from inside the script.
5. **Run the full unit-test suite BEFORE building the zip.** `set -e` then makes a failing test abort the
   deploy. Never ship an untested zip, and never measure the tests after the artifact exists.
6. **`create_tfvars`** — write `project_name`, `environment`, `prefix=${env}_${PROJECT_NAME}`,
   `company_name`, region, profile. Everything derived; nothing hardcoded.
7. **`terraform init`** with a derived backend key `${PROJECT_NAME}/${environment}/terraform.tfstate`,
   then `plan`, then `apply`.
8. **Capture `terraform apply`'s exit code and make it the script's exit code.** Print an explicit
   success or failure line. On failure, exit non-zero — never fall through to a success message, and never
   hide the code behind an `echo` or a `|| true`.
9. **Print the resolved public URL** from terraform outputs at the very end. Never a placeholder, never
   `xxxx`, never the URL from a previous run.

Optionally, before step 2: **source a gitignored `local_$(basename $(pwd)).env`** so local overrides win
and CI can supply the same variables directly. Never credentials in that file.

## Two modes, one body

Worth having, and sharing **one body** so prod cannot drift from beta — prod is the mode used least, so it
is the one that drifts:

| Mode | Does | Refuses |
|---|---|---|
| **full deploy** | login, assert, test, build, `init`/`plan`/`apply`, print URL | nothing |
| **code-only deploy** | pushes zips to functions terraform already created | to run at all if a target function does not exist; it cannot create, delete or re-wire anything |

Most changes are Python or React, not infra, which is why the second mode pays for itself. Its refusal is
the safety property: a code-only deploy that could create a function is a full deploy with fewer gates.

`.terraform.lock.hcl` stays **gitignored**. Decided; do not re-raise.

---

## URL / config convention (no per-URL env vars)

Outbound service URLs do **not** become lambda environment variables. Instead:

1. Author `configuration/urls.beta.yaml` and `configuration/urls.prod.yaml` — key → URL template, with
   `{stage}` / `{tenant}` / entity-id placeholders.
2. The deploy copies the environment-appropriate file into
   `src/deployed_utilities_references/urls.yaml` and packages it in the zip.
3. Code calls `get_url("some_key")` — see `assets/get_url_utility.py` — which **fails loudly** when a key
   is missing or empty.
4. `ENVIRONMENT` stays an env var wired by terraform. It is **not** read from the yaml, and it **must not
   default**: a missing `ENVIRONMENT` has to fail loudly so a prod lambda can never silently build beta
   URLs.

**Consequence of per-URL env vars instead:** every new callee becomes a terraform change in every caller,
and the environment blocks of ten lambdas become the place URLs actually live.

Everything else the lambda needs — table names, pool ids, secret ARNs, prefixes — is composed in `main.tf`
in `locals.common_environment_variables`, from the terraform resources themselves. **Never hand-typed.**

## The four lies a deploy tells when a gate is dropped

| Gate dropped | The lie |
|---|---|
| account assertion (4) | "deployed to beta" about a prod account |
| tests before the zip (5) | "tests pass" measured after the artifact was built |
| exit-code propagation (8) | "deploy succeeded" after a failed apply |
| real URL printed (9) | a URL nobody resolved, which is the one the next person tries |
