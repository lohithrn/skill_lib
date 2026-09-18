#!/usr/bin/env bash
#
# config.sh — GENERIC, company-agnostic defaults for the create_new_app skill.
#
# This is a PERSONAL skill used across many projects/companies, so it carries NO
# company's AWS account or SSO URL. The SSO portal + region are NOT set here —
# they are remembered PER PROJECT (see below) the first time the skill runs in a
# project, and stored in that project's own cache file.
#
# NON-SECRET defaults only. Client secrets/tokens are issued by AWS at runtime
# and written to the app's .env, never here. Per-invocation flags override these.

# --- Per-project AWS target (NOT stored here) ------------------------------
# The skill asks for the SSO start URL + region the first time it runs in a
# project, then saves them to a per-project cache file named below, at the
# project root (nearest ancestor with .git). Subsequent runs read the cache.
PROJECT_TARGET_FILE=".create_new_app.conf"

# --- OIDC login client defaults (company-agnostic) -------------------------
# Scope requested at login. For IAM Identity Center this must be
# "sso:account:access" (AWS rejects openid/profile/email).
OIDC_SCOPE="sso:account:access"

# Default client name used when registering the login client (override per run
# with --client-name; the skill typically uses the app name).
DEFAULT_CLIENT_NAME="app-login"

# Default loopback redirect URI (AWS only accepts 127.0.0.1 loopback in the form
# http://127.0.0.1:<port>/oauth/callback  or  http://127.0.0.1:<port>).
DEFAULT_REDIRECT_URI="http://127.0.0.1:9034/oauth/callback"

# --- Where to write the app's login config (.env) --------------------------
# Leave empty to AUTO-DETECT: a frontend/ (or web/, app/, client/, ui/) dir under
# the project root, else the project root. Set an explicit path to force it,
# e.g. ENV_FILE_PATH="frontend/.env" (relative to the project root) or absolute.
ENV_FILE_PATH=""
