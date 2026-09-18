# Naming, boundaries and the gates that stop a bad apply

The rule text for `md_upsert-aws-deployment-role`. Every rule here states what breaks without it.

## The naming triple

One base, three parallel suffixes:

```
<repo>-<component>-<stage>-deploy-role
<repo>-<component>-<stage>-deploy-policy
<repo>-<component>-<stage>-deploy-boundary
```

`<repo>` is the logical repo name lower-cased with every run of non-alphanumeric characters collapsed to
`-` and the ends trimmed. `<component>` is `frontend` or `backend`. `<stage>` is `beta` or `prod`.

**Never rename one of the three without the other two.** The names are how a human, a policy document
and a boundary condition find each other: the boundary ARN is embedded in the role policy's
`iam:PermissionsBoundary` condition, so a boundary whose name drifted leaves the role able to create IAM
that nothing constrains. `build_names` in `assets/deployment_plan.py` is the only place the triple is
built — read it rather than reconstructing the string.

## The permissions boundary (Option B)

The boundary is applied to **two** things: the deploy role itself, and — through the
`IAMCreateOnlyWithBoundary` condition in the role policy — every role the deploy role creates.

- It is **self-referential**: it permits creating roles only when they carry *this* boundary, so the
  ceiling propagates to grandchildren. Without that, CI creates one bounded role which then creates an
  unbounded one, and the ceiling was decorative.
- It is deliberately **looser than the role policy**: service-level `<service>:*` for the services this
  deployment actually uses, plus non-mutating read leeway across the common infrastructure services. A
  boundary is a ceiling, not the least-privilege floor. Making it as tight as the policy means every
  future permission addition needs two edits, and the second one gets forgotten.
- `s3`, `dynamodb` and `logs` are always in the allowed set — state backend and logging.
- It **denies** the escalation and takeover actions outright: `iam:CreateUser`, `iam:DeleteUser`,
  `iam:CreateAccessKey`, `iam:DeleteRolePermissionsBoundary`, `iam:PutUserPermissionsBoundary`,
  `iam:CreateSAMLProvider`, `iam:CreateOpenIDConnectProvider`, `iam:UpdateAssumeRolePolicy`,
  `organizations:*`, `account:*`. An explicit Deny beats any Allow, including one added later by
  somebody who did not read this file.

Every `aws_iam_role` in the deployed Terraform must set `permissions_boundary` to the boundary ARN or
the apply is denied.

## The region guardrail

For prod, deny regional actions outside the stage's allowed regions with a
`StringNotEquals` condition on `aws:RequestedRegion`, and exempt the global services the policy actually
grants — `cloudfront`, `route53`, `acm`, `iam`, `sts` — through `NotAction`. Two failure modes to
respect:

1. **An empty `NotAction` is invalid IAM.** When the stack grants no global service, use
   `"Action": "*"` instead. The whole document is rejected otherwise.
2. **CloudFront forces us-east-1 into the allowed set.** `NotAction` on `acm:*` does not help, because
   the certificate validation is evaluated with `aws:RequestedRegion=us-east-1`. `jobs/scan-terraform.md`
   has the full trap and the misleading error it produces.

The state backend (S3 + DynamoDB) is regional, so it stays subject to the region restriction on purpose.

## The merge gate — applies are additive

The engine never silently shrinks a live role. It fetches the live document, unions it with the
generated one, and applies the union.

| Situation | Default behaviour | How to override |
|---|---|---|
| Generated document adds actions | added, and the count is printed | — |
| Generated document omits actions the live role has | **kept** (additive), with every omitted action listed | `--allow-reduce` |
| `--allow-reduce` passed | **three** separate confirmations, each defaulting to no | answering no at any of them keeps the additive union |

Why three: a reduction is the only irreversible thing this skill does to an existing role, and a single
`y` is indistinguishable from a reflex. Any single "no" cancels the reduction and applies the union
instead.

## Access keys are opt-in

No access key is created unless `--create-access-key` is passed. The CI user's existing credentials are
reused. When a key **is** minted, it is printed once and never written to a file — copy it into CI at
that moment or mint a new one later. Do not add the flag on the user's behalf, and do not add it "while
you are in there" during a routine policy update: an unrequested key is a live credential nobody is
tracking.

## Who may assume the role

The trust policy is deliberately multi-principal, all within the verified account:

- the **CI user** — the automation path;
- the **human caller's role**, resolved from the current session, so an engineer can reproduce exactly
  what CI does without being handed a long-lived key;
- the **account root** — only with `--trust-root`, never by default.

Trusting principals only inside the same account is what keeps this from becoming a cross-account
foothold; making root opt-in is what keeps the escape hatch from becoming the normal path.

## Refusals

- **No `default` profile and no ambient credentials.** They are whatever the last tool left behind, so a
  run that trusts them can provision into the wrong account with no record of which identity did it.
- **No unverified account id.** The account comes from `aws sts get-caller-identity` on the chosen
  profile, never from memory.
- **No profile mutation.** The chosen profile is read and left exactly as found.
- **No engine replacement, no engine edit mid-run, no continuing past an engine error.**
- **No certificate or keypair minted as an authorization mechanism.** IAM roles, an SSO login, and an
  explicitly requested CI access key are the only credentials in scope. See
  `references/operating-doctrine.md`.
- **No IAM changes from the sibling scaffolding skill.** If a scaffolded repo needs a deploy role, that
  is a separate, confirmed run of this one.
