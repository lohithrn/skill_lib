# Teardown — removing the breaker, and unblocking without removing it

Two different needs get confused here. "Bedrock is blocked and I need it back now" is not a teardown —
it is a detach, and it takes one call. Teardown is "remove the breaker entirely, stop guarding this
account". Answer the question the operator actually asked.

| The operator wants | Do this | Effect |
|---|---|---|
| Bedrock back right now, keep guarding | detach `hiatus_security_bedrock_deny` from the group/role | access returns immediately; the breaker re-arms and can trip again this month |
| Bedrock back on the 1st, no action | nothing | the reset Lambda detaches at 12:00 GMT on the 1st |
| A different limit | re-run the deploy with a new `--budget` | budget updated in place, targets untouched |
| The breaker gone | `./run.sh --destroy` | every `hiatus_security_bedrock_*` resource deleted |

## What `--destroy` removes, in this order

The order is the reverse of the create order for one reason: the Deny policy cannot be deleted while
anything is attached to it, and nothing may be left able to re-attach it while we are deleting.

1. **Budget actions, then the budget** — kill the thing that can re-attach the Deny first. Delete the
   actions before the budget: a budget with a live action refuses to delete.
2. **EventBridge targets, then the rule** — a rule with targets refuses to delete.
3. **The Lambda.**
4. **Both roles** — the inline policy first (`delete_role_policy`), then the role. A role with an
   inline policy attached refuses to delete.
5. **The Deny policy last** — enumerate `list_entities_for_policy`, detach it from every group and
   role still holding it, then delete it. **This is the step that restores Bedrock access** for
   anything the breaker had blocked.
6. **The SNS topic.**

Every step is wrapped individually: a failure is logged and the run continues to the next resource.
That is deliberate — a half-deployed breaker (a deploy that died at `create_budget_action` for a
missing `iam:PassRole`) must still be removable in one pass, and stopping at the first
`NoSuchEntity` would leave the rest behind. The consequence you must handle: `--destroy` can print
errors and still exit successfully, so **always re-run `--status` afterwards** and read it, rather
than trusting "Destroy complete."

`--destroy` is behind the same mandatory account confirmation gate as a deploy: the account is
detected, displayed, and confirmed before anything is deleted. See step 3 of
`references/operator-flow.md`.

## Verifying it is gone

`./run.sh --status` on the same account should report:

- `no hiatus budget found - not deployed`
- `policy: hiatus_security_bedrock_deny absent`

If the policy is still reported present, something is still attached to it — a group or role that was
added as a target after the last deploy, so it is not in the payload the teardown enumerated. Detach
it by name and delete the policy.

## What teardown does not touch

- **CloudWatch log groups.** `/aws/lambda/hiatus_security_bedrock_scheduler` survives the Lambda.
  It is a few KB of reset records; delete it by hand if the account must be spotless.
- **Confirmed SNS email subscriptions** vanish with the topic, but the confirmation emails already
  sent do not un-send. A re-deploy creates a new topic and every subscriber must confirm again.
- **The account's own groups and roles.** This skill created none of them and deletes none of them.
  It only ever attaches and detaches one policy — everything else about those principals is left
  exactly as it was.
- **The local private virtualenv** under the skill's `assets/` directory. Removing that is a local
  cleanup, covered in `references/isolation.md`, and it costs nothing to leave in place.

## Cost after teardown

Zero. The standing cost while deployed is also effectively zero — AWS Budgets gives two
action-enabled budgets free per account, the Lambda runs **12 times a year** for well under a second,
and SNS email is free at this volume. The only cost this skill can ever create is the Bedrock spend it
exists to stop, so never present teardown as a saving.
