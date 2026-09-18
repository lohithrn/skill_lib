---
name: md_fleet-conventions
description: The standing conventions in force across an AWS lambda service fleet, and where each one came from — the <prefix>_<resource_role>_<company> naming rule with its 64-character escape hatches, the /<project_slug>/stage/{stage}/tenant/{tenant}/<methodname> route shape, urls.{env}.yaml outbound config, the single authorization gate, epoch-milliseconds-everywhere and the DynamoDB Decimal boundary, lambdas-only compute, and the ten deploy gates. Use when naming anything, wiring a route or an outbound URL, adding a resource, or reviewing an existing repo against the fleet.
when_to_use: Naming a resource, wiring a route or an outbound URL, adding a resource to a service that already exists, or reviewing a repo or a diff against the fleet's standing rules.
allowed-tools: Read, Grep, Glob
---

# /fleet-conventions

The rules actually in force across the fleet, why each one exists, and what breaks without it.
This file is a **router**: it holds the gate, the route table and the non-negotiables. Every rule,
number and cap lives in `references/`. Read the one row you need — not all nine files.

Standing up a **new** service from nothing is a different job, and it belongs to the
`md_service-blueprint` skill. This skill is the standing rules: use it to review an existing repo, or
to extend one without breaking it.

## The gate — read this first

**This skill advises. It does not edit.** No `Edit` tool is granted, deliberately.

- Every output is a suggestion with a location and a named rule. The user applies it, or does not.
- **Read the repo before ruling.** Where a convention and this document disagree, **the repo wins**
  for that repo — the older services predate half of these rules and were not retrofitted on
  purpose. Say which repo you read.
- Never retrofit an older service to a newer convention unless asked. That is a sweeping change to
  a working production service, and working rule 2 forbids it.
- **Judge against the system, not the snapshot.** An env-scoped name holding one value today, a knob
  with one mode, two slug variables carrying the same string — that is deliberate headroom and a
  feature. "You collapsed X into one value" is not a finding. When unsure, **ask**.

## Route

| You are about to… | Read |
|---|---|
| name a table, function, IAM role, topic, queue or schedule group | `references/naming.md`, then `references/naming_length_caps.md` |
| add or change a route, or call another service | `references/routes_and_urls.md` |
| touch authorization, or store/read anything | `references/auth_and_data.md` |
| choose compute, or write/change a deploy script | `references/deploy_and_compute.md` |
| lay out a repo, or touch the `api_gateway` module | `references/repo_layout.md` |
| build or restyle a frontend | `references/ui_theme.md` |
| decide which existing repo to copy from | `references/fleet_repo_index.md` |
| plan any change, or review a diff | `references/working_rules.md` — **first, before the rest** |

State which file you read in one line before ruling.

---

## The non-negotiables

These eight hold in every repo, including the ones that predate the rest of this document. A breach
of one of these is a finding; everything else is a suggestion.

1. **Nothing derived is hardcoded.** The service name comes from the repo folder name. Resource
   names come from `prefix`. Account ids come from one file. Outbound URLs come from
   `urls.{env}.yaml`. Secrets come from Secrets Manager or the environment. A hardcoded name is a
   service that breaks the day the repo moves, and it breaks in the wrong environment.
2. **Names are composed in exactly one place** — `infra/terraform/naming.tf`, one `locals` entry per
   resource. Every `.tf` reads `local.<name>` and never re-spells the rule. Re-spelling it means the
   next convention change has to find every copy.
3. **Every IAM role, function name and schedule group is asserted under its cap at plan time.** IAM
   answers a too-long name at **apply**, after a clean plan, halfway through a deploy. A comment is
   not an assertion.
4. **One authorization gate.** Every handler's first statement is the one auth call, which calls
   exactly one function. Commenting out that function's body removes authorization from the whole
   application. No handler has a second condition of its own.
5. **Never mint a certificate or a keypair as an authorization mechanism.** The only acceptable TLS
   is a CA-issued or cloud-provider-managed certificate nobody here generated, verified against the
   system trust store. Authorization direction is SigV4. This outranks every rule below it.
6. **Epoch milliseconds everywhere in the backend.** Never ISO strings. `last_updated_time` is
   mandatory on every row. One argued exception exists and it is in `references/auth_and_data.md`.
7. **A deploy can never lie.** Tests gate the zip, the resolved account is asserted before any
   mutation, `terraform apply`'s exit code is the script's exit code, and the real resolved public
   URL is printed. All ten gates are in `references/deploy_and_compute.md`.
8. **Lambdas, and nothing else.** Never Lightsail, Docker, EC2 or Fargate unless explicitly asked.
   A web frontend is one lambda behind the Lambda Web Adapter layer, pinned.

---

## The shape, in one screen

```
<prefix>_<resource_role>_<company>          # every AWS resource, composed in naming.tf
prefix       = "<environment_lower>_<project_slug>"
project_slug = repo folder name, lowercased, non-alphanumerics -> "_"
company      = lower(var.company_name)

/<project_slug>/stage/{stage}/tenant/{tenant}/<methodname>/<paramName>/{paramValue}/...
```

Mandatory parameters go in the path; optional parameters go in the query string. The **stage is a
property of the deployment, not of the request** — it selects which identity pool authorizes the
call, so a caller who could choose it could present a beta token against prod. `{tenant}` appears in
the path **and** the header, and the handler compares them.

Three AWS namespaces cap at **64** and carry extra segments on top of `prefix`, so each gets its own
slug variable rather than a truncation: schedule groups (`var.scheduler_slug`, which also carries a
tenant segment), IAM role names (`var.role_slug`, which carries a role-kind suffix on top of the
function name), and lambda function names — which keep the **full** prefix, because a function name
is what the logs and the console show. **They may hold the same value today; that is headroom.**

Code size, standing in every repo: every file **< 250** lines, every method **< 25** lines, no
nesting **> 2** levels, verbose descriptive names in both `src/` and terraform. There should be a
**test** enforcing the file cap, not just a habit.

---

## What this skill does NOT do

- **It does not scaffold.** No new repo, no new `naming.tf`, no deploy script written from scratch —
  that is the `md_service-blueprint` skill's job, and it has the templates.
- **It does not run a deploy, a login, or any AWS mutation.** It reads terraform and source.
- **It does not invent a convention.** Where this document is silent, the answer is "match the
  closest existing repo", and the answer is not a number this skill made up.
- **It does not retrofit.** Older repos compose names inline and pass `prefix` on the terraform CLI.
  That is the older convention, it works, and it stays until someone asks.
- **It does not measure.** It has no scripts. Name lengths are arithmetic you do by hand against the
  cap table; anything else you claim, you claim from a file you opened.

---

## Refusals

Say no, in one line, with the rule, to each of these:

| Asked for | Answer |
|---|---|
| a hardcoded account id, service name, prefix or outbound URL "just for now" | no — non-negotiable 1; it breaks in the wrong environment |
| a certificate or keypair minted to authenticate a client | no — non-negotiable 5, permanent |
| a second place that decides whether a request is authorized | no — non-negotiable 4; the one-gate property is the whole design |
| collapsing `role_slug` and `scheduler_slug` because they match today | no — the two caps are independent; this is headroom |
| an OPTIONS route with `authorization = NONE` for CORS | no — the browser talks to the frontend lambda, which proxies; there is no preflight to answer |
| ISO timestamps in a new table | no — non-negotiable 6 |
| RDS, Aurora, a NAT gateway or always-on compute | not without a stated monthly cost and an explicit yes |
| truncating a runtime-composed name to fit a cap | no — it merges two tenants onto one resource and destroys the isolation |

---

## Checklist before saying done

- [ ] No hardcoded service name, slug, prefix, account id, URL or secret in `src/` — and ideally not in `test/`
- [ ] Every resource name from `naming.tf`, `<prefix>_<resource_role>_<company>`, verbose and specific
- [ ] Every IAM role / schedule group / function name asserted under **64** at **plan** time
- [ ] Routes are `/<project_slug>/stage/{stage}/tenant/{tenant}/<methodname>(...)`, mandatory in path, optional in query
- [ ] Handler's first statement is the one auth call; commenting one function out disables auth
- [ ] Every backend time is epoch milliseconds; `last_updated_time` present
- [ ] `Decimal` converted once, at the DynamoDB boundary
- [ ] Every runtime-created per-tenant resource has a delete path
- [ ] Lambdas only
- [ ] Files **< 250** lines, methods **< 25** lines, nesting **≤ 2** — with a test enforcing it
- [ ] Comment lines **≤** code lines in every `.tf`
- [ ] Deploy: tests gate the zip, account asserted, exit code propagated, real URL printed
- [ ] Diff contains only what was asked, and every removed line was requested

---

## The reference files

| File | Answers |
|---|---|
| `references/naming.md` | how a resource name is composed, the taste rules, the banned name shapes, and the three tiers that derive the service name from the folder |
| `references/naming_length_caps.md` | which AWS namespaces cap where, why one prefix is not enough, the measured overflow evidence, and the plan-time assertion pattern |
| `references/routes_and_urls.md` | the route shape and its rules, why the stage belongs to the deployment, the tenant double-check, what survives the proxy hop, `/mcp`, and `urls.{env}.yaml` |
| `references/auth_and_data.md` | the one-gate seam and its two OR'd credentials, epoch-ms, the single-table DynamoDB rules, the `Decimal` boundary, and the delete-path rule |
| `references/deploy_and_compute.md` | lambdas-only and the Lambda Web Adapter rules, cost defaults, the ten deploy gates in order, the two deploy modes, and terraform comment discipline |
| `references/repo_layout.md` | the repository tree, one-file-per-resource, the `api_gateway` module and its three hardening differences, and what a local harness must serve |
| `references/working_rules.md` | the nine working rules that come before any code, and how to apply them to a diff |
| `references/ui_theme.md` | the CSS-variable palette, type, structural pieces and the one motion rule a new frontend copies |
| `references/fleet_repo_index.md` | what a fleet looks like, which role each repo plays, and how far each convention has actually spread |
