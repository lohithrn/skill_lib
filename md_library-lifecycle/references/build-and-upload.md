# Touchpoint 3 — Build artifacts, cache them, upload them, sync them to the mount

Builds artifacts locally from raw documents and optionally uploads them to the stage's artifact
bucket. The bucket, prefix and region are **read from the baked manifest**, never passed in.

## Two script layers

| Layer | Script | Scope |
|---|---|---|
| Low-level | `build_all_indices.sh` | Builds indices into an output folder. No AWS, no upload, no verification |
| High-level | `build_<domain>_for_category.sh` (a.k.a. `build_and_verify_category.sh`) | Reads the manifest, calls the low-level build, verifies, optionally uploads, optionally syncs |
| Python entry | `build_<domain>_for_category.py` | What the shell wrapper actually invokes; holds the argument contract |

Keep the layers split. The low-level script is the one a developer runs fifty times a day on a
laptop with no credentials; folding the upload into it means every local build needs AWS.

## Command

```bash
./operations/build/build_<domain>_for_category.sh \
    --input-dir=/path/to/raw/documents \
    --output-folder=.generated \
    --category=<category> \
    --model-id=<bedrock-model-id> \
    --upload=true
```

## Flags

| Flag | Required | Default | What it does |
|---|---|---|---|
| `--input-dir=<path>` | yes | | Parent of the `<category>/` subdirectories holding raw documents |
| `--output-folder=<path>` | yes | | Where generated artifacts land |
| `--category=<name>` | yes, repeatable | | One category — a subdirectory of the input dir |
| `--categories=<a,b,c>` | alternative | | Comma-separated form of the same thing |
| `--model-id=<id>` | yes | | The model used for extraction, Bedrock or local |
| `--runtime-mode=<bedrock\|local>` | no | `bedrock` | Which runtime performs the extraction |
| `--embedding-model-id=<id>` | no | from runtime | Override the embedding model |
| `--bedrock-region=<region>` | no | `us-east-1` | Where model calls go. **Not** the bucket region |
| `--max-chunks=<n>` | no | no cap | Cap the chunks fed into the build. A cap that truncates silently is a wrong artifact, so log the cap and the input size whenever it bites |
| `--include-<kind>=true\|false` | no | interactive prompt | One flag per artifact kind the library can build. Absent ⇒ prompt, so an unattended run must pass every one it wants |
| `--upload=true\|false` | no | interactive prompt | Upload after a successful build |
| `--clean=true\|false` | no | `false` | `rm -rf` the output folder before building |
| `--force-rebuild=true\|false` (a.k.a. `--ignore-cache`) | no | `false` | Rebuild even when the cache fingerprint matches |
| `--confirm-overwrite-s3=true\|false` | no | `false` | **Required** alongside the rebuild flag when artifacts already exist in S3 |

The last two are one interlock, and it is the most important flag pair here: a forced rebuild plus
an unguarded upload overwrites artifacts that a running production mount is reading. Requiring a
second, differently-named flag means the destructive path cannot be reached by adding one plausible
argument.

## The cache fingerprint

Every artifact directory carries a `metadata.json` recording how it was built:

| Field | Purpose |
|---|---|
| `source_hash` | Hash of the raw input documents |
| `config_hash` | Hash of the build configuration |
| `model_id` | The model used for extraction |
| `status` | Whether the build completed |

A build whose three hashes match an existing artifact is skipped. That is what makes the rebuild
flag necessary and what makes it dangerous: the fingerprint is the only thing standing between a
cheap no-op and a full re-extraction bill.

## What it produces

Artifacts land at:

```
<output-folder>/<category>/<artifact-directory>/
```

The artifact directory name encodes **kind, model family, and parameters**, in that order — for
example a dense-vector index built with one embedding model and one index structure, or a graph
built by one runtime mode. Two builds that differ in any parameter must produce two directory names.
Collapsing the parameters out of the name is how a hybrid index built with one fusion weight gets
silently served for a query expecting another.

## Upload destination

```
s3://<artifact-bucket>/<prefix>/<category>/<artifact-directory>/
```

`<artifact-bucket>` and `<prefix>` come from `resource_manifest.json`, baked in touchpoint 1. The
upload region is the manifest's bucket region — not `$AWS_REGION`, and not `--bedrock-region`.

The layout is `{category}/{artifact-directory}`, and it is the same on S3 and on the mount. One
layout, two roots: that is what lets touchpoint 4 build a path from
`mount_root + category + artifact-directory` without asking anything.

## Sync to the mount

With `--upload=true` and the `efs-native` mount strategy, the upload is followed automatically by a
sync step, in this order:

1. Trigger the transfer from S3 to the EFS filesystem in the bucket's own region.
2. Poll until it reports success, and **fail the build** if it does not. A build that reports success
   while the mount still holds the previous artifacts is the worst outcome available here.
3. Validate that the file count on the mount matches the file count in S3.
4. Check replication to every other region in `ARTIFACT_ACCESS_REGIONS` — status and size.

The same sync is runnable by hand against a bucket and prefix, with an optional profile argument,
for the case where an upload succeeded and the sync did not. Keep that entry point: without it the
only recovery is a full rebuild.

With `s3-mountpoint` there is no sync step — the mount reads the bucket directly, so step 1 is the
upload itself and steps 2–4 do not exist. Do not add a fake sync to make the two strategies look
alike.

## Verify

```
./operations/build/build_<domain>_for_category.sh --help
```

If `--help` does not list every flag in the table above, the shell wrapper and the Python entrypoint
have drifted, and the flag that is missing from the help is the one CI is silently not passing.
