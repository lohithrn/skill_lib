#!/usr/bin/env python3
"""
deployment_plan.py
==================

The AWS-FREE half of the deployment-role workflow: everything needed to decide
*what* a deployment role should be able to do, with no IAM/STS/SSO calls.

Given a repo path, component, and stage, this discovers the Terraform, derives
the resource names, detects the deploy regions, and assembles the least-privilege
permissions policy plus the permissions-boundary document. It calls out to
tf_policy.py (also AWS-free) for the resource->action mapping.

Keeping this separate from create_deployment_role.py means the whole plan can be
produced and printed WITHOUT authenticating to AWS — that is what powers the
provisioner's `--dry-run` mode and this module's own `python3 deployment_plan.py`
CLI. The account id is the only value the plan needs from AWS, so callers pass it
in (a placeholder is fine for a dry run).
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import tf_policy

# Account used in ARNs when the caller has not authenticated (dry-run/plan mode).
PLACEHOLDER_ACCOUNT = "000000000000"

# Well-known folders to check first when discovering terraform.
KNOWN_TF_DIRS = [
    "terraform", "infra", "infrastructure", "deploy/terraform",
    "deployment/terraform", "iac", "tf",
]


@dataclass
class DeploymentPlan:
    """The full AWS-free plan for a deployment role — everything but the apply."""
    component: str
    stage: str
    repo_name: str
    repo_path: Path
    tf_dirs: list[Path]
    detected_regions: list[str]
    regions: list[str]
    role_name: str
    policy_name: str
    boundary_name: str
    boundary_arn: str
    creates_iam: bool
    permissions_policy: dict
    boundary_policy: dict
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Terraform discovery (layered fallback — no AWS)
# --------------------------------------------------------------------------- #
def _dirs_with_tf(root: Path) -> list[Path]:
    """All directories under root that directly contain at least one *.tf."""
    found: set[Path] = set()
    for tf in root.rglob("*.tf"):
        if any(part in (".git", ".terraform", "node_modules") for part in tf.parts):
            continue
        found.add(tf.parent)
    return sorted(found)


def _resolve_hint(hint: str | None, script_dir: Path) -> Path | None:
    """Resolve a cd/chdir hint (possibly with $VARS or relative) into a real dir."""
    if hint is None:
        base = script_dir
    else:
        cleaned = re.sub(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*", "", hint).strip("\"'")
        if not cleaned:
            base = script_dir
        elif os.path.isabs(cleaned):
            base = Path(cleaned)
        else:
            base = (script_dir / cleaned).resolve()
    if base.is_dir() and list(base.glob("*.tf")):
        return base
    return None


def _infer_tf_dirs_from_scripts(root: Path) -> list[Path]:
    """Scan scripts/CI for `terraform apply|init|plan` and infer their directory."""
    candidates: set[Path] = set()
    exts = {".sh", ".bash", ".yml", ".yaml", ".zsh"}
    tf_cmd = re.compile(r"terraform\s+(?:-chdir=(\S+)\s+)?(?:apply|init|plan)", re.IGNORECASE)
    chdir_re = re.compile(r"-chdir=(\S+)")
    cd_re = re.compile(r"\bcd\s+([^\s;&|]+)")
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        if any(part in (".git", ".terraform", "node_modules") for part in f.parts):
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        if "terraform" not in text:
            continue
        candidates.update(_infer_from_text(text, f.parent, tf_cmd, chdir_re, cd_re))
    return sorted(candidates)


def _infer_from_text(text, script_dir, tf_cmd, chdir_re, cd_re) -> set[Path]:
    """Per-file inference of terraform dirs from cd/-chdir hints near tf commands."""
    found: set[Path] = set()
    last_cd: str | None = None
    for line in text.splitlines():
        m_cd = cd_re.search(line)
        if m_cd:
            last_cd = m_cd.group(1)
        if not tf_cmd.search(line):
            continue
        m_chdir = chdir_re.search(line)
        target = m_chdir.group(1) if m_chdir else last_cd
        resolved = _resolve_hint(target, script_dir)
        if resolved:
            found.add(resolved)
    return found


def discover_terraform(repo: Path, stage: str) -> list[Path]:
    """Layered fallback discovery; returns the first non-empty layer's directories."""
    known: list[Path] = []
    for rel in KNOWN_TF_DIRS:
        d = repo / rel
        if not d.is_dir():
            continue
        for stage_sub in (d / stage, d / "environments" / stage, d / "env" / stage):
            if stage_sub.is_dir() and list(stage_sub.glob("*.tf")):
                known.append(stage_sub)
        if list(d.glob("*.tf")):
            known.append(d)
    if known:
        return sorted(set(known))
    inferred = _infer_tf_dirs_from_scripts(repo)
    if inferred:
        return inferred
    anywhere = _dirs_with_tf(repo)
    return anywhere or [repo]


# --------------------------------------------------------------------------- #
# Naming + regions (no AWS)
# --------------------------------------------------------------------------- #
def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-").lower()


def build_names(repo_name: str, component: str, stage: str) -> tuple[str, str, str]:
    """Return (role_name, policy_name, boundary_name) with parallel suffixes."""
    base = f"{sanitize(repo_name)}-{component}-{stage}-deploy"
    return f"{base}-role", f"{base}-policy", f"{base}-boundary"


def parse_regions(raw: str, default: str) -> list[str]:
    """Split a comma/space separated region string into a de-duped, ordered list."""
    seen: set[str] = set()
    regions: list[str] = []
    for token in re.split(r"[,\s]+", raw.strip()):
        token = token.strip()
        if token and token not in seen:
            seen.add(token)
            regions.append(token)
    return regions or [default]


def merge_regions(regions: list[str] | None, detected: list[str], default: str) -> list[str]:
    """The caller's regions first (or detected when none), then any detected not already listed."""
    chosen = list(regions) if regions else list(detected)
    return parse_regions(",".join(chosen + detected), default)


# --------------------------------------------------------------------------- #
# Plan assembly
# --------------------------------------------------------------------------- #
def build_plan(
    repo_path: Path,
    component: str,
    stage: str,
    repo_name: str,
    account: str = PLACEHOLDER_ACCOUNT,
    regions: list[str] | None = None,
    default_region: str = "us-west-2",
) -> DeploymentPlan:
    """
    Produce the complete AWS-free plan: discovery -> regions -> names -> policy +
    boundary. `regions` (if given) are the caller's explicit choice; detected
    regions are appended. `account` only affects ARNs, so a placeholder is fine
    for a dry run.
    """
    warnings: list[str] = []
    tf_dirs = discover_terraform(repo_path, stage)
    detected = tf_policy.detect_regions(tf_dirs, repo=repo_path, stage=stage)
    merged = merge_regions(regions, detected, default_region)

    role_name, policy_name, boundary_name = build_names(repo_name, component, stage)
    boundary_arn = f"arn:aws:iam::{account}:policy/{boundary_name}"
    creates_iam = tf_policy.needs_boundary(tf_dirs)

    # Prod confines regional actions to the target region(s); beta is unrestricted.
    guardrail_regions = merged if stage == "prod" else None
    permissions_policy = tf_policy.generate_policy_from_dirs(
        tf_dirs, warn=warnings.append, regions=guardrail_regions, boundary_arn=boundary_arn,
    )
    boundary_policy = tf_policy.generate_boundary_from_dirs(tf_dirs, boundary_arn)

    return DeploymentPlan(
        component=component, stage=stage, repo_name=repo_name, repo_path=repo_path,
        tf_dirs=tf_dirs, detected_regions=detected, regions=merged,
        role_name=role_name, policy_name=policy_name, boundary_name=boundary_name,
        boundary_arn=boundary_arn, creates_iam=creates_iam,
        permissions_policy=permissions_policy, boundary_policy=boundary_policy,
        warnings=warnings,
    )


# --------------------------------------------------------------------------- #
# Standalone CLI: print a plan as JSON, no AWS calls.
#   python3 deployment_plan.py --repo-path . --component frontend --stage prod
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="deployment_plan.py",
        description="Produce the AWS-free deployment plan (terraform discovery, "
                    "regions, names, IAM policy + boundary) and print it as JSON. "
                    "Makes no AWS calls.",
    )
    p.add_argument("--repo-path", required=True, help="Local path to the repo.")
    p.add_argument("--component", required=True, choices=["frontend", "backend"])
    p.add_argument("--stage", required=True, choices=["beta", "prod"])
    p.add_argument("--repo-name", help="Logical repo name (default: folder name).")
    p.add_argument("--account", default=PLACEHOLDER_ACCOUNT, help="Account id for ARNs.")
    p.add_argument("--region", "--regions", dest="regions", help="Region(s), comma/space separated.")
    return p.parse_args(argv)


def plan_to_dict(plan: DeploymentPlan) -> dict:
    """JSON-serializable view of a plan (Paths -> strings)."""
    return {
        "component": plan.component, "stage": plan.stage, "repo_name": plan.repo_name,
        "repo_path": str(plan.repo_path),
        "tf_dirs": [str(d) for d in plan.tf_dirs],
        "detected_regions": plan.detected_regions, "regions": plan.regions,
        "role_name": plan.role_name, "policy_name": plan.policy_name,
        "boundary_name": plan.boundary_name, "boundary_arn": plan.boundary_arn,
        "creates_iam": plan.creates_iam,
        "permissions_policy": plan.permissions_policy,
        "boundary_policy": plan.boundary_policy,
        "warnings": plan.warnings,
    }


def main() -> None:
    args = parse_args()
    repo_path = Path(os.path.expanduser(args.repo_path)).resolve()
    plan = build_plan(
        repo_path=repo_path, component=args.component, stage=args.stage,
        repo_name=args.repo_name or repo_path.name, account=args.account,
        regions=parse_regions(args.regions, "us-west-2") if args.regions else None,
    )
    print(json.dumps(plan_to_dict(plan), indent=2))


if __name__ == "__main__":
    main()
