---
name: md_hiatus-bedrock
description: "Deploy a reusable Amazon Bedrock spend circuit breaker on any AWS account. It CREATES REAL RESOURCES and CAN CUT REAL ACCESS: a monthly AWS Budget filtered to Amazon Bedrock whose action attaches a Deny(bedrock:*) policy to the IAM groups and roles you name once spend hits the limit, plus a scheduled Lambda that detaches it on the 1st. Standing cost is effectively zero; the blast radius is not. Use when asked to cap, guard or circuit-break Bedrock spend."
when_to_use: The user asks to cap, guard, circuit-break or alert on Amazon Bedrock spend on an AWS account, or invokes /hiatus-bedrock.
argument-hint: "nothing — the skill interviews you for mode, region, budget and targets"
allowed-tools: AskUserQuestion, Read, Bash, Write
---

# /hiatus-bedrock

**This skill changes a live AWS account.** It creates seven resources, and when the budget trips it
attaches a `Deny bedrock:*` policy that stops Bedrock for every principal in the groups and roles you
name — including CI and service identities that share them. Standing cost is effectively zero (two
action-enabled budgets are free per account, the Lambda runs **12** times a year); the cost it
prevents is Bedrock spend, and the cost of getting the targets wrong is an outage. Teardown is one
command and leaves nothing behind.

Nothing here is a rule store. The mechanism is in `references/`, the interview is in
`references/operator-flow.md`, and the deploy code is in `assets/`. Read the one you need.

## The gate — read this before running anything

| Question | Answer |
|---|---|
| What does it create? | a Deny(bedrock:*) managed policy, 2 IAM roles, a monthly budget + its action, a Lambda, an EventBridge rule, an SNS topic — all prefixed `hiatus_security_bedrock` |
| What does it cost to run? | ~$0. Budgets: 2 action-enabled budgets free per account. Lambda: **12** invocations/year. SNS email: free at this volume. |
| What does it cost to get wrong? | every principal in a targeted group or role loses Bedrock until the 1st, or until someone detaches the policy by hand |
| How do I undo it? | `./run.sh --destroy` removes everything; detaching the deny policy restores access immediately (`references/teardown.md`) |
| Is it a hard cap? | **No.** Billing lags **6–24h**, so a **$700** budget realistically blocks at **$730–$800**. Say this out loud before deploying. |
| Whose credentials? | only the ones the operator pastes in this conversation. Never the machine's — see the hard ban below. |

Three gates exist and none of them is optional:

1. **The account gate.** Detect the account from the pasted credentials, print it back with the
   caller identity, and get one explicit approval before any change. `deploy.py` then re-prints it
   and makes the operator retype the account ID. Never pass `--yes` unless they already confirmed in
   conversation.
2. **The blast-radius gate.** Before the operator picks targets, say plainly that every principal in
   those groups and roles loses Bedrock when the breaker trips. Offer the exemption: move production
   principals into a group you do not target.
3. **The soft-cap gate.** State the overshoot arithmetic before deploying, not after. An operator who
   expected a hard cap and got a **$780** bill was mis-sold, and the fix is a gateway, not this skill.

## Route

Ask for credentials first, then mode. Every row runs through `assets/run.sh` — **never** call
`assets/deploy.py` directly; `run.sh` owns the private virtualenv it needs.

| Mode | Command | Changes the account? | Read this |
|---|---|---|---|
| Deploy / update | `./run.sh --region <r> --groups <g> --roles <r> --budget <n> --email <e>` | **yes** | `references/operator-flow.md` steps 1–8, `references/wiring.md` |
| Status | `./run.sh --status` | no | `references/operator-flow.md` step 3 |
| List principals | `./run.sh --list-principals` | no | `references/operator-flow.md` step 5 |
| Dry run | `./run.sh --dry-run` + the deploy flags | no | `references/wiring.md` §Dry-run |
| Destroy | `./run.sh --destroy` | **yes** | `references/teardown.md` |

Credentials go in on **stdin as a heredoc** on every single invocation — never on the command line,
never as environment variables, and nothing is cached between runs.

State which mode you selected, and whether it will CREATE or UPDATE, in one line before starting.

---

## Non-negotiables

1. **The credential hard ban.** This skill has no authority over the machine's AWS credentials. It
   never reads any `AWS_*` variable, `~/.aws/credentials` or `~/.aws/config`, the AWS CLI's resolved
   credentials, the `default` profile, any pre-existing named profile, or an instance/SSO/role chain.
   The only credential it may touch is the one pasted in this conversation. Cannot get one? **Abort.**
   Consequence of weakening this: a breaker deployed to whichever account the machine was pointed at,
   which is an outage in an account nobody was watching. Full text: `references/isolation.md`.
2. **Never guess a principal name.** Enumerate the account's real groups and roles with
   `--list-principals` and offer those. A guessed name either does nothing or blocks the wrong team.
3. **Never ask for the account ID.** It is derived from the credentials. Asking invites a typo that
   the retype gate then "confirms".
4. **Status before inputs.** Decide CREATE vs UPDATE from `--status` *before* collecting targets or an
   email. Asking a re-run operator to re-subscribe an email they already confirmed is a defect.
5. **Every input through the picker.** All of it — credentials, region, budget, targets, email — is an
   `AskUserQuestion` tab with the value typed into "Other". Returning the operator to the chat to type
   free-hand is banned, and so is ending a turn waiting for them to type.
6. **Never echo a secret.** Mask the key id (`AKIA…7F4Q`), never print the secret or session token,
   and tell the operator once that the transcript holds what they pasted so they can rotate it.
7. **Collect only what the chosen change needs.** On the update path, gather inputs for the ticked
   boxes and nothing else. "Leave it as-is" is a valid answer: honour it and stop.
8. **Keep the prefix.** Every resource name starts `hiatus_security_bedrock`. That prefix is how a
   re-run recognises its own work and how teardown finds it; rename it and the next run builds a
   second breaker beside the first.
9. **Never widen the created roles to fix a permissions error.** Both breaker roles are pinned by an
   `ArnEquals` condition to this skill's one policy and to the chosen targets. Fix the operator's
   credential instead (`references/permissions.md`) or stop and say what is missing.
10. **Never invent a number.** The budget is whatever the operator chose. Do not default silently,
    and do not quote a spend figure the account did not report.

## What this does NOT do

- **It is not a real-time cap.** Billing data lags **6–24h**. If the requirement is "never one cent
  over", the answer is a proxy or gateway in front of the model calls, and you say so instead of
  deploying this.
- **It does not throttle, queue or degrade.** There is one lever: Bedrock allowed, or Bedrock denied.
- **It does not cap per-user, per-model or per-request spend.** The budget is account-wide and
  filtered only to the Amazon Bedrock service; the Deny is `bedrock:*` in every region.
- **It does not touch the account's groups, roles or users.** It attaches and detaches one policy and
  nothing else.
- **It does not create or read credentials, profiles, certificates or keypairs.** Never run a tool to
  mint an auth credential for this skill; the only credential is the one the operator pastes.
- **It does not manage the AWS Organization.** One account per run. A second account is a second run,
  with a second explicit confirmation.
- **It does not report spend.** Use Cost Explorer for that. `--status` reports the breaker's
  configuration, not the bill.

---

## Index

| File | What it answers |
|---|---|
| `references/operator-flow.md` | the eight interview steps in order, the picker contract, the credential paste form, the account gate, and the CREATE vs UPDATE branch |
| `references/wiring.md` | what the seven resources are, the deploy order and the two propagation waits, the 100%-trip and 1st-of-month reset arithmetic, the overshoot math, the blast radius, dry-run |
| `references/permissions.md` | the actions the operator's credential needs (and why `iam:PassRole` is the one that bites), and the least-privilege policies on the two created roles |
| `references/teardown.md` | detach vs destroy, the exact deletion order and why it is reversed, how to verify the breaker is gone, what survives |
| `references/isolation.md` | the credential hard ban and the four ways `deploy.py` enforces it, the private virtualenv, what must stay git-ignored |
| `assets/deploy.py` | the deployer: credential intake, account detection, the idempotent create/update helpers, `--status`, `--destroy`, `--dry-run` |
| `assets/run.sh` | the only entry point: builds and reuses the private virtualenv, then runs `deploy.py` inside it with stdin passed through |
| `assets/requirements.txt` | the single dependency (`boto3`), hashed to decide whether the venv needs refreshing |

## Checklist before saying done

- [ ] Credentials came from the operator in this conversation, via stdin, and nothing else was read
- [ ] The account was detected, displayed with its identity, and explicitly confirmed
- [ ] The operator heard the blast radius **and** the **6–24h** overshoot before the deploy ran
- [ ] Targets came from `--list-principals`, not from a guess
- [ ] Only the inputs the chosen change needs were collected
- [ ] `--status` was run afterwards and its output reported, rather than assumed
- [ ] The operator was told once that the transcript holds the pasted key, and how to tear the
      breaker down
