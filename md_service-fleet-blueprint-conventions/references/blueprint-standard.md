# The service blueprint standard

The build-arc rulebook: the house style for standing up and deploying an AWS lambda service, distilled
from ~10 services in one fleet. Cited from `SKILL.md` as the **build** arc.


The house style for standing up and deploying an AWS lambda service, distilled from ~10 services in one
fleet. This file is a **router**: it holds the gate, the route table and the two things this skill
enforces above all. The procedures are in `jobs/`, the rules in `references/`, the copyable files in
`assets/`.

Two things this skill enforces above everything else:

1. **Nothing is hardcoded** — every name, URL and account derives from one source of truth.
2. **A deploy can never lie** — it gates on tests and on the resolved account, and it reports the real
   exit code and the real URL.

The standing rules used to *review* an existing repo — the fleet's route shape, the one authorization
gate, the data conventions, the measured name-length evidence, how far each convention has spread — belong
to the review arc — the fleet reference files named in `SKILL.md` §Route. This standard is the job of building.

## The gate — read this first

**This skill writes files.** It has `Edit` and `Write` on purpose: its job is to produce a tree.

- **Read before writing.** If a sibling repo in the fleet exists, read its `infra/` and its `naming.tf`
  **first** and mirror them. **Consistency with the existing fleet beats this document** where they
  differ, and you say which repo you read.
- **Never retrofit an older repo** to a newer convention unless asked. That is a sweeping change to a
  working production service.
- **Never run a deploy, a login, or any AWS mutation.** This skill writes the script; the user runs it.
- **Never mint a certificate or a keypair as an authorization mechanism.** The direction is SigV4, and the
  only acceptable TLS is a CA-issued or cloud-provider-managed certificate nobody here generated, verified
  against the system trust store. This is permanent and outranks everything below.
- **Never fill a `REPLACE_` placeholder with a guess.** An account id, a state bucket or a profile name you
  invented is a deploy that lands somewhere nobody chose. Leave it, and say you left it.

## Route

| The task is | Read |
|---|---|
| "create a new service / repo / backend / frontend" | `jobs/new_service.md` |
| "add a resource" (table, lambda, topic, bucket, pool, secret, WAF, …) | `jobs/add_resource.md` |
| "add or change a route" | `jobs/add_resource.md` |
| "write / fix / change the deploy script", or anything under `infra/` | `jobs/add_resource.md`, then `references/deploy_discipline.md` |
| naming *any* AWS resource, tfvars var or env var | `references/blueprint_naming.md` |
| wiring an outbound URL or per-environment config | `references/deploy_discipline.md` |
| "is this production ready?" / review before a deploy | `references/blueprint_working_rules.md`, then the checklist below |

Read the one job file for the row and follow it. State which job you selected in one line before starting.

---

## Apply this without waiting to be asked

The tasks above are this skill's triggers whether or not it was named. If the task is "add a DynamoDB
table" and nobody mentioned conventions, the conventions still apply — a resource named outside the rule
is a resource that has to be destroyed to be renamed.

---

## The non-negotiables

1. **Names are composed in exactly one place**, `infra/terraform/naming.tf`, one `locals` entry per
   resource. Every `.tf` reads `local.<name>`. Re-spelling the rule means the next convention change has
   to find every copy, and misses one.
2. **The service name is the repo folder name**, `basename $(pwd)`, resolved at deploy time and injected.
   Never hardcoded, not even in tests.
3. **Account ids live in `infra/aws_account_config.sh` and nowhere else**, and the resolved account is
   asserted after login and **before any mutation**.
4. **Tests run before the zip is built.** `set -e` then makes a failing test abort the deploy rather than
   ship it.
5. **`terraform apply`'s exit code is the script's exit code.** A failed apply can never print success.
6. **The real resolved public URL is printed**, from a terraform output, at the end. Never `xxxx`.
7. **Outbound URLs live in `configuration/urls.{env}.yaml`**, read through `get_url()`, which fails loudly
   on a missing key. `ENVIRONMENT` is terraform-wired and **must not default**.
8. **Every IAM role, lambda function name and scheduler group name is asserted under 64 at plan time.**
   IAM answers a too-long name at **apply**, after a clean plan, halfway through the deploy.
9. **Lambdas, and the cheapest thing that meets the need.** Any RDS/Aurora/NAT/always-on is flagged with a
   monthly cost and needs an explicit yes.

---

## What this skill does NOT do

- **It does not deploy.** No login, no `apply`, no AWS mutation. It writes the one command the user runs.
- **It does not review an existing fleet against the standing rules** — that is the review arc, which also holds the measured name-length evidence and the index of which repo demonstrates what.
- **It does not invent an account id, a state bucket, a profile or a company name.** Those stay as
  `REPLACE_` placeholders until someone supplies them.
- **It does not modernize a repo it was asked to extend.** Additive only.
- **It does not measure anything.** It ships no scripts. Name lengths are arithmetic; everything else you
  claim, you claim from a file you opened.

---

## Quick checklist before saying "done"

- [ ] No hardcoded service name, account id, URL or secret anywhere — and ideally not in `test/`
- [ ] Every resource name comes from `naming.tf` and follows `<prefix>_<resource_role>_<company>`
- [ ] Every name in a capped namespace is asserted under **64** at plan time
- [ ] Deploy script is one self-contained command, login included
- [ ] Tests gate the deploy; the account is asserted before mutation
- [ ] `terraform apply`'s exit code is the script's exit code
- [ ] The real public URL is printed — no placeholder
- [ ] Every `set -e`, `pipefail` and exit-code line from the templates survived
- [ ] Outbound URLs are yaml keys read through `get_url()`, not env vars
- [ ] Files **< 250** lines, methods **< 25** lines, nesting **≤ 2**; comment lines **≤** code lines in every `.tf`
- [ ] Diff contains only what was asked — no incidental deletions or reformatting
- [ ] Existing users cannot be affected by this change
- [ ] Cheapest infra that meets the need; any RDS/Aurora/always-on flagged with a stated cost
- [ ] Every `REPLACE_` placeholder still in the tree is named in the reply
- [ ] If the user asked a yes/no or a number, that answer leads the response

---

## The files

| File | Answers |
|---|---|
| `jobs/new_service.md` | the ordered procedure for a service that does not exist yet, phase 0 through 6, and what to refuse mid-job |
| `jobs/add_resource.md` | the surgical path for adding one resource, route or deploy change to a repo that already has conventions |
| `references/blueprint_working_rules.md` | the eight working rules, the consequence attached to each, and where the ninth lives |
| `references/blueprint_naming.md` | how a name is composed, the taste rules, the three 64-character namespaces and their slug variables, and the plan-time assertion |
| `references/deploy_discipline.md` | the nine ordered deploy steps, the two deploy modes, the `urls.{env}.yaml` seam, and the four lies a dropped gate tells |
| `references/blueprint_repo_layout.md` | the full tree with per-file responsibilities, the rules of thumb, the code-size caps, and the cost defaults |

| Asset | Copy it to |
|---|---|
| `assets/naming.tf.template` | `infra/terraform/naming.tf` — the naming `locals` skeleton and the length `precondition` |
| `assets/aws_account_config.sh.template` | `infra/aws_account_config.sh` — the account single source of truth and `assert_aws_account` |
| `assets/deploy_utils.sh.template` | `infra/deploy_utils.sh` — `init_deployment_vars`, `create_tfvars`, `run_terraform`, `deploy`, `print_public_url` |
| `assets/z_setup_deploy.sh.template` | `z_setup_deploy_beta.sh` — the self-contained entrypoint, all nine gates in order |
| `assets/get_url_utility.py` | `src/deployed_utilities_references/get_url_utility.py` — the runtime URL resolver, verbatim |

The assets live in `assets/` and not in `scripts/` because they call AWS. Nothing in this skill is a
measurement tool, and nothing here is meant to be executed from the skill directory: every asset is a file
you copy into a repo and then fill in.
