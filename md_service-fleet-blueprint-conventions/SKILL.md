---
name: md_service-fleet-blueprint-conventions
description: The standing conventions in force across an AWS lambda service fleet and the job of building to them — the <prefix>_<resource_role>_<company> naming rule with its 64-character escape hatches composed in one naming.tf, the /<project_slug>/stage/{stage}/tenant/{tenant}/<methodname> route shape, urls.{env}.yaml outbound config, the single authorization gate, epoch-milliseconds-everywhere and the DynamoDB Decimal boundary, lambdas-only compute, and the ten deploy gates. Reviews an existing repo against the fleet, and stands up a new service or adds a resource from the bundled naming, deploy, account-config and URL-resolver templates. Use when naming anything, wiring a route or an outbound URL, adding a resource, creating a service or repo from nothing, writing or changing a deploy script, or checking a service for production readiness.
when_to_use: Naming a resource, wiring a route or an outbound URL, reviewing a repo or a diff against the fleet's standing rules — or standing up a new service, backend or frontend from nothing and adding resources to one that exists.
argument-hint: "nothing to review — or 'build' to stand up a service or add a resource"
allowed-tools: Read, Grep, Glob, Edit, Write, TodoWrite
---

# /md_service-fleet-blueprint-conventions

The rules actually in force across the fleet, why each one exists, what breaks without it, and how to
build a service that obeys them. This file is a **router**: it holds the gate, the route table and the
non-negotiables. Every rule, number and cap lives in `references/`; the build procedures are in `jobs/`;
the copyable files are in `assets/`.

**Two arcs. Pick one before you do anything.**

| Arc | You are | Starts at |
|---|---|---|
| **review** (default) | Reading an existing repo, ruling on a diff, naming one thing, deciding whether something is production ready | the route table below — **no file is edited** |
| **build** | Standing up a new service/repo/backend/frontend, adding a resource or a route, writing or changing a deploy script | `references/blueprint-standard.md`, then the `jobs/` file it names — **files are written** |

## The gate — read this first

**The review arc advises; it does not edit.** The build arc writes files, because producing a tree is
its job. State which arc you are in, in one line, before touching anything.

- **Review:** every output is a suggestion with a location and a named rule. The user applies it, or
  does not. Nothing in the tree changes.
- **Build:** `Edit` and `Write` are granted for this arc only, and its own gate is
  `references/blueprint-standard.md` §The gate — read a sibling repo's `infra/` and `naming.tf` first
  and mirror them, and never fill a `REPLACE_` placeholder with a guess. An account id, state bucket or
  profile name you invented is a deploy that lands somewhere nobody chose. Leave it, and say you left it.
- **Read the repo before ruling or writing.** Where a convention and this document disagree, **the repo
  wins** for that repo — the older services predate half of these rules and were not retrofitted on
  purpose. Say which repo you read.
- **Never retrofit an older service** to a newer convention unless asked. That is a sweeping change to
  a working production service, and working rule 2 forbids it.
- **Never run a deploy, a login, or any AWS mutation** in either arc. The build arc writes the script;
  the user runs it.
- **Judge against the system, not the snapshot.** An env-scoped name holding one value today, a knob
  with one mode, two slug variables carrying the same string — that is deliberate headroom and a
  feature. "You collapsed X into one value" is not a finding. When unsure, **ask**.

## Route

| You are about to… | Arc | Read |
|---|---|---|
| name a table, function, IAM role, topic, queue or schedule group | review | `references/naming.md`, then `references/naming_length_caps.md` |
| know which resources a service owns, their caps, and which rules a **legacy** repo is exempt from | both | `references/resource_catalog.md` — one row per resource kind |
| add or change a route, or call another service | review | `references/routes_and_urls.md` |
| touch authorization, or store/read anything | review | `references/auth_and_data.md` |
| choose compute, or judge a deploy script | review | `references/deploy_and_compute.md` |
| lay out a repo, or touch the `api_gateway` module | review | `references/repo_layout.md` |
| build or restyle a frontend | review | `references/ui_theme.md` |
| decide which existing repo to copy from | review | `references/fleet_repo_index.md` |
| plan any change, or review a diff | review | `references/working_rules.md` — **first, before the rest** |
| create a new service / repo / backend / frontend | build | `references/blueprint-standard.md`, then `jobs/new_service.md` |
| add a resource, a route, or a deploy change to a repo that exists | build | `references/blueprint-standard.md`, then `jobs/add_resource.md` |
| write / fix / change the deploy script, or anything under `infra/` | build | `jobs/add_resource.md`, then `references/deploy_discipline.md` |
| wire an outbound URL or per-environment config while building | build | `references/deploy_discipline.md` |

State which file you read in one line before ruling or writing.

**The build arc applies without waiting to be asked.** If the task is "add a DynamoDB table" and nobody
mentioned conventions, the conventions still apply — a resource named outside the rule is a resource
that has to be destroyed to be renamed.

---

## The non-negotiables

These eight hold in every repo, in both arcs, including the ones that predate the rest of this
document. A breach of one of these is a finding; everything else is a suggestion. The build arc adds
nine more that apply while writing — they are in `references/blueprint-standard.md`
§The non-negotiables, and they are not optional either.

**Which code each one binds.** `all code` = a breach is a finding in any repo, however old.
`new only` = existing repos are grandfathered and **never retrofitted** (working rule 2), so a finding
there is noise. Per-resource exemptions are in `references/resource_catalog.md`.

| # | Rule | Applies to |
|---|---|---|
| 1 | Nothing derived is hardcoded | all code |
| 2 | Names composed in exactly one `naming.tf` | **new only** — 1 of 10 repos has it |
| 3 | Every 64-char name asserted at plan time | all code |
| 4 | One authorization gate | all code |
| 5 | Never mint a certificate or keypair | all code — permanent |
| 6 | Epoch milliseconds, `last_updated_time` present | **new only** for existing tables; all code for new ones |
| 7 | A deploy can never lie — the ten gates | all code |
| 8 | Lambdas, and nothing else | **new only** — never re-platform a working service |

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

- **It does not deploy.** No login, no `apply`, no AWS mutation, in either arc. The build arc writes
  the one command the user runs.
- **It does not invent a convention.** Where this document is silent, the answer is "match the
  closest existing repo", and the answer is not a number this skill made up.
- **It does not invent an account id, a state bucket, a profile or a company name.** Those stay as
  `REPLACE_` placeholders until someone supplies them.
- **It does not retrofit or modernize.** Older repos compose names inline and pass `prefix` on the
  terraform CLI. That is the older convention, it works, and it stays until someone asks. Extending a
  repo is additive only.
- **It does not measure.** It has no scripts. Name lengths are arithmetic you do by hand against the
  cap table; anything else you claim, you claim from a file you opened. Proving a cap or a cycle at
  repo scale is `md_policy-code-review` and `md_codegraph`.

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
| a `REPLACE_` placeholder filled with a plausible-looking guess | no — build gate; leave it and name it in the reply |

---

## Checklist before saying done

Both arcs. The build arc has a longer one — `references/blueprint-standard.md` §Quick checklist —
which adds the template-fidelity and placeholder rows.

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

| File | Arc | Answers |
|---|---|---|
| `references/naming.md` | review | how a resource name is composed, the taste rules, the banned name shapes, and the three tiers that derive the service name from the folder |
| `references/naming_length_caps.md` | review | which AWS namespaces cap where, why one prefix is not enough, the measured overflow evidence, and the plan-time assertion pattern |
| `references/resource_catalog.md` | both | every resource kind a service owns — its terraform file, its `naming.tf` local, its cap, when the cap answers, and whether a legacy repo is exempt; plus the two cases that are **not decided** |
| `references/routes_and_urls.md` | review | the route shape and its rules, why the stage belongs to the deployment, the tenant double-check, what survives the proxy hop, `/mcp`, and `urls.{env}.yaml` |
| `references/auth_and_data.md` | review | the one-gate seam and its two OR'd credentials, epoch-ms, the single-table DynamoDB rules, the `Decimal` boundary, and the delete-path rule |
| `references/deploy_and_compute.md` | review | lambdas-only and the Lambda Web Adapter rules, cost defaults, the ten deploy gates in order, the two deploy modes, and terraform comment discipline |
| `references/repo_layout.md` | review | the repository tree, one-file-per-resource, the `api_gateway` module and its three hardening differences, and what a local harness must serve |
| `references/working_rules.md` | review | the nine working rules that come before any code, and how to apply them to a diff |
| `references/ui_theme.md` | review | the CSS-variable palette, type, structural pieces and the one motion rule a new frontend copies |
| `references/fleet_repo_index.md` | review | what a fleet looks like, which role each repo plays, and how far each convention has actually spread |
| `references/blueprint-standard.md` | build | the build gate, the nine build non-negotiables, the build checklist, and the index of the jobs and assets |
| `references/blueprint_naming.md` | build | how a name is composed while writing it, the taste rules, the three 64-character namespaces and their slug variables, the plan-time assertion |
| `references/blueprint_working_rules.md` | build | the eight working rules, the consequence attached to each, and where the ninth lives |
| `references/blueprint_repo_layout.md` | build | the full tree with per-file responsibilities, the rules of thumb, the code-size caps, and the cost defaults |
| `references/deploy_discipline.md` | build | the nine ordered deploy steps, the two deploy modes, the `urls.{env}.yaml` seam, and the four lies a dropped gate tells |
| `jobs/new_service.md` | build | the ordered procedure for a service that does not exist yet, phase 0 through 6, and what to refuse mid-job |
| `jobs/add_resource.md` | build | the surgical path for adding one resource, route or deploy change to a repo that already has conventions |

The five files under `assets/` — `naming.tf.template`, `aws_account_config.sh.template`,
`deploy_utils.sh.template`, `z_setup_deploy.sh.template`, `get_url_utility.py` — are copied into a
repo and then filled in. They live in `assets/` and not in `scripts/` because they call AWS: nothing in
this skill is a measurement tool, and nothing here is meant to be executed from the skill directory.
`references/blueprint-standard.md` §The files says where each one lands.
