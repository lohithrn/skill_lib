#!/usr/bin/env python3
"""
tf_policy.py
============

Deterministic Terraform -> IAM permissions policy generator.

Given a set of Terraform directories, this parses out the `aws_*` resource and
data-source types actually used (plus any `backend "s3"` block) and emits a
least-privilege IAM policy granting exactly the actions a CI `terraform apply`
needs: create/read/update/delete for each resource type, read for each data
source, and S3+DynamoDB access for the remote state backend.

This replaces the previous "shell out to an AI CLI" approach: it is fast,
offline, reproducible, and has no external dependencies. Unknown resource types
degrade gracefully to a service-level wildcard (e.g. `elasticache:*`) with a
warning, so nothing is silently dropped.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Regexes for the two things we care about in .tf source.
_RESOURCE_RE = re.compile(r'resource\s+"(aws_[a-z0-9_]+)"')
_DATA_RE = re.compile(r'data\s+"(aws_[a-z0-9_]+)"')
_BACKEND_S3_RE = re.compile(r'backend\s+"s3"')

# --------------------------------------------------------------------------- #
# Resource-type -> IAM actions mapping.
#
# Keys are Terraform aws_* resource type names. Values are the IAM actions a
# full CRUD terraform lifecycle needs. Kept intentionally explicit (not just
# "s3:*") so the generated policy is genuinely least-privilege for the common
# resource types. Anything not in this table falls back to "<service>:*".
# --------------------------------------------------------------------------- #
RESOURCE_ACTIONS: dict[str, list[str]] = {
    # ---- S3 ----
    "aws_s3_bucket": [
        "s3:CreateBucket", "s3:DeleteBucket", "s3:ListBucket",
        "s3:GetBucketLocation", "s3:GetBucketTagging", "s3:PutBucketTagging",
        "s3:GetBucketVersioning", "s3:PutBucketVersioning",
        "s3:GetBucketAcl", "s3:PutBucketAcl",
        "s3:GetEncryptionConfiguration", "s3:PutEncryptionConfiguration",
        "s3:GetBucketLogging", "s3:PutBucketLogging",
        "s3:GetLifecycleConfiguration", "s3:PutLifecycleConfiguration",
        "s3:GetBucketCORS", "s3:PutBucketCORS",
        "s3:GetBucketOwnershipControls", "s3:PutBucketOwnershipControls",
        "s3:GetAccelerateConfiguration",
    ],
    "aws_s3_bucket_policy": [
        "s3:GetBucketPolicy", "s3:PutBucketPolicy", "s3:DeleteBucketPolicy",
    ],
    "aws_s3_bucket_public_access_block": [
        "s3:GetBucketPublicAccessBlock", "s3:PutBucketPublicAccessBlock",
    ],
    "aws_s3_bucket_website_configuration": [
        "s3:GetBucketWebsite", "s3:PutBucketWebsite", "s3:DeleteBucketWebsite",
    ],
    "aws_s3_bucket_versioning": [
        "s3:GetBucketVersioning", "s3:PutBucketVersioning",
    ],
    "aws_s3_bucket_acl": ["s3:GetBucketAcl", "s3:PutBucketAcl"],
    "aws_s3_object": [
        "s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket",
    ],
    # ---- CloudFront ----
    "aws_cloudfront_distribution": [
        "cloudfront:CreateDistribution", "cloudfront:CreateDistributionWithTags",
        "cloudfront:GetDistribution",
        "cloudfront:GetDistributionConfig", "cloudfront:UpdateDistribution",
        "cloudfront:DeleteDistribution", "cloudfront:ListDistributions",
        "cloudfront:TagResource", "cloudfront:UntagResource",
        "cloudfront:ListTagsForResource", "cloudfront:CreateInvalidation",
        # A distribution with a viewer_certificate ALWAYS makes CloudFront read
        # the ACM cert during CreateDistribution — even when the cert is passed
        # by raw ARN (var.certificate_arn) with no aws_acm_certificate resource
        # or data source in the TF for the scanner to see. That validation call
        # runs against us-east-1 (where CloudFront certs must live). Without
        # these, CloudFront rejects the create with the MISLEADING error
        # "InvalidViewerCertificate: certificate doesn't exist / isn't valid".
        # So a distribution implies ACM read regardless of what else the TF
        # references. (acm is in GLOBAL_SERVICES, so granting it here also makes
        # the region guardrail below exempt it from the us-east-1 deny.)
        "acm:DescribeCertificate", "acm:ListCertificates",
        "acm:GetCertificate", "acm:ListTagsForCertificate",
    ],
    "aws_cloudfront_origin_access_identity": [
        "cloudfront:CreateCloudFrontOriginAccessIdentity",
        "cloudfront:GetCloudFrontOriginAccessIdentity",
        "cloudfront:GetCloudFrontOriginAccessIdentityConfig",
        "cloudfront:UpdateCloudFrontOriginAccessIdentity",
        "cloudfront:DeleteCloudFrontOriginAccessIdentity",
        "cloudfront:ListCloudFrontOriginAccessIdentities",
    ],
    "aws_cloudfront_origin_access_control": [
        "cloudfront:CreateOriginAccessControl",
        "cloudfront:GetOriginAccessControl",
        "cloudfront:GetOriginAccessControlConfig",
        "cloudfront:UpdateOriginAccessControl",
        "cloudfront:DeleteOriginAccessControl",
        "cloudfront:ListOriginAccessControls",
    ],
    # ---- Route53 ----
    "aws_route53_record": [
        "route53:ChangeResourceRecordSets", "route53:GetHostedZone",
        "route53:ListResourceRecordSets", "route53:GetChange",
    ],
    "aws_route53_zone": [
        "route53:CreateHostedZone", "route53:GetHostedZone",
        "route53:DeleteHostedZone", "route53:ListHostedZones",
        "route53:ChangeTagsForResource", "route53:ListTagsForResource",
    ],
    # ---- ACM (certs, common for CloudFront) ----
    "aws_acm_certificate": [
        "acm:RequestCertificate", "acm:DescribeCertificate",
        "acm:DeleteCertificate", "acm:ListCertificates",
        "acm:AddTagsToCertificate", "acm:ListTagsForCertificate",
    ],
    "aws_acm_certificate_validation": [
        "acm:DescribeCertificate", "acm:ListCertificates",
    ],
    # ---- IAM (roles/policies the terraform itself manages) ----
    # NOTE: when any of these are present, build_policy() gates the create/put
    # actions on the permissions-boundary condition (Option B) so the deploy
    # role cannot mint UNbounded roles. See IAM_MANAGE_ACTIONS below.
    "aws_iam_role": ["__iam_manage__"],
    "aws_iam_role_policy": ["__iam_manage__"],
    "aws_iam_role_policy_attachment": ["__iam_manage__"],
    "aws_iam_policy": ["__iam_manage__"],
    "aws_iam_instance_profile": ["__iam_manage__"],
}

# IAM role/policy management actions a terraform apply needs when it creates IAM
# roles. Split into two groups: the "creation" actions are gated on the
# permissions-boundary condition (Option B); the rest are safe to grant plainly.
IAM_CREATE_ACTIONS = [
    "iam:CreateRole",
    "iam:PutRolePolicy",
    "iam:AttachRolePolicy",
    "iam:PutRolePermissionsBoundary",
]
IAM_OTHER_ACTIONS = [
    "iam:GetRole", "iam:GetRolePolicy", "iam:ListRolePolicies",
    "iam:ListAttachedRolePolicies", "iam:ListInstanceProfilesForRole",
    "iam:DeleteRole", "iam:DeleteRolePolicy", "iam:DetachRolePolicy",
    "iam:TagRole", "iam:UntagRole", "iam:ListRoleTags",
    "iam:CreatePolicy", "iam:GetPolicy", "iam:GetPolicyVersion",
    "iam:ListPolicyVersions", "iam:CreatePolicyVersion",
    "iam:DeletePolicyVersion", "iam:DeletePolicy",
    "iam:CreateInstanceProfile", "iam:GetInstanceProfile",
    "iam:DeleteInstanceProfile", "iam:AddRoleToInstanceProfile",
    "iam:RemoveRoleFromInstanceProfile", "iam:PassRole",
]

# Actions no deploy-created role should EVER have — the escalation/takeover set.
# These are explicitly denied in the permissions boundary (Option B ceiling).
BOUNDARY_DENY_ACTIONS = [
    "iam:CreateUser", "iam:DeleteUser", "iam:CreateAccessKey",
    "iam:DeleteRolePermissionsBoundary", "iam:PutUserPermissionsBoundary",
    "iam:CreateSAMLProvider", "iam:CreateOpenIDConnectProvider",
    "iam:UpdateAssumeRolePolicy",
    "organizations:*", "account:*",
]

# Sentinel used inside RESOURCE_ACTIONS to mark "this type needs IAM management";
# build_policy() expands it into the gated + plain IAM action sets.
_IAM_SENTINEL = "__iam_manage__"

# Data sources only ever need read/describe permissions.
DATA_ACTIONS: dict[str, list[str]] = {
    "aws_caller_identity": ["sts:GetCallerIdentity"],
    "aws_region": [],  # resolved client-side, no IAM call
    # The route53_zone data source reads the zone AND its tags, so the provider
    # calls ListTagsForResource in addition to the lookup actions.
    "aws_route53_zone": [
        "route53:ListHostedZones", "route53:GetHostedZone",
        "route53:ListTagsForResource",
    ],
    "aws_acm_certificate": ["acm:ListCertificates", "acm:DescribeCertificate"],
    "aws_s3_bucket": ["s3:ListBucket", "s3:GetBucketLocation"],
    "aws_availability_zones": ["ec2:DescribeAvailabilityZones"],
}


# Services that are global (region-less) — their actions are effectively
# all-region and must NOT be caught by an aws:RequestedRegion Deny (CloudFront
# and Route53 present no region; ACM certs for CloudFront live in us-east-1;
# IAM/STS are global control-plane). The region guardrail exempts whichever of
# these the policy actually grants, so global resources get "*" (all regions)
# while regional resources stay confined.
GLOBAL_SERVICES = {"cloudfront", "route53", "acm", "iam", "sts"}

# Services the boundary allows non-mutating reads on (Describe*/List*/Get*), for
# debugging leeway. Common infrastructure services a deploy/debug session touches
# — enumerated (not a wildcard) so the generated IAM is always valid.
BOUNDARY_READ_SERVICES = sorted({
    "s3", "dynamodb", "cloudfront", "route53", "acm", "iam", "sts", "ec2",
    "lambda", "ecs", "ecr", "logs", "cloudwatch", "sns", "sqs", "rds",
    "elasticloadbalancing", "apigateway", "secretsmanager", "ssm", "kms",
    "autoscaling", "elasticache", "cloudformation",
})


def _service_of(resource_type: str) -> str:
    """aws_cloudfront_distribution -> cloudfront (best-effort service prefix)."""
    body = resource_type[len("aws_"):] if resource_type.startswith("aws_") else resource_type
    # Map the common terraform prefixes whose IAM service name differs.
    special = {
        "s3": "s3", "cloudfront": "cloudfront", "route53": "route53",
        "acm": "acm", "iam": "iam", "lambda": "lambda", "dynamodb": "dynamodb",
        "cloudwatch": "cloudwatch", "sns": "sns", "sqs": "sqs", "ecs": "ecs",
        "ec2": "ec2", "rds": "rds", "elasticache": "elasticache",
        "apigateway": "apigateway", "secretsmanager": "secretsmanager",
        "ssm": "ssm", "kms": "kms", "ecr": "ecr", "elb": "elasticloadbalancing",
        "lb": "elasticloadbalancing", "cloudwatch_log": "logs",
    }
    for prefix, svc in special.items():
        if body == prefix or body.startswith(prefix + "_"):
            return svc
    # Fallback: first token before the first underscore.
    return body.split("_", 1)[0]


def scan_tf_dirs(tf_dirs: list[Path]) -> dict:
    """
    Parse the .tf files in the given dirs. Returns:
        {"resources": {type: count}, "data": {type: count}, "s3_backend": bool}
    """
    resources: dict[str, int] = {}
    data: dict[str, int] = {}
    s3_backend = False
    seen: set[Path] = set()

    for d in tf_dirs:
        tf_files = sorted(d.glob("*.tf")) or sorted(d.rglob("*.tf"))
        for tf in tf_files:
            if tf in seen:
                continue
            seen.add(tf)
            try:
                text = tf.read_text(errors="ignore")
            except OSError:
                continue
            for m in _RESOURCE_RE.finditer(text):
                resources[m.group(1)] = resources.get(m.group(1), 0) + 1
            for m in _DATA_RE.finditer(text):
                data[m.group(1)] = data.get(m.group(1), 0) + 1
            if _BACKEND_S3_RE.search(text):
                s3_backend = True

    return {"resources": resources, "data": data, "s3_backend": s3_backend}


# --------------------------------------------------------------------------- #
# Region detection (best-effort, from Terraform + shell/CI scripts).
#
# The concrete deploy region is often not in the .tf itself (a `region =
# var.aws_region` provider with no default tells us nothing), so we scan both:
#   - Terraform:  provider region literals, `default = "..."` on an aws_region
#     variable, region literals in *.tfvars.
#   - Scripts:    AWS_REGION / AWS_DEFAULT_REGION assignments (incl. the
#     `${AWS_REGION:-us-west-2}` default form) and `--region <r>` flags.
# Results are ordered by how many times each region was seen (most-cited first),
# so callers can offer the top hit as a *suggested default* — never forced,
# since a detected value can be wrong.
# --------------------------------------------------------------------------- #
_REGION_RE = r"(?:us|eu|ap|ca|sa|me|af|il)-(?:east|west|north|south|central|northeast|northwest|southeast|southwest)-[1-9]"

# Terraform hints.
_TF_PROVIDER_REGION_RE = re.compile(r'region\s*=\s*"(' + _REGION_RE + r')"')
_TF_VAR_DEFAULT_RE = re.compile(
    r'variable\s+"(?:aws_region|region)"\s*\{[^}]*?default\s*=\s*"(' + _REGION_RE + r')"',
    re.DOTALL,
)
# Script hints.
_SH_ENV_RE = re.compile(
    r'(?:AWS_REGION|AWS_DEFAULT_REGION)\s*[=:]\s*["\']?\$?\{?[A-Za-z_:%\- ]*?-?\s*(' + _REGION_RE + r')'
)
_SH_FLAG_RE = re.compile(r'--region[=\s]+["\']?(' + _REGION_RE + r')')
# Bare region literal (last-resort, e.g. tfvars `aws_region = "us-west-2"`).
_BARE_REGION_RE = re.compile(r'\b(' + _REGION_RE + r')\b')

_SCRIPT_EXTS = {".sh", ".bash", ".zsh", ".yml", ".yaml"}
_TFVARS_SUFFIXES = (".tfvars", ".tfvars.json")


# Stage keywords used to attribute a region hit to beta vs prod. A hit whose
# filename OR line mentions the *current* stage is strongly preferred; a hit
# that mentions the *other* stage is excluded (it belongs to the other env).
_STAGE_WORDS = {
    "beta": ("beta", "stage", "staging", "dev", "development", "test", "qa"),
    "prod": ("prod", "production", "prd", "live"),
}


def _stage_of(text: str, stage: str) -> str | None:
    """Classify a filename/line as 'beta', 'prod', or None by keyword mention."""
    low = text.lower()
    for s, words in _STAGE_WORDS.items():
        if any(w in low for w in words):
            return s
    return None


def detect_regions(
    tf_dirs: list[Path], repo: Path | None = None, stage: str | None = None
) -> list[str]:
    """
    Best-effort ordered list of candidate deploy regions (most-preferred first).
    Scans the terraform dirs for provider/variable/tfvars hints and — if `repo`
    is given — shell/CI scripts for AWS_REGION and --region hints.

    STAGE-AWARE: when `stage` is given (e.g. "prod"), a region mentioned on a
    line or in a file tied to that stage (PROD_AWS_REGION, *_prod.sh, ...) is
    strongly preferred, and a region tied to the *other* stage is dropped — so a
    prod run suggests the prod region even if beta regions appear more often.
    Returns [] if nothing is found.
    """
    counts: dict[str, int] = {}

    def bump(region: str, weight: int, context: str, file_stage: str | None) -> None:
        # Determine which stage this specific hit belongs to: the line's own
        # keyword wins, else the file's.
        hit_stage = _stage_of(context, stage) if stage else None
        if hit_stage is None:
            hit_stage = file_stage
        if stage and hit_stage:
            if hit_stage == stage:
                weight += 10          # this hit is explicitly for our stage
            else:
                return                # belongs to the other stage — ignore it
        counts[region] = counts.get(region, 0) + weight

    seen: set[Path] = set()

    def scan_lines(text: str, rx: re.Pattern, weight: int, file_stage: str | None) -> None:
        for line in text.splitlines():
            for m in rx.finditer(line):
                bump(m.group(1), weight, line, file_stage)

    # ---- Terraform + tfvars in the discovered dirs ----
    for d in tf_dirs:
        for f in sorted(d.glob("*.tf")) or sorted(d.rglob("*.tf")):
            if f in seen:
                continue
            seen.add(f)
            try:
                text = f.read_text(errors="ignore")
            except OSError:
                continue
            fstage = _stage_of(f.name, stage) if stage else None
            scan_lines(text, _TF_PROVIDER_REGION_RE, 3, fstage)
            # Variable defaults can span lines; match on the whole text.
            for m in _TF_VAR_DEFAULT_RE.finditer(text):
                bump(m.group(1), 3, m.group(0), fstage)
        for f in sorted(d.rglob("*")):
            if any(p in (".git", ".terraform", "node_modules") for p in f.parts):
                continue
            if f.name.endswith(_TFVARS_SUFFIXES) and f not in seen:
                seen.add(f)
                fstage = _stage_of(f.name, stage) if stage else None
                try:
                    scan_lines(f.read_text(errors="ignore"), _BARE_REGION_RE, 3, fstage)
                except OSError:
                    pass

    # ---- Shell / CI scripts across the repo ----
    scan_root = repo
    if scan_root is None and tf_dirs:
        scan_root = tf_dirs[0]
    if scan_root is not None:
        for f in scan_root.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in _SCRIPT_EXTS:
                continue
            if any(p in (".git", ".terraform", "node_modules") for p in f.parts):
                continue
            try:
                text = f.read_text(errors="ignore")
            except OSError:
                continue
            fstage = _stage_of(f.name, stage) if stage else None
            scan_lines(text, _SH_ENV_RE, 2, fstage)
            scan_lines(text, _SH_FLAG_RE, 2, fstage)

    # Most-preferred first; tie-break alphabetically for determinism.
    return [r for r, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def scan_creates_iam(scan: dict) -> bool:
    """True if the terraform manages IAM roles/policies (needs Option B gating)."""
    return any(
        RESOURCE_ACTIONS.get(rtype) == [_IAM_SENTINEL] for rtype in scan["resources"]
    )


def build_policy(
    scan: dict,
    warn=lambda m: None,
    regions: list[str] | None = None,
    boundary_arn: str | None = None,
) -> dict:
    """
    Turn a scan() result into an IAM policy document. `warn` is an optional
    callback used to report resource types that fell back to a service wildcard.

    If `regions` is given, a Deny statement is appended that confines all
    *regional* actions to those regions (via aws:RequestedRegion), while
    exempting the global/region-less services (CloudFront, Route53, ACM, IAM,
    STS) so the deploy still works. Pass the prod stage's target regions here to
    get a region guardrail; pass None (the default) for no restriction.

    If the terraform manages IAM roles (aws_iam_role etc.) and `boundary_arn` is
    given, the IAM *creation* actions (CreateRole/PutRolePolicy/...) are granted
    ONLY under the condition iam:PermissionsBoundary == boundary_arn (Option B):
    the deploy role can then only create roles that carry that boundary, so it
    cannot mint an unbounded/admin role. IAM creation is emitted as its own
    gated statement; other IAM actions are granted normally.
    """
    actions: set[str] = set()
    wildcard_services: set[str] = set()
    needs_iam = False

    for rtype, _count in sorted(scan["resources"].items()):
        mapped = RESOURCE_ACTIONS.get(rtype)
        if mapped == [_IAM_SENTINEL]:
            needs_iam = True
            continue
        if mapped:
            actions.update(mapped)
        else:
            svc = _service_of(rtype)
            wildcard_services.add(svc)
            warn(f"No explicit action map for '{rtype}' — granting '{svc}:*'.")

    # IAM management: the non-creation actions are safe to grant plainly; the
    # creation actions are handled as a gated statement below (needs boundary).
    if needs_iam:
        actions.update(IAM_OTHER_ACTIONS)
        if not boundary_arn:
            warn(
                "Terraform manages IAM roles but no permissions boundary was "
                "provided — IAM creation actions will be granted UNGATED "
                "(privilege-escalation risk)."
            )
            actions.update(IAM_CREATE_ACTIONS)

    for dtype, _count in sorted(scan["data"].items()):
        mapped = DATA_ACTIONS.get(dtype)
        if mapped is not None:
            actions.update(mapped)
        else:
            svc = _service_of(dtype)
            wildcard_services.add(svc)
            warn(f"No explicit action map for data source '{dtype}' — granting '{svc}:*'.")

    for svc in wildcard_services:
        actions.add(f"{svc}:*")

    # Services actually granted by this policy (prefix before the ':').
    granted_services = {a.split(":", 1)[0] for a in actions}

    statements: list[dict] = []
    if actions:
        statements.append({
            "Sid": "TerraformManagedResources",
            "Effect": "Allow",
            "Action": sorted(actions),
            "Resource": "*",
        })

    # Loose read/describe leeway: for every service this policy touches, also
    # grant Describe*/List*/Get*. `terraform plan`/`refresh` reads far more than
    # it writes (a create implies reads of neighbouring attributes), and a
    # missing read is the most common cause of a confusing apply failure. Reads
    # are non-mutating, so this widens debuggability without widening blast
    # radius. Writes stay confined to the explicit least-privilege set above.
    read_services = sorted(granted_services - {"sts"})
    if read_services:
        statements.append({
            "Sid": "ReadDescribeLeeway",
            "Effect": "Allow",
            "Action": sorted(
                f"{svc}:{verb}" for svc in read_services for verb in ("Describe*", "List*", "Get*")),
            "Resource": "*",
        })

    # Option B: IAM creation gated on the permissions boundary. Only emitted when
    # the terraform manages IAM roles AND a boundary ARN is supplied. The deploy
    # role may create/attach roles ONLY if the new role carries this boundary,
    # so it cannot escalate by minting an unbounded admin role.
    if needs_iam and boundary_arn:
        statements.append({
            "Sid": "IAMCreateOnlyWithBoundary",
            "Effect": "Allow",
            "Action": IAM_CREATE_ACTIONS,
            "Resource": "*",
            "Condition": {
                "StringEquals": {"iam:PermissionsBoundary": boundary_arn}
            },
        })

    # Remote state backend (S3 + DynamoDB lock table). ARNs aren't known here
    # (the backend block is populated at `terraform init` time), so scope to the
    # backend actions on "*". CI can tighten this to the real bucket/table.
    if scan["s3_backend"]:
        statements.append({
            "Sid": "TerraformStateBackend",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
                "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem",
                "dynamodb:DescribeTable",
            ],
            "Resource": "*",
        })

    # Optional region guardrail: deny regional actions outside the allowed
    # regions. Global (region-less) services are exempted via NotAction so they
    # keep "*" (all regions) — NotAction means "this Deny does NOT apply to
    # these actions". We exempt only the global services this policy actually
    # grants, keeping the deny as tight as possible. The state backend (S3 +
    # DynamoDB) is regional, so it stays subject to the region restriction.
    if regions:
        allowed_regions = list(regions)
        # CloudFront's CreateDistribution validates the viewer certificate in
        # us-east-1 (where its ACM certs live). Even with acm:* exempted from the
        # deny via NotAction below, that validation is evaluated with
        # aws:RequestedRegion=us-east-1 and gets denied unless us-east-1 is an
        # allowed region — surfacing as the misleading "InvalidViewerCertificate"
        # error. So whenever the stack has a CloudFront distribution, us-east-1
        # MUST be in the allowed set. (Verified against webapp-prod: adding
        # us-east-1 here is exactly what unblocked the CloudFront create.)
        if "aws_cloudfront_distribution" in scan["resources"] and "us-east-1" not in allowed_regions:
            allowed_regions.append("us-east-1")
        exempt = sorted(GLOBAL_SERVICES & granted_services)
        deny = {
            "Sid": "DenyOutsideAllowedRegions",
            "Effect": "Deny",
            "Resource": "*",
            "Condition": {
                "StringNotEquals": {"aws:RequestedRegion": allowed_regions}
            },
        }
        # Exempt the global services present (NotAction). If none are present
        # (regional-only stack), an empty NotAction is invalid IAM — deny all
        # actions outside the regions with Action "*" instead.
        if exempt:
            deny["NotAction"] = [f"{svc}:*" for svc in exempt]
        else:
            deny["Action"] = "*"
        statements.append(deny)

    return {"Version": "2012-10-17", "Statement": statements}


def build_boundary_policy(scan: dict, boundary_arn: str) -> dict:
    """
    Build the permissions-boundary document for a deployment (Option B ceiling).

    This is the cap applied to (a) the deploy role itself and (b) — via the
    IAMCreateOnlyWithBoundary condition in build_policy — every role the deploy
    role creates. It is SELF-REFERENTIAL: it permits creating roles only when
    they carry THIS boundary, so the handicap propagates to grandchildren, not
    just direct children.

    Contents:
      - Allow the services this deployment actually uses (mirrors the deploy
        policy's service set, at service granularity — a boundary is a ceiling,
        not the least-privilege floor).
      - Allow self-propagating IAM creation (gated on this same boundary).
      - Deny the escalation/takeover actions no deploy-created role should hold
        (BOUNDARY_DENY_ACTIONS) — an explicit Deny always wins.
    """
    # Ceiling service set = whatever the deploy policy would grant, at service
    # granularity, minus iam (handled explicitly below) and always including the
    # state backend services.
    base = build_policy(scan)  # ungated view, just to harvest services
    services = {
        a.split(":", 1)[0]
        for s in base["Statement"] if s["Effect"] == "Allow"
        for a in (s.get("Action") or [])
    }
    services |= {"s3", "dynamodb", "logs"}  # backend + logging, always allowed
    services.discard("iam")  # IAM is governed by the explicit statements below

    statements: list[dict] = [
        {
            "Sid": "BoundaryAllowedServices",
            "Effect": "Allow",
            "Action": sorted(f"{svc}:*" for svc in services),
            "Resource": "*",
        },
        # Boundary read leeway: a boundary is a ceiling, not the least-privilege
        # floor, so allow non-mutating reads across the common infrastructure
        # services. This gives a debugging engineer (trusted via the
        # multi-principal trust policy) room to inspect state without the
        # boundary silently capping a Describe/List/Get. Writes are still bounded
        # by BoundaryAllowedServices + the deny floor below. (IAM uses an explicit
        # service prefix per action — a bare `*:Get*` service-wildcard is not
        # reliably accepted, so read verbs are enumerated per service.)
        {
            "Sid": "BoundaryReadEverywhere",
            "Effect": "Allow",
            "Action": sorted(
                f"{svc}:{verb}"
                for svc in BOUNDARY_READ_SERVICES
                for verb in ("Describe*", "List*", "Get*")),
            "Resource": "*",
        },
        # Self-referential: created roles may themselves only create roles that
        # carry this same boundary — propagation survives past one generation.
        {
            "Sid": "BoundarySelfPropagatingIAM",
            "Effect": "Allow",
            "Action": IAM_CREATE_ACTIONS,
            "Resource": "*",
            "Condition": {"StringEquals": {"iam:PermissionsBoundary": boundary_arn}},
        },
        {
            "Sid": "BoundaryReadIAM",
            "Effect": "Allow",
            "Action": [a for a in IAM_OTHER_ACTIONS if not a.startswith("iam:Delete")],
            "Resource": "*",
        },
        # The hard floor: escalation/takeover actions are denied outright.
        {
            "Sid": "BoundaryDenyEscalation",
            "Effect": "Deny",
            "Action": BOUNDARY_DENY_ACTIONS,
            "Resource": "*",
        },
    ]
    return {"Version": "2012-10-17", "Statement": statements}


def generate_policy_from_dirs(
    tf_dirs: list[Path],
    warn=lambda m: None,
    regions: list[str] | None = None,
    boundary_arn: str | None = None,
) -> dict:
    """Convenience: scan + build the deploy-role policy in one call."""
    return build_policy(scan_tf_dirs(tf_dirs), warn=warn, regions=regions, boundary_arn=boundary_arn)


def generate_boundary_from_dirs(tf_dirs: list[Path], boundary_arn: str) -> dict:
    """Convenience: scan + build the permissions-boundary document in one call."""
    return build_boundary_policy(scan_tf_dirs(tf_dirs), boundary_arn)


def needs_boundary(tf_dirs: list[Path]) -> bool:
    """True if these terraform dirs manage IAM roles (so a boundary is warranted)."""
    return scan_creates_iam(scan_tf_dirs(tf_dirs))


# Standalone CLI:
#   python3 tf_policy.py <dir> [<dir> ...] [--regions us-west-2,us-east-1]
# The --regions flag adds the region guardrail (Deny outside those regions).
if __name__ == "__main__":
    import sys

    argv = sys.argv[1:]
    regions: list[str] | None = None
    if "--regions" in argv:
        i = argv.index("--regions")
        regions = [r for r in re.split(r"[,\s]+", argv[i + 1].strip()) if r]
        del argv[i : i + 2]

    dirs = [Path(a).resolve() for a in argv] or [Path.cwd()]
    scan = scan_tf_dirs(dirs)
    print(f"# resources: {scan['resources']}", file=sys.stderr)
    print(f"# data:      {scan['data']}", file=sys.stderr)
    print(f"# s3_backend: {scan['s3_backend']}", file=sys.stderr)
    print(f"# regions:   {regions or 'unrestricted'}", file=sys.stderr)
    policy = build_policy(scan, warn=lambda m: print(f"# WARN: {m}", file=sys.stderr), regions=regions)
    print(json.dumps(policy, indent=2))
