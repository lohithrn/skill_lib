# Job — interview, provision, report

Steps 1, 3 and 4 of the route. Step 2 is `jobs/scan-terraform.md` and it happens between them.

## Step 1 — interview

Use the invocation arguments to pre-fill; ask only for what is missing. Use `AskUserQuestion` for the
choice-style answers. Collect:

| # | Input | Rule |
|---|---|---|
| 1 | **component** | `frontend` or `backend` — no third value; the engine rejects one |
| 2 | **stage** | `beta` or `prod` — it decides the region and whether a prod guardrail is added |
| 3 | **repo-name** | the logical name used in AWS resource naming; it is lower-cased and non-alphanumerics become `-` |
| 4 | **repo source** | either a local path to a checked-out repo **or** a remote GitHub URL with an optional branch. Confirm a local path exists |
| 5 | **user-name** | the IAM user CI assumes the role as. Offer `<ORG>_<STAGE>_<COMPONENT>_DEPLOYMENT` as a default shape, filled from the user's own convention |
| 6 | **AWS profile** | list the named profiles, ask which one, verify it — see below |

For the repo source: a **local folder is used in place and never deleted**; only a clone the engine made
itself is cleaned up afterwards. Deleting a user's working folder because the input was ambiguous is
unrecoverable, so the two forms are classified explicitly, never guessed.

### The profile is chosen by the user, verified by you

1. List the named profiles with `aws configure list-profiles`.
2. Ask which one. Never choose for the user, and never accept `default` — see the refusals in
   `references/naming-and-gates.md`.
3. Verify with `aws sts get-caller-identity --profile <profile>`.
4. If that fails, run `aws sso login --profile <profile>` and verify again.
5. Use the **verified** account id for `--account`. Never type an account id from memory or from a
   document: a wrong account id turns the account check into theatre.

Do not create, rewrite or delete the selected profile. The engine reads it and leaves it exactly as it
found it.

## Step 2 — scan

Follow `jobs/scan-terraform.md`. Come back with `/tmp/<repo>-<stage>-policy.json`, optionally
`/tmp/<repo>-<stage>-boundary.json`, and the user's confirmation of the policy.

## Step 3 — run the engine with your policy

```bash
python3 assets/create_deployment_role.py \
  --component <component> --stage <stage> \
  --repo-name <repo-name> --repo-path <repo-path> \
  --user-name <user-name> --region <stage-region(s)> \
  --sso-profile <selected-profile> --account <verified-account-id> \
  --policy-file /tmp/<repo>-<stage>-policy.json \
  --boundary-file /tmp/<repo>-<stage>-boundary.json \
  --yes
```

The path is relative to this skill directory. Substitute `--repo-url <url> --branch <branch>` for
`--repo-path` when the user gave a remote repo.

| Flag | Why it is there |
|---|---|
| `--policy-file` | makes the engine use **your** scanned policy verbatim and bypass its static analyzer. That bypass is the point of this skill |
| `--boundary-file` | pairs with `--policy-file`. Omit both files and the engine falls back to its own generators |
| `--region` | pass the stage-correct region(s) you determined, so nothing is ambiguous. Detected regions are appended, not replaced |
| `--account` | the verified account id. The engine still asks whether that account is the right place |
| `--yes` | accepts the default answer at each confirmation. It does **not** enable any reduction or any key creation |

Do **not** add `--create-access-key` unless the user asked to mint or rotate a CI key and confirmed it
separately. Do **not** add `--allow-reduce` unless the user asked to remove permissions and understands
that three confirmations follow. Do **not** add `--trust-root` unless the user asked for the account-root
escape hatch; the CI user and the human caller's own role are trusted without it.

If the engine exits non-zero, stop. Print its real error output and the likely cause. Do not perform the
failed operation another way.

## Step 4 — report

Surface the engine's output, then give the user the two things a CI pipeline needs:

1. the **CI user name**, and
2. the **role ARN** to assume:
   `arn:aws:iam::<account-id>:role/<repo>-<component>-<stage>-deploy-role`.

If the Terraform creates IAM roles, remind them that every `aws_iam_role` must set

```hcl
permissions_boundary = "arn:aws:iam::<account-id>:policy/<repo>-<component>-<stage>-deploy-boundary"
```

or the apply is denied. That denial reads as a generic `AccessDenied` on `iam:CreateRole` and costs an
afternoon to attribute if nobody was told.

If anything failed, show the real terraform `Error:` line, not a paraphrase, and name the likely cause.
