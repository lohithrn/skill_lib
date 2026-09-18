# Contract: the skill manifest

One YAML file, hand-authored, in the repository's contracts directory and packaged into the deployed
artifact. It is the source of truth for the skill set: the generator reads it, validates it against the
OpenAPI document, and generates prompt registration, the skill index and the resource registration from
it.

## Fields

| Field | Required | Contents | Consequence if wrong |
|---|---|---|---|
| `name` | yes | lower snake case, unique | it is the prompt name, the resource URI segment and the file stem at once; a duplicate silently shadows a skill |
| `title` | yes | natural English, title case | `prompts/list` shows a raw identifier to a human |
| `description` | yes | one sentence, what the skill accomplishes | this is what a client's model reads when choosing a workflow |
| `document` | yes | path to the Markdown, relative to the repository root | a missing document fails the build, which is the point |
| `tools` | yes | exact tool names, in call order where an order exists | every name is validated against the OpenAPI document; a miss fails the build |
| `destructive` | yes | boolean | an unflagged destructive skill escapes the confirmation assertions in the test suite |
| `arguments` | no | prompt argument names, all strings | an undeclared placeholder in the document renders as itself |

Set `destructive: true` for any skill whose tool list contains a delete or remove operation, local or
external. A skill that writes to an external system without deleting is not destructive, but it still
needs a confirmation rule — see `references/skill-authoring.md` §4.

## Example

Neutral worked example: four skills over a records service with an external target system.

```yaml
# <product> MCP skill manifest.
#
# Source of truth for the skill set. Each entry maps a skill to its Markdown
# document, the MCP tools it orchestrates, and whether it is destructive.
# Skills are NOT tools: they guide the client's model, which then calls the
# tools. Prompt names, resource URIs and document stems all key off `name`.
skills:
  - name: inspect_groups
    title: Inspect Groups
    description: List the groups belonging to a tenant.
    document: skills/inspect_groups.md
    tools:
      - listGroups
    destructive: false

  - name: create_records_in_group
    title: Create Records in Group
    description: Create or update records and assign their latest group.
    document: skills/create_records_in_group.md
    tools:
      - createBatchRecords
    destructive: false

  - name: export_records_to_target
    title: Export Records to Target
    description: Move a group-scoped row range into an existing external target dataset.
    document: skills/export_records_to_target.md
    tools:
      - listRecordsByRange
      - exportRecordsToTarget
      - getExportData
    destructive: false

  - name: reverse_export
    title: Reverse Export
    description: Remove exported records from the external target, then optionally delete the local export record.
    document: skills/reverse_export.md
    tools:
      - getExportData
      - deleteExportFromTarget
    destructive: true
```

## Validation the generator performs

Every one of these **fails the build**. A warning here is a run-time failure later, mid-workflow, after
the irreversible steps have already run.

| Check | Message must name |
|---|---|
| Every `tools` entry exists in the OpenAPI document | the skill and the missing tool |
| Every `document` path resolves | the skill and the path |
| Every `name` is unique | both offending entries |
| Every `name` is lower snake case | the offending name |
| Every entry has all required fields | the skill and the missing field |
| Every `arguments` entry appears as a placeholder in the document, and every placeholder is declared | the skill and the mismatched name |

The last check is cheap and catches the failure that is hardest to see in review: a renamed argument that
leaves a placeholder nothing will ever fill.

## What the manifest does not do

- **It does not define tools.** Tools come from the OpenAPI document. The manifest only references them
  by name, and the generator's job is to prove those names are real.
- **It does not contain workflow.** Ordering, confirmation and refusals live in the Markdown, where a
  human reviews them as prose.
- **It is never generated.** It encodes the decision about which business tasks deserve a skill, which
  is a human decision. Generating it means generating that judgement.
- **It holds no credentials and no environment configuration.** It is packaged into the artifact and is
  therefore world-readable to anyone who can read the artifact.
