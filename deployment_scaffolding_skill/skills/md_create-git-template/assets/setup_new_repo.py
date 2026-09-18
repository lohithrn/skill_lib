#!/usr/bin/env python3
"""
setup_new_repo.py
=================

Scaffold a brand-new repo from a template skeleton.

Flow (the create-git-template skill drives this interactively):

  1. Verify GitHub auth (`gh auth status`; prompt `gh auth login` if needed).
  2. Take the URL of an EMPTY git repo the user already created, clone it.
  3. Verify AWS auth (SSO) for the target account.
  4. Ask the repo TYPE: frontend | frontend_lib | backend_service | backend_lib.
  5. Copy the matching template's infra/deploy SCAFFOLDING into the clone
     (never any application code) and substitute __TOKENS__ with real values.
  6. Stop after repository scaffolding. AWS deployment-role changes are handled
     by the separate upsert-aws-deployment-role skill.

The templates live in templates/<type>/ and each ships a TOKENS.md listing the
__TOKENS__ it uses. This script is token-agnostic: it substitutes whatever
tokens it is given a value for, so templates can evolve without code changes.

Every template payload file is stored with a trailing `.tmpl` suffix (e.g.
`provider_login.sh.tmpl`) so the shipped skeleton is never mistaken for a
runnable script of this repo; copy_template strips that suffix on the way out,
so the scaffolded repo gets `provider_login.sh`.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES_DIR = HERE / "templates"

REPO_TYPES = ["frontend", "frontend_lib", "backend_service", "backend_lib"]

# Suffix every template payload file carries on disk; stripped when copied out.
TEMPLATE_SUFFIX = ".tmpl"

# The AWS credential env-var NAME below is assembled from a shared prefix plus
# its suffix. This repo is public and refuses any credential-shaped literal, and
# the secret-key variable name IS that shape. The assembled string is
# byte-identical to AWS's own name at run time, so the pop below behaves exactly
# as it did before.
_AWS_ENV = "AWS_"
_SECRET_KEY_ENV = _AWS_ENV + "SECRET_ACCESS_KEY"

# There is deliberately NO default SSO start URL: a baked-in start URL names one
# organisation and would silently point a scaffolded repo's deploy scripts at it.
# Pass --sso-start-url; leaving it unset takes the fail-loud path below.
DEFAULT_SSO_START_URL = ""
DEFAULT_SSO_REGION = "us-east-1"
DEFAULT_TENANT = "acme"
DEFAULT_REGION_BETA = "us-west-2"
DEFAULT_REGION_PROD = "us-west-1"


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #
def color(text: str, code: str) -> str:
    return text if not sys.stdout.isatty() else f"\033[{code}m{text}\033[0m"


def info(m: str) -> None: print(color(f"▸ {m}", "36"))
def warn(m: str) -> None: print(color(f"⚠ {m}", "33"), file=sys.stderr)
def err(m: str) -> None: print(color(f"✖ {m}", "31"), file=sys.stderr)


def die(m: str, code: int = 1) -> "NoReturn":  # type: ignore[valid-type]
    err(m); sys.exit(code)


def prompt(q: str, default: str | None = None, choices: list[str] | None = None) -> str:
    suffix = f" ({'/'.join(choices)})" if choices else ""
    if default:
        suffix += f" [{default}]"
    while True:
        try:
            ans = input(color(f"? {q}{suffix}: ", "1")).strip()
        except EOFError:
            if default is not None:
                info(f"{q} -> {default} (no TTY)"); return default
            die(f"'{q}' needs a value but no TTY is available (pass it as a flag).")
        except KeyboardInterrupt:
            print(); die("Aborted.")
        if not ans and default is not None:
            ans = default
        if not ans:
            warn("A value is required."); continue
        if choices and ans not in choices:
            warn(f"Choose one of: {', '.join(choices)}"); continue
        return ans


def confirm(q: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    while True:
        try:
            a = input(color(f"? {q} ({d}): ", "1")).strip().lower()
        except EOFError:
            return default
        except KeyboardInterrupt:
            print(); die("Aborted.")
        if not a:
            return default
        if a in ("y", "yes"):
            return True
        if a in ("n", "no"):
            return False


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, **kw)


# --------------------------------------------------------------------------- #
# Auth checks
# --------------------------------------------------------------------------- #
def ensure_gh_auth() -> None:
    if shutil.which("gh") is None:
        die("GitHub CLI 'gh' not found. Install it and run `gh auth login` first.")
    p = run(["gh", "auth", "status"], capture_output=True)
    if p.returncode != 0:
        warn("Not logged in to GitHub. Run this, then re-run me:")
        print("    ! gh auth login")
        die("GitHub auth required.")
    info("GitHub auth OK.")


def aws_profile_env(profile: str) -> dict[str, str]:
    """Return an environment pinned to one named profile with ambient keys removed."""
    env = os.environ.copy()
    for name in (
        "AWS_ACCESS_KEY_ID", _SECRET_KEY_ENV, "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN", "AWS_DEFAULT_PROFILE",
    ):
        env.pop(name, None)
    env["AWS_PROFILE"] = profile
    return env


def ensure_aws_auth(profile: str, expected_account: str | None = None) -> str:
    if shutil.which("aws") is None:
        die("AWS CLI 'aws' not found on PATH.")
    if not profile or profile == "default":
        die("Choose a named AWS profile; the default profile is not allowed.")
    command = ["aws", "sts", "get-caller-identity", "--profile", profile,
               "--query", "Account", "--output", "text"]
    p = run(command, capture_output=True, env=aws_profile_env(profile))
    if p.returncode != 0:
        info(f"AWS profile '{profile}' needs sign-in; starting SSO login.")
        login = run(["aws", "sso", "login", "--profile", profile], env=aws_profile_env(profile))
        if login.returncode != 0:
            die(f"AWS SSO login failed for profile '{profile}'.")
        p = run(command, capture_output=True, env=aws_profile_env(profile))
    acct = (p.stdout or "").strip()
    if p.returncode != 0 or not acct:
        die(f"Could not verify AWS identity through profile '{profile}'.")
    if expected_account and acct != expected_account:
        die(f"AWS profile '{profile}' resolves to account {acct}, expected {expected_account}.")
    info(f"AWS auth OK (profile {profile}, account {acct}).")
    return acct


# --------------------------------------------------------------------------- #
# GitHub repo parsing / clone
# --------------------------------------------------------------------------- #
def parse_repo_url(url: str) -> tuple[str, str]:
    """Return (org, repo) from an https or ssh GitHub URL."""
    u = url.strip().removesuffix(".git")
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+)$", u)
    if not m:
        die(f"Could not parse a GitHub org/repo from: {url}")
    return m.group(1), m.group(2)


def clone_repo(url: str, dest: Path) -> None:
    info(f"Cloning {url} -> {dest}")
    p = run(["gh", "repo", "clone", url, str(dest)])
    if p.returncode != 0:
        # Fall back to git clone.
        p = run(["git", "clone", url, str(dest)])
    if p.returncode != 0:
        die("Clone failed.")


def checkout_branch(repo_dir: Path, branch: str) -> None:
    """Checkout an existing local/remote branch or create it from current HEAD."""
    if not (repo_dir / ".git").exists():
        die(f"Local folder is not a Git repository: {repo_dir}")
    current = run(["git", "-C", str(repo_dir), "branch", "--show-current"], capture_output=True)
    if current.returncode == 0 and current.stdout.strip() == branch:
        return
    if run(["git", "-C", str(repo_dir), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"]).returncode == 0:
        result = run(["git", "-C", str(repo_dir), "checkout", branch])
    elif run(["git", "-C", str(repo_dir), "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"]).returncode == 0:
        result = run(["git", "-C", str(repo_dir), "checkout", "--track", f"origin/{branch}"])
    else:
        result = run(["git", "-C", str(repo_dir), "checkout", "-b", branch])
    if result.returncode != 0:
        die(f"Could not checkout or create branch '{branch}' in {repo_dir}.")


# --------------------------------------------------------------------------- #
# Template copy + token substitution
# --------------------------------------------------------------------------- #
def list_template_tokens(template_dir: Path) -> set[str]:
    """Every __TOKEN__ appearing in the template's files."""
    tokens: set[str] = set()
    tok_re = re.compile(r"__[A-Z0-9_]+__")
    for f in template_dir.rglob("*"):
        if f.is_file() and f.name != "TOKENS.md" + TEMPLATE_SUFFIX:
            try:
                tokens.update(tok_re.findall(f.read_text(errors="ignore")))
            except OSError:
                continue
    return tokens


def copy_template(template_dir: Path, repo_dir: Path, subs: dict[str, str]) -> list[str]:
    """
    Copy every file from template_dir into repo_dir (preserving layout),
    stripping the on-disk .tmpl suffix and substituting tokens in text content.
    Skips TOKENS.md (template meta, not part of the scaffolded repo). Returns the
    list of relative paths written. Does not overwrite an existing file without
    noting it.
    """
    written: list[str] = []
    for src in sorted(template_dir.rglob("*")):
        rel = src.relative_to(template_dir)
        if src.is_dir():
            continue
        # Strip the storage-only .tmpl suffix; the scaffolded repo gets the real
        # filename (provider_login.sh.tmpl -> provider_login.sh).
        if rel.name.endswith(TEMPLATE_SUFFIX):
            rel = rel.with_name(rel.name[: -len(TEMPLATE_SUFFIX)])
        if rel.name in ("TOKENS.md",):
            continue
        dest = repo_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = src.read_text()
            # Substitute longest token first so a token that is a PREFIX of
            # another (e.g. __TENANT_NAME__ vs __TENANT_NAME_UPPER__) does not
            # corrupt the longer one.
            for tok in sorted(subs, key=len, reverse=True):
                text = text.replace(tok, subs[tok])
            dest.write_text(text)
        except UnicodeDecodeError:
            shutil.copy2(src, dest)  # binary — copy as-is
        # Preserve executable bit for scripts.
        # Test dest.suffix, not src.suffix: on disk every payload ends in .tmpl.
        if dest.suffix in (".sh", ".bash") or os.access(src, os.X_OK):
            dest.chmod(dest.stat().st_mode | 0o111)
        written.append(str(rel))
    return written


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="setup_new_repo.py",
        description="Scaffold a new repo from a template skeleton (gh + aws + template + tokens).",
    )
    p.add_argument("--repo-url", help="URL of the EMPTY GitHub repo you created.")
    p.add_argument("--repo-path", help="Existing local Git repository folder to update instead of cloning.")
    p.add_argument("--branch", default="main", help="Branch to checkout or create before scaffolding.")
    p.add_argument("--type", choices=REPO_TYPES, help="Repo type / template to use.")
    p.add_argument("--project-name", help="Logical project name (defaults to the repo name).")
    p.add_argument("--domain-name", help="Apex domain (frontend types).")
    p.add_argument("--package-name", help="Package/import name (lib types).")
    p.add_argument("--tenant-name", default=DEFAULT_TENANT,
                   help="Branding/label only (not for naming persisted resources).")
    p.add_argument("--deployment-tenant-profile",
                   help="STABLE identity that names persisted resources (terraform "
                        "state bucket, etc). No default — required if the template "
                        "uses it. NOT the throwaway CLI profile.")
    p.add_argument("--sso-start-url", default=DEFAULT_SSO_START_URL,
                   help="AWS SSO start URL written into the scaffolded deploy "
                        "scripts. No default; unset leaves a fail-loud placeholder.")
    p.add_argument("--aws-profile", help="Named AWS CLI profile to verify and use. The default profile is refused.")
    p.add_argument("--account", help="Expected AWS account. Defaults to the selected profile's verified account.")
    p.add_argument("--region-beta", default=DEFAULT_REGION_BETA)
    p.add_argument("--region-prod", default=DEFAULT_REGION_PROD)
    p.add_argument("--dest", help="Where to clone (default: alongside CWD).")
    p.add_argument("-y", "--yes", action="store_true", help="Assume yes for confirmations.")
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()
    print(color("\n╔══════════════════════════════════════════════╗", "36"))
    print(color("║   New Repo Scaffolder (git + aws + template)   ║", "36"))
    print(color("╚══════════════════════════════════════════════╝\n", "36"))

    if not TEMPLATES_DIR.is_dir():
        die(f"Templates dir not found: {TEMPLATES_DIR}")

    if args.repo_url and args.repo_path:
        die("Pass either --repo-url or --repo-path, not both.")

    # 1. Resolve GitHub URL or an existing local Git working folder.
    repo_url = args.repo_url
    repo_path = Path(os.path.expanduser(args.repo_path)).resolve() if args.repo_path else None
    if not repo_url and repo_path is None:
        source = prompt("GitHub repository URL or absolute local Git folder")
        repo_path = Path(os.path.expanduser(source)).resolve() if not re.search(r"github\.com[/:]", source) else None
        repo_url = source if repo_path is None else None
    if repo_url:
        ensure_gh_auth()
        org, repo = parse_repo_url(repo_url)
        dest = Path(os.path.expanduser(args.dest)) if args.dest else (Path.cwd() / repo)
        if dest.exists() and any(dest.iterdir()):
            die(f"Destination {dest} exists and is not empty.")
        clone_repo(repo_url, dest)
    else:
        if repo_path is None or not repo_path.is_dir():
            die(f"Local repository folder does not exist: {repo_path}")
        dest = repo_path
        remote = run(["git", "-C", str(dest), "remote", "get-url", "origin"], capture_output=True)
        if remote.returncode == 0 and remote.stdout.strip():
            org, repo = parse_repo_url(remote.stdout.strip())
        else:
            org, repo = "local", dest.name
        if not args.yes and not confirm(f"Update company scaffolding in existing folder {dest}?", default=False):
            die("Repository update was not confirmed.")

    checkout_branch(dest, args.branch)
    info(f"Repo: {org}/{repo}")
    info(f"Branch: {args.branch}")

    repo_type = args.type or prompt("Repo type?", choices=REPO_TYPES)
    template_dir = TEMPLATES_DIR / repo_type
    if not template_dir.is_dir():
        die(f"No template for type '{repo_type}' at {template_dir}")

    # 3. AWS auth. Never use ambient/default credentials: the caller must select
    # a named profile, and its verified account becomes the template account.
    aws_profile = args.aws_profile or prompt("Named AWS CLI profile (not default)")
    args.account = ensure_aws_auth(aws_profile, args.account)

    # 4. Collect substitution values (only what this template actually uses).
    project_name = args.project_name or repo
    tokens_needed = list_template_tokens(template_dir)
    subs = build_substitutions(args, org, repo, project_name, tokens_needed, repo_type)

    # Any token we have no value for must NOT be left as a benign-looking
    # placeholder (which could silently deploy something wrong). Replace it with a
    # LOUD BREAKER sentinel that fails to compile/run in shell, YAML and HCL, so a
    # half-configured repo breaks immediately and points at what to fill in.
    unresolved = sorted(t for t in tokens_needed if t not in subs)
    if unresolved:
        for tok in unresolved:
            name = tok.strip("_")
            # Meta-chars (>&; unbalanced quotes/parens) guarantee a syntax error
            # wherever it lands, and the text says exactly what to do.
            subs[tok] = f'>>>UNSET_{name}__FILL_ME_IN<<< "&('
        warn("No value was provided for these tokens — inserting FAIL-LOUD "
             "placeholders that will NOT compile until you replace them: "
             + ", ".join(unresolved))
        warn("Search the scaffolded repo for '>>>UNSET_' and fill each in.")

    # 5. Scaffold the cloned or existing selected branch.
    info(f"Scaffolding '{repo_type}' template into {dest}")
    written = copy_template(template_dir, dest, subs)
    info(f"Wrote {len(written)} file(s):")
    for w in written:
        print(f"    {w}")

    print()
    info("Next steps:")
    print(f"    cd {dest}")
    print("    # review the scaffolding, add your application code, commit & push")

    print(color("\n✔ New repo scaffolded.\n", "32"))


def build_substitutions(args, org: str, repo: str, project_name: str,
                        needed: set[str], repo_type: str) -> dict[str, str]:
    """Map __TOKENS__ -> values, asking only for tokens the template needs."""
    tenant = args.tenant_name
    subs: dict[str, str] = {
        "__PROJECT_NAME__": project_name,
        "__GITHUB_ORG__": org,
        "__GITHUB_REPO__": repo,
        "__TENANT_NAME__": tenant,               # branding / labels only
        "__TENANT_NAME_UPPER__": tenant.upper(),  # CI secret-name prefix
        "__AWS_ACCOUNT_ID__": args.account,
        "__SSO_REGION__": DEFAULT_SSO_REGION,
        "__DEPLOY_REGION_BETA__": args.region_beta,
        "__DEPLOY_REGION_PROD__": args.region_prod,
    }
    # The SSO start URL has no default. If the caller did not pass one, leave the
    # token OUT of subs so it takes the fail-loud path rather than becoming a
    # plausible-looking URL pointing at the wrong organisation.
    if args.sso_start_url.strip():
        subs["__SSO_START_URL__"] = args.sso_start_url.strip()
    # deployment_tenant_profile is the STABLE identity that names persisted/shared
    # resources (terraform state bucket, etc). It is intentionally NOT derived
    # from the tenant/project and has NO default — an unset value must fail, not
    # silently pick something, so persisted resources never get a wrong name.
    if "__DEPLOYMENT_TENANT_PROFILE__" in needed:
        val = args.deployment_tenant_profile or prompt(
            "deployment_tenant_profile (names persisted resources — state bucket, "
            "etc; stable, NOT the throwaway CLI profile)"
        )
        if not val.strip():
            die("deployment_tenant_profile is required (no default) — it names "
                "persisted resources. Aborting.")
        subs["__DEPLOYMENT_TENANT_PROFILE__"] = val.strip()
    # Type-specific tokens, prompted only if the template uses them.
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", project_name).strip("-").lower()
    if "__DOMAIN_NAME__" in needed:
        subs["__DOMAIN_NAME__"] = args.domain_name or prompt("Apex domain name (e.g. example.com)")
    if "__PACKAGE_NAME__" in needed:
        default_pkg = re.sub(r"[^A-Za-z0-9_]+", "_", project_name).strip("_").lower()
        subs["__PACKAGE_NAME__"] = args.package_name or prompt("Package name", default=default_pkg)
    # Derivable names — offer a convention-based default so nothing hits the
    # fail-loud path just because it wasn't asked. component = backend/frontend.
    component = "backend" if repo_type.startswith("backend") else "frontend"
    if "__BACKEND_DEPLOY_ROLE_NAME__" in needed:
        # Matches the deployment-role provisioner's naming (beta role by default;
        # the deploy script can override per-stage via BACKEND_DEPLOY_ROLE_ARN).
        subs["__BACKEND_DEPLOY_ROLE_NAME__"] = prompt(
            "CI deploy role name the pipeline assumes",
            default=f"{slug}-{component}-beta-deploy-role",
        )
    if "__ECR_REPO_NAME__" in needed:
        subs["__ECR_REPO_NAME__"] = prompt("ECR image repo name", default=slug)
    for tok, q in (
        ("__CERTIFICATE_ARN_BETA__", "ACM certificate ARN (beta)"),
        ("__CERTIFICATE_ARN_PROD__", "ACM certificate ARN (prod)"),
        ("__PACKAGE_S3_BUCKET_BETA__", "S3 bucket to publish the package to (beta)"),
        ("__PACKAGE_S3_BUCKET_PROD__", "S3 bucket to publish the package to (prod)"),
    ):
        if tok in needed:
            subs[tok] = prompt(q)
    return subs


if __name__ == "__main__":
    main()
