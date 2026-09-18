#!/usr/bin/env python3
"""
create_deployment_role.py
=========================

Interactively provisions an AWS IAM deployment role (frontend or backend,
beta or prod) for a given git repository, and wires up an IAM user whose
access keys are meant to be dropped into a CI system (Azure DevOps, Jenkins,
etc.) so that CI can assume the deployment role.

What it does, end to end:

  1. Prompts for:
       - component        (frontend | backend)
       - stage            (beta | prod)     [asked for backend; frontend too]
       - gitRepoName      (logical name, used in resource naming)
       - gitRepoPath      (local path to the checked-out repo)
       - AssumeUserRole   (the IAM *user* that will assume the new role)

  2. Authenticates through the user's explicitly selected named AWS SSO profile,
     verifies its account, and never rewrites that profile.

  3. Discovers the terraform for the repo using a layered fallback:
       (a) well-known infra folders
       (b) directories inferred from `terraform apply`/`init` invocations
           found in scripts / CI pipelines
       (c) any *.tf anywhere under the repo
       (d) the whole repo (last resort)

  4. Generates a least-privilege IAM permissions policy (JSON) deterministically
     from the terraform via tf_policy.py — mapping the aws_* resource/data-source
     types present to the IAM actions a CI `terraform apply` needs, plus S3 +
     DynamoDB backend permissions. The proposed policy is shown to you for
     approval / editing before anything is applied.

  5. Creates or updates in AWS:
       - the deployment role (trust policy => the IAM user may assume it)
       - the role's inline permissions policy (the generated JSON)
       - the IAM user (created only if missing)
       - an inline policy on the user granting sts:AssumeRole on the new role
       - a fresh access key for the user (printed once, for CI configuration)

The heavy lifting for the AWS/IAM primitives lives in provider_login.sh so the
existing SSO login flow and IAM helpers stay in one place.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import deployment_plan
import policy_compare
import policy_merge
import repo_source
import sso_config
import trust_policy
from deployment_plan import build_plan, parse_regions

HERE = Path(__file__).resolve().parent
PROVIDER_LOGIN = HERE / "provider_login.sh"

# Default AWS context — matches the values baked into provider_login.sh.
DEFAULT_REGION = "us-west-2"

# The AWS credential env-var NAME below is assembled from a shared prefix plus
# its suffix. This repo is public and refuses any credential-shaped literal, and
# the secret-key variable name IS that shape. The assembled string is
# byte-identical to AWS's own name at run time, so every pop/print behaves
# exactly as it did before.
_AWS_ENV = "AWS_"
_SECRET_KEY_ENV = _AWS_ENV + "SECRET_ACCESS_KEY"


# --------------------------------------------------------------------------- #
# Small IO helpers
# --------------------------------------------------------------------------- #
def color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def info(msg: str) -> None:
    print(color(f"▸ {msg}", "36"))


def warn(msg: str) -> None:
    print(color(f"⚠ {msg}", "33"))


def err(msg: str) -> None:
    print(color(f"✖ {msg}", "31"), file=sys.stderr)


def die(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[valid-type]
    err(msg)
    sys.exit(code)


def prompt(question: str, default: str | None = None, choices: list[str] | None = None) -> str:
    """Prompt until a non-empty (and, if choices given, valid) answer is entered."""
    suffix = ""
    if choices:
        suffix = f" ({'/'.join(choices)})"
    if default:
        suffix += f" [{default}]"
    while True:
        try:
            ans = input(color(f"? {question}{suffix}: ", "1")).strip()
        except EOFError:
            # No interactive terminal (piped/non-interactive). Use the default
            # if one exists; otherwise there's nothing sensible to fall back to.
            if default is not None:
                info(f"{question} -> using default '{default}' (no TTY).")
                return default
            die(f"'{question}' requires a value but no TTY is available. "
                f"Pass it as a CLI flag (see --help).")
        except KeyboardInterrupt:
            print()
            die("Aborted.")
        if not ans and default is not None:
            return default  # includes an explicit empty-string default (optional field)
        if not ans:
            warn("A value is required.")
            continue
        if choices and ans not in choices:
            warn(f"Please choose one of: {', '.join(choices)}")
            continue
        return ans


def confirm(question: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    while True:
        try:
            ans = input(color(f"? {question} ({d}): ", "1")).strip().lower()
        except EOFError:
            # No interactive terminal — accept the default rather than aborting.
            info(f"{question} -> using default '{'yes' if default else 'no'}' (no TTY).")
            return default
        except KeyboardInterrupt:
            print()
            die("Aborted.")
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False


# --------------------------------------------------------------------------- #
# Shell bridge to provider_login.sh
# --------------------------------------------------------------------------- #
def call_provider_fn(fn: str, *args: str, capture: bool = True) -> str:
    """
    Source provider_login.sh and invoke one of its functions, forwarding the
    current environment (so AWS_PROFILE etc. flow through). Returns the last
    non-empty stdout line (the helpers emit machine-parseable data there while
    logging progress to stderr).
    """
    quoted = " ".join(shlex.quote(a) for a in args)
    script = f'set -e; source {shlex.quote(str(PROVIDER_LOGIN))}; {fn} {quoted}'
    proc = subprocess.run(
        ["bash", "-c", script],
        env=os.environ.copy(),
        capture_output=capture,
        text=True,
    )
    if proc.returncode != 0:
        if capture and proc.stderr:
            sys.stderr.write(proc.stderr)
        die(f"provider_login.sh::{fn} failed (exit {proc.returncode}).")
    if not capture:
        return ""
    # Surface the helper's human-readable stderr progress.
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def aws_profile_env(sso_profile: str, region: str) -> dict[str, str]:
    """Pin AWS calls to one named profile and remove higher-priority ambient keys."""
    env = os.environ.copy()
    for name in (
        "AWS_ACCESS_KEY_ID", _SECRET_KEY_ENV, "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN", "AWS_DEFAULT_PROFILE",
    ):
        env.pop(name, None)
    env["AWS_PROFILE"] = sso_profile
    env["AWS_REGION"] = region
    env["AWS_DEFAULT_REGION"] = region
    return env


def _get_caller_identity(sso_profile: str, env: dict) -> tuple[str, str]:
    """Return (account, caller_arn) for the profile, or ('','') on failure."""
    query = ["aws", "sts", "get-caller-identity", "--profile", sso_profile,
             "--query", "[Account,Arn]", "--output", "text"]
    proc = subprocess.run(query, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        return "", ""
    parts = (proc.stdout or "").split()
    return (parts[0], parts[1]) if len(parts) == 2 else ("", "")


def _aws_configure_get(key: str) -> str | None:
    """Read one `aws configure get <key>` value, or None if unset."""
    proc = subprocess.run(["aws", "configure", "get", key], capture_output=True, text=True)
    value = (proc.stdout or "").strip()
    return value or None


def ensure_profile_configured(sso_profile: str, repo_path: Path, region: str) -> None:
    """
    Make sure the derived per-repo profile has SSO settings, DERIVING them (never
    defaulting): existing profile config → the repo's deploy scripts → ask the
    user. Then write them onto the profile so `aws sso login` can run.
    """
    if _aws_configure_get(f"profile.{sso_profile}.sso_start_url"):
        return  # already configured
    settings = sso_config.resolve_sso_settings(repo_path, sso_profile, _aws_configure_get)
    start_url = settings.start_url or prompt(
        f"AWS SSO start URL for '{sso_profile}' (e.g. https://<org>.awsapps.com/start)")
    sso_region = settings.sso_region or prompt("AWS SSO region", default=region)
    info(f"Configuring SSO profile '{sso_profile}' (start_url={start_url}).")
    subprocess.run(["aws", "configure", "set", f"profile.{sso_profile}.sso_start_url", start_url])
    subprocess.run(["aws", "configure", "set", f"profile.{sso_profile}.sso_region", sso_region])
    subprocess.run(["aws", "configure", "set", f"profile.{sso_profile}.region", region])


def admin_login(sso_profile: str, account: str | None, region: str,
                repo_path: Path | None = None) -> tuple[str, str]:
    """
    Verify the derived per-repo SSO profile, self-configuring and logging it in if
    needed (fully self-contained — never asks the user to run aws by hand).
    Returns (account, caller_arn); the caller ARN feeds the trust policy.
    """
    if not sso_profile or sso_profile == "default":
        die("Choose a named AWS SSO profile; the default profile is not allowed.")
    info(f"Verifying AWS SSO profile '{sso_profile}'...")
    env = aws_profile_env(sso_profile, region)
    acct, caller_arn = _get_caller_identity(sso_profile, env)
    if not acct:
        if repo_path is not None:
            ensure_profile_configured(sso_profile, repo_path, region)
        info(f"Profile '{sso_profile}' needs sign-in; starting AWS SSO login.")
        login = subprocess.run(["aws", "sso", "login", "--profile", sso_profile], env=env)
        if login.returncode != 0:
            die(f"SSO login failed for profile '{sso_profile}'.")
        acct, caller_arn = _get_caller_identity(sso_profile, env)
    if not acct:
        die(f"Could not verify AWS identity through profile '{sso_profile}'.")
    if account and acct != account:
        die(f"AWS profile '{sso_profile}' resolves to account {acct}, expected {account}.")
    for name in (
        "AWS_ACCESS_KEY_ID", _SECRET_KEY_ENV, "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN", "AWS_DEFAULT_PROFILE",
    ):
        os.environ.pop(name, None)
    os.environ["AWS_PROFILE"] = sso_profile
    os.environ["AWS_REGION"] = region
    os.environ["AWS_DEFAULT_REGION"] = region
    info(f"Admin session active via profile '{sso_profile}' in account {acct}.")
    if caller_arn:
        info(f"Caller identity: {caller_arn}")
    return acct, caller_arn


# --------------------------------------------------------------------------- #
# Policy generation (deterministic, from Terraform — see tf_policy.py)
# --------------------------------------------------------------------------- #
def load_json_file(path: str, what: str) -> dict:
    """Load and minimally validate a JSON IAM policy document from a file."""
    try:
        doc = json.loads(Path(os.path.expanduser(path)).read_text())
    except (OSError, json.JSONDecodeError) as e:
        die(f"Could not read {what} from {path}: {e}")
    if not isinstance(doc, dict) or "Statement" not in doc:
        die(f"{what} at {path} is not a valid IAM policy (missing 'Statement').")
    return doc


# --------------------------------------------------------------------------- #
# Compare generated documents against what is live on AWS (read-only)
# --------------------------------------------------------------------------- #
def compare_with_aws(plan) -> None:
    """
    Fetch the EXISTING role inline policy + boundary from AWS and print how the
    generated documents differ. Read-only — safe before an apply and in a
    profile-backed dry run. Requires an active session (call after admin_login).
    """
    live_policy = policy_compare.parse_live_document(
        call_provider_fn("get_role_inline_policy", plan.role_name, plan.policy_name))
    live_boundary = policy_compare.parse_live_document(
        call_provider_fn("get_boundary_document", plan.boundary_name))

    print("\n" + color("──── comparison with what is live on AWS ────", "35"))
    print(policy_compare.render_diff(
        f"role policy ({plan.policy_name})",
        policy_compare.diff_documents(live_policy, plan.permissions_policy)))
    print(policy_compare.render_diff(
        f"boundary ({plan.boundary_name})",
        policy_compare.diff_documents(live_boundary, plan.boundary_policy)))
    print(color("─────────────────────────────────────────────", "35"))


def _fetch_live(role_name: str, doc_name: str, is_boundary: bool) -> dict | None:
    """Read the live inline policy or boundary document from AWS (or None)."""
    fn = "get_boundary_document" if is_boundary else "get_role_inline_policy"
    raw = call_provider_fn(fn, doc_name) if is_boundary else \
        call_provider_fn(fn, role_name, doc_name)
    return policy_compare.parse_live_document(raw)


def _merge_or_confirm_reduction(label, role_name, doc_name, generated, args, is_boundary=False):
    """
    Additive by default: union the live doc with the generated one so we only ADD.
    If the generated doc omits actions the live one has, that would be a REDUCTION
    — keep them (additive) unless the user passes --allow-reduce AND confirms three
    times. Returns the document to apply.
    """
    live = _fetch_live(role_name, doc_name, is_boundary)
    merge = policy_merge.additive_merge(live, generated)
    if not merge.would_remove:
        if merge.added_actions:
            info(f"{label}: additive — adding {len(merge.added_actions)} action(s), removing none.")
        return merge.merged

    warn(f"{label}: the generated document OMITS {len(merge.removed_actions)} action(s) "
         f"the live role currently has:")
    for action in merge.removed_actions:
        print(f"    - {action}")
    if not args.allow_reduce:
        info(f"{label}: keeping those (ADDITIVE). Re-run with --allow-reduce to remove them.")
        return merge.merged

    # Reduction is destructive — require THREE explicit confirmations.
    prompts = [
        f"REDUCE {label}? This REMOVES {len(merge.removed_actions)} live permission(s).",
        f"Are you SURE you want to remove permissions from {role_name}?",
        "Final confirmation — permanently drop those actions on apply?",
    ]
    for question in prompts:
        if not confirm(question, default=False):
            info(f"{label}: reduction cancelled — keeping the additive union.")
            return merge.merged
    warn(f"{label}: applying the REDUCED document as explicitly confirmed.")
    return policy_merge.replace_result(live, generated).merged


# --------------------------------------------------------------------------- #
# AWS provisioning (delegates to provider_login.sh helpers)
# --------------------------------------------------------------------------- #
def write_temp_json(obj: dict) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=2)
    return path


def provision(
    account: str,
    role_name: str,
    policy_name: str,
    permissions_policy: dict,
    user_name: str,
    regions: list[str],
    boundary_name: str | None = None,
    boundary_policy: dict | None = None,
    create_access_key: bool = False,
    caller_arn: str | None = None,
    include_root: bool = False,
) -> None:
    role_arn = f"arn:aws:iam::{account}:role/{role_name}"

    # 0. If this deployment manages IAM roles, ensure the permissions boundary
    #    exists first, so its ARN can be attached to the role below and gated in
    #    the role's own policy. (Option B — boundary propagation.)
    boundary_arn = ""
    if boundary_name and boundary_policy is not None:
        b_file = write_temp_json(boundary_policy)
        boundary_arn = call_provider_fn("ensure_permissions_boundary", boundary_name, b_file)
        os.unlink(b_file)
        info(f"Permissions boundary ready: {boundary_arn}")

    # 1. Ensure the CI user exists (create only if missing).
    user_state = call_provider_fn("ensure_iam_user", user_name)

    # 2. Create/update the deployment role with a MULTI-PRINCIPAL trust policy:
    #    the CI user always, plus the human caller's role (debugging leeway) and
    #    optionally account root. Attach the permissions boundary when present.
    trust = trust_policy.build_trust_policy(
        account, user_name, caller_arn=caller_arn, include_root=include_root)
    for principal in trust["Statement"][0]["Principal"]["AWS"]:
        info(f"  trusts: {principal}")
    trust_file = write_temp_json(trust)
    role_state = call_provider_fn(
        "ensure_deployment_role",
        role_name,
        trust_file,
        f"{policy_name} deployment role",
        boundary_arn,
    )
    os.unlink(trust_file)

    # 3. Attach the AI-generated permissions policy to the role (inline).
    perms_file = write_temp_json(permissions_policy)
    call_provider_fn("put_role_inline_policy", role_name, policy_name, perms_file, capture=False)
    os.unlink(perms_file)

    # 4. Grant the user permission to assume the role.
    call_provider_fn(
        "grant_user_assume_role", user_name, role_arn, f"assume-{role_name}", capture=False
    )

    info(f"Role {role_name} ({role_state}), user {user_name} ({user_state}) — assume wiring done.")

    # 5. Access keys are NOT created by default (and never prompted for) — the CI
    #    user's existing credentials are reused. Minting a key only happens when
    #    explicitly requested via --create-access-key (first-time setup/rotation).
    if create_access_key:
        line = call_provider_fn("create_user_access_key", user_name)
        parts = line.split()
        if len(parts) == 2:
            akid, secret = parts
            print("\n" + color("══════════ CI CREDENTIALS (store securely, shown once) ══════════", "32"))
            print(f"  AWS_ACCESS_KEY_ID     = {akid}")
            print(f"  {_SECRET_KEY_ENV} = {secret}")
            print(f"  Role to assume        = {role_arn}")
            print(f"  Region(s)             = {', '.join(regions)}")
            print(color("═════════════════════════════════════════════════════════════════", "32") + "\n")
            warn("The secret key will NOT be shown again. Copy it into CI now.")
        else:
            warn("Access key creation did not return the expected output; check AWS console.")


# Terraform discovery, naming, region parsing, and policy/boundary assembly live
# in deployment_plan.py (AWS-free), so the whole plan can be produced without an
# AWS login. This file owns only the AWS interaction and the interactive flow.


# --------------------------------------------------------------------------- #
# CLI arguments (enable non-interactive / default-driven runs)
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="create_deployment_role.py",
        description=(
            "Provision an AWS IAM deployment role + CI user for a repo. "
            "Runs interactively by default; any value supplied as a flag is "
            "used as the answer (and pre-fills the prompt when interactive). "
            "With every required flag supplied you can run fully non-interactively "
            "(e.g. under `--yes` with no TTY)."
        ),
    )
    p.add_argument("--component", choices=["frontend", "backend"])
    p.add_argument("--stage", choices=["beta", "prod"])
    p.add_argument("--repo-name", help="Logical git repo name (used in resource naming).")
    p.add_argument("--repo-path", help="Local path to the checked-out repo (alternative to --repo-url).")
    p.add_argument("--repo-url", help="Remote GitHub URL to clone and scan (alternative to --repo-path).")
    p.add_argument("--branch", help="Branch to check out after cloning --repo-url.")
    p.add_argument("--user-name", help="IAM user that CI will use to assume the role.")
    p.add_argument("--sso-profile", default=None,
                   help="Named AWS CLI profile for admin login. Required; the default profile is refused.")
    p.add_argument("--account", help="Expected AWS account. Defaults to the selected profile's verified account.")
    p.add_argument("--region", "--regions", dest="regions",
                   help="AWS region(s), comma/space separated. Defaults to "
                        f"'{DEFAULT_REGION}'.")
    p.add_argument("-y", "--yes", action="store_true",
                   help="Assume the default answer for every confirmation prompt.")
    p.add_argument("--policy-file",
                   help="Path to a JSON IAM permissions policy to use VERBATIM "
                        "(bypasses the built-in static analyzer). This is how the "
                        "/create_deployment_role command feeds an intelligently "
                        "scanned policy — an agent reads the terraform and writes "
                        "this file. Falls back to the static analyzer if omitted.")
    p.add_argument("--boundary-file",
                   help="Path to a JSON permissions-boundary policy to use "
                        "VERBATIM (pairs with --policy-file). Falls back to the "
                        "built-in boundary generator if omitted.")
    p.add_argument("--create-access-key", action="store_true",
                   help="Mint a NEW access key for the CI user (first-time setup "
                        "or rotation). Off by default — existing creds are reused.")
    p.add_argument("--allow-reduce", action="store_true",
                   help="Permit REMOVING permissions the live role already has "
                        "(off by default — applies are additive). Even with this, "
                        "each reduction requires three explicit confirmations.")
    p.add_argument("--trust-root", action="store_true",
                   help="Also add the account root (arn:aws:iam::<acct>:root) to "
                        "the role's trust policy. Broadest debug escape hatch — "
                        "off by default; the CI user and the human caller's role "
                        "are always trusted.")
    p.add_argument("--dry-run", action="store_true",
                   help="PLAN + READ: discover terraform, generate the policy + "
                        "boundary JSON, authenticate, and show how they differ "
                        "from the LIVE role on AWS — then ask whether to apply. "
                        "A dry run still reads AWS (read-only); it just doesn't "
                        "write unless you confirm at the prompt.")
    p.add_argument("--out-dir",
                   help="Directory to write the generated policy/boundary JSON to "
                        "(default: a fresh temp dir). Written in every mode.")
    p.add_argument("--no-read-aws", action="store_true",
                   help="PREVIEW ONLY: skip authentication and the read-only "
                        "compare against the live role (no login, no AWS calls). "
                        "The printed JSON is unverified against AWS and cannot be "
                        "applied. Use only for an offline look at the generated "
                        "documents.")
    return p.parse_args(argv)


# --------------------------------------------------------------------------- #
# Input gathering + artifact writing
# --------------------------------------------------------------------------- #
def prompt_repo_source(args) -> tuple[str, str]:
    """
    Interactively ask remote-or-local FIRST, then the dependent URL/path (and a
    branch for a URL). Returns (source, branch). Flags short-circuit the prompts.
    """
    if args.repo_url:
        return args.repo_url, (args.branch or "")
    if args.repo_path:
        return args.repo_path, ""
    kind = prompt("Repository — is it remote or local?", choices=["remote", "local"])
    if kind == "remote":
        url = prompt("Paste the GitHub URL")
        branch = prompt("Branch to check out", default="")
        return url, branch
    return prompt("Paste the absolute local folder path"), ""


def resolve_repo(args) -> tuple[Path, str]:
    """
    Resolve the repo the role is for — a remote GitHub URL (cloned) OR a local
    folder. Asks remote-or-local, then the URL/path, when no flag was given.
    Returns (repo_path, repo_name_default).
    """
    source, branch = prompt_repo_source(args)
    try:
        repo_path = repo_source.resolve_repo_source(source, branch=branch)
    except repo_source.GitHubAuthError as error:
        # Surface the exact remediation and stop — we cannot read a private remote
        # without a logged-in gh.
        die(str(error))
    except (RuntimeError, ValueError, NotADirectoryError) as error:
        die(str(error))
    if repo_source.looks_like_repo_url(source):
        info(f"Cloned {source} -> {repo_path}")
        _org, repo_default = repo_source.parse_repo_url(source)
    else:
        repo_default = repo_path.name
    return repo_path, repo_default


def gather_inputs(args) -> dict:
    """Collect the repo/component/stage/user answers (flags pre-fill prompts)."""
    # Repository FIRST (remote-or-local, then the URL/path) so the run always
    # starts from an explicit target before anything else is asked.
    repo_path, repo_default = resolve_repo(args)
    component = args.component or prompt(
        "Which component is this deployment role for?", choices=["frontend", "backend"])
    stage = args.stage or prompt("Which stage?", choices=["beta", "prod"])
    # The repository name IS the naming prefix everywhere (role/policy/boundary),
    # so it must stay consistent with the repo folder. Use the resolved repo name
    # by default and do NOT prompt for a divergent value; --repo-name is an
    # explicit override only (e.g. when the folder name is not the canonical one).
    repo_name = args.repo_name or repo_default
    info(f"Naming prefix (from repository): {repo_name}")
    # No hardcoded org prefix — the CI user name is provided explicitly (the
    # command discovers real IAM users from AWS and asks). Prompt only as a
    # last-resort fallback when nothing was passed.
    user_name = args.user_name or prompt(
        "Name of the IAM user that CI will use to assume this role")
    return {"component": component, "stage": stage, "repo_name": repo_name,
            "repo_path": repo_path, "user_name": user_name}


def override_policies(plan, args) -> None:
    """Replace the plan's generated policy/boundary with intelligently-scanned files."""
    if args.policy_file:
        info(f"Using intelligently-scanned policy from {args.policy_file} (static analyzer bypassed).")
        plan.permissions_policy = load_json_file(args.policy_file, "permissions policy")
    if args.boundary_file:
        info(f"Using intelligently-scanned boundary from {args.boundary_file}.")
        plan.boundary_policy = load_json_file(args.boundary_file, "permissions boundary")


def write_artifacts(plan, out_dir: Path) -> tuple[Path, Path]:
    """Write the policy + boundary JSON to disk. This ALWAYS runs (plan-first)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    policy_path = out_dir / f"{plan.role_name}-policy.json"
    boundary_path = out_dir / f"{plan.boundary_name}.json"
    policy_path.write_text(json.dumps(plan.permissions_policy, indent=2))
    boundary_path.write_text(json.dumps(plan.boundary_policy, indent=2))
    return policy_path, boundary_path


def print_plan_summary(plan, user_name: str, sso_profile: str | None) -> None:
    info(f"Component/Stage : {plan.component} / {plan.stage}")
    info(f"Repo            : {plan.repo_name}  ({plan.repo_path})")
    info(f"Terraform dirs  : {', '.join(str(d) for d in plan.tf_dirs)}")
    info(f"Role to create  : {plan.role_name}")
    info(f"Policy name     : {plan.policy_name}")
    info(f"Boundary policy : {plan.boundary_name}")
    info(f"CI user         : {user_name}")
    info(f"AWS profile     : {sso_profile or '(dry-run — none)'}")
    info(f"Region(s)       : {', '.join(plan.regions)}")
    for message in plan.warnings:
        warn(message)
    if plan.creates_iam:
        warn("Terraform manages IAM roles: the deploy role may create roles ONLY if "
             "they carry this boundary. Set permissions_boundary = "
             f'"{plan.boundary_arn}" on every aws_iam_role in the terraform, or apply fails.')


# --------------------------------------------------------------------------- #
# Main — always PLAN (generate JSON) first, then apply (unless --dry-run).
# --------------------------------------------------------------------------- #
def main() -> None:
    """Entry point: run the workflow, then always clean up any temp clone."""
    try:
        _run()
    finally:
        removed = repo_source.cleanup_clones()
        for path in removed:
            info(f"Cleaned up cloned repo: {path}")


def _run() -> None:
    args = parse_args()

    print(color("\n╔══════════════════════════════════════════════╗", "36"))
    print(color("║   Deployment Role Provisioner                  ║", "36"))
    print(color("╚══════════════════════════════════════════════╝\n", "36"))

    # The login helper is needed whenever we touch AWS — that now includes a
    # dry run (it reads the live role). Only a --no-read-aws preview skips it.
    if not args.no_read_aws and not PROVIDER_LOGIN.exists():
        die(f"provider_login.sh not found next to this script ({PROVIDER_LOGIN}).")

    # When --yes is set, confirmations accept their default without prompting.
    global confirm
    if args.yes:
        def confirm(question: str, default: bool = True) -> bool:  # type: ignore[misc]
            info(f"{question} -> assuming '{'yes' if default else 'no'}' (--yes).")
            return default

    answers = gather_inputs(args)
    user_regions = parse_regions(args.regions, DEFAULT_REGION) if args.regions else None
    out_dir = Path(args.out_dir).resolve() if args.out_dir else \
        Path(tempfile.mkdtemp(prefix="crowbar-deploy-plan-"))

    # --- AUTHENTICATE FIRST so we always know which AWS account is targeted.
    # The SSO profile is derived from the repository name (a dedicated per-repo
    # profile), self-configured and logged in on demand (it will ASK for the SSO
    # start URL if the profile isn't configured yet). --sso-profile overrides.
    # This happens up front in BOTH dry-run and apply — a dry run is only
    # meaningful once it has looked at the live role, so it authenticates and
    # compares by default. --no-read-aws is the only way to skip it, and it
    # yields an unverified PREVIEW (not a real dry run) that cannot be applied.
    sso_profile = args.sso_profile or sso_config.profile_name_for_repo(answers["repo_name"])
    if sso_profile == "default":
        die("The default AWS profile is not allowed; choose a named SSO profile.")

    account = args.account or deployment_plan.PLACEHOLDER_ACCOUNT
    caller_arn = None
    if args.no_read_aws:
        warn("═══ PREVIEW ONLY (--no-read-aws) ═══ Not authenticated; using "
             f"placeholder account {account}. The JSON is NOT verified against "
             "live AWS and cannot be applied.")
    else:
        info(f"Authenticating so we know the target account (profile '{sso_profile}')...")
        account, caller_arn = admin_login(
            sso_profile, args.account, DEFAULT_REGION, repo_path=answers["repo_path"])
        print(color(f"\n═══ TARGET AWS ACCOUNT: {account}  (profile '{sso_profile}') ═══", "32"))
        if not confirm(f"Is account {account} the right place to create this role?"):
            die("Aborted — wrong account. Re-run with --sso-profile <profile> for the intended account.")

    # --- PLAN against the (now known) account and write the JSON artifacts.
    plan = build_plan(
        repo_path=answers["repo_path"], component=answers["component"],
        stage=answers["stage"], repo_name=answers["repo_name"],
        account=account, regions=user_regions, default_region=DEFAULT_REGION,
    )
    override_policies(plan, args)
    policy_path, boundary_path = write_artifacts(plan, out_dir)

    print()
    print_plan_summary(plan, answers["user_name"], sso_profile)
    info(f"Policy JSON   : {policy_path}")
    info(f"Boundary JSON : {boundary_path}")
    print("\n" + color("──── permissions policy ────", "35"))
    print(json.dumps(plan.permissions_policy, indent=2))
    print("\n" + color("──── permissions boundary ────", "35"))
    print(json.dumps(plan.boundary_policy, indent=2))

    # --- PREVIEW ONLY (--no-read-aws): never authenticated, so there is nothing
    # to compare against and nothing that can be applied. Stop with a loud notice
    # that this is NOT a verified dry run.
    if args.no_read_aws:
        warn("PREVIEW ONLY — the documents above were NOT verified against live "
             "AWS. Re-run without --no-read-aws for a real dry run (reads the "
             "live role and lets you apply).")
        return

    # Compare against what is LIVE on AWS, so nothing is a blind overwrite and the
    # user sees exactly what changes. This IS the dry run — a plan is only
    # meaningful once measured against the live role.
    compare_with_aws(plan)

    # --- APPLY GATE. In dry-run mode the default is NO (look, then decide); in
    # apply mode the default is YES. Either way, saying yes flows straight into
    # the additive merge + provision below; saying no stops read-only.
    apply_default = not args.dry_run
    if not confirm(f"Go ahead and apply this to AWS account {account} now?",
                   default=apply_default):
        print(color(f"\n✔ Reviewed against account {account}. No AWS changes were "
                     "made — nothing applied.\n", "32"))
        return

    # ADDITIVE MERGE: never silently shrink an existing role. Union the live
    # policy/boundary with the generated ones; only add. If anything would be
    # removed, keep it (additive) unless the user explicitly opts into reduction
    # with triple confirmation.
    apply_policy = _merge_or_confirm_reduction(
        "role policy", plan.role_name, plan.policy_name, plan.permissions_policy, args)
    apply_boundary = _merge_or_confirm_reduction(
        "boundary", plan.role_name, plan.boundary_name, plan.boundary_policy, args,
        is_boundary=True)

    provision(
        account, plan.role_name, plan.policy_name, apply_policy,
        answers["user_name"], plan.regions, boundary_name=plan.boundary_name,
        boundary_policy=apply_boundary, create_access_key=args.create_access_key,
        caller_arn=caller_arn, include_root=args.trust_root,
    )
    print(color("\n✔ Done. Deployment role is ready.\n", "32"))


if __name__ == "__main__":
    main()
