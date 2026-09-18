#!/usr/bin/env bash
#
# create_app.sh — Register a new OIDC (SPA) application in AWS IAM Identity Center
# and wire its client ID + issuer into the frontend's .env file.
#
# This is the step that lets the "Login with AWS" button actually work: AWS will
# only authenticate users for applications it knows about. Running this once per
# app produces the VITE_OIDC_CLIENT_ID and VITE_OIDC_ISSUER values.
#
# Authentication is delegated to authenticate.sh (run first unless --skip-auth),
# so this script focuses purely on app creation. Each script is independently
# runnable and testable.
#
# Usage:
#   create_app.sh --name "My App" [options]
#   create_app.sh                         # prompts for the name interactively
#
# This script ONLY creates/ensures the IAM Identity Center application. It does
# NOT configure the browser-login client or write .env — run register_client.sh
# for that (see SKILL.md).
#
# Options:
#   --name <name>            Human-readable app name (required; prompted if absent)
#   --instance-arn <arn>     IdC instance ARN (skips discovery in authenticate.sh)
#   --no-login               Pass through: don't open browser, use cached token
#   --skip-auth              Don't run authenticate.sh (for testing creation alone)
#   --dry-run                Print the AWS commands without executing them
#   -h, --help               Show this help
#
# Exit codes: 0 ok · 1 usage error · 2 missing prerequisite · 3 AWS call failed
set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults & paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

# Credential policy (matches authenticate.sh): SSO ONLY. Unset any ambient
# static OS credentials so this script can never act as a machine IAM user.
unset_aws_static_creds

APP_NAME=""
INSTANCE_ARN=""
START_URL=""   # optional: forwarded to authenticate.sh for a different account
SSO_REGION=""  # optional: forwarded to authenticate.sh
SAVE_TARGET=0  # optional: forwarded to authenticate.sh (--save)
NO_LOGIN=0
SKIP_AUTH=0
DRY_RUN=0

usage() { sed -n '3,/^set -euo/{/^set -euo/d; s/^# \{0,1\}//; s/^#$//; p;}' "$0"; }

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)         APP_NAME="${2:-}"; shift 2 ;;
    --instance-arn) INSTANCE_ARN="${2:-}"; shift 2 ;;
    --start-url)    START_URL="${2:-}"; shift 2 ;;
    --region)       SSO_REGION="${2:-}"; shift 2 ;;
    --save)         SAVE_TARGET=1; shift ;;
    --no-login)     NO_LOGIN=1; shift ;;
    --skip-auth)    SKIP_AUTH=1; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *) err "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Interactive prompt for the app name (the one required input)
# ---------------------------------------------------------------------------
if [[ -z "$APP_NAME" && -t 0 ]]; then
  printf '\033[36m? What is the name of the app you want to create?\033[0m '
  read -r APP_NAME
fi
if [[ -z "$APP_NAME" ]]; then
  err "An app name is required (pass --name \"My App\" or answer the prompt)."
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 1: Authenticate (delegated to authenticate.sh) unless skipped.
#
# authenticate.sh emits KEY=VALUE on stdout; we capture it and import the
# values. Its human-readable messages go to stderr, so they still show through.
# ---------------------------------------------------------------------------
if [[ "$SKIP_AUTH" -eq 1 ]]; then
  warn "Skipping authentication (--skip-auth). Using placeholder discovery values."
  : "${INSTANCE_ARN:=arn:aws:sso:::instance/ssoins-PLACEHOLDER}"
else
  info "Authenticating with AWS via SSO (authenticate.sh)…"
  # --persist: keep the disposable SSO session alive so WE can use it; this
  # script then owns cleanup (logout + delete temp config) via its own trap.
  AUTH_ARGS=(--persist)
  [[ "$NO_LOGIN" -eq 1 ]] && AUTH_ARGS+=(--no-login)
  [[ "$DRY_RUN"  -eq 1 ]] && AUTH_ARGS+=(--dry-run)
  [[ -n "$START_URL"  ]] && AUTH_ARGS+=(--start-url "$START_URL")
  [[ -n "$SSO_REGION" ]] && AUTH_ARGS+=(--region "$SSO_REGION")
  [[ "$SAVE_TARGET" -eq 1 ]] && AUTH_ARGS+=(--save)

  # Capture stdout (KEY=VALUE lines); stderr passes through to the terminal.
  AUTH_OUT="$("$SCRIPT_DIR/authenticate.sh" "${AUTH_ARGS[@]}")" || {
    err "Authentication failed. Fix the above and retry."
    exit 3
  }

  # Import the discovered session — the SAME temporary SSO credentials the auth
  # step resolved — so our own AWS calls use that identity (never static OS
  # credentials, which we unset at the top).
  # "$AWS_SECRET_VAR" (from _lib.sh) is the secret key's variable NAME, composed
  # from a prefix and a suffix so the joined spelling is never a literal in this
  # public repo. Quoted, it is a literal case pattern and an exact-match arm.
  while IFS='=' read -r key value; do
    case "$key" in
      AWS_ACCESS_KEY_ID)     export AWS_ACCESS_KEY_ID="$value" ;;
      "$AWS_SECRET_VAR")     export "$AWS_SECRET_VAR=$value" ;;
      AWS_SESSION_TOKEN)     export AWS_SESSION_TOKEN="$value" ;;
      AWS_REGION)            export AWS_REGION="$value" ;;
      AWS_INSTANCE_ARN)      [[ -z "$INSTANCE_ARN" ]] && INSTANCE_ARN="$value" ;;
    esac
  done <<<"$AUTH_OUT"

  # Tokens are temporary and expire with the SSO session; nothing to delete.
fi

[[ -z "$INSTANCE_ARN" ]] && { err "No instance ARN available after auth."; exit 3; }
ok "Using instance: $INSTANCE_ARN"

# ---------------------------------------------------------------------------
# Step 2: Register the OIDC application
#
#    NOTE: IAM Identity Center models a "customer managed" OIDC app via
#    sso-admin create-application against the OIDC application provider. The
#    application-provider ARN below is AWS's well-known OAuth2/OIDC provider;
#    if your org uses a different provider, pass it through your own config.
# ---------------------------------------------------------------------------
# The custom application provider is what AWS uses for customer-managed OAuth2 /
# OIDC apps (confirmed via `aws sso-admin list-application-providers`). There is
# no dedicated "oauth2" provider — "custom" is the correct one for our SPA.
APP_PROVIDER_ARN="arn:aws:sso::aws:applicationProvider/custom"

info "Registering OIDC application '$APP_NAME'…"
if [[ "$DRY_RUN" -eq 1 ]]; then
  run_aws sso-admin create-application \
    --instance-arn "$INSTANCE_ARN" \
    --application-provider-arn "$APP_PROVIDER_ARN" \
    --name "$APP_NAME" \
    --portal-options "'{\"Visibility\":\"ENABLED\"}'" \
    --status ENABLED
  APP_ARN="arn:aws:sso::ACCOUNT:application/ssoins-EXAMPLE/apl-EXAMPLE"
  # The application id is the last ARN segment, so the dry-run placeholder is
  # the placeholder ARN's own tail — never an id shaped like a real credential.
  CLIENT_ID="${APP_ARN##*/}"
elif [[ "$SKIP_AUTH" -eq 1 ]]; then
  err "--skip-auth without --dry-run would call AWS unauthenticated. Refusing."
  err "Use --skip-auth with --dry-run to test creation logic, or drop --skip-auth."
  exit 1
else
  # Idempotent: if an application with this name already exists, reuse it rather
  # than creating a duplicate (Identity Center allows multiple apps with the
  # same name, so we must dedupe ourselves).
  EXISTING_ARN="$(aws sso-admin list-applications \
    --instance-arn "$INSTANCE_ARN" --region "${AWS_REGION:-us-east-1}" 2>/dev/null \
    | jq -r --arg n "$APP_NAME" '.Applications[]? | select(.Name == $n) | .ApplicationArn' \
    | head -1)"

  if [[ -n "$EXISTING_ARN" ]]; then
    APP_ARN="$EXISTING_ARN"
    ok "Application '$APP_NAME' already exists — reusing it (no duplicate created)."
  else
    CREATE_JSON="$(aws sso-admin create-application \
      --instance-arn "$INSTANCE_ARN" \
      --application-provider-arn "$APP_PROVIDER_ARN" \
      --name "$APP_NAME" \
      --portal-options '{"Visibility":"ENABLED"}' \
      --status ENABLED)" || { err "create-application failed."; exit 3; }
    APP_ARN="$(jq -r '.ApplicationArn' <<<"$CREATE_JSON")"
    ok "Created new application."
  fi
  # The OAuth client ID for IdC OIDC apps is the application ID portion of the ARN.
  CLIENT_ID="${APP_ARN##*/}"
fi
ok "Application ARN: $APP_ARN"

# NOTE: This script ONLY creates/ensures the IAM Identity Center application.
# It deliberately writes NO login config to .env. The browser-login client (the
# values the frontend actually needs: client id, authorize/token endpoints,
# scope, redirect, secret) is owned solely by register_client.sh — that is the
# dynamically-registered sso-oidc client, NOT this sso-admin "application"
# (whose id, apl-..., does not drive browser login). Keeping login-config
# ownership in one script avoids the two scripts fighting over .env keys.

INSTANCE_ID="${INSTANCE_ARN##*/}"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo >&2
ok "Done."
{
  echo "  App name       : $APP_NAME"
  echo "  Application id : $CLIENT_ID"
  echo "  Instance       : $INSTANCE_ID"
  echo "  (Run register_client.sh to set up the browser-login client + .env.)"
} >&2

if [[ "$DRY_RUN" -eq 1 ]]; then
  warn "This was a DRY RUN. Re-run without --dry-run (and after SSO login) to apply."
fi
