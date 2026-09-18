# The files the template owns

Create or maintain every one of these. A repo missing one is not "mostly compliant" — each entry is
load-bearing for either the install path or the review path.

| File | What it is for | What breaks without it |
|---|---|---|
| `setup.py` | The distribution definition: package name, version, `src/` layout, extras | No wheel; nothing to publish |
| `.gitignore` | Excludes `build/`, `dist/`, `*.egg-info`, virtualenvs, caches | Build outputs land in review diffs and eventually in the wheel |
| `README.md` | The install URL and the entry points, per stage | Consumers guess the URL, and guess the stage |
| `src/<package_name>/__init__.py` | The import package root, under `src/` | An accidental import of the repo directory instead of the installed package, so tests pass on a broken wheel |
| `tests/__init__.py` | Makes the test tree a package | Test discovery depends on the runner's cwd |
| `tests/<domain>/test_*.py` | One directory per domain | Tests accumulate in one file and stop being run selectively |
| `infra/utils.sh` | Shared shell: auth, bucket creation, upload | Each publish script re-implements auth, and one of them gets it wrong |
| `infra/setup_bucket.py` | Package bucket creation, called by `utils.sh` | Bucket creation drifts per repo — usually the region |
| `infra/z_clean.sh` | Removes build outputs | Step 6 of the workflow has no implementation, so it is skipped |
| `z_run_local_tests.sh` | The single test entry point | The publish scripts and CI run different test commands |
| `operations/login/aws_sso_login.sh` | Local SSO login | Every developer invents their own login, and one of them exports long-lived keys |
| `z_build_and_publish_beta.sh` | Publish to the beta bucket, with a prompt | — |
| `z_build_and_publish_prod.sh` | Publish to the prod bucket, no prompt | — |
| `pipelines/pipelines/azure-pipelines.yml` | The beta-then-prod promotion | Deployments move to laptops, and the promotion of one commit stops being enforced |

Two publish scripts, not one with a stage flag. Keep both names even when their bodies are nearly
identical: the split is what stops a mistyped argument from publishing beta over prod, and it is the
seam that lets prod tighten later without touching beta.

**`src/` ships; `tests/` proves.** `src/<package_name>/` holds only what a consumer imports and what
the build needs — nothing else. Every test (unit, integration, contract, QE, load), every fixture,
every stub and every recorded response lives under `tests/`; `infra/`, `pipelines/` and the `z_`
scripts are peers of `src/`, not children. A test file inside the package goes into the wheel: the
consumer installs your fixtures and a test double one import away from their production path, and
your own suite goes green against the source tree while the packaged wheel is broken.

## Deployment rules

Use the sibling library's deployment helper as the preferred common version — the most mature
`infra/utils.sh` in the family is the source, and new repos take it rather than writing a fourth one.

| Rule | Why |
|---|---|
| `infra/utils.sh` supports **both** a local AWS profile and environment-injected credentials | The same script runs on a laptop with SSO and in CI with injected variables. Two scripts means the CI path is only exercised in CI |
| `create_s3_bucket_if_not_exists` delegates to `infra/setup_bucket.py` | One implementation of bucket creation, in a language that can express a region argument clearly |
| `z_build_and_publish_beta.sh` runs the local tests **before** publishing | A wheel that fails its own tests must never reach a bucket a consumer installs from |
| `z_build_and_publish_beta.sh` allows non-interactive approval by piping `y` into it | CI needs the interactive script, unmodified. A separate non-interactive copy is a second script that will diverge |
| `z_build_and_publish_prod.sh` builds and publishes with no beta prompt | The prod gate is the pipeline's environment approval, not a prompt nobody sees in CI |

## The publish script skeleton

Both stage scripts have the same shape. Only the stage name, the bucket and the prompt differ.

```bash
#!/usr/bin/env bash
set -euo pipefail

source ./project_constants.sh
source ./infra/utils.sh

STAGE="beta"                       # or "prod" in the prod script
BUCKET="$(s3_upload_bucket_name "$STAGE")"

./z_run_local_tests.sh             # step 2: never skipped
setup_aws                          # SSO profile locally, injected credentials in CI
create_s3_bucket_if_not_exists "$BUCKET" "$BUCKET_REGION"
build_package                      # python setup.py sdist bdist_wheel
upload_to_s3 "$BUCKET"
```

`set -euo pipefail` on the first line is not decoration. Without `-e` a failed test or a failed bucket
creation is followed by an upload, and the wheel that lands is the one built before the failure.

A library that also bakes a resource manifest inserts two more steps between the bucket creation and
the build — resolving the mount properties and writing the manifest. That ordering, and why it cannot
be moved, is in arc 2, `references/lifecycle-standard.md`.

## Extras

Declare optional dependency sets in `setup.py` rather than importing everything at module load. The
base install must work with nothing optional present, and a feature whose dependency is missing must
fail with a message naming the extra to install — not with a bare `ModuleNotFoundError` from three
frames deep. Arc 3 (`references/migration-standard.md`) covers what to do when a formerly-bundled dependency
becomes an extra.
