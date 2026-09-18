# Operating doctrine for both skills in this plugin

These rules apply to every run of `md_upsert-aws-deployment-role` and
`md_create-git-template`. They are the doctrine both skills were written against;
each rule states what breaks without it. Read this file before either skill's
first AWS call.

## Credentials

**Never print, read, or commit credential material.** A secret that reaches a
transcript, a log or a commit is compromised and must be rotated; there is no
way to un-print it. The one exception is the deliberate, opt-in access-key print
at the end of the deployment-role run — it happens only when the operator asked
for `--create-access-key`, it is shown once, and it is never written to a file.

**Never mint a certificate or a keypair as an authorization mechanism.** No
`openssl`/`keytool` invocation belongs in a deploy, connect or client flow, and
no such material belongs in a repo as an auth substitute. TLS must be a real
CA-issued or cloud-provider-managed certificate that we do not generate.
Provisioning an IAM role, an SSO login, or a CI access key is the supported
path.

## The AWS profile

**The operator must explicitly select a named AWS profile.** Never use ambient
credentials, and never use `default`. Ambient keys and `default` are whatever the
last tool left behind, so a run that trusts them can create real resources in
the wrong account and there is no record of which identity did it.

**Verify the selected profile before using its account.** Run an explicit
`aws sts get-caller-identity --profile <name>` and use the account it returns.
An unverified profile name is a guess.

**Pass `--profile` and `--region` explicitly on every AWS CLI call.** Relying on
an exported variable means the call silently changes behaviour when the
environment does, which is how a beta command lands in prod.

## The deterministic engine

**Each skill is a thin interactive layer over a deterministic engine.** The
engine (`assets/create_deployment_role.py`, `assets/setup_new_repo.py`) does the
heavy lifting and must never be reimplemented, simplified, or worked around. If
you replace the engine with a sequence of CLI calls you lose every validation,
confirmation, cap and comparison it performs, and the result only looks the
same.

**Never route around a script failure.** A non-zero exit is a stop, not a hint
to try another way. Report the failure with its output and wait for the
operator.

**Never skip a safeguard.** Validation, confirmation prompts, account checks and
the permissions-boundary rules are the product, not overhead.

## Scope

**Load the skill's own documents completely before acting.** A partially read
procedure produces a partially applied procedure, and the missing half is
usually a refusal.

**`md_create-git-template` must never change AWS IAM.** It authenticates and
scaffolds files; role and policy changes belong to
`md_upsert-aws-deployment-role`, which has the confirmations for them.

**Before changing AWS resources, explain the intended change and request
confirmation.** Destructive or production-impacting actions require an explicit
yes. State what will be created, what will be modified, and in which account and
region.

## Honesty about inputs

**Do not infer the task from repository files, Terraform modules, the current
directory, or a prior session unless the operator explicitly referred to them.**
An inferred target is the most expensive kind of mistake here: the run succeeds,
against the wrong repo.

**Never claim the operator referenced a file or module when they did not.** Ask.
