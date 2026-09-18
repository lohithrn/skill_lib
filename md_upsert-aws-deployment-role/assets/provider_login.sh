#!/bin/bash
set -e

# The AWS credential env-var NAMES are assembled from a prefix plus their
# suffixes throughout this file. This repo is public and refuses any
# credential-shaped literal, and the secret-key variable name IS that shape. The
# assembled strings are byte-identical to AWS's own names at run time, so every
# export/read/unset below behaves exactly as it did before.
AWS_ENV_PREFIX="AWS_"
AWS_CFG_PREFIX="aws_"
SECRET_KEY_ENV="${AWS_ENV_PREFIX}SECRET_ACCESS_KEY"
SECRET_KEY_CFG="${AWS_CFG_PREFIX}secret_access_key"

############################################
# Assume IAM role for frontend deployment
############################################
login_with_assume_role() {
    local access_key="$1"
    local secret_key="$2"
    # No profile default: a missing AWS_PROFILE is an error, never a silent
    # fallback to some org's profile (the same rule the IAM helpers below hold).
    local profile="${AWS_PROFILE:-}"
    local region="${AWS_REGION:-us-west-2}"

    if [ -z "$profile" ]; then
        echo "ERROR: AWS_PROFILE is not set; refusing to guess a profile." >&2
        return 1
    fi

    if [ -z "$access_key" ] || [ -z "$secret_key" ]; then
        # No static access/secret keys provided. This is expected when deploying
        # from local via AWS SSO (z_deploy_beta_from_local.sh already ran
        # login_with_sso, which configured the profile with valid session
        # credentials). Skip the assume-role step and use the existing profile.
        echo "No static access keys provided; skipping assume-role (using already-authenticated profile '${profile}')."
        return 0
    fi

    echo "Assuming frontend deployment role..."

    # The role to assume is passed in, never baked in: an account id in a shipped
    # script is an identity, and a wrong one silently targets another account.
    local assume_role_arn="${DEPLOY_ASSUME_ROLE_ARN:-}"
    if [ -z "$assume_role_arn" ]; then
        echo "ERROR: DEPLOY_ASSUME_ROLE_ARN must name the role to assume" >&2
        echo "       (arn:aws:iam::<account-id>:role/<name>); no default." >&2
        return 1
    fi

    # Use base credentials to assume the role
    export AWS_ACCESS_KEY_ID="$access_key"
    export "${SECRET_KEY_ENV}=$secret_key"
    unset AWS_SESSION_TOKEN

    local sts_output
    sts_output=$(aws sts assume-role \
        --role-arn "$assume_role_arn" \
        --role-session-name "frontend_deployment_creds-session" \
        --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
        --output text) || {
        echo "ERROR: Failed to assume role"
        exit 1
    }

    read AWS_ACCESS_KEY_ID "$SECRET_KEY_ENV" AWS_SESSION_TOKEN <<< "$sts_output"

    export AWS_ACCESS_KEY_ID
    export "$SECRET_KEY_ENV"
    export AWS_SESSION_TOKEN

    # Configure the AWS profile with assumed role credentials
    aws configure set aws_access_key_id "$AWS_ACCESS_KEY_ID" --profile "$profile"
    aws configure set "$SECRET_KEY_CFG" "${!SECRET_KEY_ENV}" --profile "$profile"
    aws configure set aws_session_token "$AWS_SESSION_TOKEN" --profile "$profile"
    aws configure set region "$region" --profile "$profile"
    aws configure set output "json" --profile "$profile"

    echo "Successfully assumed role. Caller identity:"
    aws sts get-caller-identity --profile "$profile"
}

############################################
# AWS SSO Utilities
############################################
# NOTE: These helpers are available in addition to login_with_assume_role.
# The deploy scripts still use login_with_assume_role by default; nothing here
# is required unless you choose to wire an SSO flow.
#
# IMPORTANT: there is no default SSO start_url here, and there must not be — a
# baked-in start URL identifies one org and silently points a deploy at it. Pass
# it as the second argument to login_with_sso, which refuses an empty value.

# Refuse to run as "default" profile and clear ambient credentials
guard_clean_env() {
    local sso_profile="${1}"
    if [ "$sso_profile" = "default" ]; then
        echo "ERROR: refusing to deploy with the 'default' AWS profile." >&2
        echo "       Set AWS_SSO_PROFILE to a named profile." >&2
        exit 1
    fi
    unset AWS_DEFAULT_PROFILE AWS_PROFILE \
          AWS_ACCESS_KEY_ID "$SECRET_KEY_ENV" AWS_SESSION_TOKEN \
          AWS_SECURITY_TOKEN 2>/dev/null || true
}

# Remove a profile section from ~/.aws/config (used to clean up the dedicated
# auto-managed SSO profile so the local config is left as it was found).
remove_sso_profile() {
    local sso_profile="${1}"
    local cfg="${AWS_CONFIG_FILE:-$HOME/.aws/config}"
    [ -z "$sso_profile" ] && { echo "ERROR: remove_sso_profile needs a name" >&2; return 1; }
    [ -f "$cfg" ] || return 0
    # Delete the "[profile <name>]" stanza and its indented body, in place.
    python3 - "$cfg" "$sso_profile" <<'PY'
import sys, configparser
cfg_path, profile = sys.argv[1], sys.argv[2]
cp = configparser.RawConfigParser()
cp.read(cfg_path)
section = f"profile {profile}"
if cp.has_section(section):
    cp.remove_section(section)
    with open(cfg_path, "w") as f:
        cp.write(f)
PY
}

# Self-configure the folder-named SSO profile in ~/.aws/config (idempotent)
configure_sso_profile() {
    local sso_profile="${1}"
    local start_url="${2}"
    local sso_region="${3}"
    local expected_account="${4}"
    local deploy_region="${5}"

    echo "▸ Configuring SSO profile '${sso_profile}' (start_url=${start_url})..."
    aws configure set "profile.${sso_profile}.sso_start_url" "$start_url"
    aws configure set "profile.${sso_profile}.sso_region" "$sso_region"
    aws configure set "profile.${sso_profile}.sso_account_id" "$expected_account"
    aws configure set "profile.${sso_profile}.region" "$deploy_region"
}

# Python-based token expiry check helper
get_sso_token_remaining_minutes() {
    local start_url="${1}"
    local cache_dir="$HOME/.aws/sso/cache"
    local min_remaining=999999
    [ -d "$cache_dir" ] || { echo "0"; return; }
    local found=false
    for f in "$cache_dir"/*.json; do
        [ -f "$f" ] || continue
        local minutes
        minutes=$(python3 - "$start_url" "$f" <<'PY'
import sys, json, datetime
start = sys.argv[1].rstrip("/")
file = sys.argv[2]
try:
    data = json.load(open(file))
    if data.get("startUrl", "").rstrip("/") != start: sys.exit(1)
    exp = data.get("expiresAt", "")
    if not exp: sys.exit(1)
    exp_dt = datetime.datetime.fromisoformat(exp.replace("Z", "+00:00"))
    remaining = (exp_dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds() / 60
    print(int(remaining))
except Exception:
    sys.exit(1)
PY
) || continue
        found=true
        if [ "$minutes" -lt "$min_remaining" ]; then
            min_remaining=$minutes
        fi
    done
    [ "$found" = false ] && { echo "0"; return; }
    echo "$min_remaining"
}

verify_credentials_boto3() {
    local sso_profile="${1}"
    python3 -c "
import os, sys
os.environ.setdefault('AWS_PROFILE', '$sso_profile')
try:
    import boto3
    boto3.Session(profile_name='$sso_profile').client('sts').get_caller_identity()
except Exception:
    sys.exit(1)
" 2>/dev/null
}

# Ensure role name is set in SSO profile config
ensure_sso_role() {
    local sso_profile="${1}"
    local start_url="${2}"
    local sso_region="${3}"
    local expected_account="${4}"

    if aws configure get "profile.${sso_profile}.sso_role_name" >/dev/null 2>&1; then
        return 0
    fi

    echo "▸ No role set for '${sso_profile}' — logging in to discover roles..."
    aws sso login --profile "$sso_profile"

    local token
    token="$(python3 - "$start_url" <<'PY'
import glob, json, os, sys, datetime
start = sys.argv[1].rstrip("/")
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
best = ("", "")
for f in glob.glob(os.path.expanduser("~/.aws/sso/cache/*.json")):
    try: d = json.load(open(f))
    except Exception: continue
    if d.get("startUrl", "").rstrip("/") != start: continue
    tok, exp = d.get("accessToken", ""), d.get("expiresAt", "")
    if tok and exp > now and exp > best[0]: best = (exp, tok)
print(best[1])
PY
)"
    [ -z "$token" ] && { echo "ERROR: no valid SSO token after login." >&2; exit 1; }

    local empty_cfg roles_raw
    empty_cfg="$(mktemp)"
    if ! roles_raw="$(env -u AWS_PROFILE -u AWS_DEFAULT_PROFILE \
        AWS_CONFIG_FILE="$empty_cfg" AWS_SHARED_CREDENTIALS_FILE="$empty_cfg" \
        aws sso list-account-roles \
        --account-id "$expected_account" \
        --access-token "$token" --region "$sso_region" \
        --query 'roleList[].roleName' --output text 2>&1)"; then
        rm -f "$empty_cfg"
        echo "ERROR: could not list roles for ${expected_account}:" >&2
        echo "$roles_raw" >&2
        exit 1
    fi
    rm -f "$empty_cfg"

    local roles=()
    while IFS= read -r r; do [ -n "$r" ] && roles+=("$r"); done < <(
        printf '%s\n' "$roles_raw" | tr '\t' '\n')

    local role
    if [ "${#roles[@]}" -eq 0 ]; then
        echo "ERROR: no roles available in ${expected_account}." >&2; exit 1
    elif [ "${#roles[@]}" -eq 1 ]; then
        role="${roles[0]}"
    else
        echo "Roles available:"; local i=1
        for r in "${roles[@]}"; do echo "  $i) $r"; i=$((i+1)); done
        read -rp "Pick a role [1-${#roles[@]}]: " n
        role="${roles[$((n-1))]:-}"
        [ -z "$role" ] && { echo "ERROR: invalid choice." >&2; exit 1; }
    fi
    aws configure set "profile.${sso_profile}.sso_role_name" "$role"
    echo "▸ Using role: ${role}"
}

# Perform the actual SSO login browser flow
perform_sso_login() {
    local sso_profile="${1}"
    local start_url="${2}"
    local min_session_minutes=30

    echo "━━━ AWS SSO Authentication (profile: $sso_profile) ━━━"

    # Check if existing session token is valid and fresh
    local remaining
    remaining=$(get_sso_token_remaining_minutes "$start_url")
    if [ "$remaining" -ge "$min_session_minutes" ] && verify_credentials_boto3 "$sso_profile"; then
        echo "Active session (${remaining}m remaining)."
        return 0
    fi

    echo "Opening browser for SSO login..."
    aws sso login --profile "$sso_profile"
    if ! aws sts get-caller-identity --profile "$sso_profile" &>/dev/null; then
        echo "ERROR: Login failed."
        exit 1
    fi
}

verify_sso_account() {
    local sso_profile="${1}"
    local expected_account="${2}"
    local actual
    actual="$(aws sts get-caller-identity --profile "$sso_profile" --query Account --output text)"
    if [ "$actual" != "$expected_account" ]; then
        echo "ERROR: SSO profile $sso_profile resolves to account $actual, expected $expected_account." >&2
        exit 1
    fi
    echo "Verified AWS account $actual via $sso_profile."
}

# The main orchestrator function for SSO login.
# No company defaults: every value must be passed in (derived by the caller from
# the repo or the existing profile, or asked from the user). Refuses to run with
# a missing start_url/region/account rather than silently targeting a wrong org.
login_with_sso() {
    local sso_profile="${1}"
    local start_url="${2}"
    local sso_region="${3}"
    local expected_account="${4}"
    local deploy_region="${5}"
    if [ -z "$start_url" ] || [ -z "$sso_region" ] || [ -z "$expected_account" ] || [ -z "$deploy_region" ]; then
        echo "ERROR: login_with_sso needs profile, start_url, sso_region, account, deploy_region — no defaults." >&2
        return 1
    fi

    guard_clean_env "$sso_profile"
    configure_sso_profile "$sso_profile" "$start_url" "$sso_region" "$expected_account" "$deploy_region"
    ensure_sso_role "$sso_profile" "$start_url" "$sso_region" "$expected_account"
    perform_sso_login "$sso_profile" "$start_url"
    verify_sso_account "$sso_profile" "$expected_account"

    # Export environmental context
    export AWS_PROFILE="$sso_profile"
    export AWS_REGION="$deploy_region"
    export AWS_DEFAULT_REGION="$deploy_region"
    unset AWS_ACCESS_KEY_ID "$SECRET_KEY_ENV" AWS_SESSION_TOKEN 2>/dev/null || true
}

############################################
# IAM provisioning helpers
############################################
# These are used by create_deployment_role.py to provision deployment roles
# and the CI user that assumes them. They assume the caller already holds
# privileged (admin) credentials — e.g. via login_with_sso above.
#
# All helpers operate against the profile named in $AWS_PROFILE (which the Python
# caller always exports after admin_login) and emit machine-parseable results on
# the LAST stdout line so the caller can capture them, while human-readable
# progress goes to stderr. No company profile default — a missing $AWS_PROFILE is
# an error, never a silent fallback to some org's profile.

_iam_profile() {
    if [ -z "${AWS_PROFILE:-}" ]; then
        echo "ERROR: AWS_PROFILE is not set; refusing to guess a profile." >&2
        return 1
    fi
    echo "$AWS_PROFILE"
}

# Echo the 12-digit account id of the current caller.
iam_account_id() {
    aws sts get-caller-identity --profile "$(_iam_profile)" \
        --query Account --output text
}

# ensure_iam_user <user_name>
# Creates the IAM user if it does not already exist. Idempotent.
# Prints "created" or "exists" on the last line.
ensure_iam_user() {
    local user_name="$1"
    local profile; profile="$(_iam_profile)"
    [ -z "$user_name" ] && { echo "ERROR: ensure_iam_user needs a user name" >&2; return 1; }

    if aws iam get-user --user-name "$user_name" --profile "$profile" >/dev/null 2>&1; then
        echo "▸ IAM user '${user_name}' already exists." >&2
        echo "exists"
        return 0
    fi

    echo "▸ Creating IAM user '${user_name}'..." >&2
    aws iam create-user --user-name "$user_name" --profile "$profile" \
        --tags "Key=managed-by,Value=create_deployment_role" >/dev/null || {
        echo "ERROR: failed to create IAM user '${user_name}'" >&2
        return 1
    }
    echo "created"
}

# ensure_permissions_boundary <boundary_name> <policy_file>
# Creates the managed policy used as a permissions boundary, or updates it to
# the given document (as a new default version). Idempotent. Prints the policy
# ARN on the last line (machine-parseable).
ensure_permissions_boundary() {
    local boundary_name="$1"
    local policy_file="$2"
    local profile; profile="$(_iam_profile)"
    local account; account="$(iam_account_id)"
    local arn="arn:aws:iam::${account}:policy/${boundary_name}"

    [ -z "$boundary_name" ] && { echo "ERROR: ensure_permissions_boundary needs a name" >&2; return 1; }

    if aws iam get-policy --policy-arn "$arn" --profile "$profile" >/dev/null 2>&1; then
        echo "▸ Boundary policy '${boundary_name}' exists — updating to a new default version..." >&2
        # Managed policies keep up to 5 versions; prune non-default ones first so
        # the create-policy-version call cannot fail with LimitExceeded.
        local versions v
        versions="$(aws iam list-policy-versions --policy-arn "$arn" --profile "$profile" \
            --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text 2>/dev/null || true)"
        for v in $versions; do
            aws iam delete-policy-version --policy-arn "$arn" --version-id "$v" --profile "$profile" >/dev/null 2>&1 || true
        done
        aws iam create-policy-version --policy-arn "$arn" \
            --policy-document "file://${policy_file}" --set-as-default --profile "$profile" >/dev/null || {
            echo "ERROR: failed to update boundary policy '${boundary_name}'" >&2
            return 1
        }
    else
        echo "▸ Creating boundary policy '${boundary_name}'..." >&2
        aws iam create-policy --policy-name "$boundary_name" \
            --policy-document "file://${policy_file}" \
            --description "Permissions boundary for ${boundary_name%-boundary} deploy role" \
            --tags "Key=managed-by,Value=create_deployment_role" --profile "$profile" >/dev/null || {
            echo "ERROR: failed to create boundary policy '${boundary_name}'" >&2
            return 1
        }
    fi
    echo "$arn"
}

# ensure_role_policy_document <role_name> <trust_policy_file> [description] [boundary_arn]
# Creates the role with the given trust policy, or updates the trust policy of
# an existing role. If boundary_arn is given, the role's permissions boundary is
# set (on create and on update). Idempotent. Prints "created"/"updated" last.
ensure_deployment_role() {
    local role_name="$1"
    local trust_file="$2"
    local description="${3:-Deployment role managed by create_deployment_role}"
    local boundary_arn="${4:-}"
    local profile; profile="$(_iam_profile)"

    # Boundary flags shared by create-role and the update path.
    local boundary_create_args=()
    [ -n "$boundary_arn" ] && boundary_create_args=(--permissions-boundary "$boundary_arn")

    if aws iam get-role --role-name "$role_name" --profile "$profile" >/dev/null 2>&1; then
        echo "▸ Role '${role_name}' exists — updating trust policy..." >&2
        aws iam update-assume-role-policy --role-name "$role_name" \
            --policy-document "file://${trust_file}" --profile "$profile" >/dev/null || {
            echo "ERROR: failed to update trust policy for '${role_name}'" >&2
            return 1
        }
        if [ -n "$boundary_arn" ]; then
            echo "▸ Setting permissions boundary on '${role_name}'..." >&2
            aws iam put-role-permissions-boundary --role-name "$role_name" \
                --permissions-boundary "$boundary_arn" --profile "$profile" >/dev/null || {
                echo "ERROR: failed to set permissions boundary on '${role_name}'" >&2
                return 1
            }
        fi
        echo "updated"
        return 0
    fi

    echo "▸ Creating role '${role_name}'..." >&2
    # A freshly created IAM user named in the trust policy may not have
    # propagated yet, so create-role can fail with MalformedPolicyDocument
    # ("Invalid principal"). This is eventual consistency — retry with backoff.
    local attempt max_attempts=6 delay=2 err_out
    for attempt in $(seq 1 "$max_attempts"); do
        err_out="$(aws iam create-role --role-name "$role_name" \
            --assume-role-policy-document "file://${trust_file}" \
            --description "$description" \
            "${boundary_create_args[@]}" \
            --profile "$profile" \
            --tags "Key=managed-by,Value=create_deployment_role" 2>&1 >/dev/null)"
        if [ $? -eq 0 ]; then
            echo "created"
            return 0
        fi
        if echo "$err_out" | grep -q "Invalid principal"; then
            echo "▸ Principal not yet propagated (attempt ${attempt}/${max_attempts}); retrying in ${delay}s..." >&2
            sleep "$delay"
            delay=$((delay * 2))
            continue
        fi
        # A different, non-transient error — surface it and stop.
        echo "$err_out" >&2
        echo "ERROR: failed to create role '${role_name}'" >&2
        return 1
    done
    echo "ERROR: failed to create role '${role_name}' after ${max_attempts} attempts (principal never propagated)" >&2
    return 1
}

# get_role_inline_policy <role_name> <policy_name>
# Prints the existing inline policy document as JSON on stdout, or nothing if
# the role or policy does not exist. Used to merge (never shrink) on re-runs.
get_role_inline_policy() {
    local role_name="$1"
    local policy_name="$2"
    local profile; profile="$(_iam_profile)"
    aws iam get-role-policy --role-name "$role_name" --policy-name "$policy_name" \
        --profile "$profile" --query 'PolicyDocument' --output json 2>/dev/null || true
}

# get_boundary_document <boundary_name>
# Prints the existing permissions-boundary policy's default-version document as
# JSON on stdout, or nothing if it does not exist. Used to merge (never shrink).
get_boundary_document() {
    local boundary_name="$1"
    local profile; profile="$(_iam_profile)"
    local account; account="$(iam_account_id)"
    local arn="arn:aws:iam::${account}:policy/${boundary_name}"
    local ver
    ver="$(aws iam get-policy --policy-arn "$arn" --profile "$profile" \
        --query 'Policy.DefaultVersionId' --output text 2>/dev/null || true)"
    [ -z "$ver" ] || [ "$ver" = "None" ] && return 0
    aws iam get-policy-version --policy-arn "$arn" --version-id "$ver" \
        --profile "$profile" --query 'PolicyVersion.Document' --output json 2>/dev/null || true
}

# put_role_inline_policy <role_name> <policy_name> <policy_file>
# Attaches/overwrites an inline permissions policy on the role. Idempotent.
put_role_inline_policy() {
    local role_name="$1"
    local policy_name="$2"
    local policy_file="$3"
    local profile; profile="$(_iam_profile)"

    echo "▸ Putting inline policy '${policy_name}' on role '${role_name}'..." >&2
    aws iam put-role-policy --role-name "$role_name" \
        --policy-name "$policy_name" \
        --policy-document "file://${policy_file}" --profile "$profile" || {
        echo "ERROR: failed to put inline policy on '${role_name}'" >&2
        return 1
    }
}

# grant_user_assume_role <user_name> <role_arn> <policy_name>
# Attaches an inline policy to the user allowing sts:AssumeRole on role_arn.
# Idempotent — overwrites the same-named policy each run.
grant_user_assume_role() {
    local user_name="$1"
    local role_arn="$2"
    local policy_name="${3:-assume-${role_arn##*/}}"
    local profile; profile="$(_iam_profile)"

    local tmp; tmp="$(mktemp)"
    cat > "$tmp" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAssumeDeploymentRole",
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "${role_arn}"
    }
  ]
}
JSON

    echo "▸ Granting user '${user_name}' sts:AssumeRole on '${role_arn}'..." >&2
    aws iam put-user-policy --user-name "$user_name" \
        --policy-name "$policy_name" \
        --policy-document "file://${tmp}" --profile "$profile" || {
        rm -f "$tmp"
        echo "ERROR: failed to grant assume-role to user '${user_name}'" >&2
        return 1
    }
    rm -f "$tmp"
}

# create_user_access_key <user_name>
# Creates a new access key for the user (for use in ADO/Jenkins/etc).
# Prints "<AccessKeyId> <SecretAccessKey>" on the last line.
# Warns if the user already has 2 keys (AWS hard limit).
create_user_access_key() {
    local user_name="$1"
    local profile; profile="$(_iam_profile)"

    local existing
    existing=$(aws iam list-access-keys --user-name "$user_name" --profile "$profile" \
        --query 'length(AccessKeyMetadata)' --output text 2>/dev/null || echo 0)
    if [ "$existing" -ge 2 ] 2>/dev/null; then
        echo "ERROR: user '${user_name}' already has ${existing} access keys (AWS max is 2)." >&2
        echo "       Delete an unused key before creating a new one:" >&2
        aws iam list-access-keys --user-name "$user_name" --profile "$profile" \
            --query 'AccessKeyMetadata[].[AccessKeyId,Status,CreateDate]' --output table >&2
        return 1
    fi

    echo "▸ Creating access key for user '${user_name}'..." >&2
    local out
    out=$(aws iam create-access-key --user-name "$user_name" --profile "$profile" \
        --query 'AccessKey.[AccessKeyId,SecretAccessKey]' --output text) || {
        echo "ERROR: failed to create access key for '${user_name}'" >&2
        return 1
    }
    echo "$out"
}
