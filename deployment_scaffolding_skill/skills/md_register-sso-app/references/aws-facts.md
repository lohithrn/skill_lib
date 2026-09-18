# What AWS IAM Identity Center actually does

Every rule below was verified against the live API, not assumed. They are the
reason the tools in `assets/` are shaped the way they are; each one states what
breaks when it is ignored.

## The application and the login client are two different objects

| Object | Created by | Id shape | Drives browser login? |
|---|---|---|---|
| IdC **application** | `sso-admin create-application` (`assets/create_app.sh`) | `apl-…`, the last ARN segment | **no** |
| **OIDC login client** | a POST to `oidc.<region>.amazonaws.com/client/register` (`assets/register_client.sh`) | the `clientId` the endpoint returns | **yes** |

The browser logs in against the **dynamically registered OIDC client**, not the
`sso-admin` application. This was proven by hitting `/authorize` with the
resulting `client_id` and watching it redirect to the company's real sign-in page.
Wiring the `apl-…` application id into the frontend produces a login page that
never authenticates anybody, and the error surfaces as a generic invalid-client
response with nothing pointing at the cause.

Two consequences the tools encode:

- `assets/create_app.sh` writes **no** `.env` and configures **no** grant. Login
  config has exactly one owner, `assets/register_client.sh`, so the two tools
  cannot fight over the same `.env` keys.
- `/client/register` must be called **server-side**. The browser is CORS-blocked
  on it; `/token` does allow CORS. A frontend that tries to self-register gets a
  CORS failure that looks like a network outage.

## The redirect URI rules

AWS accepts a **127.0.0.1 loopback** URI only, in one of exactly two forms:

- `http://127.0.0.1:<port>/oauth/callback`
- `http://127.0.0.1:<port>`

Everything else is rejected:

| Rejected | Why it matters |
|---|---|
| `localhost` | resolves to the same host and reads as equivalent, and AWS still refuses it — "must use loopback interface for redirect" |
| a bare `/callback` | the path must be `/oauth/callback` or empty; nothing else |
| a trailing `/` | rejected as a non-loopback form, with the same vague message |
| a hosted domain | there is no hosted-redirect option for this client type at all |
| wildcards | never accepted |

The loopback IP **and an explicit port** are both required. Multiple loopback URIs
in one client are allowed.

`assets/register_client.sh` validates this itself and exits **1** with a targeted
hint (replace `localhost` with `127.0.0.1`; use `/oauth/callback`, not
`/callback`) rather than letting AWS answer with its own wording, which names
neither the offending URI nor the fix.

## The redirect set is fixed at registration time

There is no "add a redirect URI" call. Adding one means **re-registering with the
union** of the stored set and the new values — that is what `--merge-existing`
does, order-preserving and deduped. `--list` prints the stored set so the choice
can be put to the user first.

The full set is persisted to `VITE_OIDC_REDIRECT_URIS` (space-separated) precisely
so a later `--merge-existing` run knows every URI the client was registered with.
`VITE_OIDC_REDIRECT_URI` (singular) is the primary one the frontend uses, and is
read as a fallback for older `.env` files.

## Client registration facts

| Field | Required value | Consequence of anything else |
|---|---|---|
| `clientType` | `"public"` | `confidential` is rejected at `/client/register` |
| `grantTypes` | `["authorization_code","refresh_token"]` | no other combination completes a browser flow |
| `scopes` | `["sso:account:access"]` | `openid`/`profile`/`email` are rejected at `/authorize` |
| `issuerUrl` | the portal start URL | a different issuer fails the flow |

`/client/register` is **unauthenticated** — self-registration is how the endpoint
is meant to be used — so no SSO token and no extra IAM permission is needed for
that call. That is also why the browser is blocked from it.

## The token has no role claims

Scope `sso:account:access` returns an **opaque access token**, not an OIDC
`id_token`. There are therefore no role claims to read. Leave
`VITE_OIDC_ALLOWED_ROLES` blank unless a separate role lookup is added; a
role-gated UI built on claims that do not exist either locks everyone out or lets
everyone in, depending on how the empty list is interpreted.

## The endpoints, derived per region

For `OIDC_BASE = https://oidc.<region>.amazonaws.com`:

| Key written to `.env` | Value |
|---|---|
| `VITE_OIDC_CLIENT_ID` | the registered `clientId` |
| `VITE_OIDC_AUTH_ENDPOINT` | `OIDC_BASE/authorize` |
| `VITE_OIDC_TOKEN_ENDPOINT` | `OIDC_BASE/token` |
| `VITE_OIDC_SCOPES` | `sso:account:access` |
| `VITE_OIDC_REDIRECT_URI` | the primary loopback URI |
| `VITE_OIDC_REDIRECT_URIS` | the full registered set, space-separated |
| `VITE_OIDC_CLIENT_SECRET` | the secret the endpoint returned, if any |
| `VITE_OIDC_CLIENT_SECRET_EXPIRES_AT` | epoch seconds, so a later run can reuse the client instead of orphaning it |

The issuer is `https://identitycenter.amazonaws.com/<instance-id>`, where the
instance id is the last segment of the Identity Center instance ARN.

The client secret AWS returns for a public client is a low-sensitivity client
credential, not a user secret, and it is needed for the code exchange at the token
endpoint. It is written to the app's `.env` and must never be echoed into a
transcript or committed.

## Prerequisites

- AWS CLI **v2** and `jq` installed. Each tool checks and exits **2** with the
  install hint rather than failing halfway through a registration.
- An IAM Identity Center permission set / role that can call `sso:ListInstances`,
  `sso:CreateApplication` and `sso:ListApplications`. Without `sso:ListInstances`
  the discovery step exits **3** and says so: the role either lacks the permission
  or is not in the account that owns the portal.
- No extra permission for the client registration itself — that endpoint is
  unauthenticated.

## Exit codes, the same in every tool

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | usage error (including an invalid redirect URI, and `--skip-auth` without `--dry-run`) |
| 2 | missing prerequisite, or no AWS SSO target set for this project |
| 3 | auth, discovery, lookup or registration failed |

Treat any non-zero exit as a stop. `assets/create_app.sh` refuses `--skip-auth`
without `--dry-run` outright, because that combination would call AWS
unauthenticated.
