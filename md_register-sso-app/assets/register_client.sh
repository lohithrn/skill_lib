#!/usr/bin/env bash
#
# register_client.sh — Register a PUBLIC OIDC client with the IAM Identity Center
# sso-oidc service (the piece that actually drives browser login), and write the
# resulting client + endpoints into the frontend .env.
#
# WHY this exists separately from create_app.sh:
#   The IdC "application" (create_app.sh) is NOT what a browser logs in against.
#   Browser login uses a DYNAMICALLY REGISTERED OIDC client at
#   https://oidc.<region>.amazonaws.com/client/register. This was proven by
#   hitting /authorize with the resulting client_id and watching it redirect to
#   the company's real sign-in page. This registration MUST be done server-side:
#   the browser is CORS-blocked on /client/register (but /token allows CORS).
#
# Proven facts this encodes (all verified against AWS, not assumed):
#   * clientType must be "public" (confidential is rejected here).
#   * redirectUris must be 127.0.0.1 loopback (NOT localhost, NOT a hosted
#     domain, NO wildcards). Multiple loopback URIs are allowed.
#   * scope must be "sso:account:access" (openid/profile are rejected at
#     /authorize).
#   * issuerUrl must be the portal start URL.
#
# A registered client's redirect set is fixed at registration time, so "add
# another redirect URL" means re-registering with the union of the existing set
# and the new ones. `--list` shows what's currently configured; `--merge-existing`
# unions the stored redirects with any new `--redirect-uri` values (deduped).
#
# Usage:
#   register_client.sh --list [--env-file PATH]            # show current redirects
#   register_client.sh [--redirect-uri URI]... [--merge-existing]
#                      [--env-file PATH] [--region R] [--start-url URL]
#                      [--client-name NAME] [--dry-run]
#
# Options:
#   --list               Print the currently-configured redirect URIs and exit.
#   --redirect-uri URI   A 127.0.0.1 loopback redirect URI. Repeatable.
#                        Default (if none given and not merging): 127.0.0.1:9034/oauth/callback
#   --merge-existing     Union the new redirect URIs with the ones already stored.
#   --env-file PATH      .env to write (default: <repo>/frontend/.env)
#   --region R           sso-oidc region (default: us-east-1)
#   --start-url URL      portal start URL (else the project's remembered target)
#   --client-name NAME   client name (default: DEFAULT_CLIENT_NAME from
#                        config.sh, which ships as "app-login")
#   --dry-run            Print what would happen; do not call AWS or write files.
#   -h, --help           Show this help.
#
# Exit codes: 0 ok · 1 usage · 2 missing prerequisite · 3 registration failed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

REGION=""      # resolved from flags or the project's remembered target
START_URL=""   # resolved from flags or the project's remembered target
CLIENT_NAME="$DEFAULT_CLIENT_NAME"
ENV_FILE=""   # resolved after arg parsing via resolve_env_file (portable)
SCOPE="$DEFAULT_OIDC_SCOPE"
DRY_RUN=0
LIST_ONLY=0
MERGE_EXISTING=0
REDIRECT_URIS=()

usage() { sed -n '3,/^set -euo/{/^set -euo/d; s/^# \{0,1\}//; s/^#$//; p;}' "$0"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --redirect-uri)   REDIRECT_URIS+=("${2:-}"); shift 2 ;;
    --merge-existing) MERGE_EXISTING=1; shift ;;
    --list)           LIST_ONLY=1; shift ;;
    --env-file)       ENV_FILE="${2:-}"; shift 2 ;;
    --region)         REGION="${2:-}"; shift 2 ;;
    --start-url)      START_URL="${2:-}"; shift 2 ;;
    --client-name)    CLIENT_NAME="${2:-}"; shift 2 ;;
    --dry-run)        DRY_RUN=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    *) err "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# Resolve the .env target portably (explicit --env-file wins; else auto-detect a
# frontend-like dir / project root — works wherever the skill is copied).
ENV_FILE="$(resolve_env_file "$ENV_FILE")"

# read_existing_redirects — prints the stored redirect URIs (one per line) from
# .env. Reads VITE_OIDC_REDIRECT_URIS (space-separated, authoritative full set)
# and falls back to the single VITE_OIDC_REDIRECT_URI for older .env files.
read_existing_redirects() {
  [[ -f "$ENV_FILE" ]] || return 0
  local many one
  # `|| true`: grep exits 1 when a key is absent, which under `set -e` would
  # abort the function before the fallback line could run.
  many="$(grep -E '^VITE_OIDC_REDIRECT_URIS=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  one="$(grep -E '^VITE_OIDC_REDIRECT_URI=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  if [[ -n "$many" ]]; then
    tr ' ' '\n' <<<"$many" | sed '/^$/d'
  elif [[ -n "$one" ]]; then
    printf '%s\n' "$one"
  fi
}

# read_existing_array — portable (bash 3.2, no mapfile) read of existing
# redirects into the global array `_existing`.
read_existing_array() {
  _existing=()
  local line
  while IFS= read -r line; do
    [[ -n "$line" ]] && _existing+=("$line")
  done < <(read_existing_redirects)
}

# --list: show what's configured and exit (used by the skill to ask "add more?").
if [[ "$LIST_ONLY" -eq 1 ]]; then
  read_existing_array
  if [[ ${#_existing[@]} -eq 0 ]]; then
    echo "(no redirect URIs configured yet)"
  else
    printf '%s\n' "${_existing[@]}"
  fi
  exit 0
fi

# Merge with existing redirects if asked (union, order-preserving, deduped).
# Guard array expansions for bash 3.2 + set -u, where "${empty[@]}" errors.
if [[ "$MERGE_EXISTING" -eq 1 ]]; then
  read_existing_array
  local_new=()
  [[ ${#REDIRECT_URIS[@]} -gt 0 ]] && local_new=("${REDIRECT_URIS[@]}")
  REDIRECT_URIS=()
  [[ ${#_existing[@]} -gt 0 ]] && REDIRECT_URIS=("${_existing[@]}")
  [[ ${#local_new[@]} -gt 0 ]] && REDIRECT_URIS=("${REDIRECT_URIS[@]:+${REDIRECT_URIS[@]}}" "${local_new[@]}")
fi

# Default redirect if none supplied and nothing merged.
[[ ${#REDIRECT_URIS[@]} -eq 0 ]] && REDIRECT_URIS=("$DEFAULT_REDIRECT_URI")

# Dedupe while preserving first-seen order.
_seen=" "; _deduped=()
for uri in "${REDIRECT_URIS[@]}"; do
  [[ -z "$uri" ]] && continue
  if [[ "$_seen" != *" $uri "* ]]; then _deduped+=("$uri"); _seen="$_seen$uri "; fi
done
REDIRECT_URIS=("${_deduped[@]}")

# Validate redirect URIs against AWS's (quirky, empirically-verified) rules:
#   * must be http://127.0.0.1:<port>  (loopback IP + explicit port required)
#   * path must be "/oauth/callback" OR empty — a bare "/callback" or trailing
#     "/" is REJECTED by AWS with "must use loopback interface for redirect".
#   * "localhost", hosted domains, and wildcards are all rejected.
for uri in "${REDIRECT_URIS[@]}"; do
  if [[ ! "$uri" =~ ^http://127\.0\.0\.1:[0-9]+(/oauth/callback)?$ ]]; then
    err "Invalid redirect URI: $uri"
    err "AWS only accepts: http://127.0.0.1:<port>  or  http://127.0.0.1:<port>/oauth/callback"
    [[ "$uri" == *localhost* ]] && err "Hint: replace 'localhost' with '127.0.0.1'."
    [[ "$uri" == */callback && "$uri" != */oauth/callback ]] && err "Hint: AWS requires the path '/oauth/callback', not '/callback'."
    exit 1
  fi
done

# Resolve the AWS target: flags win; else this project's remembered target.
if [[ -z "$REGION" || -z "$START_URL" ]]; then
  if load_project_target; then
    [[ -z "$REGION"    ]] && REGION="$PROJECT_SSO_REGION"
    [[ -z "$START_URL" ]] && START_URL="$PROJECT_SSO_START_URL"
  fi
fi
if [[ "$DRY_RUN" -eq 0 && ( -z "$REGION" || -z "$START_URL" ) ]]; then
  err "No AWS SSO target set for this project."
  err "Provide --start-url <portal-url> --region <region>, or run authenticate.sh"
  err "with --save first to remember it ($(project_target_file))."
  exit 2
fi
# Dry-run can proceed with placeholders so the payload is still inspectable.
[[ -z "$REGION"    ]] && REGION="us-east-1"
[[ -z "$START_URL" ]] && START_URL="https://example.awsapps.com/start"

OIDC_BASE="https://oidc.${REGION}.amazonaws.com"

require_cmd curl "Install curl."
require_cmd jq   "Install jq."

# Build the JSON redirectUris array from the bash array.
REDIRECT_JSON="$(printf '%s\n' "${REDIRECT_URIS[@]}" | jq -R . | jq -s .)"

PAYLOAD="$(jq -n \
  --arg name "$CLIENT_NAME" \
  --arg scope "$SCOPE" \
  --arg issuer "$START_URL" \
  --argjson redirects "$REDIRECT_JSON" '{
    clientName: $name,
    clientType: "public",
    grantTypes: ["authorization_code","refresh_token"],
    redirectUris: $redirects,
    scopes: [$scope],
    issuerUrl: $issuer
  }')"

# --- Idempotency: reuse an existing valid client instead of minting a new one.
# AWS sso-oidc has no GET/list for dynamically-registered public clients, so a
# fresh POST each run would orphan the previous client. Instead we cache the
# client (id, secret, expiry, and the redirect set it was registered with) in
# .env and REUSE it when: it exists, hasn't expired, and the requested redirect
# set is unchanged. We only register anew when something actually changed.
read_env_val() { # key — print stored value from .env, or empty
  [[ -f "$ENV_FILE" ]] || return 0
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true
}

EXISTING_ID="$(read_env_val VITE_OIDC_CLIENT_ID)"
EXISTING_REDIRECTS="$(read_env_val VITE_OIDC_REDIRECT_URIS)"
EXISTING_EXPIRES="$(read_env_val VITE_OIDC_CLIENT_SECRET_EXPIRES_AT)"
WANT_REDIRECTS="${REDIRECT_URIS[*]}"
# `now` in epoch seconds (config scripts can't use date in some contexts, but
# this is a normal script run, so date is fine here).
NOW_EPOCH="$(date +%s)"

REUSE=0
if [[ -n "$EXISTING_ID" && "$EXISTING_REDIRECTS" == "$WANT_REDIRECTS" ]]; then
  # Reuse if there is no recorded expiry, OR the expiry (numeric) is in the
  # future. A non-numeric/garbage expiry is treated as "unknown" → reuse (the
  # token endpoint will reject a truly-dead secret, prompting a fresh run).
  if [[ ! "$EXISTING_EXPIRES" =~ ^[0-9]+$ ]] || [[ "$EXISTING_EXPIRES" -gt "$NOW_EPOCH" ]]; then
    REUSE=1
  fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  if [[ "$REUSE" -eq 1 ]]; then
    warn "Dry run — would REUSE existing client $EXISTING_ID (unchanged redirects, not expired)."
  else
    warn "Dry run — would register a new client. Payload:"
    echo "$PAYLOAD" | jq .
  fi
  exit 0
fi

if [[ "$REUSE" -eq 1 ]]; then
  ok "Reusing existing client $EXISTING_ID (unchanged redirects, not expired) — no new client created."
  CLIENT_ID="$EXISTING_ID"
  CLIENT_SECRET="$(read_env_val VITE_OIDC_CLIENT_SECRET)"
  CLIENT_SECRET_EXPIRES_AT="$EXISTING_EXPIRES"
else
  [[ -n "$EXISTING_ID" ]] && info "Redirect set changed or client expired — registering a fresh client."
  info "Registering public OIDC client '$CLIENT_NAME' at $OIDC_BASE/client/register"
  info "Redirect URIs: ${REDIRECT_URIS[*]}"

  # NOTE: This endpoint is unauthenticated (it's how clients self-register) — no
  # SSO token needed. Browser is CORS-blocked on it, hence this server-side step.
  RESP="$(curl -s -X POST "$OIDC_BASE/client/register" \
    -H "Content-Type: application/json" -d "$PAYLOAD")"

  CLIENT_ID="$(jq -r '.clientId // empty' <<<"$RESP")"
  if [[ -z "$CLIENT_ID" ]]; then
    err "Client registration failed: $(jq -r '.error_description // .error // .' <<<"$RESP" 2>/dev/null || echo "$RESP")"
    exit 3
  fi
  CLIENT_SECRET="$(jq -r '.clientSecret // empty' <<<"$RESP")"
  CLIENT_SECRET_EXPIRES_AT="$(jq -r '.clientSecretExpiresAt // empty' <<<"$RESP")"
  ok "Registered client: $CLIENT_ID"
fi

# --- Write the proven-correct values into .env (upsert_env is from _lib.sh) ---
info "Writing client + endpoints to $ENV_FILE"
upsert_env "$ENV_FILE" "VITE_OIDC_CLIENT_ID"      "$CLIENT_ID"
upsert_env "$ENV_FILE" "VITE_OIDC_AUTH_ENDPOINT"  "$OIDC_BASE/authorize"
upsert_env "$ENV_FILE" "VITE_OIDC_TOKEN_ENDPOINT" "$OIDC_BASE/token"
upsert_env "$ENV_FILE" "VITE_OIDC_SCOPES"         "$SCOPE"
# Primary redirect the frontend uses, plus the FULL set (space-separated) so a
# later --merge-existing run knows every URI this client was registered with.
upsert_env "$ENV_FILE" "VITE_OIDC_REDIRECT_URI"   "${REDIRECT_URIS[0]}"
upsert_env "$ENV_FILE" "VITE_OIDC_REDIRECT_URIS"  "${REDIRECT_URIS[*]}"
# The public-client secret AWS returns is needed by the token endpoint; it is a
# low-sensitivity client credential (not a user secret), acceptable for a public
# client. Stored so the frontend can complete the code exchange.
[[ -n "$CLIENT_SECRET" ]] && upsert_env "$ENV_FILE" "VITE_OIDC_CLIENT_SECRET" "$CLIENT_SECRET"
# Store the secret's expiry (epoch seconds) so future runs can REUSE this client
# instead of registering a new one (avoids orphaning clients in AWS).
[[ -n "${CLIENT_SECRET_EXPIRES_AT:-}" ]] && upsert_env "$ENV_FILE" "VITE_OIDC_CLIENT_SECRET_EXPIRES_AT" "$CLIENT_SECRET_EXPIRES_AT"

echo
if [[ "${REUSE:-0}" -eq 1 ]]; then
  ok "Done. Reused existing client; .env confirmed."
else
  ok "Done. Client registered and .env updated."
fi
cat <<EOF
  Client ID     : $CLIENT_ID
  Authorize URL : $OIDC_BASE/authorize
  Token URL     : $OIDC_BASE/token
  Scope         : $SCOPE
  Redirect URIs : ${REDIRECT_URIS[*]}
  Env file      : $ENV_FILE
EOF
