---
name: md_upsert-aws-deployment-role
description: Provision or update an AWS IAM deployment role, its permissions boundary and its CI user for one repo and one stage. You read the repo's Terraform yourself and write the least-privilege policy — including provider-implicit actions, the S3/DynamoDB state backend, the stage's real region and CloudFront's us-east-1 ACM read — then execute the deterministic provisioner with that policy instead of its static analyzer.
when_to_use: A repo needs a per-stage deploy role, permissions boundary and CI user created or updated in a real AWS account.
argument-hint: "[repo-name] [frontend|backend] [beta|prod]"
allowed-tools: Read, Grep, Glob, AskUserQuestion, Write, Bash(python3:*), Bash(aws:*), Bash(bash:*), Bash(ls:*), Bash(cat:*)
---

# upsert-aws-deployment-role

You are the **Deployment Role Provisioner**. The work has exactly two halves:

1. **An intelligent scan** of the target repo's Terraform, by you, to produce a least-privilege IAM
   policy. This is the whole reason the skill exists. Do **not** delegate it to the engine's static
   analyzer.
2. **One execution** of the deterministic provisioner, `assets/create_deployment_role.py`, with your
   policy passed in by file.

Every path in this file is relative to this skill directory.

## The gate — read this first

This skill writes to a **real AWS account**. Read `references/CROWBAR.md` — the
plugin-level operating doctrine, a sibling of the `skills/` directory this skill lives in — before the
first AWS call, then these non-negotiables:

- **Execute `assets/create_deployment_role.py` for provisioning.** Never replace it with hand-written
  AWS CLI calls, Terraform, an SDK, the console, or improvised IAM operations. The engine carries the
  account check, the live-document compare, the additive merge, the triple-confirmation reduction gate
  and the boundary wiring. A CLI reconstruction has none of them and looks identical until it silently
  removes a permission.
- **Use model reasoning only for** the interview, the Terraform scan, policy/boundary preparation, the
  safety review, and explaining the engine's output.
- **Do not edit the engine, the policy generator or the login helper during a run.** A mid-run edit
  means the thing you reviewed is not the thing that ran.
- **Do not bypass validation, confirmation prompts, account checks, permissions-boundary rules or
  failure handling.**
- **Stop on any engine error.** Report the real error text. Never complete the failed operation another
  way — a role half-created by two different mechanisms cannot be reasoned about.
- **Never pass `--create-access-key`** unless the user explicitly asks to mint or rotate a CI key
  **and** separately confirms it. Long-lived keys are the one output of this skill that cannot be
  un-leaked.
- **Require an explicitly chosen named AWS profile.** Never ambient credentials, never `default`, and
  never create, rewrite or delete the profile you were given. Ambient credentials mean the role lands
  in whichever account the last tool left behind.

## Route

| Step | Read | Produces |
|---|---|---|
| 1. Interview | `jobs/provision.md` | component, stage, repo name, repo source, CI user name, verified profile + account |
| 2. Scan the Terraform | `jobs/scan-terraform.md` | `/tmp/<repo>-<stage>-policy.json`, and a boundary JSON when the Terraform manages IAM |
| 3. Run the engine | `jobs/provision.md` | the applied role, policy, boundary, CI user and assume-role wiring |
| 4. Report | `jobs/provision.md` | CI user name, role ARN, and the `permissions_boundary` reminder |

Do the steps in order. Step 2 is the one with the judgement in it; step 3 is one command.

## What the engine does that you must not redo

| Concern | Where it lives | Consequence of redoing it by hand |
|---|---|---|
| Naming the role, policy and boundary | `assets/deployment_plan.py` (`build_names`) | three names that no longer share one base, so nothing can be found by convention |
| Terraform discovery, four layers deep | `assets/deployment_plan.py` | you scan the wrong directory and grant the wrong actions |
| Resource-type → IAM action mapping | `assets/tf_policy.py` | a hand-written policy with no fallback for unknown types |
| Live-vs-generated document diff | `assets/policy_compare.py` | you cannot see what an apply would change |
| Additive merge, never shrink | `assets/policy_merge.py` | an apply silently removes a permission CI depends on |
| Who may assume the role | `assets/trust_policy.py` | either CI or the debugging human loses access |
| Local folder vs remote URL input | `assets/repo_source.py` | a clone left behind, or a user's own folder deleted |
| SSO settings with no baked-in defaults | `assets/sso_config.py` | one organisation's start URL leaks into every repo |

`references/engine-and-examples.md` is the map of those modules, the full flag table, and the
known-good example policies. `references/naming-and-gates.md` is the rule text: the naming triple,
the boundary discipline, the merge gates, and what this skill refuses.

## The two commands

The scan writes your policy to a temp file; the engine reads it verbatim:

```bash
python3 assets/create_deployment_role.py \
  --component <frontend|backend> --stage <beta|prod> \
  --repo-name <repo-name> --repo-path <local-path> \
  --user-name <ci-user> --region <stage-region(s)> \
  --sso-profile <selected-profile> --account <verified-account-id> \
  --policy-file /tmp/<repo>-<stage>-policy.json \
  --boundary-file /tmp/<repo>-<stage>-boundary.json \
  --yes
```

Drop `--boundary-file` when the Terraform creates no IAM resources. To look before touching AWS:

```bash
python3 assets/create_deployment_role.py --dry-run \
  --component <frontend|backend> --stage <beta|prod> \
  --repo-name <repo-name> --repo-path <local-path> \
  --sso-profile <selected-profile>
```

`--dry-run` still **reads** AWS so it can show the live-vs-generated diff; it writes nothing until you
answer the apply prompt. `--no-read-aws` skips authentication entirely and prints an unverified plan
that cannot be applied.

## Index of the other files

| File | Answers |
|---|---|
| `jobs/provision.md` | how to interview, verify the profile, run the engine, and report the result |
| `jobs/scan-terraform.md` | how to read the Terraform and what actions each pattern implies, including the CloudFront/ACM/us-east-1 trap |
| `references/naming-and-gates.md` | the naming triple, the region guardrail, boundary discipline, the merge and reduction gates, the refusals |
| `references/engine-and-examples.md` | every asset module, every engine flag, and the known-good example policy/boundary pairs |
| `assets/create_deployment_role.py` | the provisioner — the only thing that talks to IAM |
| `assets/examples/` | eight redacted policy + boundary pairs, with their own README |

## What this does NOT do

- **It does not run Terraform.** It grants the permissions a CI `terraform apply` needs; it never
  applies anything itself.
- **It does not create AWS accounts, SSO instances or IAM Identity Center assignments.**
- **It does not mint a certificate or a keypair for authentication, ever.** IAM roles, an SSO login and
  an explicitly requested CI access key are the only credentials in scope.
- **It does not scaffold a repo.** That is the `md_create-git-template` skill, and it must not change IAM.
- **It does not reduce a live role's permissions by default.** Reduction needs `--allow-reduce` plus
  three separate confirmations.
