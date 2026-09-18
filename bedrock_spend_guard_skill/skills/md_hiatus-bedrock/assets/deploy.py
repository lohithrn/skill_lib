#!/usr/bin/env python3
"""
hiatus_bedrock circuit breaker deployer.

Deploys an account-wide Amazon Bedrock spend circuit breaker:
  - AWS Budget filtered to Amazon Bedrock, monthly.
  - Budget action: when ACTUAL spend >= threshold, attach a Deny(bedrock:*)
    managed policy to the specified IAM groups and/or roles.
  - Reset Lambda + EventBridge cron (1st of month, 12:00 GMT) that detaches
    the Deny so access resumes for the new month.

All resources are prefixed `hiatus_security_bedrock`. Idempotent: re-running
detects existing resources and updates the budget threshold and/or targets.

CREDENTIALS — HARD BAN (do not weaken):
  This tool has NO authority over the operating system's AWS credentials. It
  MUST NEVER read or fall back to any AWS_* environment variable, ~/.aws/
  credentials or config, the AWS CLI's resolved creds, the `default` profile,
  ANY pre-existing named profile on the machine, or an instance/SSO/role chain.
  The only credential it may use is the one handed to it on stdin (or at an
  interactive prompt). It is held in memory for the life of the process and is
  never written to disk, so there is no file to leak and none to clean up. No
  system profile — including any default profile — is read, created, or touched.
  See _read_creds() and make_session() below; both re-state this ban.

Usage:
  # creds are fed via stdin as key=value lines (never argv, never env):
  ./run.sh --region us-east-1 --list-principals <<'EOF'
  access_key_id=<key-id>
  secret_access_key=<secret>
  session_token=<token>        # optional
  EOF
  ./run.sh --status             # show current deployment, no changes
  ./run.sh --destroy            # remove all hiatus_security_bedrock_* resources

Always invoke through run.sh, which owns the private virtualenv this file needs.
"""
import argparse
import getpass
import io
import json
import os
import sys
import time
import zipfile

PREFIX = "hiatus_security_bedrock"
DENY_POLICY_NAME = f"{PREFIX}_deny"
BUDGET_ROLE_NAME = f"{PREFIX}_budget_role"
BUDGET_NAME = f"{PREFIX}_budget"
LAMBDA_ROLE_NAME = f"{PREFIX}_lambda_role"
LAMBDA_NAME = f"{PREFIX}_scheduler"
RULE_NAME = f"{PREFIX}_reset_rule"
SNS_TOPIC_NAME = f"{PREFIX}_email_group"
RESET_CRON = "cron(0 12 1 * ? *)"  # 12:00 GMT on the 1st of every month
DEFAULT_BUDGET = "700"             # example value only — the operator sets this deliberately

try:
    import boto3
    import botocore.session
    from botocore.exceptions import ClientError
except ImportError:
    sys.exit("boto3 is required. Run this deployer through run.sh, which builds "
             "the private virtualenv it needs; do not call deploy.py directly.")


DRY_RUN = False
_MUTATING_PREFIXES = ("create_", "update_", "put_", "attach_", "detach_",
                      "delete_", "add_", "remove_", "tag_", "untag_",
                      "set_", "subscribe", "unsubscribe")


def log(msg):
    print(f"  {msg}", flush=True)


class DryClient:
    """Wraps a boto3 client: read calls pass through, mutating calls are printed
    (with args) and return a benign stub instead of executing."""

    def __init__(self, real, service):
        self._real = real
        self._service = service
        # expose the real client's exception classes so `except client.exceptions.X` works
        self.exceptions = real.exceptions

    def __getattr__(self, name):
        attr = getattr(self._real, name)
        if not callable(attr) or not name.startswith(_MUTATING_PREFIXES):
            return attr

        def _stub(**kwargs):
            printable = {k: (v if k not in ("PolicyDocument", "AssumeRolePolicyDocument",
                                            "ZipFile", "Code") else "<...>")
                         for k, v in kwargs.items()}
            print(f"  [DRY] {self._service}.{name}({json.dumps(printable, default=str)})", flush=True)
            # return plausible stubs for the few return values the code reads
            if name == "create_budget_action":
                return {"ActionId": "dry-action-id"}
            if name == "create_topic":
                return {"TopicArn": f"arn:aws:sns:dry:0:{kwargs.get('Name', 'topic')}"}
            return {}
        return _stub


def client(session, service, **kw):
    real = session.client(service, **kw)
    return DryClient(real, service) if DRY_RUN else real


def prompt(msg, secret=False, default=None):
    if secret:
        v = getpass.getpass(f"{msg}: ")
    else:
        suffix = f" [{default}]" if default else ""
        v = input(f"{msg}{suffix}: ").strip()
    if not v and default is not None:
        return default
    return v


# ---------- credential + account handling ----------

# Isolated, self-contained credential handling.
#
# HARD BAN (repeated): this tool has NO authority over the OS's AWS creds. It
# NEVER reads AWS_* env vars, ~/.aws, the AWS CLI, the `default` profile, ANY
# other pre-existing profile, or an instance/SSO/role chain. The credential
# handed to it on stdin is set directly on the botocore session, in memory only,
# and is used for this process and nothing else. Nothing is written to disk, so
# no system profile or AWS config is read, created, or modified.
_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
# A path inside this folder that is deliberately never created: botocore is
# pointed at it so any code path that still tries to resolve a shared profile
# finds an absent file rather than the operator's ~/.aws.
_ISOLATED_DIR = os.path.join(_SKILL_DIR, ".aws_hiatus_bedrock")


def _normalise_cred_key(key):
    """`access_key_id` and `aws_access_key_id` are the same field — the console
    copy button emits the prefixed spelling and a heredoc usually does not, so
    accept both. `secret_key` is the short spelling some consoles use."""
    k = key.strip().lower()
    if k.startswith("aws_"):
        k = k[4:]
    if k == "secret_key":
        k = "secret_access_key"
    if k == "security_token":
        k = "session_token"
    return k


def _read_creds():
    """Obtain credentials WITHOUT ever reading the OS environment or ~/.aws.

    The only accepted sources are (in priority order):
      1. stdin, if piped — one `key=value` per line (access_key_id,
         secret_access_key, session_token, optionally region). This is how the
         skill feeds creds: `./run.sh ... <<'EOF'`.
      2. interactive prompts, if we have a TTY.

    We deliberately do NOT fall back to any AWS_* variable, AWS_PROFILE, or
    ~/.aws — this breaker uses only credentials explicitly handed to it.
    """
    creds = {}
    if not sys.stdin.isatty():
        # creds piped in (heredoc). Parse key=value lines; ignore blanks/#.
        for raw in sys.stdin.read().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            creds[_normalise_cred_key(k)] = v.strip()
    else:
        creds["access_key_id"] = prompt("AWS Access Key ID")
        creds["secret_access_key"] = prompt("AWS Secret Access Key", secret=True)
        tok = prompt("AWS Session Token (optional, blank if none)")
        if tok:
            creds["session_token"] = tok
    return creds


def make_session(args):
    creds = _read_creds()
    ak = creds.get("access_key_id", "")
    sk = creds.get("secret_access_key", "")
    st = creds.get("session_token") or None  # empty/blank -> no token
    if not ak or not sk:
        sys.exit("Missing credentials: an Access Key ID and Secret Access Key are "
                 "required (piped via stdin as key=value lines, or entered at the prompt). "
                 "This skill never reads OS environment credentials or ~/.aws.")
    # region: CLI flag wins, else creds line, else default. NOT from env.
    region = args.region or creds.get("region") or "us-east-1"

    # Scrub EVERY ambient AWS_* variable before botocore is asked for anything.
    # Scrub by prefix, not by a list of names: an enumerated list silently lets
    # the container-credentials, web-identity and role-chain variables through,
    # and the ban above covers those too.
    for stray in [k for k in os.environ if k.startswith("AWS_")]:
        os.environ.pop(stray, None)
    # Point botocore at paths inside this folder that do not exist, and close
    # the instance-metadata door, so no ambient profile or role can be reached.
    os.environ["AWS_SHARED_CREDENTIALS_FILE"] = os.path.join(_ISOLATED_DIR, "credentials")
    os.environ["AWS_CONFIG_FILE"] = os.path.join(_ISOLATED_DIR, "config")
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"

    # The credential lives in this process's memory and nowhere else. Setting it
    # explicitly on the botocore session pins it as the only provider, so the
    # resolver chain (env vars, shared files, IMDS) is never consulted at all.
    inner = botocore.session.Session()
    inner.set_credentials(ak, sk, st)
    return boto3.Session(botocore_session=inner, region_name=region)


def detect_account(session):
    ident = session.client("sts").get_caller_identity()
    return ident["Account"], ident["Arn"]


def account_alias(session):
    try:
        aliases = session.client("iam").list_account_aliases().get("AccountAliases", [])
        return aliases[0] if aliases else None
    except Exception:
        return None


def list_principals(session):
    """Enumerate the account's IAM groups and roles so the caller can present
    the REAL names to pick from (instead of guessing). Filters out AWS
    service-linked roles (path starts with /aws-service-role/), which can't have
    policies attached this way. Emits JSON on stdout."""
    iam = session.client("iam")
    groups, roles = [], []
    try:
        p = iam.get_paginator("list_groups")
        for page in p.paginate():
            groups.extend(g["GroupName"] for g in page.get("Groups", []))
    except ClientError as e:
        print(f"# warning: could not list groups: {e}", file=sys.stderr)
    try:
        p = iam.get_paginator("list_roles")
        for page in p.paginate():
            for r in page.get("Roles", []):
                if r.get("Path", "/").startswith("/aws-service-role/"):
                    continue
                roles.append(r["RoleName"])
    except ClientError as e:
        print(f"# warning: could not list roles: {e}", file=sys.stderr)
    print(json.dumps({"groups": sorted(groups), "roles": sorted(roles)}))


def double_confirm_account(account, arn, alias, assume_yes=False):
    """Require the operator to approve the target account TWICE before any change."""
    print("\n" + "=" * 60)
    print("  ACCOUNT UNDER ACTION")
    print(f"    Account ID : {account}")
    if alias:
        print(f"    Alias      : {alias}")
    print(f"    Identity   : {arn}")
    print("=" * 60)
    if assume_yes:
        print("  (--yes supplied: skipping interactive confirmation)")
        return True
    # Confirmation 1: explicit approval
    c1 = prompt("Confirm #1 — is this the account you intend to modify? (yes/no)")
    if c1.strip().lower() not in ("yes", "y"):
        return False
    # Confirmation 2: retype the account id (can't be fat-fingered)
    c2 = prompt("Confirm #2 — re-type the Account ID exactly to proceed")
    if c2.strip().replace("-", "") != account:
        print(f"  Account id mismatch ('{c2}' != '{account}') — aborting.")
        return False
    return True


# ---------- policy documents ----------

def deny_policy_doc():
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "HiatusDenyBedrock",
            "Effect": "Deny",
            "Action": "bedrock:*",
            "Resource": "*",
        }],
    }


def budget_role_trust():
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "budgets.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }


def budget_role_perms(account, groups, roles):
    # Budgets must be able to attach/detach ONLY our deny policy to the targets.
    policy_arn = f"arn:aws:iam::{account}:policy/{DENY_POLICY_NAME}"
    resources = [f"arn:aws:iam::{account}:group/{g}" for g in groups] + \
                [f"arn:aws:iam::{account}:role/{r}" for r in roles]
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "AttachDetachDenyOnly",
            "Effect": "Allow",
            "Action": ["iam:AttachGroupPolicy", "iam:DetachGroupPolicy",
                       "iam:AttachRolePolicy", "iam:DetachRolePolicy"],
            "Resource": resources or ["*"],
            "Condition": {"ArnEquals": {"iam:PolicyARN": policy_arn}},
        }],
    }


def lambda_role_trust():
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }


def lambda_role_perms(account, groups, roles):
    policy_arn = f"arn:aws:iam::{account}:policy/{DENY_POLICY_NAME}"
    resources = [f"arn:aws:iam::{account}:group/{g}" for g in groups] + \
                [f"arn:aws:iam::{account}:role/{r}" for r in roles]
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DetachDenyOnly",
                "Effect": "Allow",
                "Action": ["iam:DetachGroupPolicy", "iam:DetachRolePolicy",
                           "iam:AttachGroupPolicy", "iam:AttachRolePolicy"],
                "Resource": resources or ["*"],
                "Condition": {"ArnEquals": {"iam:PolicyARN": policy_arn}},
            },
            {
                "Sid": "Logs",
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": "*",
            },
        ],
    }


# ---------- lambda source (reset: detach deny from targets) ----------

LAMBDA_SRC = '''
import json, boto3
iam = boto3.client("iam")

def handler(event, context):
    policy_arn = event["policy_arn"]
    detached = []
    for g in event.get("groups", []):
        try:
            iam.detach_group_policy(GroupName=g, PolicyArn=policy_arn)
            detached.append(f"group/{g}")
        except iam.exceptions.NoSuchEntityException:
            pass
        except Exception as e:
            detached.append(f"group/{g} ERR {e}")
    for r in event.get("roles", []):
        try:
            iam.detach_role_policy(RoleName=r, PolicyArn=policy_arn)
            detached.append(f"role/{r}")
        except iam.exceptions.NoSuchEntityException:
            pass
        except Exception as e:
            detached.append(f"role/{r} ERR {e}")
    print(json.dumps({"detached": detached}))
    return {"detached": detached}
'''


def zip_lambda():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("lambda_function.py", LAMBDA_SRC)
    return buf.getvalue()


# ---------- idempotent resource helpers ----------

def ensure_sns(sns, account, region, emails):
    """Create the notification 'email group' topic, allow Budgets to publish,
    and subscribe the initial email(s). Adding more people later = subscribing
    their email to this topic."""
    topic_arn = f"arn:aws:sns:{region}:{account}:{SNS_TOPIC_NAME}"
    sns.create_topic(Name=SNS_TOPIC_NAME)  # idempotent - returns existing if present
    log(f"sns topic: {topic_arn}")
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "AllowBudgetsPublish",
            "Effect": "Allow",
            "Principal": {"Service": "budgets.amazonaws.com"},
            "Action": "SNS:Publish",
            "Resource": topic_arn,
        }],
    }
    sns.set_topic_attributes(TopicArn=topic_arn, AttributeName="Policy",
                             AttributeValue=json.dumps(policy))
    # subscribe initial emails (idempotent-ish: duplicate subs are ignored by SNS)
    existing = set()
    if not DRY_RUN:
        try:
            for s in sns.list_subscriptions_by_topic(TopicArn=topic_arn).get("Subscriptions", []):
                existing.add(s.get("Endpoint"))
        except Exception:
            pass
    for e in emails:
        if e in existing:
            log(f"  already subscribed: {e}")
            continue
        sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=e)
        log(f"  subscribed (pending email confirm): {e}")
    return topic_arn


def ensure_deny_policy(iam, account):
    arn = f"arn:aws:iam::{account}:policy/{DENY_POLICY_NAME}"
    try:
        iam.get_policy(PolicyArn=arn)
        log(f"deny policy exists: {arn}")
    except iam.exceptions.NoSuchEntityException:
        iam.create_policy(PolicyName=DENY_POLICY_NAME,
                          PolicyDocument=json.dumps(deny_policy_doc()),
                          Description="hiatus: Deny bedrock:* attached by budget circuit breaker")
        log(f"created deny policy: {arn}")
    return arn


def ensure_role(iam, name, trust, inline_name, inline_doc):
    try:
        iam.get_role(RoleName=name)
        log(f"role exists: {name}")
    except iam.exceptions.NoSuchEntityException:
        iam.create_role(RoleName=name, AssumeRolePolicyDocument=json.dumps(trust),
                        Description=f"hiatus circuit breaker role {name}")
        log(f"created role: {name}")
        if not DRY_RUN:
            time.sleep(8)  # IAM propagation
    iam.put_role_policy(RoleName=name, PolicyName=inline_name,
                        PolicyDocument=json.dumps(inline_doc))
    log(f"  set inline policy on {name}")
    return name


def ensure_budget(budgets, account, amount, groups, roles, policy_arn, budget_role_arn, topic_arn):
    budget_obj = {
        "BudgetName": BUDGET_NAME,
        "BudgetLimit": {"Amount": str(amount), "Unit": "USD"},
        "BudgetType": "COST",
        "TimeUnit": "MONTHLY",
        "CostFilters": {"Service": ["Amazon Bedrock"]},
    }
    try:
        budgets.describe_budget(AccountId=account, BudgetName=BUDGET_NAME)
        budgets.update_budget(AccountId=account, NewBudget=budget_obj)
        log(f"updated budget {BUDGET_NAME} -> ${amount}/mo (Amazon Bedrock)")
    except budgets.exceptions.NotFoundException:
        budgets.create_budget(AccountId=account, Budget=budget_obj)
        log(f"created budget {BUDGET_NAME} = ${amount}/mo (Amazon Bedrock)")

    definition = {"IamActionDefinition": {"PolicyArn": policy_arn}}
    if groups:
        definition["IamActionDefinition"]["Groups"] = groups
    if roles:
        definition["IamActionDefinition"]["Roles"] = roles

    subscribers = [{"SubscriptionType": "SNS", "Address": topic_arn}]
    action_kwargs = dict(
        AccountId=account, BudgetName=BUDGET_NAME,
        NotificationType="ACTUAL",
        ActionType="APPLY_IAM_POLICY",
        ActionThreshold={"ActionThresholdValue": 100.0, "ActionThresholdType": "PERCENTAGE"},
        Definition=definition,
        ExecutionRoleArn=budget_role_arn,
        ApprovalModel="AUTOMATIC",
        Subscribers=subscribers,
    )
    try:
        existing = budgets.describe_budget_actions_for_budget(
            AccountId=account, BudgetName=BUDGET_NAME).get("Actions", [])
    except budgets.exceptions.NotFoundException:
        existing = []  # budget just created (or dry-run) - no actions yet
    if existing:
        aid = existing[0]["ActionId"]
        budgets.update_budget_action(AccountId=account, BudgetName=BUDGET_NAME, ActionId=aid,
                                     NotificationType="ACTUAL",
                                     ActionThreshold=action_kwargs["ActionThreshold"],
                                     Definition=definition,
                                     ExecutionRoleArn=budget_role_arn,
                                     ApprovalModel="AUTOMATIC")
        log(f"updated budget action {aid}")
    else:
        last = None
        for attempt in range(5):
            try:
                r = budgets.create_budget_action(**action_kwargs)
                log(f"created budget action {r['ActionId']}")
                last = None
                break
            except budgets.exceptions.NotFoundException as e:
                last = e  # budget not yet propagated
                if not DRY_RUN:
                    time.sleep(5)
            except ClientError as e:
                last = e
                break
        if last:
            log(f"budget action create note: {last}")


def ensure_lambda(lam, account, region, lambda_role_arn):
    code = zip_lambda()
    try:
        lam.get_function(FunctionName=LAMBDA_NAME)
        lam.update_function_code(FunctionName=LAMBDA_NAME, ZipFile=code)
        log(f"updated lambda {LAMBDA_NAME}")
    except lam.exceptions.ResourceNotFoundException:
        lam.create_function(
            FunctionName=LAMBDA_NAME, Runtime="python3.12", Role=lambda_role_arn,
            Handler="lambda_function.handler", Code={"ZipFile": code}, Timeout=60,
            Description="hiatus: monthly reset - detach Deny(bedrock:*) from targets")
        log(f"created lambda {LAMBDA_NAME}")
    return f"arn:aws:lambda:{region}:{account}:function:{LAMBDA_NAME}"


def ensure_schedule(events, lam, account, region, lambda_arn, policy_arn, groups, roles):
    events.put_rule(Name=RULE_NAME, ScheduleExpression=RESET_CRON, State="ENABLED",
                    Description="hiatus: 1st of month 12:00 GMT - reset bedrock block")
    rule_arn = f"arn:aws:events:{region}:{account}:rule/{RULE_NAME}"
    try:
        lam.add_permission(FunctionName=LAMBDA_NAME, StatementId="hiatus_events_invoke",
                           Action="lambda:InvokeFunction", Principal="events.amazonaws.com",
                           SourceArn=rule_arn)
    except lam.exceptions.ResourceConflictException:
        pass
    payload = {"policy_arn": policy_arn, "groups": groups, "roles": roles}
    events.put_targets(Rule=RULE_NAME, Targets=[{
        "Id": "hiatus_reset", "Arn": lambda_arn, "Input": json.dumps(payload)}])
    log(f"scheduled monthly reset: {RESET_CRON}")


# ---------- top-level ops ----------

def deploy(session, account, groups, roles, amount, region, emails):
    iam = client(session, "iam")
    budgets = client(session, "budgets", region_name="us-east-1")  # budgets is us-east-1 global
    lam = client(session, "lambda")
    events = client(session, "events")
    sns = client(session, "sns")

    print(f"\nDeploying hiatus circuit breaker on account {account} ({region})")
    print(f"  targets: groups={groups or '-'} roles={roles or '-'}  budget=${amount}/mo\n")

    policy_arn = ensure_deny_policy(iam, account)
    budget_role_arn = "arn:aws:iam::%s:role/%s" % (account, ensure_role(
        iam, BUDGET_ROLE_NAME, budget_role_trust(), f"{PREFIX}_budget_inline",
        budget_role_perms(account, groups, roles)))
    lambda_role_arn = "arn:aws:iam::%s:role/%s" % (account, ensure_role(
        iam, LAMBDA_ROLE_NAME, lambda_role_trust(), f"{PREFIX}_lambda_inline",
        lambda_role_perms(account, groups, roles)))
    lambda_arn = ensure_lambda(lam, account, region, lambda_role_arn)
    topic_arn = ensure_sns(sns, account, region, emails)
    ensure_budget(budgets, account, amount, groups, roles, policy_arn, budget_role_arn, topic_arn)
    ensure_schedule(events, lam, account, region, lambda_arn, policy_arn, groups, roles)
    print("\nDone. Circuit breaker armed.")
    print(f"  When Amazon Bedrock spend >= ${amount} this month, Deny(bedrock:*) attaches to the targets.")
    print(f"  On the 1st @ 12:00 GMT the reset Lambda detaches it automatically.")
    print(f"  Change the limit later: re-run and enter a new budget (updates in place).")


def status(session, account):
    iam = session.client("iam")
    budgets = session.client("budgets", region_name="us-east-1")
    print(f"\nhiatus status on account {account}:")
    try:
        b = budgets.describe_budget(AccountId=account, BudgetName=BUDGET_NAME)["Budget"]
        print(f"  budget: ${b['BudgetLimit']['Amount']}/{b['TimeUnit']}  filter={b.get('CostFilters')}")
        acts = budgets.describe_budget_actions_for_budget(AccountId=account, BudgetName=BUDGET_NAME).get("Actions", [])
        for a in acts:
            d = a["Definition"]["IamActionDefinition"]
            print(f"  action {a['ActionId']}: status={a.get('Status')} groups={d.get('Groups')} roles={d.get('Roles')}")
    except budgets.exceptions.NotFoundException:
        print("  no hiatus budget found - not deployed")
    for n in (DENY_POLICY_NAME,):
        arn = f"arn:aws:iam::{account}:policy/{n}"
        try:
            iam.get_policy(PolicyArn=arn)
            print(f"  policy: {arn} present")
        except iam.exceptions.NoSuchEntityException:
            print(f"  policy: {n} absent")


def destroy(session, account, region):
    iam = session.client("iam")
    budgets = session.client("budgets", region_name="us-east-1")
    lam = session.client("lambda")
    events = session.client("events")
    print(f"\nDestroying hiatus resources on {account}...")
    # budget actions + budget
    try:
        for a in budgets.describe_budget_actions_for_budget(AccountId=account, BudgetName=BUDGET_NAME).get("Actions", []):
            budgets.delete_budget_action(AccountId=account, BudgetName=BUDGET_NAME, ActionId=a["ActionId"])
        budgets.delete_budget(AccountId=account, BudgetName=BUDGET_NAME)
        log("deleted budget + actions")
    except Exception as e:
        log(f"budget: {e}")
    try:
        events.remove_targets(Rule=RULE_NAME, Ids=["hiatus_reset"])
        events.delete_rule(Name=RULE_NAME)
        log("deleted schedule rule")
    except Exception as e:
        log(f"rule: {e}")
    try:
        lam.delete_function(FunctionName=LAMBDA_NAME)
        log("deleted lambda")
    except Exception as e:
        log(f"lambda: {e}")
    for role, inline in ((BUDGET_ROLE_NAME, f"{PREFIX}_budget_inline"),
                         (LAMBDA_ROLE_NAME, f"{PREFIX}_lambda_inline")):
        try:
            iam.delete_role_policy(RoleName=role, PolicyName=inline)
            iam.delete_role(RoleName=role)
            log(f"deleted role {role}")
        except Exception as e:
            log(f"role {role}: {e}")
    # detach + delete deny policy last
    arn = f"arn:aws:iam::{account}:policy/{DENY_POLICY_NAME}"
    try:
        ents = iam.list_entities_for_policy(PolicyArn=arn)
        for g in ents.get("PolicyGroups", []):
            iam.detach_group_policy(GroupName=g["GroupName"], PolicyArn=arn)
        for r in ents.get("PolicyRoles", []):
            iam.detach_role_policy(RoleName=r["RoleName"], PolicyArn=arn)
        iam.delete_policy(PolicyArn=arn)
        log("deleted deny policy")
    except Exception as e:
        log(f"policy: {e}")
    try:
        sns = session.client("sns")
        topic_arn = f"arn:aws:sns:{region}:{account}:{SNS_TOPIC_NAME}"
        sns.delete_topic(TopicArn=topic_arn)
        log("deleted sns topic")
    except Exception as e:
        log(f"sns: {e}")
    print("Destroy complete.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", default="")
    ap.add_argument("--roles", default="")
    ap.add_argument("--budget", type=float)
    ap.add_argument("--email", help="notification email for the budget action (required by AWS)")
    ap.add_argument("--region")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--list-principals", action="store_true",
                    help="print the account's IAM groups/roles as JSON, then exit (no changes)")
    ap.add_argument("--destroy", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print mutating calls without executing")
    ap.add_argument("--yes", action="store_true", help="skip interactive account double-confirmation (use with care)")
    args = ap.parse_args()

    global DRY_RUN
    DRY_RUN = args.dry_run
    if DRY_RUN:
        print("\n*** DRY RUN — no resources will be created or modified ***")

    session = make_session(args)

    if args.list_principals:
        # Read-only: enumerate real IAM groups/roles for the caller to choose from.
        return list_principals(session)

    account, arn = detect_account(session)
    alias = account_alias(session)
    print(f"\nDetected AWS account: {account}\n  identity: {arn}")

    if args.status:
        return status(session, account)

    # Double-confirm the target account before ANY change (deploy or destroy).
    if not double_confirm_account(account, arn, alias, assume_yes=args.yes):
        return print("Aborted — account not confirmed. No changes made.")

    if args.destroy:
        return destroy(session, account, args.region or session.region_name)

    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    # Only prompt when NOTHING was supplied on the CLI (interactive mode).
    if not groups and not roles:
        groups = [g.strip() for g in prompt("Groups to block (comma-separated, blank if none)").split(",") if g.strip()]
        roles = [r.strip() for r in prompt("Roles to block (comma-separated, blank if none)").split(",") if r.strip()]
    if not groups and not roles:
        sys.exit("Must specify at least one group or role to block.")
    amount = args.budget or float(prompt("Monthly Bedrock budget in USD", default=DEFAULT_BUDGET))
    email_raw = args.email or prompt("Notification email(s), comma-separated (added to the alert group)")
    emails = [e.strip() for e in email_raw.split(",") if e.strip()]
    if not emails:
        sys.exit("At least one notification email is required by AWS for budget actions.")

    deploy(session, account, groups, roles, amount, args.region or session.region_name, emails)


if __name__ == "__main__":
    main()
