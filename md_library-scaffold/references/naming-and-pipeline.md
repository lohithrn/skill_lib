# Naming, and the pipeline that promotes one commit

## Derive every name, do not invent one

| Name | Derivation | Notes |
|---|---|---|
| `tenant_name` | lower-case organisation slug | The only hand-written identity value in the repo |
| `AWS_PROFILE` | same as `tenant_name` for local runs | Unless pipeline credentials are injected, in which case the profile is unused |
| `package_name` | lower-case Python distribution/import package, **underscores** | This is the `src/` directory name |
| `project_name_lower` | the repository directory name, **lower-cased** | S3 rejects uppercase in a bucket name, and rejects it at the end of a build |
| S3 bucket | `{tenant_name}-{project_name_lower}-{stage_lower}` | One per stage. Changing this pattern needs explicit approval |
| CI variable group | the organisation name, **upper case** | e.g. `<ORG>` |
| CI credential variables | see the pair below | Renaming one half breaks auth in a way that surfaces later, as a bucket permission error |

`package_name` uses underscores and `project_name_lower` does not: the first is a Python identifier
and the second is part of a DNS-compatible bucket name. They are different strings for the same
library and both are derived, so neither needs typing twice.

### Expected buckets

For a repo whose directory is `<ProjectName>`, the two buckets are:

| Stage | Bucket |
|---|---|
| beta | `<tenant>-<project_name_lower>-beta` |
| prod | `<tenant>-<project_name_lower>-prod` |

Both names exist from day one, even when only beta is in use. A stage added later means adding a
name, a script and a pipeline stage — never adding a conditional to an existing one.

### The CI credential pair

Two variables per stage, in the upper-case variable group:

| Half | Name |
|---|---|
| Access key id | `{ORG}_{STAGE}_AWS_ACCESS_KEY_ID` |
| Secret half | the same `{ORG}_{STAGE}_AWS` prefix, with the trailing `_ACCESS_KEY_ID` replaced by `_SECRET_ACCESS_KEY` |

`{STAGE}` is the upper-cased stage, so beta and prod carry **separate credentials** and a beta
pipeline literally cannot write to the prod bucket. That is the whole reason the stage is in the
variable name; do not collapse the pair into one set of shared credentials to save two variables.

Both are secret variables in the group, injected as environment variables into the publish step, where
`infra/utils.sh` picks them up instead of an SSO profile. Never echo them, never write them to a file,
and never commit a fallback default for either.

## The pipeline contract

The pipeline exists to enforce one property that a human cannot be trusted to enforce by hand:
**prod runs the same commit beta ran.**

1. **Deploy beta** from the triggering commit.
2. **Record the deployed commit SHA** as an output of that stage.
3. **Wait for environment approval** on the prod stage.
4. **Deploy that same recorded SHA** to prod.

Step 2 is the one that gets dropped in a rewrite, and dropping it turns step 4 into "deploy whatever
is on the branch now" — so a commit merged during the approval window ships to prod having never been
in beta. The approval then certifies a build nobody tested.

Do not replace the recorded SHA with a branch name, a tag that moves, or "latest". A tag is only
acceptable if the pipeline creates it at step 2 and never moves it.

## Reviewing a pipeline change

Flag any of these:

- the beta stage no longer running the tests,
- the prod stage taking its source from anything other than the recorded SHA,
- the approval gate removed, made conditional, or given an auto-approve path,
- either half of the credential pair renamed, defaulted, or shared between stages,
- a bucket name assembled inline in the YAML instead of derived from the constants,
- the pipeline file moved out of `pipelines/pipelines/azure-pipelines.yml` without a replacement
  common pipeline.

Each of these still deploys successfully, which is why none of them is caught by a green pipeline.
