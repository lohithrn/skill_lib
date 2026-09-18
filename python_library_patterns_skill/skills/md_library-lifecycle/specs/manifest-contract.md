# Touchpoint 2 — the baked manifest: the contract between the library and its infrastructure

The output contract for the Infra Provisioner (client 2). This is the whole interface: a provisioner
that needs a fact not listed here needs a manifest change, not a lookup.

## Invocation

```
python -m <package>.resource_manifest
./operations/build/get_all_features.sh
```

**Pure read. No AWS calls, no credentials, no network.** The file being printed is already inside the
installed wheel. Anything that would require a `describe` or a `list` call belongs in touchpoint 1,
at bake time, where credentials exist.

Exit non-zero when the manifest is absent or unparseable. Never print a default.

## Output format A — properties

Three blocks, in this order. The order is part of the contract: consumers `grep` this.

```properties
artifact.stage=beta
artifact.bucket=<tenant>-<project>-artifacts-beta
artifact.bucket.region=us-west-2
artifact.prefix=artifacts
artifact.s3.uri=s3://<tenant>-<project>-artifacts-beta/artifacts
artifact.s3.endpoint=https://<tenant>-<project>-artifacts-beta.s3.us-west-2.amazonaws.com/artifacts

<PACKAGE_PREFIX>_ARTIFACT_BUCKET=<tenant>-<project>-artifacts-beta
<PACKAGE_PREFIX>_ARTIFACT_REGION=us-west-2
<PACKAGE_PREFIX>_ARTIFACT_MOUNT_ROOT=/mnt/efs/<tenant>-<project>/artifacts

aws.us-west-2.role=primary
aws.us-west-2.vpc.id=vpc-<id>
aws.us-west-2.security.group.id=sg-<id>
aws.us-west-2.private.subnet.ids=subnet-<id>,subnet-<id>
aws.us-east-1.role=secondary
aws.us-east-1.vpc.id=vpc-<id>
```

| Block | Purpose |
|---|---|
| `artifact.*` | Where the artifacts are. Read by anything that resolves a path or a URI |
| `<PACKAGE_PREFIX>_ARTIFACT_*` | The same facts, shaped as shell exports, so a consumer can `eval` them |
| `aws.<region>.*` | One block per region in `ARTIFACT_ACCESS_REGIONS`, each tagged `primary` or `secondary` |

Exactly one region carries `role=primary` — the one holding the bucket. Every other access region is
`secondary`. A provisioner that treats two regions as primary creates two writable mounts and the two
diverge silently.

## Output format B — one JSON object

The earlier spelling of the same contract. Same facts, plus the two path templates.

```json
{
  "stage": "beta",
  "bucket": "<tenant>-<project>-artifacts-beta",
  "prefix": "artifacts",
  "region": "us-west-2",
  "s3_uri": "s3://<tenant>-<project>-artifacts-beta/artifacts",
  "s3_category_uri_template": "s3://<tenant>-<project>-artifacts-beta/artifacts/{category}",
  "mount_root": "/mnt/efs/<tenant>-<project>/artifacts",
  "mount_category_path_template": "/mnt/efs/<tenant>-<project>/artifacts/{category}",
  "mount_strategy": "efs-native",
  "environment_variables": {
    "<PACKAGE_PREFIX>_ARTIFACT_STAGE": "beta",
    "<PACKAGE_PREFIX>_ARTIFACT_BUCKET": "<tenant>-<project>-artifacts-beta",
    "<PACKAGE_PREFIX>_ARTIFACT_PREFIX": "artifacts",
    "<PACKAGE_PREFIX>_ARTIFACT_REGION": "us-west-2",
    "<PACKAGE_PREFIX>_ARTIFACT_MOUNT_ROOT": "/mnt/efs/<tenant>-<project>/artifacts",
    "<PACKAGE_PREFIX>_ARTIFACT_MOUNT_STRATEGY": "efs-native"
  },
  "artifact_layout": "{category}/{artifact-directory}"
}
```

`artifact_layout` is the one field that tells a consumer how to compose a path *without* knowing the
library's domain. Ship it. Both templates are derivable from `bucket`/`prefix`/`mount_root`, and they
are emitted anyway so that no consumer re-implements the join and gets the slash wrong.

Pick one format per library and keep it. Emitting both doubles the number of places a new field has
to be added, and the field will be added to one of them.

## Python API

```python
from <package>.resource_manifest import load, ResourceManifest

manifest: ResourceManifest = load()
manifest.stage                    # "beta"
manifest.bucket                   # "<tenant>-<project>-artifacts-beta"
manifest.prefix                   # "artifacts"
manifest.artifact_bucket_region   # "us-west-2"   <- not `region`; see the naming rules
manifest.s3_uri                   # "s3://<tenant>-<project>-artifacts-beta/artifacts"
manifest.mount_root               # "/mnt/efs/<tenant>-<project>/artifacts"
manifest.mount_strategy           # "s3-mountpoint" | "efs-native"
manifest.vpc_regions              # [VpcRegionConfig(region="us-west-2", role="primary", ...)]
```

The earlier spelling, for libraries on format B:

```python
from <package>.configuration.artifact_cache_manifest import ArtifactCacheManifest
from <package>.exported_artifact import getAllPaths

manifest = ArtifactCacheManifest.load()   # same fields, `region` instead of artifact_bucket_region
paths = getAllPaths()                     # the whole object as a dict, templates included
```

Every dataclass here is **frozen**. A consumer that could mutate the manifest could give two callers
in one process two different answers about where production artifacts live.

## Env-var overrides

The reader accepts overrides at the highest priority. Nine keys, no others:

| Env var | Overrides |
|---|---|
| `<PACKAGE_PREFIX>_ARTIFACT_STAGE` | `stage` |
| `<PACKAGE_PREFIX>_ARTIFACT_BUCKET` | `bucket` |
| `<PACKAGE_PREFIX>_ARTIFACT_PREFIX` | `prefix` |
| `<PACKAGE_PREFIX>_ARTIFACT_REGION` | `artifact_bucket_region` (`region` on format B) |
| `<PACKAGE_PREFIX>_ARTIFACT_MOUNT_ROOT` | `mount_root` |
| `<PACKAGE_PREFIX>_ARTIFACT_MOUNT_STRATEGY` | `mount_strategy` |
| `<PACKAGE_PREFIX>_ARTIFACT_MOUNT_BUCKET` | `mount_bucket` |
| `<PACKAGE_PREFIX>_ARTIFACT_EFS_FILE_SYSTEM_ID` | `efs_file_system_id` |
| `<PACKAGE_PREFIX>_ARTIFACT_EFS_ACCESS_POINT_ID` | `efs_access_point_id` |

**Resolution order: env var > manifest JSON > default.** Three sources, that order, nothing else.

The overrides exist for one job — pointing a local run or a test at a scratch bucket without
rebuilding the wheel. They are not a deployment mechanism. A production task definition that sets
five of these has moved the manifest into the task definition, where nothing validates it and the
wheel's own copy is now a decoy.

## How external systems consume it

```bash
eval "$(python -m <package>.resource_manifest)"
# then use $<PACKAGE_PREFIX>_ARTIFACT_BUCKET, ..._MOUNT_ROOT, ... in Terraform, CDK or a task definition
```

On format B, project the JSON's `environment_variables` object into exports first, then `eval` that.

## What a provisioner may and may not assume

**May assume:**

- The bucket named exists in the region named — touchpoint 1 created it before baking.
- Every region in the `aws.*` blocks is one the deploy declared in `ARTIFACT_ACCESS_REGIONS`.
- `artifact_layout` describes the on-mount layout as well as the S3 layout. One layout, two roots.
- The stage in the manifest is the stage of the wheel it came from — a beta wheel cannot report prod.

**May not assume:**

- That any artifact exists yet. The manifest describes coordinates, not contents. Provisioning runs
  before or after the build; the pattern does not order them.
- That the mount exists. Creating it is the provisioner's job — that is why it is reading this.
- That a second read returns the same values as the first *if the wheel was upgraded in between*.
  Pin the wheel version alongside the infrastructure that was provisioned from it.
