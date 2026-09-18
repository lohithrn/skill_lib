---
name: md_library-scaffold
description: Scaffold, audit or repair an in-house Python library repository so the shared packaging pattern survives — setup.py distribution, src/ layout, a unittest hook, the beta and prod S3 publish scripts, the CI pipeline that promotes one commit from beta to prod, and the common infra helpers. Use when creating a new internal Python library, reviewing a change to one of these repos, adding the shared deployment pipeline, normalizing package/bucket/CI variable naming, or checking that a repo has not drifted from the template.
when_to_use: Any repo that is an in-house Python library published as a wheel to S3, whether you are creating it, changing it, or reviewing someone else's change to it.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
---

# library-scaffold

A repository-owned rulebook, and it does two jobs with one set of facts:

- **a scaffold** for creating a new in-house Python library, and
- **a guardrail** for reviewing changes so the shared deployment and packaging pattern is not quietly
  disturbed.

Which job you are doing changes nothing about the rules — only whether you are writing them or
checking them.

## The gate — read this first

**Copy structure, never source.** The template is the packaging, the publish path and the pipeline.
Business logic, tests, demos, IAM provisioning, install smoke-tests, editor settings and build
artifacts from a sibling library are **not** part of it, and a copied module is the fastest way to
give two libraries one bug.

- Inspect **at least two** sibling libraries before changing a target repo, when examples exist, and
  prefer the files that are common to both. One example cannot tell a convention from an accident.
- Keep this rulebook **portable and plain text**. Do not add lock files or metadata for one AI
  vendor, editor or harness — the moment it exists, the pattern is only enforceable from that tool.
- Adapt **names only**: package identifiers, profile names, repository URLs, CI variable prefixes.
  Anything else you change is a fork of the template, and it must be argued for, not slipped in.
- When reviewing, **flag any change that removes, renames, bypasses or weakens a template file**
  without a stated reason. Silence is how the template dies: one repo at a time, each with a good
  local excuse.

## Route

| You are | Read |
|---|---|
| Creating a new library, or adding a missing piece | `references/common-files.md` |
| Deriving a name, a bucket, or wiring the pipeline | `references/naming-and-pipeline.md` |
| Reviewing a change for drift, or deciding what to leave out | `references/review-guardrails.md` |
| Publishing artifacts and a baked manifest as well | the `md_library-lifecycle` skill |

`md_library-lifecycle` is a **superset** for one kind of library: it assumes everything here plus a
resource manifest baked into the wheel. Start here; go there when the library ships artifacts.

---

## The workflow

Six steps, in order. Steps 1 and 5 are the two people skip, and they are the two that catch drift.

1. **Inspect two siblings.** Prefer files common to both. Note what differs — a difference between
   two siblings is a decision you now have to make consciously.
2. **Keep source code package-specific.** No business logic, tests, demos, IAM setup, public install
   demos, editor settings or local build artifacts unless the user explicitly asks.
3. **Apply the common template files** and adapt only names, package identifiers, profile names,
   repository URLs and pipeline variable prefixes.
4. **Review against the guardrails**, flagging anything that removes, renames, bypasses or weakens a
   template file without an explicit reason.
5. **Validate**: local tests, a syntax check on every helper script, and a real source+wheel build.
   A packaging change that was never built is a packaging change that does not work.
6. **Clean the generated build artifacts** before handing off. A repo handed over with `build/`,
   `dist/` and `*.egg-info` in it teaches the next person that committing them is normal.

---

## Non-negotiables

Each of these has been weakened at least once, and each weakening was invisible until a deploy.

1. **The CI pipeline file stays** at `pipelines/pipelines/azure-pipelines.yml` unless it is replaced
   by an approved common pipeline. Deleting it does not stop deployments; it moves them to somebody's
   laptop, where the beta-then-prod promotion does not happen.
2. **`infra/setup_bucket.py` stays**, and `infra/utils.sh` delegates bucket creation to it. Shell that
   creates buckets inline drifts per repo, and the drift is a region or an ACL.
3. **Bucket naming stays `{tenant_name}-{project_name_lower}-{stage_lower}`** without explicit
   approval. The publish script, the pipeline and every install URL derive from this one string.
4. **CI credential variable naming stays** as `references/naming-and-pipeline.md` specifies. Renaming
   one half of the pair produces a pipeline that authenticates as nobody, and the error surfaces as a
   bucket permission failure three steps later.
5. **No sibling library's source behaviour is hardcoded into this package.** Copy the shape, not the
   implementation.
6. **No AI/editor/harness-specific metadata files** in this repo-owned rulebook: no `.vscode/`, no
   `.claude/`, no `agents/openai.yaml`. A rulebook readable by one tool is enforceable by one tool.
7. **No build outputs, virtualenvs, caches or `*.egg-info` committed.** Ever.
8. **Tests and the build verification are never skipped** when packaging, infra or pipeline files
   change. Those are precisely the files whose breakage is invisible until someone installs the wheel.

---

## Validation — run all four, in this order

```
./z_run_local_tests.sh
python3 -m py_compile infra/setup_bucket.py
python3 setup.py sdist bdist_wheel
./infra/z_clean.sh
```

The order matters: tests before build, because a failing test makes the build irrelevant; the clean
last, because it deletes what step 3 produced.

If the system `python3` lacks the packaging tools, use an available Python runtime that has
`setuptools` and `wheel`, and **say so in the handoff**. A build that was "verified" on a runtime
nobody else has is not verified. Do not add a dependency-installation step to make step 3 pass — this
repo's validation must run on a machine with no network.

---

## Index

| File | Answers |
|---|---|
| `references/common-files.md` | Every file the template owns, what it must do, and the deployment rules for `infra/utils.sh` and the two publish scripts |
| `references/naming-and-pipeline.md` | How every name is derived, the per-stage buckets, the CI variable group and secret pair, and the beta-then-prod promotion contract |
| `references/review-guardrails.md` | What to flag in review, and the explicit exclusion list — what must *not* be pulled into the template |

---

## What this does NOT do

- **It does not describe the artifact lifecycle.** Baked manifests, artifact buckets, mounts and
  tool-calling belong to the `md_library-lifecycle` skill. A library can follow every rule here and
  publish no artifacts at all.
- **It does not provision IAM.** Assume-role provisioning is on the exclusion list on purpose: it is
  account-shaped, not library-shaped, and copying it between repos copies a trust policy.
- **It does not generate any authentication material.** The publish path uses an SSO profile locally
  and injected CI credentials in the pipeline. There is no key or certificate for this repo to mint.
- **It does not decide your test framework beyond the hook.** `z_run_local_tests.sh` is the contract;
  what it runs is the library's business.
