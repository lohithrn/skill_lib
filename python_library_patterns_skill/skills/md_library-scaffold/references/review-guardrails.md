# Reviewing a change to one of these repos

The template dies by attrition, not by decision: one repo removes the pipeline because "we deploy by
hand for now", another inlines bucket creation because "the Python script was overkill", and a year
later there is no template. Every rule below exists because the change it forbids looks reasonable in
isolation.

## Flag these

| Change | Why it is a finding, not a style note |
|---|---|
| `pipelines/pipelines/azure-pipelines.yml` deleted or moved | Deployments do not stop; they move to a laptop, and the beta-then-prod promotion of one commit stops being enforced |
| `infra/setup_bucket.py` deleted, or `infra/utils.sh` creating buckets inline | Bucket creation drifts per repo. The value that drifts is usually the region, and a bucket in the wrong region fails at read time, not create time |
| Bucket naming changed away from `{tenant_name}-{project_name_lower}-{stage_lower}` | The publish script, the pipeline and every published install URL derive from this one string |
| Either CI credential variable renamed | The pipeline authenticates as nobody, and the failure surfaces as a permission error several steps later |
| A sibling library's source module copied in | Two libraries now share one bug and neither owner knows |
| `.vscode/`, `.claude/`, `agents/openai.yaml` or similar added | A rulebook readable by one tool is enforceable by one tool |
| `build/`, `dist/`, `*.egg-info`, a virtualenv or a cache committed | It teaches the next contributor that this is normal, and it eventually ships inside a wheel |
| Tests or the build verification skipped on a packaging/infra/pipeline change | Those are exactly the files whose breakage is invisible until someone installs the wheel |
| A publish script losing `set -euo pipefail` | A failed test is followed by an upload of the previously built wheel |
| One of the two publish scripts replaced by a `--stage` flag | A mistyped argument now publishes beta over prod |

State the rule and the consequence for each finding. "This differs from the template" is not a
finding; "this removes the only thing that stops beta publishing over prod" is.

## Exclusions — do not pull these into the template

The template is deliberately small. These are common in individual repos and must stay there:

- `.vscode/` or any other editor-local config
- `.claude/`
- `agents/openai.yaml` or any vendor-specific skill metadata
- `educate/`, examples, benchmarks, demo scripts
- IAM assume-role provisioning scripts — account-shaped, not library-shaped; copying one copies a
  trust policy into a repo that did not ask for it
- public install smoke-test scripts tied to one package
- `build/`, `dist/`, `*.egg-info`, virtualenv folders, generated caches
- copied source modules from sibling libraries

Each of these has a legitimate life inside one repo. What is forbidden is *promoting* it to the shared
template, where every future library inherits it and nobody remembers why.

## When the template itself should change

It should, sometimes. The bar is:

1. **Two siblings already do it,** independently. One repo doing something is a preference.
2. **The change is expressible as names only** for the next adopter — no repo has to write logic to
   take it.
3. **It has a stated consequence.** A template entry with no answer to "what breaks without it" is a
   preference, and it will be the first thing the next reviewer deletes.
4. **It is written down here** in the same change. A template rule that lives only in a reviewer's
   head is enforced only while that reviewer is on the team.
