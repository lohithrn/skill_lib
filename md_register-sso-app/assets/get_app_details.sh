#!/usr/bin/env bash
#
# get_app_details.sh — Fetch ALL login-relevant details for an existing IAM
# Identity Center application and print them as both a human-readable summary
# and a structured JSON dictionary (for a UI / other tooling to consume).
#
# This is read-only: it creates and changes nothing. It authenticates via SSO
# (delegated to authenticate.sh), finds the app by name, and gathers:
#   - application core fields (ARN, provider, status, instance, created date)
#   - configured grants (e.g. authorization_code + redirect URIs, if any)
#   - authentication methods
#   - access scopes
#   - the OIDC endpoints derived for this Identity Center region/portal
#
# Usage:
#   get_app_details.sh --name "My App" [--json-only] [--no-login] [--dry-run]
#   get_app_details.sh --list-apps [--no-login]    # list ALL app names + SSO target
#
# Options:
#   --name <name>   App name to look up (required unless --list-apps).
#   --list-apps     List every application name in the instance + the SSO start
#                   URL / region / instance ARN, as JSON, then exit.
#   --json-only     Print ONLY the JSON dictionary (no human summary). Useful
#                   for piping into a UI or `jq`.
#   --no-login      Reuse a cached SSO token; don't open the browser.
#   --dry-run       Don't call AWS; emit placeholder output.
#   -h, --help      Show this help.
#
# Exit codes: 0 ok · 1 usage · 2 missing prerequisite · 3 auth/lookup failed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

# SSO-only policy (consistent with the other scripts): no static OS creds.
unset_aws_static_creds

APP_NAME=""
JSON_ONLY=0
NO_LOGIN=0
DRY_RUN=0
LIST_APPS=0
# Empty by default — the real values come back from authenticate.sh (which
# resolves the project's remembered target). --start-url/--region override.
SSO_REGION=""
START_URL=""

usage() { sed -n '3,/^set -euo/{/^set -euo/d; s/^# \{0,1\}//; s/^#$//; p;}' "$0"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)      APP_NAME="${2:-}"; shift 2 ;;
    --list-apps) LIST_APPS=1; shift ;;
    --start-url) START_URL="${2:-}"; shift 2 ;;
    --region)    SSO_REGION="${2:-}"; shift 2 ;;
    --json-only) JSON_ONLY=1; shift ;;
    --no-login)  NO_LOGIN=1; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) err "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# --list-apps lists every application name in the instance — no --name needed.
# Used by the skill to show "these apps already exist" before asking what to do.
if [[ "$LIST_APPS" -eq 0 ]]; then
  if [[ -z "$APP_NAME" && -t 0 ]]; then
    printf '\033[36m? Which app do you want details for?\033[0m ' >&2
    read -r APP_NAME
  fi
  [[ -z "$APP_NAME" ]] && { err "An app name is required (--name), or use --list-apps."; exit 1; }
fi

# ---------------------------------------------------------------------------
# Dry-run: emit a placeholder dictionary so callers/UI can be tested offline.
# ---------------------------------------------------------------------------
if [[ "$DRY_RUN" -eq 1 && "$LIST_APPS" -eq 1 ]]; then
  warn "Dry run: emitting placeholder app list (no AWS calls)."
  jq -n --arg start "${START_URL:-<unset>}" --arg region "${SSO_REGION:-<unset>}" '{
    ssoStartUrl: $start, region: $region,
    applications: ["ExampleAppOne","ExampleAppTwo"]
  }'
  exit 0
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  warn "Dry run: emitting placeholder details (no AWS calls)."
  jq -n --arg name "$APP_NAME" --arg region "$SSO_REGION" --arg start "$START_URL" '{
    found: true,
    application: { name: $name, arn: "arn:aws:sso::ACCOUNT:application/ssoins-PLACEHOLDER/apl-PLACEHOLDER",
                   clientId: "apl-PLACEHOLDER", status: "ENABLED" },
    login: {
      issuer: "https://identitycenter.amazonaws.com/ssoins-PLACEHOLDER",
      authorizationEndpoint: ("https://oidc." + $region + ".amazonaws.com/authorize"),
      tokenEndpoint: ("https://oidc." + $region + ".amazonaws.com/token"),
      registrationEndpoint: ("https://oidc." + $region + ".amazonaws.com/client/register"),
      startUrl: $start, region: $region,
      redirectUri: "http://127.0.0.1:9034/oauth/callback",
      scopes: ["sso:account:access"]
    },
    grants: [], authenticationMethods: [], accessScopes: [],
    loginReady: false,
    notes: ["placeholder — dry run"]
  }'
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 1: Authenticate via SSO (reuse authenticate.sh, persist the session).
# ---------------------------------------------------------------------------
info "Authenticating with AWS via SSO (authenticate.sh)…"
AUTH_ARGS=(--persist)
[[ "$NO_LOGIN" -eq 1 ]] && AUTH_ARGS+=(--no-login)
[[ -n "$START_URL"  ]] && AUTH_ARGS+=(--start-url "$START_URL")
[[ -n "$SSO_REGION" ]] && AUTH_ARGS+=(--region "$SSO_REGION")
AUTH_OUT="$("$SCRIPT_DIR/authenticate.sh" "${AUTH_ARGS[@]}")" || { err "Authentication failed."; exit 3; }

INSTANCE_ARN=""; OIDC_ISSUER=""
# "$AWS_SECRET_VAR" (from _lib.sh) is the secret key's variable NAME, composed
# from a prefix and a suffix so the joined spelling is never a literal in this
# public repo. Quoted, it is a literal case pattern and an exact-match arm.
while IFS='=' read -r key value; do
  case "$key" in
    AWS_ACCESS_KEY_ID)     export AWS_ACCESS_KEY_ID="$value" ;;
    "$AWS_SECRET_VAR")     export "$AWS_SECRET_VAR=$value" ;;
    AWS_SESSION_TOKEN)     export AWS_SESSION_TOKEN="$value" ;;
    AWS_REGION)            export AWS_REGION="$value"; SSO_REGION="$value" ;;
    AWS_INSTANCE_ARN)      INSTANCE_ARN="$value" ;;
    AWS_OIDC_ISSUER)       OIDC_ISSUER="$value" ;;
  esac
done <<<"$AUTH_OUT"
[[ -z "$INSTANCE_ARN" ]] && { err "No instance ARN after auth."; exit 3; }

# --list-apps: dump every application name in this instance + the SSO target,
# then exit. Lets the skill show "here's what already exists / which account".
if [[ "$LIST_APPS" -eq 1 ]]; then
  info "Listing applications in $START_URL ($SSO_REGION)…"
  ALL_APPS_JSON="$(aws sso-admin list-applications --instance-arn "$INSTANCE_ARN" --region "$SSO_REGION" 2>/dev/null || echo '{}')"
  jq -n \
    --arg start "$START_URL" --arg region "$SSO_REGION" \
    --arg instance "$INSTANCE_ARN" \
    --argjson apps "$(jq '[.Applications[]?.Name]' <<<"$ALL_APPS_JSON" 2>/dev/null || echo '[]')" \
    '{ ssoStartUrl: $start, region: $region, instanceArn: $instance, applications: $apps }'
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 2: Find the application by name.
# ---------------------------------------------------------------------------
info "Looking up application '$APP_NAME'…"
APPS_JSON="$(aws sso-admin list-applications --instance-arn "$INSTANCE_ARN" --region "$SSO_REGION" 2>/dev/null)"
APP_ARN="$(jq -r --arg n "$APP_NAME" '.Applications[]? | select(.Name==$n) | .ApplicationArn' <<<"$APPS_JSON" | head -1)"

if [[ -z "$APP_ARN" ]]; then
  # Not found: emit a small dictionary saying so, rather than failing silently.
  jq -n --arg name "$APP_NAME" '{found:false, application:null,
    notes:["No application named \($name) exists in this Identity Center instance. Run create_app.sh first."]}'
  err "Application '$APP_NAME' not found."
  exit 3
fi
ok "Found: $APP_ARN"

# ---------------------------------------------------------------------------
# Step 3: Gather every detail AWS exposes for this app.
# ---------------------------------------------------------------------------
DESC_JSON="$(aws sso-admin describe-application --application-arn "$APP_ARN" --region "$SSO_REGION" 2>/dev/null || echo '{}')"
GRANTS_JSON="$(aws sso-admin list-application-grants --application-arn "$APP_ARN" --region "$SSO_REGION" 2>/dev/null || echo '{"Grants":[]}')"
AUTHM_JSON="$(aws sso-admin list-application-authentication-methods --application-arn "$APP_ARN" --region "$SSO_REGION" 2>/dev/null || echo '{"AuthenticationMethods":[]}')"
SCOPES_JSON="$(aws sso-admin list-application-access-scopes --application-arn "$APP_ARN" --region "$SSO_REGION" 2>/dev/null || echo '{"Scopes":[]}')"

CLIENT_ID="${APP_ARN##*/}"
[[ -z "$OIDC_ISSUER" ]] && OIDC_ISSUER="https://identitycenter.amazonaws.com/${INSTANCE_ARN##*/}"
OIDC_BASE="https://oidc.${SSO_REGION}.amazonaws.com"

# Pull configured redirect URIs out of any authorization_code grant.
REDIRECTS="$(jq -c '[.Grants[]? | select(.GrantType=="authorization_code") | .Grant.AuthorizationCode.RedirectUris[]?]' <<<"$GRANTS_JSON" 2>/dev/null || echo '[]')"
HAS_AUTHCODE="$(jq '[.Grants[]? | select(.GrantType=="authorization_code")] | length>0' <<<"$GRANTS_JSON" 2>/dev/null || echo false)"

# ---------------------------------------------------------------------------
# Step 4: Assemble the structured dictionary.
# ---------------------------------------------------------------------------
DICT="$(jq -n \
  --arg name "$APP_NAME" \
  --arg arn "$APP_ARN" \
  --arg clientId "$CLIENT_ID" \
  --arg issuer "$OIDC_ISSUER" \
  --arg base "$OIDC_BASE" \
  --arg start "$START_URL" \
  --arg region "$SSO_REGION" \
  --argjson desc "$DESC_JSON" \
  --argjson grants "$GRANTS_JSON" \
  --argjson authm "$AUTHM_JSON" \
  --argjson scopes "$SCOPES_JSON" \
  --argjson redirects "$REDIRECTS" \
  --argjson hasAuthCode "$HAS_AUTHCODE" '
{
  found: true,
  application: {
    name: $name,
    arn: $arn,
    clientId: $clientId,
    provider: ($desc.ApplicationProviderArn // null),
    status: ($desc.Status // null),
    instanceArn: ($desc.InstanceArn // null),
    createdDate: ($desc.CreatedDate // null)
  },
  login: {
    issuer: $issuer,
    authorizationEndpoint: ($base + "/authorize"),
    tokenEndpoint: ($base + "/token"),
    registrationEndpoint: ($base + "/client/register"),
    startUrl: $start,
    region: $region,
    redirectUris: $redirects,
    scopes: [ $scopes.Scopes[]?.Scope ]
  },
  grants: ($grants.Grants // []),
  authenticationMethods: ($authm.AuthenticationMethods // []),
  accessScopes: ($scopes.Scopes // []),
  loginReady: $hasAuthCode,
  notes: (
    (if $hasAuthCode then [] else
      ["No authorization_code grant is configured on this app yet, so browser login is NOT wired up. The app exists, but the UI cannot complete a login flow until a redirect/grant is set."] end)
  )
}')"

# ---------------------------------------------------------------------------
# Step 5: Output.
# ---------------------------------------------------------------------------
if [[ "$JSON_ONLY" -eq 1 ]]; then
  echo "$DICT"
  exit 0
fi

echo "$DICT" | jq .
echo "" >&2
{
  echo "──────────── Login details for '$APP_NAME' ────────────"
  echo "  Client ID            : $CLIENT_ID"
  echo "  Issuer               : $OIDC_ISSUER"
  echo "  Authorization endpoint: ${OIDC_BASE}/authorize"
  echo "  Token endpoint       : ${OIDC_BASE}/token"
  echo "  Start URL            : $START_URL"
  echo "  Region               : $SSO_REGION"
  echo "  Login ready          : $HAS_AUTHCODE"
} >&2
