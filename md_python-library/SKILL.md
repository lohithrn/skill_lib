---
name: md_python-library
description: The whole life of an in-house Python library published as a wheel to S3 — scaffold or audit the repository against the shared packaging pattern (setup.py, src/ layout, the unittest hook, the beta and prod publish scripts, the CI pipeline that promotes one commit from beta to prod), run the artifact lifecycle for a library whose resource manifest is baked into the wheel at deploy time (publish per stage, read the baked manifest to provision AWS, build and upload artifacts, query the mount at runtime), and migrate consumers when the public import surface is refactored (write the old-to-new map from measurement, migrate a consumer in order, prove no leftover import remains). Use when creating, reviewing, deploying, debugging or renaming the surface of an internal Python library.
when_to_use: Any repo that is an in-house Python library published as a wheel to S3 — creating it, changing it, reviewing someone else's change to it, deploying its artifacts, or renaming its public import paths.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
---

# python-library

A router over one repository kind — **an in-house Python library published as a wheel to S3** — and the
three arcs of its life. No rule text lives here. Each arc has one standard file that owns its gate, its
non-negotiables and its own index; read the one arc you are in.

## Route — pick the arc first

| Arc | You are | Read |
|---|---|---|
| **1 — scaffold** | Creating a new library, adding a missing template piece, or reviewing a change for drift from the pattern | `references/scaffold-standard.md` |
| **2 — lifecycle** | Publishing per stage, baking or reading the resource manifest, building and uploading artifacts, querying the mount | `references/lifecycle-standard.md` |
| **3 — migration** | Renaming the public import surface, writing the old-to-new map, migrating a consumer repo | `references/migration-standard.md` |

**Arc 1 is the floor; arc 2 is a superset of it.** Every library obeys arc 1. A library that also ships
artifacts and bakes a manifest into its wheel obeys arc 2 on top — arc 2 assumes everything in arc 1
plus a `resource_manifest.json` inside `src/<package>/`. A library can follow arc 1 perfectly and
publish no artifacts at all. Arc 3 fires only when a **public import path** changes and other repos
import it.

State which arc you are in before changing anything. A change that spans two arcs is two changes, and
the wheel between them is the contract you must not silently move.

---

## The gate — read this first

One rule per arc, and each is the one that has been broken before:

- **Arc 1 — copy structure, never source.** The template is the packaging, the publish path and the
  pipeline. Business logic, tests, demos, IAM provisioning, editor settings and build artifacts from a
  sibling library are **not** part of it, and a copied module is the fastest way to give two libraries
  one bug. Adapt **names only**.
- **Arc 2 — touchpoint 1 is the only writer.** Where artifacts live — bucket, prefix, region, mount
  root, VPC — is written into the manifest at build time and *read* everywhere afterwards. Computing a
  bucket name anywhere else has already broken the pattern. A consumer that cannot find the manifest
  must **fail**, never fall back to a default bucket: a silent default publishes into the wrong stage,
  which is a data leak between beta and prod, not an inconvenience.
- **Arc 3 — no consumer is touched before the map is complete.** Complete means every row has a
  right-hand side: a new import, a method call, an instruction, or `REMOVED` with a reason — never
  blank, never "TBD". A half-written map turns each consumer's migration into a guess, and the
  divergence outlives the refactor.

Each arc's standard file carries the rest of its gate. Read it there rather than reasoning from this
summary.

---

## Cross-cutting non-negotiables

These hold in all three arcs. The arc-specific rules — eight for scaffold, eight for lifecycle, seven
for migration — are in the three standard files, and they are not optional either.

1. **beta and prod are separate names at every level** — bucket, artifact bucket, properties file,
   publish script, pipeline stage. They may point at the same VPC or the same target today. **Keep both
   names anyway**: the split is the seam that lets one stage move without re-plumbing the other, and
   collapsing it is not a simplification.
2. **Identity is derived, not retyped.** `PACKAGE_NAME` from the `src/` directory name, `PROJECT_NAME`
   from the repo directory name lower-cased, buckets from
   `{tenant_name}-{project_name_lower}-{stage_lower}`. Only `TENANT_NAME` is written by hand. Every
   hand-typed copy is a name that can drift from the directory it must match.
3. **Prove it, do not assert it.** A packaging change that was never built does not work; a migration
   whose leftover imports were never scanned is not done. Run the command, then say what it returned —
   `references/scaffold-standard.md` §Validation and §Verification below.
4. **No AI, editor or harness-specific metadata** in a library repo, and no lock file for one vendor.
   A rulebook readable by one tool is enforceable by one tool.
5. **Nothing here mints an auth credential.** Installs are anonymous over HTTPS from a public bucket;
   the publish path uses an SSO profile locally and injected CI credentials in the pipeline; everything
   else is SigV4 through the AWS SDK. There is no key or certificate for a library to generate.

---

## Validation and verification — the two commands that decide "done"

**Arc 1 — after any packaging, infra or pipeline change**, all four, in this order:

```
./z_run_local_tests.sh
python3 -m py_compile infra/setup_bucket.py
python3 setup.py sdist bdist_wheel
./infra/z_clean.sh
```

Tests before build, because a failing test makes the build irrelevant; the clean last, because it
deletes what the build produced. If the system `python3` lacks `setuptools`/`wheel`, use a runtime that
has them and **say so in the handoff** — and do not add a dependency-installation step to make it pass,
because this validation must run on a machine with no network.

**Arc 3 — before a migration is called done:**

```
bash scripts/leftover_imports.sh --root <consumer-repo> --prefix <old.module.path> --text
```

Repeat `--prefix` for every old top-level path in the map; `violations` must reach **0**. The same
command with **no** `--prefix` inventories every module the tree imports, which is how you find the old
paths in the first place. The scan is **lexical**: it cannot see a module named only at run time
(`importlib`, a string in a config, a plugin registry), and it says so in `degraded` on every run. Treat
a clean run as "no static import remains", never as "nothing references it".

---

## Index

| File | Answers |
|---|---|
| `references/scaffold-standard.md` | **Arc 1**: the gate, the six-step workflow, the eight non-negotiables, the validation order, and the index of the three scaffold reference files |
| `references/lifecycle-standard.md` | **Arc 2**: the four clients and the real order of operations, the four touchpoints, the eight non-negotiables, and the index of the four lifecycle reference files |
| `references/migration-standard.md` | **Arc 3**: the gate, the seven non-negotiables, the verification contract, and the index of its jobs and references |
| `references/common-files.md` | Arc 1: every file the template owns, what it must do, the rules for `infra/utils.sh` and the two publish scripts |
| `references/naming-and-pipeline.md` | Arc 1: how every name is derived, the per-stage buckets, the CI variable group and secret pair, the beta-then-prod promotion contract |
| `references/review-guardrails.md` | Arc 1: what to flag in review, and the explicit exclusion list — what must *not* be pulled into the template |
| `references/deploy-and-publish.md` | Arc 2 touchpoint 1: identity, the ordered publish steps, the per-stage buckets, the auto-publish flag |
| `specs/manifest-contract.md` | Arc 2 touchpoint 2: both output formats, the Python API, the env-var override table, what a provisioner may and may not assume |
| `references/build-and-upload.md` | Arc 2 touchpoint 3: build flags, the cache fingerprint, the overwrite interlock, upload paths, the mount sync |
| `references/runtime-access.md` | Arc 2 touchpoint 4: loading artifacts, the three access modes, the tool-call surface and its adapter |
| `references/repo-layout.md` | Arc 2: the whole file tree, the naming rules, the five mistakes already paid for, the new-library checklist |
| `jobs/write-the-map.md` | Arc 3: how to measure the old surface, group the rows, decide each row's right-hand side |
| `jobs/execute-the-migration.md` | Arc 3: the five ordered steps a consumer applies, and what must be true before each |
| `references/change-classes.md` | Arc 3: the five classes of change a map has to express, and the row shape for each |
| `references/troubleshooting.md` | Arc 3: the errors a mid-migration consumer actually hits, with cause and fix |
| `assets/project_constants.sh` | Arc 1/2: the identity file, ready to copy — the only file where a name is written by hand |
| `assets/migration-map-template.md` | Arc 3: the map document skeleton, plus a short worked example |
| `scripts/leftover_imports.sh` | Arc 3: offline scan — leftover old imports, or an inventory of every module imported |

`assets/project_constants.sh` is a template, not something to run from here: it is sourced by a
library's own publish scripts, which authenticate to AWS.

---

## What this does NOT do

- **It does not describe any one library's internals.** Which retrieval strategies exist, what a graph
  build does, how a reranker scores — that belongs to the library. This skill stops at the seams:
  packaging, the baked manifest, the import surface.
- **It does not provision IAM or infrastructure.** Assume-role provisioning is on arc 1's exclusion
  list on purpose — it is account-shaped, not library-shaped, and copying it copies a trust policy. The
  Terraform that consumes the manifest's properties lives in the infrastructure repo;
  `md_upsert-aws-deployment-role` provisions the deploy role.
- **It does not choose your stages.** `beta` and `prod` are the two this pattern names. A third means a
  third properties file and a third publish script, not a conditional.
- **It does not rewrite imports for you.** No codemod ships here. A mechanical rewrite nobody read is
  how a shim-backed old path gets "migrated" to itself.
- **It does not decide the refactor, or the test framework.** Whether `commons` should become five
  domain modules is an architecture question — `md_policy-code-review` rules on that, and arc 3 starts
  once the answer exists. `z_run_local_tests.sh` is the contract; what it runs is the library's
  business.
- **It is not a JavaScript pattern.** Every rule here is Python-and-wheel shaped. The npm library
  templates are `md_create-git-template`'s `frontend_lib` type, and they do not share this publish
  path.
