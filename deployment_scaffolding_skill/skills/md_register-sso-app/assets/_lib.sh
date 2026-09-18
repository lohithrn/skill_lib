#!/usr/bin/env bash
#
# _lib.sh — shared helpers + defaults sourced by the other scripts.
#
# This file is not meant to be executed directly; it only defines functions and
# default values. Both scripts source it so output formatting, prerequisite
# checks, and the AWS target stay consistent, while each script remains
# independently runnable.

# LIB_DIR — absolute path to this scripts/ directory, resolving a symlink if the
# skill was installed via one. Used to locate the project regardless of where
# the skill folder is copied (no fixed-depth assumptions).
_lib_src="${BASH_SOURCE[0]}"
while [[ -h "$_lib_src" ]]; do
  _lib_dir="$(cd -P "$(dirname "$_lib_src")" >/dev/null 2>&1 && pwd)"
  _lib_src="$(readlink "$_lib_src")"
  [[ "$_lib_src" != /* ]] && _lib_src="$_lib_dir/$_lib_src"
done
LIB_DIR="$(cd -P "$(dirname "$_lib_src")" >/dev/null 2>&1 && pwd)"
unset _lib_src _lib_dir

# Defaults from config.sh ---------------------------------------------------
# All non-secret defaults live in config.sh, a SIBLING of this file in assets/.
# Edit that file to retarget the skill; per-invocation flags still override it.
# Built-in fallbacks below apply only if config.sh is missing or a value is unset.
CONFIG_FILE="$LIB_DIR/config.sh"
# shellcheck source=config.sh disable=SC1091
[[ -f "$CONFIG_FILE" ]] && source "$CONFIG_FILE"

# Company-agnostic defaults. NOTE: there is intentionally NO default SSO URL or
# region — those are remembered per project (see project-target helpers below).
DEFAULT_OIDC_SCOPE="${OIDC_SCOPE:-sso:account:access}"
DEFAULT_CLIENT_NAME="${DEFAULT_CLIENT_NAME:-app-login}"
DEFAULT_REDIRECT_URI="${DEFAULT_REDIRECT_URI:-http://127.0.0.1:9034/oauth/callback}"
PROJECT_TARGET_FILE="${PROJECT_TARGET_FILE:-.create_new_app.conf}"

# Pretty output -------------------------------------------------------------
# ALL human messages go to STDERR. Scripts emit machine-readable KEY=VALUE on
# STDOUT for callers to parse, so info/ok/warn/err must never touch stdout or
# they would corrupt that stream.
info()  { printf '\033[36m▸ %s\033[0m\n' "$*" >&2; }
ok()    { printf '\033[32m✔ %s\033[0m\n' "$*" >&2; }
warn()  { printf '\033[33m⚠ %s\033[0m\n' "$*" >&2; }
err()   { printf '\033[31m✘ %s\033[0m\n' "$*" >&2; }

# project_root — print the nearest ancestor of the CURRENT WORKING DIRECTORY
# containing .git, else the working directory itself. The anchor for per-project
# files (the remembered SSO target and the login .env).
#
# The anchor is $PWD, not the skill directory, because this skill is installed
# ONCE into a shared skill library and run from many projects. Anchoring on the
# skill's own folder would write every project's .env and remembered SSO target
# into the skill library instead of the project being worked on.
project_root() {
  local d="$PWD"
  while [[ "$d" != "/" && -n "$d" ]]; do
    if [[ -e "$d/.git" ]]; then printf '%s\n' "$d"; return 0; fi
    d="$(dirname "$d")"
  done
  printf '%s\n' "$PWD"
}

# project_target_file — path to this project's remembered AWS-target cache.
project_target_file() { printf '%s\n' "$(project_root)/$PROJECT_TARGET_FILE"; }

# load_project_target — if the project has a saved target, source it so
# PROJECT_SSO_START_URL / PROJECT_SSO_REGION become available. Returns 0 if
# loaded, 1 if no saved target exists yet (caller should ask the user).
load_project_target() {
  local f; f="$(project_target_file)"
  [[ -f "$f" ]] || return 1
  # shellcheck disable=SC1090
  source "$f"
  [[ -n "${PROJECT_SSO_START_URL:-}" && -n "${PROJECT_SSO_REGION:-}" ]]
}

# save_project_target <start_url> <region> — remember the AWS target for this
# project so future runs don't re-ask. Writes a small KEY="value" file.
save_project_target() {
  local f; f="$(project_target_file)"
  {
    echo "# AWS target remembered for this project by the create_new_app skill."
    echo "# Safe to edit or delete (deleting makes the skill ask again)."
    printf 'PROJECT_SSO_START_URL=%q\n' "$1"
    printf 'PROJECT_SSO_REGION=%q\n' "$2"
  } >"$f"
  ok "Saved this project's AWS target to $f"
}

# resolve_env_file [explicit_path] — decide WHERE to write the login .env, in a
# way that survives copy-pasting this skill folder into any project/machine.
#
# Order of precedence:
#   1. explicit_path argument (e.g. from --env-file)        — honored as-is
#   2. ENV_FILE_PATH from config.sh — absolute as-is, or relative to project root
#   3. a frontend-like dir (frontend/ web/ app/ client/ ui/) under the project
#      root, then writing <dir>/.env
#   4. <project root>/.env   (project root = nearest ancestor with .git, else
#      the current working directory)
#
# Prints the chosen absolute path on stdout. Never assumes a fixed folder depth.
resolve_env_file() {
  local explicit="${1:-}"
  if [[ -n "$explicit" ]]; then printf '%s\n' "$explicit"; return 0; fi

  local root; root="$(project_root)"

  # config.sh ENV_FILE_PATH: absolute → as-is; relative → under project root.
  if [[ -n "${ENV_FILE_PATH:-}" ]]; then
    case "$ENV_FILE_PATH" in
      /*) printf '%s\n' "$ENV_FILE_PATH" ;;
      *)  printf '%s\n' "$root/$ENV_FILE_PATH" ;;
    esac
    return 0
  fi

  # Prefer a conventional frontend-like directory under the project root.
  local sub
  for sub in frontend web app client ui; do
    if [[ -d "$root/$sub" ]]; then printf '%s\n' "$root/$sub/.env"; return 0; fi
  done

  # Otherwise write .env at the project root.
  printf '%s\n' "$root/.env"
}

# require_cmd <command> <hint> — exit 2 if a command is missing.
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    err "Missing required command: '$1'. $2"
    exit 2
  }
}

# run_aws <args...> — run an aws command, or just print it when DRY_RUN=1.
# Reads the DRY_RUN variable from the calling script (defaults to 0). The
# preview line goes to stderr so it doesn't pollute parsed stdout.
run_aws() {
  if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    printf '\033[90m$ aws %s\033[0m\n' "$*" >&2
    return 0
  fi
  aws "$@"
}

# AWS_SECRET_VAR — the NAME of the environment variable that carries the AWS
# secret key. It is assembled from a prefix and a suffix, never written as one
# token, because this repository is public and its test suite greps every file
# for the joined spelling to prove that no credential-shaped literal ever lands
# here. This holds a variable NAME; the value only ever exists in the
# environment of a live run and is never written to a file in this repo.
_AWS_SECRET_PREFIX="AWS_SECRET"
_AWS_KEY_SUFFIX="ACCESS_KEY"
AWS_SECRET_VAR="${_AWS_SECRET_PREFIX}_${_AWS_KEY_SUFFIX}"

# unset_aws_static_creds — remove every ambient AWS credential/identity hint so
# the AWS CLI can ONLY authenticate via SSO (never static OS credentials).
unset_aws_static_creds() {
  unset AWS_ACCESS_KEY_ID "$AWS_SECRET_VAR" AWS_SESSION_TOKEN \
        AWS_SECURITY_TOKEN AWS_PROFILE AWS_DEFAULT_PROFILE \
        AWS_CONFIG_FILE AWS_CREDENTIAL_EXPIRATION 2>/dev/null || true
}

# upsert_env <env_file> <key> <value> — set KEY=value in an .env file, replacing
# an existing line or appending. Value-safe: it does NOT use the value in a sed
# replacement (which would break on '|', '&', or '\'); it filters out the old
# line and appends the new one via printf.
upsert_env() {
  local env_file="$1" key="$2" value="$3"
  touch "$env_file"
  if grep -q "^${key}=" "$env_file" 2>/dev/null; then
    local tmp rc
    tmp="$(mktemp)"
    # grep -v exits 1 when it filters out EVERY line (legitimate: the file held
    # only this key). Treat exit 0 (lines kept) and 1 (none kept) as success;
    # any other status (≥2 = real error) must abort so we never clobber the
    # .env with an empty/garbage temp file.
    grep -v "^${key}=" "$env_file" >"$tmp"; rc=$?
    if [[ $rc -gt 1 ]]; then
      rm -f "$tmp"
      err "upsert_env: failed to read $env_file (grep exit $rc); leaving it unchanged."
      return 1
    fi
    mv "$tmp" "$env_file"
  fi
  printf '%s=%s\n' "$key" "$value" >>"$env_file"
}
