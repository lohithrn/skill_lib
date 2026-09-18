# Where every file goes, what every name means, and what already went wrong

## The tree

```
<repo>/
├── project_constants.sh                     # identity, sourced by every script
├── mount_beta.properties                    # VPC/subnet/security-group config for beta
├── mount_prod.properties                    # VPC/subnet/security-group config for prod
├── z_build_and_publish_beta.sh              # deploy beta
├── z_build_and_publish_prod.sh              # deploy prod
├── z_run_local_tests.sh                     # test runner, called by the publish scripts
├── operations/
│   ├── build/
│   │   ├── build_all_indices.sh             # low-level: build only, no AWS
│   │   ├── build_<domain>_for_category.sh   # high-level: build, verify, optional upload
│   │   ├── build_<domain>_for_category.py   # the Python entrypoint the wrapper calls
│   │   ├── download_required_local_models.sh# client 1: pull model weights locally
│   │   └── get_all_features.sh              # client 2: print the manifest (pure read)
│   ├── setup/
│   │   └── ensure_venv.sh
│   ├── login/
│   │   └── aws_sso_login.sh
│   └── eval/
│       └── run_category_eval.sh             # optional: score one category's artifacts
├── infra/
│   ├── utils.sh                             # shared shell functions (auth, buckets, upload)
│   ├── parse_properties.py                  # .properties parser used by resolve_mount_config
│   ├── setup_bucket.py                      # package bucket creation
│   ├── setup_artifact_bucket.py             # artifact bucket creation
│   ├── setup_efs.py                         # mount config resolver
│   ├── setup_distribution_channel_efs.py    # EFS + sync + cross-region replication
│   ├── trigger_efs_sync.py                  # trigger the sync, poll it, validate counts
│   └── write_resource_manifest.py           # the manifest writer — deploy time only
└── src/<package>/
    ├── resource_manifest.json               # baked at deploy time, read by everything
    ├── resource_manifest/                   # the reader/writer module
    │   ├── __init__.py                      # public API: load(), ResourceManifest, VpcRegionConfig
    │   ├── __main__.py                      # CLI: python -m <package>.resource_manifest
    │   ├── schema.py                        # frozen dataclasses
    │   ├── reader.py                        # JSON -> ResourceManifest
    │   ├── writer.py                        # build time only: CLI args -> JSON
    │   └── properties_io.py                 # .properties parsing and formatting
    ├── download_models.py                   # CLI: python -m <package>.download_models
    ├── configuration/
    │   └── artifact_config.py               # ArtifactConfig, carries bedrock_region
    ├── artifacts/
    │   ├── <domain>_artifacts.py            # direct build
    │   ├── s3_artifact_cache_decorator.py   # S3 cache mode
    │   └── efs_mount_decorator.py           # read-only mount mode
    └── tool_calling/
        ├── _tool_call_base.py
        └── <domain>/
            ├── <domain>_tool_call.py
            ├── <domain>_tool_constants.py
            └── <domain>_tool_schemas.py
```

### What lives under `src/`, and what does not

**`src/<package_name>/` is the wheel.** Whatever sits there is what a consumer imports, so it holds
only the shipped library plus the modules the build itself needs (the manifest writer runs at build
time and is part of the package's own contract — that is deliberate, not a leak).

Everything else is a **peer** of `src/`, never a child:

| Tree | Holds |
|---|---|
| `tests/` | every test — unit, integration, contract, QE, load — plus fixtures, stubs and recorded responses |
| `infra/` | the publish scripts, bucket setup, clean-up |
| `scripts/`, `local_development/` | generators, harnesses, experiments |

**A test file under `src/` goes into the wheel.** The consumer installs your fixtures, your recorded
responses — which usually carry a real header — and a test double that is now one import away from
their production code path. It also passes your suite on a broken wheel, because the tests import
from the source tree rather than from what was actually packaged.

### Two spellings of the same module

Libraries built earlier in this pattern name the manifest module and its accessor differently. Both
are the same role; do not treat one as a bug.

| Role | Spelling A | Spelling B |
|---|---|---|
| Baked file | `resource_manifest.json` | `artifact_cache_manifest.json` |
| Reader module | `resource_manifest/` (package) | `configuration/artifact_cache_manifest.py` |
| Loader | `load() -> ResourceManifest` | `ArtifactCacheManifest.load()` |
| Public accessor + CLI | `python -m <package>.resource_manifest` | `exported_artifact/` with `getAllPaths()` |
| Writer | `infra/write_resource_manifest.py` | `infra/write_artifact_cache_manifest.py` |
| Output format | `.properties` lines | one JSON object |

A repo may also keep a legacy top-level printer (`operations/get_artifact_manifest.sh`) that wraps
the module CLI. Keep the wrapper working when you move the module: a consumer pinned to the wrapper
is a consumer you cannot see.

## Naming rules

| Name | Derivation |
|---|---|
| `TENANT_NAME` | lower-case tenant/organisation slug — the only hand-written identity value |
| `PACKAGE_NAME` | the `src/` directory name, i.e. the Python import package, underscores |
| `PROJECT_NAME` | the repo directory name, **lower-cased** |
| `ARTIFACT_CACHE_PREFIX` | defaults to `artifacts`; overridable |
| Package bucket | `{tenant}-{project}-{stage}` |
| Artifact bucket | `{tenant}-{project}-artifacts-{stage}` |
| Mount root | `/mnt/efs/{tenant}-{project}/{artifact-cache-prefix}` |
| Env-var prefix | `<PACKAGE_PREFIX>_ARTIFACT_`, where `<PACKAGE_PREFIX>` is the package name upper-cased with its trailing role segment dropped |
| `AWS_PROFILE` | defaults to `TENANT_NAME` for local runs; overridden by injected credentials in CI |
| `AWS_REGION` | defaults to `us-west-2` — for the SDK's own default only. **Never** for bucket creation |

## Region rules

Three separate things, three separate names. This is the rule most often lost in a refactor because
all three hold a region string.

| Name | What | Set where |
|---|---|---|
| `ARTIFACT_BUCKET_REGION` | Where the S3 artifact bucket lives | `z_build_and_publish_<stage>.sh` |
| `ARTIFACT_ACCESS_REGIONS` | Which regions' compute may reach it (mounts, replication) | `z_build_and_publish_<stage>.sh` |
| `bedrock_region` | Where model calls go | `ArtifactConfig.bedrock_region` |

**Never a bare `region`. Never pass `$AWS_REGION` to bucket creation.**

## The five mistakes already paid for

Each of these shipped, cost time, and was fixed. They are listed with the fix because the fix is
short and the diagnosis was not.

1. **`PROJECT_NAME=$(basename "$PWD")`** produced upper-case bucket names, and S3 rejected them at
   the end of a build. Fix: `$(basename "$PWD" | tr '[:upper:]' '[:lower:]')`.
2. **`create_artifact_bucket "$BUCKET" "$AWS_REGION"`** picked up `us-east-1` from whatever the shell
   happened to hold, so the bucket was created in the wrong region and the mount read nothing. Fix:
   always `$ARTIFACT_BUCKET_REGION`.
3. **`region: str = "us-east-1"` in `ArtifactConfig`** was ambiguous — bucket region or model region?
   Fix: renamed to `bedrock_region`. An ambiguous name is a defect even when its value is right.
4. **`ResourceManifest.region`** had the same ambiguity on the read side. Fix: renamed to
   `artifact_bucket_region` in Python while the JSON key stays `"region"` for compatibility with
   already-published wheels. The asymmetry is deliberate; do not "tidy" the JSON key.
5. **The mount properties file was not validated**, so a deploy with a missing
   `mount_<stage>.properties` completed and baked a manifest with no VPC section. Fix:
   `resolve_mount_config "$FILE" "true"` fails fast.

## Applying this to a new library

In this order. Steps 1–4 are the ones that cannot be reordered.

1. Create `project_constants.sh` with `TENANT_NAME`, and derive `PACKAGE_NAME` and `PROJECT_NAME`.
2. Create `mount_beta.properties` **and** `mount_prod.properties` from the infrastructure repo's
   output. Both, even if they hold the same values today.
3. Copy `infra/utils.sh`, `infra/setup_bucket.py`, `infra/setup_artifact_bucket.py` and
   `infra/parse_properties.py` from a sibling library.
4. Create `z_build_and_publish_beta.sh` and `z_build_and_publish_prod.sh`, each setting
   `ARTIFACT_BUCKET_REGION` and `ARTIFACT_ACCESS_REGIONS`.
5. Create the manifest writer, adapted to your schema.
6. Create the manifest reader module with env-var override support.
7. Create `src/<package>/configuration/artifact_config.py` with a `bedrock_region` field.
8. Create the artifact class plus the three access-mode wrappers.
9. Create `operations/build/build_all_indices.sh` and `build_<domain>_for_category.sh` + `.py`.
10. Create the tool-calling interface: the base class, then one domain subclass.
11. Verify the manifest CLI prints the manifest and nothing else.
12. Verify the build wrapper's `--help` lists every flag its Python entrypoint accepts.

Steps 11 and 12 are the acceptance test for the whole pattern. If either fails, the library is not
yet consumable by clients 2 and 3, whatever else works.
