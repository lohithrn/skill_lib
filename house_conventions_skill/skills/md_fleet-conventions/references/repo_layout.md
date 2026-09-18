# Repository layout, and the `api_gateway` module

## The tree

```
<RepoFolderName>/                  # folder name IS the service name
├── z_setup_deploy_beta.sh         # z_ prefix = "the buttons you press"
├── z_setup_deploy_prod.sh
├── z_run_locally*.sh
├── local_<RepoFolderName>.env     # gitignored overrides, never credentials
├── infra/
│   ├── aws_account_config.sh      # account-per-environment + assert_aws_account
│   ├── provider_login.sh
│   ├── deploy_entrypoint.sh       # the shared body behind the z_ scripts
│   ├── deploy_utils.sh
│   ├── build_packages.sh
│   └── terraform/
│       ├── main.tf                # provider, backend "s3" {}, locals (route list, env sets)
│       ├── variables.tf
│       ├── naming.tf              # THE only place names are composed
│       ├── outputs.tf             # MUST output the real public URL(s)
│       ├── <one file per resource>.tf
│       ├── api_gateway/           # module: main.tf + variables.tf + outputs.tf
│       └── lambdas/               # module: main.tf + variables.tf + outputs.tf
├── src/
│   ├── commons/                   # environment, http_responses, dynamo_json, request_authorization
│   ├── deployed_utilities_references/   # the URL resolver + urls.yaml (packaged at deploy)
│   ├── lambda_handlers/           # one file per route
│   └── <feature>/                 # one folder per feature
├── configuration/urls.{beta,prod}.yaml
├── local_development/             # moto-backed harness serving the DEPLOYED modules, not copies
├── test/
├── postman/                       # <ServiceName>.postman_collection.json
└── pipelines/
```

**One terraform file per resource, named after it.** Sub-scope into modules, each with the standard
`main.tf` / `variables.tf` / `outputs.tf` trio. A resource whose file you cannot guess from its name is
a resource nobody finds when it misbehaves.

Two layout variants are both in the fleet and both fine: `src/lambda_handlers/` + `src/<feature>/`, and
the leaner `src/lambda_api_handlers/` + `src/utils/`. Match the repo.

## The local harness serves the deployed modules

A local harness must serve the **deployed** modules rather than copies of them — repoint the one
constant that says *where* the bundle is, so the SPA fallback, the 404 rule, the cache headers and the
traversal check are the real ones and cannot drift.

And make what it **cannot** vouch for visible: authorization is stubbed locally because it needs a real
identity pool, and that belongs in a docstring, not in a surprise. A harness that quietly stubs auth is
a harness that teaches you the unauthenticated path works.

## The `api_gateway` module

Both generations build the REST API from an **OpenAPI `body`** with `put_rest_api_mode = "overwrite"`
and `prevent_destroy`, then read the created resources back with **`data` sources** to attach methods —
so adding a route is one entry in `config`, not a new resource block.

The hardened version's three differences from the original, all of which matter:

| Difference | What breaks without it |
|---|---|
| **`config` carries one entry per (path, method)**, and the path list is `distinct()`ed before the body and the lookup | the original assumed one function per path; two methods on one path reaching different functions makes the `for i in ... : i.path => i.id` comprehension fail on a duplicate key |
| **No CORS, no OPTIONS route** | the browser talks to the frontend lambda, which proxies, so there is no preflight to answer — and an OPTIONS method with `authorization = NONE` is an unauthenticated route for nothing |
| **One `aws_lambda_permission` per (method, path)**, scoped to that exact route | a function reachable by `POST /x` becomes invocable through *any* route of the API |

Also carried over from the original and worth keeping: a **per-stage usage plan with quota and
throttle**, and **per-method throttles keyed `"METHOD /path"`** for routes that must not be able to
spend the stage's whole budget.

## Frontend proxy rules

The proxy adds **no identity of its own** — the caller's bearer token is the whole credential and is
forwarded byte for byte, not re-cased or re-prefixed, because a JWT is signed. The full
forwarded/dropped header table, the three urllib traps and the stage-prefix rule are in
`routes_and_urls.md`; they belong to the route contract, not to the layout.

## Older repos and the `prefix` argument

Older services compose names inline and pass `prefix` on the terraform CLI rather than owning a
`naming.tf`. Some of them pass it as `${PROJECT_NAME}-${environment}` — hyphenated and in the reverse
order. That is the older convention. It works, it is not retrofitted, and it is **not** copied into
anything new: new repos get `naming.tf` and `<environment>_<project_slug>`.
