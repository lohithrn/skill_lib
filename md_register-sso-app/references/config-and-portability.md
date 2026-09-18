# Configuration, portability, and every flag

Paths are relative to the skill directory.

## `assets/config.sh` — all non-secret defaults, one file

Edit `assets/config.sh` to retarget the skill. No code changes, no environment
variables. It holds:

| Key | Ships as | What it controls |
|---|---|---|
| `PROJECT_TARGET_FILE` | `.create_new_app.conf` | the per-project cache file name for the remembered SSO target |
| `OIDC_SCOPE` | `sso:account:access` | the scope requested at login. Identity Center rejects `openid`/`profile`/`email` |
| `DEFAULT_CLIENT_NAME` | `app-login` | the login client name when `--client-name` is not given |
| `DEFAULT_REDIRECT_URI` | `http://127.0.0.1:9034/oauth/callback` | the redirect used when none is supplied and nothing is merged |
| `ENV_FILE_PATH` | empty (auto-detect) | force a specific `.env` path instead of auto-detecting one |

**No secrets ever go in `assets/config.sh`.** Client secrets and tokens are issued
by AWS at run time and written to the app's `.env`, never here. A secret in a
config file is a secret in the repo, and there is no way to un-commit it.

A per-invocation flag (`--start-url`, `--region`, `--env-file`, …) always overrides
`assets/config.sh`. `assets/_lib.sh` also carries a built-in fallback for each
value, which applies only when `config.sh` is missing or a value is unset.

## The AWS target is remembered per project, not shipped

`assets/config.sh` deliberately holds **no SSO start URL and no region**. This
skill is used across many projects and accounts, so it carries no company's AWS
URL. The target is asked for once per project and cached:

1. Explicit `--start-url` / `--region` flags win.
2. Otherwise the project's `.create_new_app.conf` is read from the project root.
3. Otherwise the tool exits **2** with "No AWS SSO target set for this project"
   and names the file to create. It never guesses an account.

`--save` writes the pair into that file. Gitignore it. To switch accounts, pass a
new `--start-url`/`--region` (with `--save` to make it stick) or edit the file.

**The project root is the nearest ancestor of the current working directory that
contains `.git`, else the working directory itself.** The anchor is the working
directory and not the skill's own folder, because the skill is installed once into
a shared library and run from many projects — anchoring on the skill folder would
write every project's remembered target and `.env` into the skill library instead
of the project being worked on.

## Where the `.env` is written

`resolve_env_file` picks the target in this order, and never assumes a fixed
folder depth:

1. an explicit `--env-file` path — honoured as-is;
2. `ENV_FILE_PATH` from `assets/config.sh` — absolute as-is, relative to the
   project root otherwise;
3. the first of `frontend/`, `web/`, `app/`, `client/`, `ui/` that exists under the
   project root, writing `<dir>/.env`;
4. `<project root>/.env`.

Keys are upserted, not appended: an existing `KEY=` line is filtered out and the
new value appended. The filter is deliberately **not** a `sed` substitution,
because a value containing `|`, `&` or `\` would corrupt one. And a `grep` exit
status above **1** aborts the upsert with the `.env` left unchanged — exit 1 only
means "every line was filtered", which is legitimate, but anything higher is a
real read error and writing the temp file over the `.env` would empty it.

## The credential policy, and why the profile is disposable

Every tool calls `unset_aws_static_creds` before it does anything, clearing
`AWS_ACCESS_KEY_ID`, the secret key, `AWS_SESSION_TOKEN`, `AWS_SECURITY_TOKEN`,
`AWS_PROFILE`, `AWS_DEFAULT_PROFILE`, `AWS_CONFIG_FILE` and
`AWS_CREDENTIAL_EXPIRATION`. Login can then happen **only** through SSO.

`assets/authenticate.sh` writes a random `sso-session` + profile into a **temp**
config file and points the CLI at it, so `~/.aws/config` is never read or
modified and no existing named profile is reused. The profile name is
`<prefix>-ephemeral-<rand>`:

- `<prefix>` is the project root folder's name, lowercased, reduced to `[a-z0-9-]`,
  collapsed on repeated `-`, trimmed, and cut to **40** characters; it falls back
  to `app` if the folder name sanitizes to nothing.
- `<rand>` is 6 characters from `/dev/urandom`, falling back to the process id.

On exit it logs out and deletes the temp config — unless `--persist` was given, in
which case the caller owns cleanup. The account and role are auto-discovered from
what the login grants; if several are available the tool prompts, and
non-interactively it takes the first and says so.

**The SSO token is picked as the newest still-valid cache entry for that start
URL.** There can be several cache files for the same portal from older logins, so
the tool sorts the matching entries by `expiresAt` descending and takes the first
whose expiry is in the future. Taking any match would hand back a stale token,
which surfaces as "Session token not found or invalid" much later; the fix is to
clear the stale entries with `rm -f ~/.aws/sso/cache/*.json` and re-run.

Human messages go to **stderr** in every tool; **stdout** carries only
machine-readable `KEY=VALUE` lines (or JSON). Mixing the two corrupts the stream
the calling tool parses.

`assets/authenticate.sh` emits, on stdout: `AWS_PROFILE`, `AWS_ACCOUNT_ID`,
`AWS_ROLE_NAME`, `AWS_INSTANCE_ARN`, `AWS_IDENTITY_STORE_ID`, `AWS_OIDC_ISSUER`,
plus `AWS_CONFIG_FILE` and the three temporary credential variables under
`--persist`. Those credentials are temporary SSO-issued ones scoped to the role
just logged into; they expire with the session and there is nothing to delete.

## Every flag

`assets/authenticate.sh`

| Flag | Effect |
|---|---|
| `--start-url <url>` | SSO portal URL. No default — from the flag or the project's remembered target |
| `--region <r>` | SSO region |
| `--save` | remember this start URL + region for the project |
| `--persist` | don't clean up on exit (the caller will); also emits the temporary credentials |
| `--no-login` | fail instead of opening the browser if no token is cached |
| `--dry-run` | don't call AWS; emit placeholder values |
| `-h`, `--help` | show the header block as help |

`assets/create_app.sh`

| Flag | Effect |
|---|---|
| `--name <name>` | app name; required, prompted if absent and a TTY is attached |
| `--instance-arn <arn>` | supply the IdC instance ARN and skip discovery |
| `--start-url <url>`, `--region <r>`, `--save` | forwarded to `assets/authenticate.sh` |
| `--no-login` | pass through: use the cached token, don't open the browser |
| `--skip-auth` | don't authenticate. **Test-only — requires `--dry-run`**, and is refused without it |
| `--dry-run` | print the AWS commands instead of executing them |

`assets/register_client.sh`

| Flag | Effect |
|---|---|
| `--redirect-uri <uri>` | a 127.0.0.1 loopback redirect URI. **Repeatable** |
| `--merge-existing` | union the new URIs with the stored set, order-preserving and deduped |
| `--list` | print the currently-configured redirect URIs and exit |
| `--env-file <path>` | the `.env` to write; overrides auto-detection |
| `--region <r>`, `--start-url <url>` | the sso-oidc region and the portal URL used as `issuerUrl` |
| `--client-name <name>` | client name; defaults to `DEFAULT_CLIENT_NAME` |
| `--dry-run` | print what would happen; call no AWS and write no files |

`assets/get_app_details.sh` — read-only, creates and changes nothing

| Flag | Effect |
|---|---|
| `--name <name>` | the app to look up; required unless `--list-apps` |
| `--list-apps` | every application name in the instance plus the SSO start URL, region and instance ARN, as JSON, then exit |
| `--json-only` | print only the JSON dictionary, no human summary |
| `--start-url <url>`, `--region <r>` | forwarded to `assets/authenticate.sh` |
| `--no-login` | reuse a cached SSO token; don't open the browser |
| `--dry-run` | don't call AWS; emit placeholder output |

There is **no `--login` flag** anywhere: `assets/authenticate.sh` logs in by
default. An unknown option exits **1** with the usage block.
