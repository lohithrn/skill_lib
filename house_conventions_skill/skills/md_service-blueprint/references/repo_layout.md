# Repo layout and per-file responsibilities

The folder name **is** the service name (`project_name`). Everything derives from it.

```
<RepoFolderName>/
├── z_setup_deploy_beta.sh        # self-contained: login → assert account → test → apply → print URL
├── z_setup_deploy_prod.sh        # same, prod
├── z_deploy_<env>_from_local.sh  # optional from-local variant
├── z_run_locally*.sh             # run the service locally
├── z_setup_run_functional_tests.sh  # sets a COMPLETE PYTHONPATH itself, runs the suite
├── local_<RepoFolderName>.env    # gitignored overrides, never credentials
│
├── infra/
│   ├── aws_account_config.sh     # SINGLE SOURCE OF TRUTH for account id per environment
│   ├── provider_login.sh         # login_with_assume_role + sources aws_account_config.sh
│   ├── deploy_utils.sh           # init vars, create_tfvars, run_terraform, deploy, print_public_url
│   ├── <concern>_config.sh       # per-concern config builders sourced by the deploy scripts
│   └── terraform/
│       ├── main.tf               # provider{} + backend "s3" {} + locals.common_environment_variables
│       ├── variables.tf          # project_name, environment, prefix, company_name, aws_region, aws_profile…
│       ├── naming.tf             # THE naming locals — one entry per resource
│       ├── outputs.tf            # MUST expose `public_url` (the deploy script prints it)
│       ├── dynamodb_<name>.tf    # one file per resource, named for the resource
│       ├── cognito_<name>.tf
│       ├── sns_<name>.tf
│       ├── secret_manager_<name>.tf
│       ├── waf_api_gateway.tf
│       └── <module>/             # lambdas/, api_gateway/, custom_domain/, monitoring/
│           ├── main.tf           #   each module: the standard main/variables/outputs trio
│           ├── variables.tf
│           └── outputs.tf
│
├── src/
│   ├── commons/                  # shared: utils/, access_control, factories, base classes
│   ├── deployed_utilities_references/
│   │   ├── get_url_utility.py    # get_url(key) resolver
│   │   └── urls.yaml             # copied here at deploy from configuration/urls.<env>.yaml
│   ├── handlers/  (or lambda_handlers/)  # thin entrypoints; logic lives in feature packages
│   └── <feature>/                # one package per feature/handler group, snake_case
│
├── configuration/
│   ├── urls.beta.yaml            # key → outbound URL, beta
│   └── urls.prod.yaml            # key → outbound URL, prod
│
├── test/                         # mirrors src/; unit tests gate the deploy
├── local_development/            # a harness serving the DEPLOYED modules, not copies of them
├── postman/                      # <ServiceName>.postman_collection.json
├── pipelines/                    # CI pipeline definitions (a new CI is a new endpoint, not a rewrite)
├── requirements_beta.txt
├── requirements_prod.txt
└── README.md
```

## Rules of thumb

- **One terraform file per resource.** The file name matches the resource
  (`dynamodb_private_configuration.tf` holds the `private_configuration` table). A resource whose file
  you cannot guess from its name is a resource nobody finds when it misbehaves.
- **Compose the lambda environment in `main.tf` locals**, from the terraform resources — never hand-type
  table names, pool ids or secret ARNs into an environment block. A hand-typed ARN is correct until the
  resource is replaced.
- **`z_` prefix** on the scripts a human runs, so they sort together and read as "the buttons you press".
- **Sub-scope with terraform modules** (`lambdas/`, `api_gateway/`), each with the standard
  `main.tf` / `variables.tf` / `outputs.tf` trio.
- **`commons/` is shared code.** A prompt template or a feature-specific file does not belong in a service
  whose job is orchestration — keep responsibilities where they belong.
- **New integrations are additive.** A new CI provider, messaging channel or model becomes a **new**
  endpoint, module or config entry, not a rewrite of the existing one. That is working rule 1 expressed as
  a layout rule.
- **A local harness serves the deployed modules**, not copies of them: repoint the one constant that says
  where the bundle is, so the SPA fallback, the 404 rule and the cache headers are the real ones. State
  in a docstring what the harness **cannot** vouch for — authorization is stubbed locally, and a harness
  that stubs auth silently teaches you the unauthenticated path works.
- **`src/` is the running system and nothing else.** Only what executes in the deployed lambda and what
  the deploy itself needs: handlers, feature packages, `commons/`, the config the deploy copies in.
  Everything that does not run in production is a **peer** of `src/`, never a child — `test/` for every
  test (unit, integration, QE, contract, load) plus its fixtures and recorded responses,
  `local_development/` for the harness, `z_` scripts for the buttons, `postman/` for the collection.
  A non-runtime file under `src/` gets zipped into the artifact, so a test double sits one import away
  from a production code path and a recorded response carrying a real header ships to beta. It also
  hides dead code: a module imported only by the test beside it looks live to every tool you own.

## Code size limits (standing, all repos)

Every file **< 250** lines. Every method **< 25** lines. No nesting **> 2** levels. Verbose, descriptive
names in both `src/` and terraform. There should be a **test** enforcing the file cap — a cap nothing
measures has already been exceeded somewhere.

In any `.tf` file, **comment lines must never outnumber code lines.** Comments carry the reasoning — why a
knob exists, what breaks without it, what was tried and rejected — so summarize rather than delete. A file
that is two-thirds prose stops being read as configuration.

## Cost defaults — pick the cheap thing unless told otherwise

- DynamoDB (`PAY_PER_REQUEST`) over Aurora/RDS.
- Lambda over always-on compute. A web frontend is one lambda behind the Lambda Web Adapter layer, with
  the layer version **pinned** and `AWS_LWA_READINESS_CHECK_PATH` pointing at a **real** health path —
  the adapter's default `/` is the SPA fallback and answers 200 with index.html even when the bundle is
  broken, so a broken deploy reports itself ready.
- A function URL or API Gateway over standing up extra networking.
- **No NAT gateway, no always-on cluster, no Aurora** without an explicit approval and a stated monthly
  cost.
