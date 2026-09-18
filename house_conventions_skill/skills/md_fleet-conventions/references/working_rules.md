# The nine working rules

These come first, before any code. Treat them as acceptance criteria, not suggestions, and put the
relevant ones at the **top** of any plan.

1. **Never break existing users.** New features are additive. If a change deletes or rewrites a code
   path other customers rely on, stop and flag it. A bug fix is not a revert; a refactor is not a
   rewrite. When reviewing a diff, call out **every** removed line that was not explicitly requested.
2. **Surgical over sweeping.** Change the smallest thing that solves the problem. No drive-by
   reformatting, renaming or cleanup of unrelated code in the same change. Keep related changes in
   clearly-named files and subfolders rather than scattered.
3. **Confirm, don't hallucinate.** "X is the problem" or "X is blocked" requires having actually run,
   read or checked it. If it is unverified, say so **in the sentence**, not in a caveat at the end.
4. **Nothing hardcoded.** Folder → service name. Prefix → resource names. One file → account ids.
   `urls.{env}.yaml` → outbound URLs. Secrets Manager or the environment → secrets. And never mint a
   certificate or a keypair as an authorization mechanism.
5. **Scripts are self-contained.** One command does login, build, test, deploy. Never tell the user to
   run something first. No required pre-set environment variables beyond credentials.
6. **A deploy never lies.** Tests gate the zip; the account is asserted before mutation; `apply`'s exit
   code is the script's exit code; the real resolved URL is printed.
7. **Cost-conscious by default.** The cheapest thing that meets the need. If asked for a design, state
   the rough monthly cost. Never introduce Aurora, RDS, a NAT gateway or always-on compute without
   calling it out and getting a yes.
8. **Answer the question asked.** If it is a yes/no or a number, lead with that in one line. The
   explanation comes after, or not at all.
9. **Judge against the system, not the snapshot.** An env-scoped name or a knob that currently holds the
   loosest value, or the same value in every branch, is **deliberate headroom** — a feature. "You
   collapsed X into one value" is not a finding. A real finding breaks the system as designed or
   forecloses a path being kept open. When unsure whether something is intentional, **ask**.

## Applying them to a diff

Read in this order; each row's failure outranks every row below it.

| Order | Ask | If it fails |
|---|---|---|
| 1 | Does any removed or rewritten line serve an existing user? | stop and flag it, by line, before reviewing anything else (rule 1) |
| 2 | Is anything in the diff outside what was asked? | name each one; a reformat, a rename, a "while I was in there" (rule 2) |
| 3 | Is any claim in the description unverified? | say which, and what would verify it (rule 3) |
| 4 | Is anything derived now hardcoded? | one finding per hardcoded value, with the source of truth it should read (rule 4) |
| 5 | Can the deploy still not lie? | check gates 5, 6, 9 and 10 specifically — those are the four that decay (rule 6) |
| 6 | Did cost change? | state the delta, per month (rule 7) |
| 7 | Is a seam being closed that was open on purpose? | this is **not** a finding — ask whether it is headroom (rule 9) |

## The two rules people get wrong

**Rule 1 is about users, not about tests.** A deleted test is a rule 2 problem. A deleted code path is a
rule 1 problem, and the two get the same size of comment only because reviewers skim.

**Rule 9 is not permission to leave things loose.** It says a seam that *permits* a future change is
deliberate. It does not say a missing credential, an identity mismatch that stops a run, or a hard cap
that truncates data is headroom. Those break the system as designed, and they are real findings.

## The standing checklist

- [ ] No hardcoded service name, slug, prefix, account id, URL or secret in `src/` — and ideally not in `test/`
- [ ] Every resource name from `naming.tf`, `<prefix>_<resource_role>_<company>`, verbose and specific
- [ ] Every IAM role / schedule group / function name asserted under **64** at **plan** time
- [ ] Routes are `/<project_slug>/stage/{stage}/tenant/{tenant}/<methodname>(...)`, mandatory in path, optional in query
- [ ] Handler's first statement is the one auth call; commenting one function out disables auth
- [ ] Every backend time is epoch milliseconds; `last_updated_time` present
- [ ] `Decimal` converted once at the DynamoDB boundary
- [ ] Every runtime-created per-tenant resource has a delete path
- [ ] Lambdas only
- [ ] Files **< 250** lines, methods **< 25** lines, nesting **≤ 2** — with a test enforcing it
- [ ] Comment lines **≤** code lines in every `.tf`
- [ ] Deploy: tests gate the zip, account asserted, exit code propagated, real URL printed
- [ ] Diff contains only what was asked
