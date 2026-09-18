# Job — register the login client, in seven steps

Paths are relative to the skill directory. **You** run every command below as a
tool call. Never hand one to the user: the only thing asked of a human in this
whole job is clicking "Allow" in the browser that step 4 opens.

Behave like an intelligent interactive shell. Parse anything the user already
said, fill the gaps by asking, and route the result to the files in `assets/`.
Never silently reuse an existing app.

## Step 0 — parse the inline arguments first

The user may supply values inline, e.g.:

> `/register-sso-app name ABC url http://127.0.0.1:9034/oauth/callback`
> "create a new application called ABC with callback 127.0.0.1:3000/oauth/callback"

Extract from their message, in any phrasing:

- **name** — the app name (after "name", "called", "named", or an obvious quoted token).
- **url / callback** — one or more redirect URIs (after "url", "callback", "redirect").

Use whatever you found; only ASK for what's still missing. Don't re-ask for a
value the user already gave — a question whose answer is two lines above teaches
the user that the questions are noise.

## Step 1a — show the AWS target and existing apps, and let them switch accounts

Surface WHICH AWS account/SSO this will act on, so the skill is reusable across
accounts. List the SSO start URL, region, and existing application names:

```bash
bash assets/get_app_details.sh --list-apps --no-login
```

The skill carries NO company's AWS URL — the target is remembered PER PROJECT.

- If `--list-apps` works, this project already has a remembered target. Confirm
  with the user: "This project uses SSO **<ssoStartUrl>** (**<region>**). Existing
  apps: <names>. Use this, or switch?"
- If it errors with "No AWS SSO target set for this project", ASK the user for
  the SSO portal URL + region, then pass `--start-url <url> --region <r> --save`
  on the first call. `--save` writes them to `.create_new_app.conf` at the
  project root so future runs don't re-ask. (That file must be gitignored.)
- To switch accounts later, pass new `--start-url`/`--region` (add `--save` to
  make it stick), or edit `.create_new_app.conf`.

Skipping this step registers a client in whatever account the project last
remembered, which is the one mistake here that is invisible until a real user
cannot log in.

## Step 1b — show the existing redirect URLs, then ask "add more?"

List what redirect URLs are already configured so the user can decide:

```bash
bash assets/register_client.sh --list
```

Show that list back and ASK (`AskUserQuestion`):

- "These redirect URLs are configured: <list>. Do you want to **add more**, **keep
  as-is**, or **start fresh**?"
- If they add more, collect the new URL(s). Combine with the existing set via
  `--merge-existing` (step 5). If "start fresh", pass only the new
  `--redirect-uri` values.

A registered client's redirect set is **fixed at registration time**, so "add
another URL" means re-registering with the union of the old set and the new ones.
Registering with only the new URL silently breaks every login that used the old
one.

## Step 2 — resolve the app name

If not already parsed in step 0, ask:

> "What is the name of the app you want to create?"

Capture as `APP_NAME`.

## Step 3 — validate / normalize each callback URL

AWS only accepts a **127.0.0.1 loopback** URL in one of these exact forms
(verified against the API):

- `http://127.0.0.1:<port>/oauth/callback` — accepted
- `http://127.0.0.1:<port>` — accepted
- NOT `localhost`, NOT a bare `/callback`, NOT a trailing `/`, NOT a hosted
  domain (e.g. `app.example.com`), NOT wildcards — all rejected by AWS.

If the user gave `localhost`, silently suggest the `127.0.0.1` equivalent and
confirm. If they gave `/callback`, suggest `/oauth/callback`. Default when none
given: `http://127.0.0.1:9034/oauth/callback`.

`references/aws-facts.md` carries the rest of the verified rules, and
`assets/register_client.sh` enforces this one itself — it exits 1 with the
`localhost` and `/oauth/callback` hints rather than letting AWS reject the
registration with a vaguer message.

## Step 4 — create / reuse the IAM Identity Center application (idempotent)

```bash
bash assets/create_app.sh --name "<APP_NAME>" --no-login
```

Identity Center allows several applications with the same name, so the tool
dedupes by name itself and reuses the existing ARN rather than creating a
duplicate nobody can tell apart afterwards.

`--no-login` reuses the cached SSO token from step 1. Drop it — or run
`assets/authenticate.sh --persist` first — when there is no valid cached token;
that is the point where the browser opens and the user clicks "Allow".

## Step 5 — register / update the OIDC login client (this powers browser login)

Pass each chosen redirect URI. Add `--merge-existing` if the user wanted to ADD
to the current set rather than replace it:

```bash
bash assets/register_client.sh \
  [--merge-existing] \
  --redirect-uri "<URL_1>" [--redirect-uri "<URL_2>" ...] \
  --client-name "<APP_NAME>"
```

The tool reuses the stored client when it exists, has not expired, and the
requested redirect set is unchanged; it registers a fresh one only when something
actually changed. AWS has no list call for dynamically-registered public clients,
so a blind re-registration every run would orphan the previous client with no way
to find it again.

## Step 6 — report

Echo the Client ID, authorize/token endpoints, scope, and the FULL redirect set
now registered, and confirm they were written to the app's `.env` (the path the
tool printed). Note that with scope `sso:account:access` AWS returns an opaque
token (no role claims), so `VITE_OIDC_ALLOWED_ROLES` should stay blank unless a
separate role lookup exists.

Do **not** echo the client secret. It is written to the `.env` and belongs
nowhere else — a secret in a transcript is compromised and there is no way to
un-print it.

To read the whole login picture back for an existing app, including whether an
`authorization_code` grant is configured at all (`loginReady`):

```bash
bash assets/get_app_details.sh --name "<APP_NAME>" --no-login
```
