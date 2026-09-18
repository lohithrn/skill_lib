# Job: stand up a new service from nothing

The order below is the order that makes each step verifiable when you reach it. Do not reorder it to
"get something deployed first" — a deploy written before `naming.tf` exists is a deploy with names in it.

## Phase 0 — before writing a file

1. **Read `references/blueprint_working_rules.md`.** Put the relevant rules at the top of the plan you show the
   user. Rules 4, 5 and 6 are the ones this job is built out of.
2. **Look for a sibling repo in the fleet and read its `infra/` and `naming.tf` first.** Consistency with
   the existing fleet beats this document wherever they differ. Say which repo you read. The review arc holds the index of which repo demonstrates what, and the standing rules a
   review will hold you to.
3. **Fix the folder name, and say it out loud.** It is the service name, the `project_slug`, the first URL
   segment, the terraform state key prefix, and half of every resource name. Renaming it later renames
   every resource, which means destroying them.
4. **State the rough monthly cost** of what you are about to create, and name anything in it that is
   RDS/Aurora/NAT/always-on. Get a yes before it goes in (rule 7).

## Phase 1 — the layout and the names

5. **Create the tree** from `references/blueprint_repo_layout.md`. One terraform file per resource, `z_` on the
   scripts a human runs, the standard `main.tf`/`variables.tf`/`outputs.tf` trio in every module.
6. **Write `infra/terraform/naming.tf` from `assets/naming.tf.template`** — one `locals` entry per
   resource, `<prefix>_<resource_role>_<company>`, with the company suffix lowercased once at the top.
   Read `references/blueprint_naming.md` before choosing a single `resource_role`; the taste rules there are the ones
   that get enforced.
7. **Add `var.role_slug` and `var.scheduler_slug`** if this service will own IAM roles or scheduler groups,
   and the plan-time `precondition` that asserts the composed names against **64**. They may hold the same
   string today — leave them as two variables.
8. **Write `variables.tf`** with `project_name`, `project_slug`, `environment`, `prefix`, `company_name`,
   `aws_region`, `aws_profile`. Nothing in it has a default that could be wrong in prod.
9. **Write `outputs.tf` with a real `public_url` output.** The deploy prints it, so it exists before the
   deploy does.

## Phase 2 — the account single source of truth and the login

10. **Copy `assets/aws_account_config.sh.template` to `infra/aws_account_config.sh`** and fill in the two
    account ids. Both may be the same account today; keep both variables. **Nothing else in the repo
    hardcodes an account id.**
11. **Write `infra/provider_login.sh`** so that it signs in and then sources the account config. Sign-in
    credentials come from the environment or the CI secret store. **Never mint a certificate or a keypair
    to authenticate** — the direction is SigV4, and the only acceptable TLS is a CA-issued or
    cloud-provider-managed certificate nobody here generated.

## Phase 3 — the outbound URL seam

12. **Create `configuration/urls.beta.yaml` and `configuration/urls.prod.yaml`**, key → URL template, with
    `{stage}` / `{tenant}` / entity-id placeholders. Create them even if they start nearly empty: the seam
    is what stops the first outbound URL from becoming a lambda environment variable.
13. **Copy `assets/get_url_utility.py` to `src/deployed_utilities_references/get_url_utility.py`
    verbatim.** It fails loudly on a missing key and refuses to default `ENVIRONMENT`, and both of those
    are the point. See `references/deploy_discipline.md` for how the file gets packaged.

## Phase 4 — the deploy

14. **Copy `assets/deploy_utils.sh.template` to `infra/deploy_utils.sh`** and
    `assets/z_setup_deploy.sh.template` to `z_setup_deploy_beta.sh`, then copy that to
    `z_setup_deploy_prod.sh` with `beta` flipped to `prod`. Better: put the shared body in
    `infra/deploy_entrypoint.sh` and make both `z_` scripts thin — prod is the mode used least, so it is
    the one that drifts.
15. **Walk the nine-step checklist in `references/deploy_discipline.md` against what you wrote.** Every
    `set -e`, every `pipefail`, and every exit-code propagation line in the templates is load-bearing.
    Do not remove one to make the output quieter.
16. **Fill in the state bucket and the default profile placeholders** (`REPLACE_STATE_BUCKET`,
    `REPLACE_DEFAULT_PROFILE`, `REPLACE_COMPANY`). Leaving a `REPLACE_` in place is a deploy that fails at
    `init`, which is the correct failure — but say so rather than shipping it silently.

## Phase 5 — the tests that gate the deploy

17. **Write the unit suite before the first deploy**, because step 5 of the deploy sequence runs it and
    `set -e` means it can abort. A suite that does not exist yet is a gate that is not there.
18. **Add the three standing tests** that keep this scaffolding honest:
    - the file-length cap (**< 250** lines) over `src/`;
    - the name-length caps over every deployed environment, reading the role and function words out of
      `naming.tf` rather than restating them;
    - one test asserting the full project slug **would not** have fit in 64, so nobody removes the slug
      variables later as an unused knob.
19. **Add a test that reads a derived name from the environment using deliberately foreign literals**
    (`prod_someslug` / `othercorp`), with a "these literals are on purpose, do not fix" comment. Derived
    values would also pass for a function that ignored the environment.

## Phase 6 — before saying done

Run the checklist in SKILL.md. Then state, in one line each: the folder name, the resolved account per
environment, the printed public URL, and anything you left as a `REPLACE_` placeholder.

## Refusals inside this job

- **No deploy before `naming.tf`.** Names composed inline are names in two places.
- **No `outputs.tf` without a real public URL output.** Gate 9 has nothing to print.
- **No account id outside `infra/aws_account_config.sh`.**
- **No skipping the tests "for the first deploy".** The first deploy is the one that defines the habit.
