# Touchpoint 1 — Deploy: build the wheel with the manifest inside it

The publish script is the only writer of `resource_manifest.json`. Everything downstream reads it.

## One script per stage

```
z_build_and_publish_beta.sh    # stage = beta
z_build_and_publish_prod.sh    # stage = prod
```

Two scripts, not one script with a `--stage` flag. The reason is blast radius: a stage argument is
one typo away from publishing a beta build over prod, and the two files also legitimately diverge —
prod skips the beta prompt, beta may point at a smaller VPC. Keep both names even when their bodies
are identical today; that is the seam that lets prod tighten without touching beta.

## The ordered steps

Order is load-bearing. Each step depends on the one above it.

| # | Step | Why it is here and not later |
|---|---|---|
| **1** | Source `project_constants.sh` for identity (`TENANT_NAME`, `PROJECT_NAME`, `PACKAGE_NAME`) | Every name below is derived from these; nothing may be typed twice |
| **2** | Run the local test suite | A wheel that fails its own tests must not reach a bucket a consumer installs from |
| **3** | `setup_aws` — authenticate by SSO profile or injected environment credentials | Steps 4 and 7 need it; failing here costs nothing |
| **4** | `create_artifact_bucket_if_not_exists` in `ARTIFACT_BUCKET_REGION` | The manifest is about to name this bucket; naming a bucket that does not exist bakes a lie |
| **5** | `resolve_mount_config "mount_<stage>.properties" "true"` | The `"true"` is *required*: it makes a missing or unreadable properties file **fail the deploy**. Without it the manifest is baked with no VPC section and the provisioner creates mount targets in no subnet |
| **6** | Write `src/<package>/resource_manifest.json` | Must precede the build, or the wheel ships without it |
| **7** | `python setup.py sdist bdist_wheel` | The manifest is now *inside* the wheel |
| **8** | Upload the wheel to the package bucket | Last, so no consumer can install a wheel whose manifest is stale |

The whole of the AWS-touching part of this sequence belongs in the library's own
`infra/utils.sh` + publish scripts. This skill ships only the identity template,
`assets/project_constants.sh`.

## Identity vs deployment decisions

Two different lifetimes, so two different files.

**`project_constants.sh` — identity only.** Changes when the library is renamed, which is almost
never. See `assets/project_constants.sh` for the copyable version.

**`z_build_and_publish_<stage>.sh` — deployment decisions.** Changes when the topology changes.

```bash
export ARTIFACT_BUCKET_REGION="us-west-2"              # where the S3 artifact bucket lives
export ARTIFACT_ACCESS_REGIONS="us-west-2,us-east-1"   # regions whose compute may reach it
export MOUNT_PROPERTIES_FILE="mount_beta.properties"   # VPC config for THIS stage
```

Putting `ARTIFACT_BUCKET_REGION` in `project_constants.sh` is the mistake to avoid: it reads as
identity, so nobody thinks to change it per stage, and both stages end up in one region.

## Derived, not retyped

```bash
export PACKAGE_NAME="$(ls src/ 2>/dev/null | head -1)"
export PROJECT_NAME="$(basename "$PWD" | tr '[:upper:]' '[:lower:]')"
```

`PACKAGE_NAME` comes from the `src/` directory name — a package renamed on disk cannot drift from
the constant. `PROJECT_NAME` comes from the repo directory name, **lower-cased**, because S3 rejects
uppercase in a bucket name and the rejection arrives after the wheel is already built. Only
`TENANT_NAME` is hand-written.

## Two S3 buckets per stage

| Purpose | Pattern | beta | prod |
|---|---|---|---|
| Package (the wheel) | `{tenant}-{project}-{stage}` | `<tenant>-<project>-beta` | `<tenant>-<project>-prod` |
| Artifact cache | `{tenant}-{project}-artifacts-{stage}` | `<tenant>-<project>-artifacts-beta` | `<tenant>-<project>-artifacts-prod` |

Four buckets across the two stages. The package bucket is public-readable so the install URL needs
no credentials; the artifact cache is not. Merging the two makes the artifact tree enumerable by
anyone who can install the library.

The mount root is derived from the same identity, and is **not** stage-scoped in the path — the
stage is already in the bucket name:

```
/mnt/efs/<tenant>-<project>/<artifact-cache-prefix>
```

## Auto-publish

```bash
./z_build_and_publish_beta.sh                  # interactive: prompts before publishing
./z_build_and_publish_beta.sh --auto-publish   # skip the prompt (CI)
```

`z_build_and_publish_prod.sh` builds and publishes without the beta prompt by design. The gate for
prod is the pipeline's environment approval, not a shell prompt nobody sees in CI. The pipeline
deploys beta first, records the deployed commit SHA, and then deploys **that same SHA** to prod
after approval — see arc 1, `references/naming-and-pipeline.md`, for the pipeline contract.

## Mount strategy

`MOUNT_STRATEGY` selects how consumers reach the artifacts, and the manifest carries the answer so
consumers do not guess:

| Value | What the consumer mounts | Notes |
|---|---|---|
| `efs-native` | An EFS filesystem with an access point | Needs mount targets in every subnet of every access region; supports cross-region replication |
| `s3-mountpoint` | The artifact bucket through S3 Mountpoint | No EFS to provision; read latency is per-object |

Default it in `project_constants.sh` (`MOUNT_STRATEGY="${MOUNT_STRATEGY:-s3-mountpoint}"`) and let a
stage override it. Both values are real and in use; do not delete the branch you are not using
today.

## The version number is a promise about the API

`major.minor.patch` in `setup.py`, and the rule belongs to the consumer, not the author: **a change
that breaks an import somebody has already written is a major bump, however small the diff.**

| Change | Bump |
|---|---|
| A symbol moves between modules | **major** — the old import path is gone |
| An `__init__.py` export list narrows | **major** — a re-export a consumer used has gone |
| A required argument is added, or a default changes meaning | **major** |
| A new module, function, or optional argument | minor |
| A fix behind an unchanged signature | patch |

- **A major bump and a migration map ship together.** The map exists *because* the major bump
  happened; publishing the bump without it ships a break with no instructions, and publishing the map
  without the bump tells consumers to change code that still works. `jobs/write-the-map.md`.
- **Never re-publish a version that already exists on the index or in the bucket.** A consumer who
  pinned it gets different code under the same number, and no lockfile catches that — it is the same
  failure as a stale baked manifest below, arriving through the version string instead.
- Beta publishes carry a pre-release suffix (`1.4.0b3`), never a reused release number. A beta that
  shares a number with a release makes "which code is in the mount?" unanswerable.
- The commit that bumps the version says so: `chore(release): 2.0.0`, with the breaking changes in the
  body. That commit is what a consumer bisects to when an import disappears.

## Verifying a deploy

Run all three. The first two are pure reads and cost nothing:

```
python -m <package>.resource_manifest
./operations/build/get_all_features.sh
```

Then confirm the manifest inside the built wheel matches the one on disk. A wheel whose baked
manifest predates the last `mount_<stage>.properties` edit is the single most expensive failure in
this pattern, because every consumer of that version is wrong in the same invisible way.
