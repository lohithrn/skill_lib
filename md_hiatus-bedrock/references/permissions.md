# Permissions — what the deploying credential needs, and what the created roles get

Two different questions live here. The first is what the operator's credential must be allowed to do,
or the run dies halfway with a resource already created. The second is what the two roles this skill
creates are allowed to do, which is deliberately almost nothing.

## What the deploying credential needs

The credential handed in at step 1 of the interview must carry these, on the target account. There is
no managed policy that is exactly this set; an account admin credential covers it.

| Service | Actions | Used by |
|---|---|---|
| STS | `sts:GetCallerIdentity` | account detection — the mandatory confirmation gate cannot run without it |
| IAM (read) | `iam:ListGroups`, `iam:ListRoles`, `iam:ListAccountAliases`, `iam:GetPolicy`, `iam:GetRole`, `iam:ListEntitiesForPolicy` | `--list-principals`, `--status`, idempotency checks |
| IAM (write) | `iam:CreatePolicy`, `iam:DeletePolicy`, `iam:CreateRole`, `iam:DeleteRole`, `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:AttachGroupPolicy`, `iam:DetachGroupPolicy`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:PassRole` | the deny policy, both roles, teardown |
| Budgets | `budgets:ViewBudget`, `budgets:ModifyBudget`, `budgets:CreateBudgetAction`, `budgets:UpdateBudgetAction`, `budgets:DescribeBudgetActionsForBudget`, `budgets:DeleteBudgetAction` | the budget and its action |
| Lambda | `lambda:CreateFunction`, `lambda:UpdateFunctionCode`, `lambda:GetFunction`, `lambda:AddPermission`, `lambda:DeleteFunction` | the reset function |
| EventBridge | `events:PutRule`, `events:PutTargets`, `events:RemoveTargets`, `events:DeleteRule` | the monthly cron |
| SNS | `sns:CreateTopic`, `sns:SetTopicAttributes`, `sns:Subscribe`, `sns:ListSubscriptionsByTopic`, `sns:DeleteTopic` | the notification email group |

`iam:PassRole` is the one people forget. Budgets and Lambda both receive a role ARN they will assume,
and without `PassRole` the run fails at `create_budget_action` or `create_function` — after the deny
policy and both roles already exist. That is the half-deployed state: re-run once the permission is
granted and idempotency picks up where it stopped.

**Never** work around a missing permission by widening the created roles. Fix the operator's
credential instead, or stop and report what is missing.

## What the created roles get — least privilege, on purpose

Both roles are scoped by an `ArnEquals` condition on `iam:PolicyARN`, so neither can attach anything
except this skill's own Deny policy, and the `Resource` list is the exact target group and role ARNs
the operator picked. A stolen or misused breaker role therefore cannot attach an arbitrary policy to
an arbitrary principal — the worst it can do is the thing it was built to do.

| Role | Trusted principal | Allowed | Scope |
|---|---|---|---|
| `hiatus_security_bedrock_budget_role` | `budgets.amazonaws.com` | `iam:Attach/DetachGroupPolicy`, `iam:Attach/DetachRolePolicy` | `Condition: ArnEquals iam:PolicyARN = <deny-policy-arn>`, `Resource` = the target group/role ARNs |
| `hiatus_security_bedrock_lambda_role` | `lambda.amazonaws.com` | the same four actions, plus `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` on `*` | same condition and same resources |

Two details that look like slack but are not:

- **The Lambda role can attach, not only detach.** It is the reset path, so detach is what it uses;
  attach is present so the same role can re-arm a target the operator re-adds without a new deploy.
  The `ArnEquals` condition means the extra verb cannot reach any other policy.
- **`Resource` falls back to `["*"]` when the target list is empty.** That branch is unreachable
  through the interview — the deployer exits with "Must specify at least one group or role to block"
  when no target is given — but if you ever call the policy builders directly, pass real targets.
  A breaker with no targets is a budget that fires and blocks nobody.

Update the targets later (step 8 of the interview) and both inline policies are rewritten with the new
resource list. That is why the update path re-runs the full deploy rather than only touching the
budget action.

## The IAM evaluation rule this whole design rests on

An explicit `Deny` in any attached policy beats every `Allow`, anywhere — identity policy, resource
policy, permissions boundary. That is why a single attached managed policy is enough to stop Bedrock
for a principal, and why exempting production means *not naming its group as a target* rather than
granting it a louder allow. There is no allow that outranks this deny.

The teardown ordering that follows from the same fact is in `references/teardown.md`.
