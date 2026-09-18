# Isolation — the credential hard ban, and the private environment

Two guarantees, both of which the deployer enforces in code rather than trusting the caller: the
credential this skill uses is only ever the one handed to it in the conversation, and running the
skill does not modify the host.

## The credential hard ban — do not weaken

> **This skill has NO authority over the operating system's AWS credentials.** It must **NEVER**
> read, use, or fall back to: any `AWS_*` environment variable (`AWS_ACCESS_KEY_ID`, `AWS_PROFILE`,
> `AWS_SESSION_TOKEN`, and every other one), the file `~/.aws/credentials` or `~/.aws/config`, the
> AWS CLI's resolved credentials, the **`default` profile**, **any** named profile that already
> exists on the machine, or an instance/SSO/role chain. The only credential it may ever touch is the
> one the operator hands it in this conversation. If you cannot get credentials from the operator,
> **ABORT** — never substitute anything from the system.

The consequence of weakening this is the entire reason the ban exists: an ambient credential resolves
to whichever account the machine happens to be pointed at, and this skill's whole job is to attach a
`Deny bedrock:*` to real principals. A breaker deployed to the wrong account is an outage in an
account nobody was looking at.

`assets/deploy.py` enforces it in four ways, in this order, before any AWS call is made:

1. **Credentials come from stdin only** — `key=value` lines fed by a heredoc — or from an interactive
   prompt when there is a TTY. Never from argv (the process list is world-readable), never from the
   environment. `_read_creds()` has no other branch and no fallback.
2. **Every ambient `AWS_*` variable is deleted from the process environment.** Scrubbing is by
   *prefix*, not by a list of names: an enumerated list quietly lets the container-credentials,
   web-identity and role-chain variables through, and those are exactly the paths the ban names.
3. **The metadata door is closed** — `AWS_EC2_METADATA_DISABLED` is set, and the shared credentials
   and config paths are pointed at a `.aws_hiatus_bedrock/` directory inside the skill folder that is
   deliberately never created. Any code path that still tries to resolve a profile finds an absent
   file rather than the operator's `~/.aws`.
4. **The credential is set explicitly on the botocore session**, which pins it as the only provider,
   so the resolver chain is never consulted at all.

**Nothing is written to disk.** The credential lives in one process's memory and dies with it — there
is no file to protect, no permissions to get right, and nothing to clean up if the process is killed
with `SIGKILL` before it can tidy up. No system profile — including any default profile — is read,
created, or modified.

Two things the operator must be told once, and only once:

- Anything pasted into chat is visible in the transcript, so they may want to rotate the key
  afterward.
- Each invocation needs its own credential heredoc, because nothing is cached between runs. Reuse the
  values already collected; do not ask again.

## The private environment

`assets/run.sh` is fully self-contained and does not disturb the host:

- On first run it creates a private virtualenv at `assets/.venv` from the system `python3`, then
  installs `assets/requirements.txt` — just `boto3` — into that venv only. System Python and global
  site-packages are never modified.
- On every later run it **reuses** that venv. It only re-resolves dependencies when
  `requirements.txt` changes, tracked by a SHA-256 stamp at `.venv/.requirements.sha`, so running the
  skill many times is cheap and repeatable.
- `deploy.py` always executes with `.venv/bin/python`, so behaviour does not depend on what is on the
  host.
- `run.sh` resolves its own directory from `BASH_SOURCE`, so it works from any working directory.

To reset the environment entirely, delete `assets/.venv` and run again.

**Always invoke `assets/run.sh`, never `assets/deploy.py`.** Called directly, `deploy.py` either runs
against whatever `boto3` the host happens to have — the one thing the venv exists to prevent — or
exits telling you to use `run.sh`.

## What must be git-ignored

Both of these are created inside the skill directory at run time and must never be committed.
`assets/.gitignore` covers them; keep it if you move the assets:

| Path | Why |
|---|---|
| `assets/.venv/` | a machine-specific environment, rebuilt on demand |
| `assets/.aws_hiatus_bedrock/` | never created by the current deployer, but the path botocore is pointed at — ignore it so a future change cannot commit one |

## Requirements

- `python3` on PATH with the standard-library `venv` module. `run.sh` does the rest.
- A credential with IAM, Budgets, Lambda, EventBridge and SNS permissions on the target account —
  the exact action list is in `references/permissions.md`.
