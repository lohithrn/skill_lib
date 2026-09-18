---
name: md_register-sso-app
description: Register an OIDC login client in AWS IAM Identity Center so an app's "Login with AWS" button authenticates real users, and return the VITE_OIDC_CLIENT_ID and VITE_OIDC_ISSUER values the frontend needs. Use when the user wants to create or register a new app with AWS, set up AWS SSO login, add another loopback redirect URL, or read back an application's login details. Never Amazon Cognito.
when_to_use: An app needs AWS IAM Identity Center login wired up — a new OIDC client, one more redirect URL, or the client id, issuer and endpoints for the frontend .env.
argument-hint: "[app-name] [redirect-url]"
allowed-tools: Read, Grep, Glob, AskUserQuestion, Bash(bash:*), Bash(aws:*), Bash(jq:*), Bash(ls:*), Bash(cat:*)
---

# register-sso-app

> **HARD CONSTRAINT — NEVER USE AMAZON COGNITO.**
> This project does NOT use Cognito, ever, under any circumstance. Do not
> suggest it, scaffold it, or "fall back" to it. The entire point is to make
> login work directly against AWS IAM Identity Center. If Identity Center
> appears to be missing a capability, keep investigating IdC itself (trusted
> token issuer, OIDC/OAuth endpoints, application config) until it works — do
> not pivot to another service.

You are an **intelligent interactive shell**. This skill registers an **OIDC login
client** in AWS IAM Identity Center so an app's "Login with AWS" button can
authenticate real users. You are the micro-intelligence layer; the shell files in
`assets/` are the tools. Parse anything the user already said, fill the gaps by
asking, and route the result to the tools — which **you** run, as your own tool
calls.

Every path in this file is relative to this skill directory.

## The gate — read this first

This skill writes to a **real AWS account** and opens a browser. Read
`${CLAUDE_PLUGIN_ROOT}/references/CROWBAR.md` — the plugin-level operating
doctrine, a sibling of the `skills/` directory this skill lives in — before the
first AWS call, then these non-negotiables:

- **Never use Amazon Cognito.** See the constraint above. A Cognito "fallback"
  silently replaces the identity source the whole product authenticates against,
  and every user account already provisioned in Identity Center becomes invisible.
- **NEVER instruct the user to run a script or a shell command.** The user only
  answers questions. You run every file in `assets/` yourself, as a tool call. A
  skill that hands back a command line has done none of the work it exists for,
  and the user has to become the operator they asked you to be.
- **The single unavoidable human action is clicking "Allow" in the browser** when
  AWS SSO opens. You trigger that by running `assets/authenticate.sh`; it is
  never *asked* of the user as a command.
- **Never silently reuse an existing app.** Show the existing application names
  and the existing redirect set, then ask. Reusing one without asking rewrites the
  login configuration of an app someone else is already using.
- **Run the files in `assets/`; do not reconstruct them from AWS CLI calls.** They
  carry the SSO-only credential policy, the disposable-profile isolation, the
  idempotent reuse, the empirically-verified redirect validation and the `.env`
  upsert. A CLI reconstruction has none of them and looks identical until it
  orphans a client or clobbers an `.env`.
- **Authenticate through SSO only.** Every file unsets ambient AWS credentials
  before it starts and logs in through a randomly-named, disposable profile in a
  temp config, so `~/.aws/config` is never read or modified. Ambient static keys
  mean the client lands in whichever account the last tool left behind.
- **Stop on any non-zero exit.** Report the real error text. Never finish a failed
  registration another way — a client half-registered by two mechanisms cannot be
  reasoned about, and AWS offers no list call to find the orphan.
- **Never print a client secret into the transcript.** It is written to the app's
  `.env` by the tool that receives it, and nowhere else.

## Route

| Step | Read | Produces |
|---|---|---|
| 0. Parse what the user already said | `jobs/register.md` | the app name and any redirect URLs already given, so nothing is re-asked |
| 1. Show the AWS target, the apps, the redirects | `jobs/register.md` | a confirmed SSO start URL + region, the existing app names, the current redirect set |
| 2. Resolve the app name | `jobs/register.md` | `APP_NAME` |
| 3. Validate every callback URL | `references/aws-facts.md` | loopback URLs AWS will actually accept |
| 4. Create or reuse the application | `jobs/register.md` | the IAM Identity Center application ARN, idempotently |
| 5. Register or update the login client | `jobs/register.md` | the client id, the endpoints, the full redirect set, the written `.env` |
| 6. Report | `jobs/register.md` | client id, endpoints, scope, every registered redirect, and the roles caveat |

Do the steps in order. Step 1 exists so the user can see and switch the account
*before* anything is created; skipping it registers a client in whatever account
the project last remembered.

## The tools in `assets/`

Six shell files, each independently runnable. The reusable building block is
`assets/authenticate.sh`; the others call it.

| File | Responsibility |
|---|---|
| `assets/authenticate.sh` | SSO ONLY (ignores static creds). Disposable random profile in a temp config; opens the browser; auto-discovers account/role/instance. With `--persist` emits temporary AWS creds + `AWS_INSTANCE_ARN`/`AWS_OIDC_ISSUER` as KEY=VALUE on stdout (human messages → stderr). |
| `assets/create_app.sh` | Creates/ensures the IAM Identity Center **application** (idempotent — reuses by name). Writes NO `.env` and configures no grant — that's `register_client.sh`'s job. |
| `assets/register_client.sh` | Registers the **OIDC login client** (the thing that actually drives browser login) at `oidc.<region>.amazonaws.com/client/register`, and writes the client id, endpoints, scope, secret, and redirect(s) to the app's `.env`. Supports `--list`, `--merge-existing`. |
| `assets/get_app_details.sh` | Read-only. `--list-apps` (all app names + SSO target) or `--name <n>` (full login-details JSON, `loginReady`). |
| `assets/_lib.sh` | Shared output/helpers + AWS target defaults (sourced, not executed). |
| `assets/config.sh` | Every non-secret default, in one place. No secrets, ever. |

The application and the login client are **two different objects**, and confusing
them is the single most expensive mistake here: the `apl-…` application id does
not drive browser login. `references/aws-facts.md` has the proof and the rest of
the verified AWS behaviour.

## The full flow you drive

```bash
bash assets/authenticate.sh --persist
bash assets/create_app.sh --name "<APP_NAME>"
bash assets/register_client.sh [--merge-existing] --redirect-uri "<127.0.0.1 URL>"
```

1. `assets/authenticate.sh --persist` → SSO login + discovery (browser opens once).
2. `assets/create_app.sh --name <APP>` → create/ensure the application.
3. `assets/register_client.sh [--merge-existing] --redirect-uri <127.0.0.1 URL>` →
   register the login client and write the `.env`.

`assets/authenticate.sh` opens the browser **by default** — it logs in unless
`--no-login` is given. Reuse a cached token with `--no-login`. There is **no
`--login` flag**; passing one exits 1 on an unknown option.

## Index of the other files

| File | Answers |
|---|---|
| `jobs/register.md` | the seven steps, the questions to ask, and the exact command for each |
| `references/aws-facts.md` | every empirically-verified AWS rule: the loopback forms, the scope, the opaque token, the application-vs-client split, the endpoints, the required permissions |
| `references/config-and-portability.md` | `config.sh`, the per-project remembered SSO target, `.env` auto-detection, the disposable-profile naming, and the full flag table |
| `assets/` | the six shell files above — the only things that talk to AWS |

## What this does NOT do

- **It does not use Amazon Cognito, ever, under any circumstance.** Not as a
  suggestion, not as a scaffold, not as a fallback. When Identity Center looks
  short of a capability, keep investigating Identity Center — trusted token
  issuer, OIDC/OAuth endpoints, application config — until it works.
- **It does not tell the user to run a command.** You run every file in `assets/`
  as your own tool call. The user answers questions and clicks "Allow" in the
  browser once; that browser approval is the only human action in the whole flow.
- **It does not mint a certificate or a keypair for authentication.** The auth is
  an SSO browser login plus the temporary role credentials it issues. Nothing is
  generated locally.
- **It does not touch `~/.aws/config` or reuse a named profile.** Every run builds
  a disposable random profile in a temp config and logs out on exit unless
  `--persist` is set.
- **It does not create AWS accounts, SSO instances, permission sets or user
  assignments.** It registers an application and a login client in an instance
  that already exists.
- **It does not grant roles.** With scope `sso:account:access` AWS returns an
  opaque access token with no role claims, so `VITE_OIDC_ALLOWED_ROLES` stays
  blank unless a separate role lookup exists.
- **It does not print a client secret.** The secret goes to the app's `.env` and
  never into the transcript.
