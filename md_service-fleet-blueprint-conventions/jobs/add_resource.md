# Job: add a resource, a route, or a deploy change to a service that already exists

This is the surgical path. The repo already has conventions; your job is to add one thing to it without
touching anything else. **Working rule 2 governs the whole job: the smallest change that solves it.**

## Phase 0 — read the repo, not this document

1. **Read the repo's `infra/terraform/naming.tf`** (or, in an older repo, how it composes names inline and
   passes `prefix` on the terraform CLI). **Match what is there.** Where the repo and this document
   disagree, the repo wins for that repo, and the review arc says the same.
2. **Read the closest existing resource file** of the same kind. A new DynamoDB table copies the shape of
   the existing DynamoDB table file, down to the file name pattern.
3. **Do not retrofit.** If the repo has no `naming.tf`, adding one is a sweeping change to a working
   production service. Add your resource in the repo's own style and say, in one line, that the newer
   convention exists and was deliberately not applied.

## Phase 1 — name it

4. **Add exactly one `locals` entry** (or one inline composition, matching the repo) named
   `<prefix>_<resource_role>_<company>`. Read `references/blueprint_naming.md` before choosing the `resource_role`:
   specific, verbose, `snake_case`, includes the type word, no mechanism words, `fallback_*` not
   `default_*`.
5. **If the name lands in IAM, lambda-function or scheduler-group space, check it against 64 by hand and
   then assert it.** IAM answers a too-long name at **apply**, after a clean plan, halfway through the
   deploy. If the repo has no assertion yet, add one for **your** names only — that is additive.

## Phase 2 — wire it

6. **One new terraform file, named after the resource.** Not a block appended to an existing file whose
   subject is something else.
7. **Reference the name as `local.<name>`.** Never re-spell the prefix/suffix expression.
8. **If a lambda needs to know about it, compose that value in `main.tf` locals from the resource itself**
   — the table's own `name`, the pool's own `id`, the secret's own `arn`. Never hand-typed; a hand-typed
   ARN is correct until the resource is replaced. The locals block is usually
   `locals.common_environment_variables`.
9. **If it is a new route**, add one entry to the existing `(path, http_method, function_name)` list and
   let `outputs.tf` generate the endpoint from the same list. Mandatory parameters in the path, optional
   parameters in the query string. Do not add an OPTIONS method: the browser talks to the frontend lambda,
   which proxies, so there is no preflight to answer.
10. **If it calls another service**, add a key to `configuration/urls.{beta,prod}.yaml` and read it with
    `get_url()`. Never a new lambda environment variable per URL — see
    `references/deploy_discipline.md`. If the repo has no `urls.yaml` convention yet, follow the repo and
    say so.
11. **If it is created per tenant at runtime, ship the delete path in the same change**, in its own file
    whose whole subject is that danger. Without it the account accumulates a resource per tenant that ever
    existed, and the discovery is an account limit hit during someone else's deploy.

## Phase 3 — the deploy still cannot lie

12. **If you touched a deploy script, re-walk the nine steps** in `references/deploy_discipline.md`. The
    four that decay are the account assertion, the tests-before-zip ordering, the exit-code propagation,
    and the real printed URL. Removing a `set -e` or a `|| return $?` to quiet an error is the failure
    mode this job exists to prevent.
13. **Do not add a required environment variable** that a human has to set before running the script
    (rule 5). Give it a `:-` default, or derive it.

## Phase 4 — the diff

14. **Read your own diff and account for every line.** Every removed line that was not requested gets
    called out explicitly (rule 1). No reformatting, no renaming, no "while I was in there" (rule 2).
15. **State the cost delta** if the change creates anything billed (rule 7).
16. **Say what you verified versus what you inferred**, in the sentence, not in a footnote (rule 3).
17. **Add the test.** A new resource whose name lands in a capped namespace gets a length assertion; a new
    route gets a handler test; a new outbound URL gets a `get_url` key test.

## Refusals inside this job

- **No retrofitting an older repo to a newer convention** unless asked.
- **No account id, service name, prefix or outbound URL hardcoded "just for this one".**
- **No second place that decides authorization.** The handler's first statement is the one existing auth
  call; adding a condition of your own breaks the property that commenting out one function disables auth
  everywhere.
- **No ISO timestamps in a new table.** Epoch milliseconds, and `last_updated_time` present.
- **No truncating a name to fit a cap.** Shorten the slug variable, or raise at runtime.
