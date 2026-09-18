---
name: md_library-lifecycle
description: The end-to-end lifecycle of a Python artifact library whose resource manifest is baked into the wheel at deploy time — publish one wheel per stage (beta and prod), read the baked manifest to provision AWS infrastructure, build artifacts and upload them to that stage's S3 cache, then query the mounted artifacts at runtime. Use when creating, deploying, reviewing or debugging a library that ships a baked manifest, or when a stage's bucket, prefix, mount root, mount strategy or region is in question.
when_to_use: A Python library that publishes a wheel to S3 and carries its own artifact/infrastructure metadata inside that wheel.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
---

# library-lifecycle

A router for one library pattern: **the wheel carries its own coordinates.** Where artifacts live,
which bucket, which prefix, which region, which mount root, and what VPC a consumer needs to reach
them are written into `resource_manifest.json` inside `src/<package>/` at build time, and every
consumer afterwards *reads* that file. Nothing downstream discovers infrastructure at run time.

Rule text is in `references/`. The manifest's output contract is in `specs/manifest-contract.md`.

## The gate — read this first

**Touchpoint 1 is the only writer.** The manifest is produced by the publish script, from
`mount_<stage>.properties`, and baked into the wheel. If you find yourself computing a bucket name,
a mount root or a region anywhere else, you have already broken the pattern — the value you are
about to invent is the one the manifest exists to state.

- A consumer that cannot find the manifest must **fail**, not fall back to a default bucket.
  A silent default publishes artifacts into the wrong stage, which is a data leak between beta and
  prod, not an inconvenience.
- Touchpoint 2 makes **no AWS calls at all**. It is a pure read of a file already on disk. Adding a
  `describe`/`list` call there makes provisioning depend on credentials the provisioner does not
  have yet.
- **beta and prod are separate names at every level** — bucket, artifact bucket, properties file,
  publish script. They may point at the same VPC today. Keep both names anyway: the split is the
  seam that lets one stage move without re-plumbing the other.

## The four clients

One wheel, four consumers, four different moments. Each installs a different extra.

| # | Client | What it does | Extra installed | Entry point |
|---|---|---|---|---|
| **1** | Model Downloader | Pulls LLM + embedding model weights to the build machine | `[<domain>-local]` | `python -m <package>.download_models` |
| **2** | Infra Provisioner | Reads the baked manifest to create AWS resources (EFS mount targets, VPC wiring, S3 Mountpoint) | none — base wheel | `python -m <package>.resource_manifest` |
| **3** | Artifact Builder | Generates artifacts from raw documents, uploads them to S3 | `[<domain>-bedrock]` | `./operations/build/build_<domain>_for_category.sh` |
| **4** | Tool Caller | Queries mounted artifacts at run time through the Python API | `[<domain>-bedrock]` | `<Domain>ToolCall.answer(...)` |

The wheel is hosted on a public S3 bucket, so no client needs credentials to install it:

```
https://<tenant>-<project>-<stage>.s3.<region>.amazonaws.com/<package>-<version>-py3-none-any.whl
```

Order of operations is **not** the numbering. Models come down first, artifacts are built next,
infrastructure is provisioned from the manifest third, and queries run last:

```
[1] download models  →  [3] build artifacts  →  [2] provision infra  →  [4] query at runtime
        ↓                       ↓                       ↓                       ↓
  weights on the          artifacts in S3        mounts created from     read-only queries
  build machine           from raw docs          manifest properties     against the mount
```

## Route

| Touchpoint | Question it answers | Read |
|---|---|---|
| **1 — Deploy** | How is the wheel built, what gets baked in, which bucket per stage | `references/deploy-and-publish.md` |
| **2 — Manifest** | What the baked manifest emits, in what format, and what a provisioner may rely on | `specs/manifest-contract.md` |
| **3 — Build** | How artifacts are generated, cached, uploaded, and synced to the mount | `references/build-and-upload.md` |
| **4 — Query** | How a caller loads artifacts and which access mode applies where | `references/runtime-access.md` |
| Any | Where a file goes, what a name means, which mistakes already cost a day | `references/repo-layout.md` |

State which touchpoint you are in before changing anything. A change that spans two touchpoints is
two changes, and the manifest between them is the contract you must not silently move.

---

## Non-negotiables

1. **Three regions, three names.** `ARTIFACT_BUCKET_REGION` (where the artifact bucket lives),
   `ARTIFACT_ACCESS_REGIONS` (which regions' compute may reach it, e.g. `us-west-2,us-east-1`), and
   `bedrock_region` (where model calls go, default `us-east-1`). Never a bare `region`, and never
   pass `$AWS_REGION` to bucket creation — a shell that happens to hold `us-east-1` then creates the
   artifact bucket in the wrong region, and the mount silently reads nothing.
2. **Two buckets per stage, never one.** `{tenant}-{project}-{stage}` holds the wheel;
   `{tenant}-{project}-artifacts-{stage}` holds the built artifacts. Publishing artifacts into the
   package bucket makes the public install URL enumerate your artifact tree.
3. **`{project}` is lower-cased.** S3 rejects uppercase in a bucket name, and the failure arrives at
   the end of a build, after the wheel is already made.
4. **Identity is derived, not retyped.** `PACKAGE_NAME` from the `src/` directory name,
   `PROJECT_NAME` from the repo directory name lower-cased. Only `TENANT_NAME` is written by hand.
   Every hand-typed copy is a name that can drift from the directory it must match.
5. **The mount properties file is validated, and a missing one stops the deploy.** Without the
   fail-fast the publish completes and bakes a manifest with no VPC section, so the provisioner
   creates mount targets in no subnet and touchpoint 4 hangs on a mount that never appears.
6. **Resolution order is env var > manifest JSON > default, and nothing else.** A reader that
   consults AWS, a config service or the current shell's stage adds a fourth source that no
   consumer can see.
7. **The model id at query time must equal the one baked at build time.** They differ ⇒ raise
   `RuntimeError`. Embeddings written by one model and read by another return plausible nonsense,
   which is far worse than an exception.
8. **The artifact directory name encodes kind, model family and parameters.** Two builds with
   different parameters must never land in the same directory, or the second silently serves the
   first's index.

---

## Index

| File | Answers |
|---|---|
| `references/deploy-and-publish.md` | Touchpoint 1: identity, the ordered publish steps, the per-stage buckets, the beta/prod split, the auto-publish flag |
| `specs/manifest-contract.md` | Touchpoint 2: both output formats, the Python API, the env-var override table, what a provisioner may and may not assume |
| `references/build-and-upload.md` | Touchpoint 3: build flags, the cache fingerprint, the overwrite interlock, upload paths, the mount sync |
| `references/runtime-access.md` | Touchpoint 4: loading artifacts, the three access modes, the tool-call surface and its adapter |
| `references/repo-layout.md` | The whole file tree, the naming rules, the five mistakes already paid for, and the checklist for a new library |
| `assets/project_constants.sh` | The identity file, ready to copy — the only file where a name is written by hand |

`assets/project_constants.sh` is a template, not something to run from here: it is sourced by a
library's own publish scripts, which authenticate to AWS.

---

## What this does NOT do

- **It does not document any one library's artifact internals.** Which retrieval strategies exist,
  what a graph build does, how a reranker scores — all of that belongs to the library, not to this
  pattern. This skill stops at the seam.
- **It does not provision anything.** It tells you what the manifest guarantees; the Terraform/CDK
  that consumes those properties lives in the infrastructure repo.
- **It does not choose your stages.** `beta` and `prod` are the two this pattern names. Adding a
  third means adding a properties file and a publish script, not a conditional.
- **It never mints an auth credential.** Installs are anonymous over HTTPS from a public bucket;
  everything else is SigV4 through the AWS SDK. There is no key or certificate to generate.
