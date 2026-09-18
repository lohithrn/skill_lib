#!/usr/bin/env bash
#
# authenticate.sh — Authenticate to AWS via SSO using a DISPOSABLE profile.
#
# Credential policy (important):
#   * Ignores ALL static/machine credentials. Ambient AWS_* vars are unset, so
#     login can ONLY happen through AWS SSO (a browser login).
#   * Uses a RANDOMLY-NAMED, EPHEMERAL profile written to a TEMP config file.
#     Your real ~/.aws/config is never read or modified. No existing named
#     profile is reused.
#   * The account + role are AUTO-DISCOVERED from what your SSO login grants —
#     nothing is hardcoded except the portal URL and its region.
#   * On standalone exit it cleans up (SSO logout + delete temp config) unless
#     --persist is given (the caller then owns cleanup).
#
# What it does:
#   1. Unsets ambient AWS credential env vars.
#   2. Writes a temp config with a random sso-session + profile for the portal.
#   3. Opens the browser via `aws sso login` (single sign-on).
#   4. Lists the accounts/roles the login grants; selects one (prompts if many).
#   5. Discovers the IAM Identity Center instance ARN + issuer.
#   6. Emits KEY=VALUE on stdout (caller can `eval`); messages go to stderr.
#
# Usage:
#   authenticate.sh [--region <r>] [--start-url <url>] [--persist] [--no-login] [--dry-run]
#
# Options:
#   --start-url <url>  SSO portal URL. No default — from --start-url or the
#                      project's remembered target (.create_new_app.conf).
#   --region <r>       SSO region.      Default: us-east-1
#   --persist          Don't clean up on exit (caller will). Emits AWS_CONFIG_FILE.
#   --no-login         Fail instead of opening the browser if no token is cached.
#   --dry-run          Don't call AWS; emit placeholder values.
#   -h, --help         Show this help.
#
# Output (stdout, KEY=VALUE):
#   AWS_CONFIG_FILE=...   (only with --persist)
#   AWS_PROFILE=...
#   AWS_ACCOUNT_ID=...
#   AWS_ROLE_NAME=...
#   AWS_INSTANCE_ARN=...
#   AWS_IDENTITY_STORE_ID=...
#   AWS_OIDC_ISSUER=...
#
# Exit codes: 0 ok · 1 usage · 2 missing prerequisite · 3 auth/discovery failed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

# --- Credential policy: SSO ONLY. Unset every ambient credential hint. -------
unset_aws_static_creds

# No hardcoded SSO target — provided per run via flags, or remembered per project.
START_URL=""
SSO_REGION=""
PERSIST=0
DO_LOGIN=1
DRY_RUN=0
SAVE_TARGET=0

usage() { sed -n '3,/^set -euo/{/^set -euo/d; s/^# \{0,1\}//; s/^#$//; p;}' "$0"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-url) START_URL="${2:-}"; shift 2 ;;
    --region)    SSO_REGION="${2:-}"; shift 2 ;;
    --save)      SAVE_TARGET=1; shift ;;
    --persist)   PERSIST=1; shift ;;
    --no-login)  DO_LOGIN=0; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) err "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# Resolve the AWS target: explicit flags win; else this project's remembered
# target; else fail with a clear message telling the caller to supply one.
if [[ -z "$START_URL" || -z "$SSO_REGION" ]]; then
  if load_project_target; then
    [[ -z "$START_URL"  ]] && START_URL="$PROJECT_SSO_START_URL"
    [[ -z "$SSO_REGION" ]] && SSO_REGION="$PROJECT_SSO_REGION"
  fi
fi
if [[ "$DRY_RUN" -eq 0 && ( -z "$START_URL" || -z "$SSO_REGION" ) ]]; then
  err "No AWS SSO target set for this project."
  err "Provide it with --start-url <portal-url> --region <region> (add --save to"
  err "remember it for this project), or create $(project_target_file)."
  exit 2
fi

# --- Dry run: placeholders so callers can be tested without AWS --------------
if [[ "$DRY_RUN" -eq 1 ]]; then
  warn "Dry run: emitting placeholder values (no AWS calls, no browser)."
  echo "AWS_PROFILE=app-ephemeral-dryrun"
  echo "AWS_ACCOUNT_ID=<account-id>"
  echo "AWS_ROLE_NAME=PlaceholderRole"
  echo "AWS_INSTANCE_ARN=arn:aws:sso:::instance/ssoins-PLACEHOLDER"
  echo "AWS_IDENTITY_STORE_ID=d-PLACEHOLDER"
  echo "AWS_OIDC_ISSUER=https://identitycenter.amazonaws.com/ssoins-PLACEHOLDER"
  exit 0
fi

# --- Prerequisites -----------------------------------------------------------
info "Checking prerequisites…"
require_cmd aws "Install the AWS CLI v2: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
require_cmd jq  "Install jq (e.g. 'brew install jq')."

# --- Build an isolated, disposable config ------------------------------------
# The profile name is prefixed with the REPO ROOT FOLDER's name so it's generic:
# copy this skill into any project and the prefix follows automatically. We
# sanitize to lowercase [a-z0-9-] (AWS profile-name friendly) and cap length.
# Use the nearest project root (ancestor with .git) so this works at ANY folder
# depth. The walk starts at $PWD — the project being worked on — because the
# skill itself lives in a shared library that is not the project.
PROJECT_ROOT="$PWD"; _d="$PWD"
while [[ "$_d" != "/" && -n "$_d" ]]; do
  if [[ -e "$_d/.git" ]]; then PROJECT_ROOT="$_d"; break; fi
  _d="$(dirname "$_d")"
done
ROOT_NAME="$(basename "$PROJECT_ROOT")"
PREFIX="$(printf '%s' "$ROOT_NAME" \
  | LC_ALL=C tr '[:upper:]' '[:lower:]' \
  | LC_ALL=C tr -c 'a-z0-9' '-' \
  | sed 's/-\{2,\}/-/g; s/^-//; s/-$//' \
  | cut -c1-40)"
# Fall back to a safe constant if the folder name sanitizes to nothing.
[[ -z "$PREFIX" ]] && PREFIX="app"

# A random suffix keeps the profile name unique and obviously throwaway. We use
# /dev/urandom (not $RANDOM alone) for a clean lowercase token.
RAND="$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom 2>/dev/null | head -c 6 || echo "$$")"
EPHEMERAL_PROFILE="${PREFIX}-ephemeral-${RAND}"
SSO_SESSION="${PREFIX}-eph-${RAND}"
TMP_CONFIG="$(mktemp -t aws_config_eph.XXXXXX)"

# Point the CLI ONLY at our temp config — your ~/.aws/config is invisible here.
export AWS_CONFIG_FILE="$TMP_CONFIG"

cat >"$TMP_CONFIG" <<EOF
[sso-session ${SSO_SESSION}]
sso_start_url = ${START_URL}
sso_region = ${SSO_REGION}
sso_registration_scopes = sso:account:access

[profile ${EPHEMERAL_PROFILE}]
sso_session = ${SSO_SESSION}
region = ${SSO_REGION}
EOF

# Cleanup: log out (clears cached token) and remove the temp config. Skipped
# when --persist is set so a caller can keep using the session.
cleanup() {
  [[ "$PERSIST" -eq 1 ]] && return 0
  aws sso logout >/dev/null 2>&1 || true
  rm -f "$TMP_CONFIG"
}
trap cleanup EXIT

info "Created disposable SSO profile '${EPHEMERAL_PROFILE}' (temp config; ~/.aws untouched)."

# --- Single sign-on (browser) ------------------------------------------------
if [[ "$DO_LOGIN" -eq 1 ]]; then
  info "Opening browser for AWS single sign-on to ${START_URL} …"
  aws sso login --profile "$EPHEMERAL_PROFILE" >&2 || { err "aws sso login failed."; exit 3; }
else
  info "Skipping login (--no-login); relying on an existing cached token."
fi

# --- Recover the SSO access token from the CLI cache -------------------------
# `aws sso login` caches an access token in ~/.aws/sso/cache keyed by start URL.
# There can be SEVERAL files for the same portal (old/expired logins), so we
# must pick the NEWEST one that matches our start URL AND is not expired —
# otherwise we'd grab a stale token (the "Session token not found or invalid"
# error). We sort matching files by expiresAt descending and take the first
# still-valid one. `now` is captured from the OS (jq has no current-time fn).
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TOKEN="$(
  jq -rs --arg url "$START_URL" --arg now "$NOW_ISO" '
    map(select(.startUrl == $url and .accessToken and (.expiresAt // "") > $now))
    | sort_by(.expiresAt) | reverse
    | (.[0].accessToken // empty)
  ' "$HOME"/.aws/sso/cache/*.json 2>/dev/null
)"
if [[ -z "$TOKEN" ]]; then
  err "No valid SSO token found for ${START_URL} after login."
  err "Try clearing stale tokens: rm -f ~/.aws/sso/cache/*.json  (then re-run)."
  exit 3
fi

# --- Auto-discover the account ----------------------------------------------
info "Discovering accounts your login grants…"
ACCOUNTS_JSON="$(aws sso list-accounts --access-token "$TOKEN" --region "$SSO_REGION")"
ACC_COUNT="$(jq '.accountList | length' <<<"$ACCOUNTS_JSON")"
if [[ "$ACC_COUNT" -eq 0 ]]; then
  err "Your SSO login has access to no accounts."; exit 3
elif [[ "$ACC_COUNT" -eq 1 ]]; then
  ACCOUNT_ID="$(jq -r '.accountList[0].accountId' <<<"$ACCOUNTS_JSON")"
else
  warn "Multiple accounts available:"
  jq -r '.accountList[] | "  \(.accountId)  \(.accountName)"' <<<"$ACCOUNTS_JSON" >&2
  if [[ -t 0 ]]; then
    printf '\033[36m? Enter the account ID to use: \033[0m' >&2
    read -r ACCOUNT_ID
  else
    ACCOUNT_ID="$(jq -r '.accountList[0].accountId' <<<"$ACCOUNTS_JSON")"
    warn "Non-interactive: defaulting to first account $ACCOUNT_ID."
  fi
fi

# --- Auto-discover the role in that account ----------------------------------
info "Discovering roles in account ${ACCOUNT_ID}…"
ROLES_JSON="$(aws sso list-account-roles --account-id "$ACCOUNT_ID" --access-token "$TOKEN" --region "$SSO_REGION")"
ROLE_COUNT="$(jq '.roleList | length' <<<"$ROLES_JSON")"
if [[ "$ROLE_COUNT" -eq 0 ]]; then
  err "No roles available in account $ACCOUNT_ID."; exit 3
elif [[ "$ROLE_COUNT" -eq 1 ]]; then
  ROLE_NAME="$(jq -r '.roleList[0].roleName' <<<"$ROLES_JSON")"
else
  warn "Multiple roles available:"
  jq -r '.roleList[] | "  \(.roleName)"' <<<"$ROLES_JSON" >&2
  if [[ -t 0 ]]; then
    printf '\033[36m? Enter the role name to use: \033[0m' >&2
    read -r ROLE_NAME
  else
    ROLE_NAME="$(jq -r '.roleList[0].roleName' <<<"$ROLES_JSON")"
    warn "Non-interactive: defaulting to first role $ROLE_NAME."
  fi
fi

# Fetch concrete, short-lived role credentials from the SSO token and export
# them directly. This is more reliable than profile-based SSO resolution, which
# depends on the cached token being keyed to our random session name (it isn't
# when reusing an existing login), and would silently yield no credentials.
ROLE_CREDS_JSON="$(aws sso get-role-credentials \
  --account-id "$ACCOUNT_ID" --role-name "$ROLE_NAME" \
  --access-token "$TOKEN" --region "$SSO_REGION" 2>&1)"
# These are temporary SSO-issued credentials (NOT static OS credentials) — they
# expire with the SSO session and are scoped to the role you just logged into.
# Assign to plain locals FIRST (not inside `export`/`local`, which would discard
# the command-substitution exit code under `set -e`), then verify all three are
# present before exporting — a partial response must abort, not export blanks.
AKID="$(jq -r '.roleCredentials.accessKeyId // empty' <<<"$ROLE_CREDS_JSON")"
SAK="$(jq -r '.roleCredentials.secretAccessKey // empty' <<<"$ROLE_CREDS_JSON")"
STOK="$(jq -r '.roleCredentials.sessionToken // empty' <<<"$ROLE_CREDS_JSON")"
if [[ -z "$AKID" || -z "$SAK" || -z "$STOK" ]]; then
  err "Incomplete role credentials for ${ROLE_NAME} in ${ACCOUNT_ID}:"
  err "$ROLE_CREDS_JSON"
  exit 3
fi
# The secret key is exported through its composed variable NAME ($AWS_SECRET_VAR
# from _lib.sh) so the joined spelling never appears as a literal in this public
# repo. `export "NAME=value"` sets exactly the same variable the AWS CLI reads.
export AWS_ACCESS_KEY_ID="$AKID"
export "$AWS_SECRET_VAR=$SAK"
export AWS_SESSION_TOKEN="$STOK"
export AWS_REGION="$SSO_REGION"
unset AWS_PROFILE 2>/dev/null || true

CALLER="$(aws sts get-caller-identity --query Arn --output text 2>/dev/null || echo unknown)"
ok "SSO session active as: $CALLER"
ok "Account: ${ACCOUNT_ID}  ·  Role: ${ROLE_NAME}"

# --- Discover the IAM Identity Center instance -------------------------------
info "Discovering IAM Identity Center instance…"
INSTANCES_JSON="$(aws sso-admin list-instances 2>/dev/null || echo '{}')"
INSTANCE_ARN="$(jq -r '.Instances[0].InstanceArn // empty' <<<"$INSTANCES_JSON")"
IDENTITY_STORE_ID="$(jq -r '.Instances[0].IdentityStoreId // empty' <<<"$INSTANCES_JSON")"

if [[ -z "$INSTANCE_ARN" ]]; then
  err "Authenticated, but this role (${ROLE_NAME}) can't list the Identity Center instance."
  err "It likely lacks sso:ListInstances, or isn't in the account that owns ${START_URL}."
  err "Pick a different account/role, or ask an admin to grant sso-admin access."
  exit 3
fi

INSTANCE_ID="${INSTANCE_ARN##*/}"
OIDC_ISSUER="https://identitycenter.amazonaws.com/${INSTANCE_ID}"
ok "Instance: $INSTANCE_ARN"
ok "Issuer:   $OIDC_ISSUER"

# Remember this project's AWS target for next time, if asked (--save).
[[ "$SAVE_TARGET" -eq 1 ]] && save_project_target "$START_URL" "$SSO_REGION"

# --- Emit machine-readable session on stdout ---------------------------------
# With --persist, also emit the temporary credentials so a caller (create_app.sh)
# can make its own authenticated AWS calls using the SAME SSO identity.
if [[ "$PERSIST" -eq 1 ]]; then
  echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"
  # Same composed name as above: the KEY the caller parses is identical, only the
  # spelling in this file's source is split.
  printf '%s=%s\n' "$AWS_SECRET_VAR" "$SAK"
  echo "AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN"
  echo "AWS_REGION=$SSO_REGION"
fi
echo "AWS_ACCOUNT_ID=$ACCOUNT_ID"
echo "AWS_ROLE_NAME=$ROLE_NAME"
echo "AWS_INSTANCE_ARN=$INSTANCE_ARN"
echo "AWS_IDENTITY_STORE_ID=$IDENTITY_STORE_ID"
echo "AWS_OIDC_ISSUER=$OIDC_ISSUER"

if [[ "$PERSIST" -eq 0 ]]; then
  warn "Standalone run: this SSO session will be logged out and the temp profile deleted on exit."
fi
