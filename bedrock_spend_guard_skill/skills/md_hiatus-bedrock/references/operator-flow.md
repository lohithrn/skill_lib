# The operator interview — the eight steps, in order

This is the whole conversational procedure. The order is load-bearing: credentials before anything
else, account confirmation before any change, and status before you ask for a single input you might
not need. Run the steps in this order or you will ask a re-run operator to re-subscribe an email
they already confirmed, or worse, mutate an account nobody approved.

Everything runs through `assets/run.sh`. **Never** call `assets/deploy.py` directly — `run.sh` owns
the private virtualenv the deployer needs (see `references/isolation.md`).

## The picker contract

**Every input is collected through the `AskUserQuestion` tabbed picker. Returning the operator to
the chat or the terminal to type free-hand is BANNED.** Every input — including credentials and the
notification email — is a tab in a picker panel; the operator fills each tab's entry box ("Other")
and never leaves the UI. The account ID is **never** asked: it is derived from the credentials and
shown only for a Yes/No confirmation.

`AskUserQuestion` constraints you must respect: **2–4 questions (tabs) per call**, and **each
question needs 2–4 options** — a single-option question is rejected outright. For fields that are
pure free text (key, secret, token, email), satisfy the 2-option rule with a genuine second choice
and have the operator type the value into the tab's **"Other"** box:

| Field kind | Options to offer | Value goes in |
|---|---|---|
| required free text | `Enter value below` / `Cancel setup` (Cancel is real — aborts with zero changes) | "Other" |
| optional free text (session token) | `None (long-lived key)` / `Enter token below` | "Other" |
| re-run, multi-account | `Keep <masked>` / `Enter new credentials` | "Other" |

Never send a bare "paste it in chat" request, and never end a turn waiting for the operator to type
free-hand. Consequence: an operator who has to leave the picker loses the masking, and the value
lands in the transcript in a place you did not warn them about.

## Two things the operator does not choose

1. **The account.** It is whatever the credentials belong to. The deployer derives it from
   `sts:get-caller-identity`. Do not ask "which account" — detect it, show it, make them confirm it.
2. **The target group and role names.** This skill is account-agnostic. Never guess or hardcode a
   principal name. Enumerate the account's *real* IAM principals first (step 5) and offer those.

---

## 1. Credentials FIRST — one picker, three tabs

The very first thing you ask, as a single `AskUserQuestion` with exactly three questions (tabs), in
this order:

- **Access Key ID** — options `Enter key below` / `Cancel setup`; value in "Other".
- **Secret Access Key** — options `Enter secret below` / `Cancel setup`; value in "Other".
- **Session Token** — options `None (long-lived key)` / `Enter token below`; value in "Other"
  (optional — only for temporary/STS credentials).

If the operator picks `Cancel setup` on a required tab, abort with zero changes. Warn once that what
is entered is visible in the transcript, and that they may want to rotate the key afterward.

Feed the collected values to the deployer **via stdin (a heredoc)** — never on the command line,
never as environment variables — so the secret never lands in shell history, the process list, or
the OS environment:

```bash
cd <this-skill-dir>/assets
./run.sh --region <region> --list-principals <<'EOF'
access_key_id=<key-id>
secret_access_key=<secret>
session_token=<token>        # omit this line if none
EOF
```

The credential hard ban and what the deployer does with these values is in
`references/isolation.md`. Read it before you change anything about this step.

**Multi-account (keep / override).** The same operator may run this against several accounts in one
sitting. On every credential ask *after the first*, show what you currently hold — the **masked**
key id (e.g. `AKIA…7F4Q`) and the account it resolved to — and let them keep it or override with a
new paste. Use the 2-option picker from the table above; only drop to a paste turn when they choose
to enter new ones. Never silently reuse without offering the switch, and never show the secret or
the session token unmasked.

## 2. Mode + region + budget — one picker

After credentials, ask these together in a *single* `AskUserQuestion` as separate tabs:

| Tab | Options |
|---|---|
| **Mode** | `Deploy / update` (recommended) · `Status` · `Destroy` · `Dry-run` |
| **Region** | `us-east-1` (default) · `us-west-2` · `eu-central-1` · Other |
| **Budget** | monthly Bedrock budget in USD — **$700** (default) · **$300** · **$1000** · **$2000** · Other |

The **$700** default is an example value carried from the original deployment, not a recommendation:
the operator sets this deliberately, because it is the number that decides when their Bedrock access
stops. The budget itself always lives in `us-east-1` regardless of the region chosen. For `Status`
and `Destroy` the budget is irrelevant — drop that tab.

## 3. Detect account, SHOW IT, CONFIRM — mandatory, never skipped

Before ANY change you MUST detect the account from the supplied key/secret and display it. Run the
read-only detection first (`--status`, which calls `sts:get-caller-identity`) and print a clear
block back to the operator:

```
Account ID : <account-id>
Identity   : <caller-arn>
Region     : <region>
```

plus whatever existing deployment `--status` reported (budget, targets, policy), so they know
whether this will CREATE or UPDATE. **This is the account the credentials belong to — it cannot be
chosen, and you already know it. Do not ask the operator to type or re-type the account ID.**

Then require ONE explicit approval via `AskUserQuestion`:

- "Proceed to modify account `<account-id>` (`<identity>`)?" → `Yes, proceed` / `No, abort`.

`No` — or anything other than an explicit yes — aborts with zero changes. This gate is MANDATORY for
`deploy` and `destroy`. Never bypass it, and never pass `--yes` to the deployer unless the operator
has already explicitly confirmed in conversation. Skipping the account display or the confirmation
is a defect. The deployer runs its own second gate on top of this one: it re-prints the account and
makes the operator retype the account ID, so a fat-fingered confirmation still cannot land.

## 4. Check status FIRST — decide CREATE vs UPDATE before asking for anything else

The `--status` call in step 3 already told you whether a `hiatus_security_bedrock_*` deployment
exists on this account. **Branch here, and do NOT collect targets or an email until you know which
path you are on** — asking a re-run operator for an email when everything already exists is a
defect: they have no reason to re-subscribe.

- **Nothing deployed yet → NEW deployment.** Continue to step 5 (targets), step 6 (email), step 7
  (deploy). Those inputs are only collected on the create path.
- **A deployment already exists → UPDATE.** Skip straight to step 8.

## 5. [NEW only] Discover real targets

Run `./run.sh --list-principals` (read-only; emits JSON `{"groups":[...],"roles":[...]}` for the
detected account). Present the returned names via `AskUserQuestion` (multiSelect) so the operator
picks from the account's *actual* groups and roles — plus "Other" for a name not listed. Never
pre-populate with guessed names.

Say in the question text that **every principal in the chosen groups and roles loses Bedrock until
the 1st**. If the account has many principals, surface the likely Bedrock-related ones first but
still show the full set. Service-linked roles (path `/aws-service-role/`) are filtered out by the
deployer because a policy cannot be attached to them this way.

## 6. [NEW only] Notification email

AWS requires at least one subscriber email for a budget action. `AskUserQuestion` with one tab
"Notification email(s)" — options `Enter email(s) below` / `Cancel`; the operator types one or more
comma-separated addresses into "Other". Pass them with `--email`. Only ask this on a fresh
deployment, or when the operator has explicitly chosen "Update email" in step 8.

## 7. Deploy

Invoke the deployer with the collected values, credentials via stdin:

```bash
./run.sh --region <region> --groups <g1,g2> --roles <r1> \
         --budget <amount> --email <one@example.com,two@example.com> <<'EOF'
access_key_id=<key-id>
secret_access_key=<secret>
session_token=<token>        # omit if none
EOF
```

**Every invocation needs its own credential heredoc.** The credential is held in memory for the life
of one process and nothing is persisted, so `--list-principals`, the deploy, `--status` and
`--destroy` are each fed the values again. Reuse what the operator pasted in step 1 — do not ask
again. What the deploy creates, and in what order, is in `references/wiring.md`.

## 8. [UPDATE path] It already exists — ask what to change, collect only that

You reached here from step 4. First **show the current status** — budget value, targets, action
state, policy — so the operator sees what is live. Then ask a single `AskUserQuestion` (multiSelect);
the operator may pick none, one, or several:

| Choice | What you then collect |
|---|---|
| **Leave it as-is** | nothing — make zero changes and stop |
| **Update budget value** | the new amount, via the budget picker from step 2 |
| **Update targets** | re-run `--list-principals` and let them re-pick, as in step 5 |
| **Update notification email** | *only then* collect the email, as in step 6 |

Collect inputs **only for the boxes they ticked**, then run step 7 with just those values. Never
gather an input for a change the operator did not ask for. "Leave it as-is" is a valid and common
answer on a re-run: honour it and ask nothing further.
