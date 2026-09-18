# Job — scaffold a repo, in four steps

Paths are relative to the skill directory.

## Step 1 — auth, both halves

**GitHub.** Check the CLI's auth status. If the user is not logged in, do not log in for them: tell them
to run the GitHub CLI login themselves, then continue once they confirm. The engine performs the same
check and dies with the same instruction, so a run that skips this fails later and more confusingly.

GitHub auth is only needed when the source is a **remote URL**. An existing local folder needs no GitHub
access at all.

**AWS.** In this order:

1. List the named profiles: `aws configure list-profiles`.
2. Show them and ask which one to use. Never choose for the user; never accept `default`.
3. Verify that one selection: `aws sts get-caller-identity --profile <profile>`.
4. If it fails, run `aws sso login --profile <profile>` and verify again.
5. Use the verified account id for this run. Never use an account id obtained from another profile or
   from memory — it is written into the scaffolded repo and read by every later deploy.

The engine refuses an empty profile and refuses `default` outright, and it strips ambient credential
variables from the environment it passes to the AWS CLI so an exported key cannot override the profile.

## Step 2 — collect the inputs

Use `AskUserQuestion` for the choice-style answers.

| # | Input | Rule |
|---|---|---|
| 1 | **repository source** | either a GitHub repo URL **or** an absolute path to an existing local Git folder. Confirm which one, and confirm the clone target or the folder |
| 2 | **branch** | the existing branch to update, or a new branch to create. Confirm before checkout or creation |
| 3 | **type** | one of `frontend`, `frontend_lib`, `backend_service`, `backend_lib` — see the table in SKILL.md |
| 4 | **project-name** | defaults to the repo name; ask only if the user wants it to differ |
| 5 | **the type's tokens** | read `assets/templates/<type>/TOKENS.md` and collect **only** the tokens that file lists |

Two rules that matter more than they look:

- **A URL is cloned; a local folder is used in place.** The engine classifies the two explicitly and
  refuses a destination that exists and is non-empty. It asks for confirmation before touching an
  existing folder, because scaffolding into the wrong checkout overwrites work that was never committed.
- **Do not ask for tokens the chosen template does not use.** `references/repo-types.md` says which type
  needs what. Asking for an ACM certificate ARN for a library repo teaches the user that the questions
  are noise.

## Step 3 — run the scaffolder

```bash
python3 assets/setup_new_repo.py \
  [--repo-url <repo-url> | --repo-path <absolute-local-folder>] \
  --branch <branch> --type <type> \
  --project-name <name> \
  --deployment-tenant-profile <stable-identity> \
  --sso-start-url <start-url> \
  [--domain-name <domain>] \
  [--package-name <pkg>] \
  --aws-profile <selected-profile> \
  --account <verified-account-id> \
  -y
```

Pass everything you gathered rather than letting the engine prompt, so the run needs no TTY. For the
tokens with no flag — the certificate ARNs, the publish buckets, the ECR repo name, the CI deploy role
name — the engine prompts with a convention-based default; answer from what the user gave you.

| Flag | Why |
|---|---|
| `--deployment-tenant-profile` | the stable identity that names persisted resources. No default; an empty value aborts |
| `--sso-start-url` | no default either. Unset leaves the fail-loud placeholder rather than pointing the repo at some other organisation |
| `--account` | the verified account id, written into the scaffolding |
| `--branch` | checked out or created before anything is copied |
| `-y` | accepts the default answer at each confirmation. It does not skip the account verification |

If the engine reports unresolved tokens, surface the whole list. Do not patch the files yourself: the
placeholder is designed to break the build until a human fills it in, and quietly fixing three of five
leaves the other two looking intentional.

## Step 4 — stop, then report

Stop after the template work. Do not run a deployment-role provisioner and do not make AWS IAM changes.
If the user also needs a deploy role, offer the `md_upsert-aws-deployment-role` skill as a separate next
action.

The report covers, in this order:

1. the repository or folder, and the branch;
2. the type, the selected profile, and the verified account;
3. the file list the engine wrote, with the count;
4. every unresolved token, and the instruction to search for `>>>UNSET_`;
5. next steps — review the scaffolding, add the application code, commit and push;
6. an explicit statement that **this run made no AWS IAM changes**.

Point 6 is not a courtesy. It is the sentence that lets a reviewer skip an IAM audit for this change.
