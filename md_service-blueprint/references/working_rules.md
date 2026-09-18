# The 8 working rules

Mined from how work is actually directed on this fleet. Treat them as **acceptance criteria**, not
suggestions, and put the relevant ones at the **top** of any plan you write.

1. **Never break existing users.** New features are additive. If a change deletes or rewrites code paths
   other customers rely on, **stop and flag it**. A bug or pattern fix is not a revert; a refactor is not
   a rewrite. When reviewing a diff, call out *every* removed line that was not explicitly requested.
2. **Surgical over sweeping.** Change the smallest thing that solves the problem. Do not reformat,
   rename, or "clean up" unrelated code in the same change. Keep related changes organized into
   clearly-named files and subfolders, not scattered.
3. **Confirm, don't hallucinate.** Never present speculation as fact. If you say "X is the problem" or
   "X is blocked", you must have actually verified it — run it, read it, checked the resource. If it is
   unverified, say so **explicitly, in the sentence**.
4. **Nothing hardcoded.** The service name derives from the repo folder. Resource names derive from
   `prefix`. Account ids live in one config file. URLs live in `urls.{env}.yaml`. Secrets come from
   Secrets Manager or the environment, never source. And never mint a certificate or a keypair as an
   authorization mechanism — the direction is SigV4, and the only acceptable TLS is a CA-issued or
   cloud-provider-managed certificate nobody here generated.
5. **Scripts are self-contained.** One command does everything — login, build, test, deploy. **Never**
   tell the user to run an extra command first; run it inside the script. No required pre-set environment
   variables beyond credentials.
6. **A deploy never lies.** Gate on unit tests before the zip is built. Assert the resolved AWS account
   matches the environment before any mutation. Propagate `terraform apply`'s exit code as the script's
   exit code — a failed apply can never report success. Always **print the real, resolved public URL** at
   the end, never a placeholder.
7. **Cost-conscious by default.** Prefer the cheapest thing that meets the need: DynamoDB over
   Aurora/RDS, lambda over always-on compute, a function URL over standing up extra networking. If asked
   for a design, state the rough monthly cost. Never introduce Aurora, RDS, a NAT gateway or always-on
   compute without calling it out and getting a yes.
8. **Answer the question asked.** If it is a yes/no or a number, lead with that in one line. Save the
   explanation for after, or omit it. Do not bury the answer in a wall of text.

## The consequence attached to each

A rule with no consequence reads as a preference, so here is what each one costs when it is skipped.

| Rule | What breaks |
|---|---|
| 1 | a customer's integration stops working, and the change that did it looked like a cleanup |
| 2 | the diff is unreviewable, so the one real change in it is approved unread |
| 3 | someone spends a day on the wrong cause because a guess was stated as a finding |
| 4 | the service works in the environment it was written in and nowhere else |
| 5 | half the deploys are run half-way, and the failure looks like an AWS problem |
| 6 | "deployed" and "deployed successfully" stop being the same thing |
| 7 | a NAT gateway or an idle cluster becomes the largest line on the bill, discovered a quarter later |
| 8 | the answer exists in the reply and is not found |

## The ninth rule lives with the standing rules

The `md_fleet-conventions` skill carries a ninth: **judge against the system, not the snapshot.** An
env-scoped name holding one value today, a knob with one mode, two slug variables carrying the same
string — deliberate headroom, a feature, not a finding. It matters most while *reviewing* an existing
repo, which is that skill's job; it matters here only as a reason not to "simplify" a seam the templates
deliberately leave open.
