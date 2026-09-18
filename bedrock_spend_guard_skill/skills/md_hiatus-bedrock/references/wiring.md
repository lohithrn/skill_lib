# The mechanism — what gets built, in what order, and the arithmetic

Everything this skill creates is prefixed `hiatus_security_bedrock`. That prefix is the contract
between the deployer, `--status` and `--destroy`: it is how a re-run recognises its own resources and
how teardown finds them. Rename it and the skill stops being idempotent — the next run creates a
second breaker beside the first.

## The seven resources

| Resource | Name | What it does |
|---|---|---|
| Managed policy | `hiatus_security_bedrock_deny` | `Deny bedrock:*` on `*`, Sid `HiatusDenyBedrock`. The only thing ever attached or detached. |
| IAM role | `hiatus_security_bedrock_budget_role` | assumed by `budgets.amazonaws.com`; may attach/detach **only** that one policy, **only** to the named targets |
| Budget | `hiatus_security_bedrock_budget` | `COST`, `MONTHLY`, `CostFilters: {Service: ["Amazon Bedrock"]}`, limit in USD |
| Budget action | (AWS-assigned id) | `ACTUAL` spend, `APPLY_IAM_POLICY`, threshold **100.0 PERCENTAGE**, `ApprovalModel: AUTOMATIC` |
| IAM role | `hiatus_security_bedrock_lambda_role` | assumed by `lambda.amazonaws.com`; detach/attach that one policy, plus CloudWatch Logs |
| Lambda | `hiatus_security_bedrock_scheduler` | `python3.12`, handler `lambda_function.handler`, timeout **60**s; detaches the Deny from every target |
| EventBridge rule | `hiatus_security_bedrock_reset_rule` | `cron(0 12 1 * ? *)` — 12:00 GMT on the 1st — target id `hiatus_reset` |
| SNS topic | `hiatus_security_bedrock_email_group` | the notification "email group"; Budgets is allowed `SNS:Publish` to it |

The topic is the subscriber list, not a one-off address: adding a person later means subscribing
their email to this topic, and nothing about the budget action changes.

## The deploy order — do not reorder it

`deploy()` runs these in exactly this sequence, and each step depends on the one before:

1. **Deny policy** — everything else references its ARN, so it exists first.
2. **Budget role** + its inline policy `hiatus_security_bedrock_budget_inline`.
3. **Lambda role** + its inline policy `hiatus_security_bedrock_lambda_inline`.
4. **Lambda** — needs the role ARN from step 3.
5. **SNS topic** + publish policy + email subscriptions — the budget action needs a subscriber ARN.
6. **Budget**, then the **budget action** — needs the policy ARN (1), the execution role ARN (2) and
   the topic ARN (5).
7. **EventBridge rule** + `lambda:InvokeFunction` permission + target — needs the Lambda ARN (4).

Two waits are in that path because IAM and Budgets are eventually consistent, and both were put
there by a failure that actually happened:

- After creating a role: **sleep 8s** for IAM propagation, skipped in dry-run. Without it,
  `create_budget_action` is handed an `ExecutionRoleArn` that Budgets cannot yet see.
- `create_budget_action` retries **5 times with a 5s sleep** on `NotFoundException`, because the
  budget it was just told about has not propagated. Any other `ClientError` breaks out immediately —
  retrying a permission error only delays the message.

Re-running is idempotent by construction: every helper does a `get_*`/`describe_*` first and either
updates in place or creates. An existing budget action is **updated** (same ActionId), never
duplicated — AWS allows only a handful of actions per budget, and a second one would attach the same
Deny twice.

## The trip and the reset

- **Trip:** the budget action fires when **ACTUAL** month-to-date Bedrock spend reaches **100%** of
  the limit, and Budgets — not this skill — attaches the Deny to every named group and role.
  `AUTOMATIC` approval means no human step: the block lands whether or not anyone reads the email.
- **Reset:** the EventBridge rule invokes the Lambda at **12:00 GMT on the 1st** with the payload
  `{"policy_arn": …, "groups": [...], "roles": [...]}`. The Lambda detaches the Deny from each
  target, swallowing `NoSuchEntityException` (already detached is success) and reporting any other
  error per target in its `detached` list. So the block clears itself for the new month.
- **Manual reset:** detaching `hiatus_security_bedrock_deny` from the group or role restores Bedrock
  immediately. You do not have to wait for the 1st, and you do not have to destroy anything.

## The overshoot — this is a soft cap, say so

AWS billing data lags **6–24 hours**. The block therefore lands somewhat *above* the limit: for a
**$700** budget, expect the Deny to attach somewhere around **$730–$800** of real spend. That
arithmetic is the whole honesty of this skill — it is a reactive cap, not a real-time one. A
proxy or gateway in front of the model calls is the only way to get an exact per-request hard cap;
if the operator needs "never one cent over", this is the wrong tool and you say so.

## Blast radius — the thing that surprises people

Every principal in a named group or role loses Bedrock when the breaker trips, including service and
CI identities that happen to share the group. If production calls Bedrock through a shared group, its
AI features go down until the 1st or until someone detaches the policy by hand.

The fix is structural, and you offer it at step 5 of the interview: put production principals in a
separate group that is **not** named as a target. A Deny in an attached policy beats any Allow
anywhere else, so there is no "but production has an explicit allow" escape.

## Region facts

- **Budgets is global and lives in `us-east-1`.** The deployer opens the `budgets` client pinned to
  `us-east-1` regardless of the working region. The operator's region choice governs Lambda,
  EventBridge and SNS only.
- **Deny is account-wide.** `bedrock:*` on `*` is not region-scoped: tripping the breaker stops
  Bedrock for the targets in every region, not just the deployment region.

## Dry-run

`--dry-run` wraps every client so that read calls pass through and any call whose name starts with a
mutating prefix (`create_`, `update_`, `put_`, `attach_`, `detach_`, `delete_`, `add_`, `remove_`,
`tag_`, `untag_`, `set_`, `subscribe`, `unsubscribe`) is printed with its arguments and returns a
stub. Policy documents and zipped code print as `<...>` so the output stays readable. Use it to show
an operator exactly what a first deploy would do; the propagation sleeps are skipped, so it also
returns fast.
