#!/usr/bin/env bash
# hiatus_bedrock bootstrap.
#
# Owns a private virtualenv INSIDE this skill's own folder (.venv) and runs
# deploy.py inside it. Never touches the system / OS Python or global
# site-packages. Idempotent: creates .venv on first run, reuses it after.
#
# Credentials are read ONLY from stdin as key=value lines. They are never taken
# from the environment, ~/.aws, or any pre-existing profile — deploy.py scrubs
# every ambient AWS_* variable at startup.
#
# Usage (all args are forwarded to deploy.py):
#   ./run.sh --region us-east-1 --list-principals <<'EOF'
#   access_key_id=<key-id>
#   secret_access_key=<secret>
#   session_token=<token>        # omit this line if none
#   EOF
#   ./run.sh --status
#   ./run.sh --destroy
set -euo pipefail

# Resolve this script's own directory so it works from any CWD.
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SKILL_DIR/.venv"
REQS="$SKILL_DIR/requirements.txt"
STAMP="$VENV_DIR/.requirements.sha"

# Pick a base interpreter WITHOUT mutating it. Prefer python3.
PYBASE="$(command -v python3 || command -v python || true)"
if [ -z "$PYBASE" ]; then
  echo "hiatus_bedrock: no python3 found on PATH." >&2
  exit 1
fi

# Create the private venv once; reuse it on every later run.
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "hiatus_bedrock: creating private venv at $VENV_DIR" >&2
  "$PYBASE" -m venv "$VENV_DIR"
fi

VPY="$VENV_DIR/bin/python"

# Install/refresh deps only when requirements.txt changed (cheap on reuse).
CUR_SHA="$(shasum -a 256 "$REQS" 2>/dev/null | awk '{print $1}' || sha256sum "$REQS" | awk '{print $1}')"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP" 2>/dev/null)" != "$CUR_SHA" ]; then
  echo "hiatus_bedrock: installing requirements into private venv" >&2
  "$VPY" -m pip install --quiet --upgrade pip
  "$VPY" -m pip install --quiet -r "$REQS"
  echo "$CUR_SHA" > "$STAMP"
fi

# Run the deployer inside the venv. Args pass straight through; the credential
# heredoc on stdin is inherited by the child process untouched.
exec "$VPY" "$SKILL_DIR/deploy.py" "$@"
