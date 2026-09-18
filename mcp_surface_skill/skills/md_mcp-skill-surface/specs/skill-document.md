# Contract: the skill document

One Markdown file per skill, served verbatim as an MCP prompt and as a read-only resource. It is the
only artifact in the surface written by a human, and the only one a model reads before acting.

## The 13 required sections

All 13, in this order, in every skill. No exceptions, including read-only skills.

| # | Section | Contains | Empty means |
|---|---|---|---|
| 1 | Skill name | the lower snake case name, matching the manifest key and the file stem | the identifier is derived twice and the two forms will diverge |
| 2 | Display title | natural English, title case | `prompts/list` shows a snake_case string to a human |
| 3 | Purpose | one or two sentences: what business task this accomplishes | the model guesses from the name |
| 4 | When to use | the situations this skill is the right answer for | the model applies it where it does not fit |
| 5 | When not to use | the situations it is the wrong answer for, naming the right skill instead | **the most-skipped section, and how a read skill gets used to mutate** |
| 6 | Required information | every input the workflow cannot start without | the model invents values to proceed |
| 7 | Optional information | filters, page size, cursors, mapping overrides | the model either ignores capability or invents a filter |
| 8 | Tools used | exact tool names, one per line | the generator cannot validate the skill and a reviewer cannot see its blast radius |
| 9 | Ordered workflow | numbered steps, one action each, validation before the first call | the model chooses an order, and irreversible steps move earlier |
| 10 | Human confirmation rules | when to ask, and what to say. For a read skill: "none, this skill only reads" | a destructive operation runs unattended |
| 11 | Validation rules | what must be true before calling, and what must never be fabricated | fabricated identifiers reach another tenant's data |
| 12 | Failure behaviour | expected error codes, what to present, what not to conclude | a failure is narrated as a success or as an outage |
| 13 | Expected final response | the fields the answer must contain | the human gets prose without the identifiers needed for a follow-up |

Plus the universal client instructions from `references/skill-authoring.md` §3 — all 10, in every
document. A skill is retrieved alone; a rule in a file the client never fetches does not exist.

A 14th section is worth adding as a closing block: the refusals, restated compactly. The model reads the
end of a document last and closest to acting.

## Template

Substitute freely; delete nothing.

```markdown
# <Display Title>

- **Skill name:** `<skill_name>`
- **Display title:** <Display Title>

## Purpose
<One or two sentences. The business task, not the tools.>

## When to use
- <Situation where this is the right skill.>

## When not to use
- <Situation where it is not — and which skill is.>
- <A capability this skill must never claim.>

## Required information
- `<argument>` — <what it is, and that it must come from the human or a prior tool result>

## Optional information
- `<argument>` — <what it changes>

## Tools used
- `<toolName>`

## Ordered workflow
1. Validate `<argument>`. Never invent it.
2. <Next action.>
3. Read the tool result before reporting anything.
4. <Report step.>

## Human confirmation rules
- <When to ask, and the exact scope to state.>
- <Or: "None. This skill only reads and needs no confirmation.">

## Validation rules
- <What must be true before calling.>
- <What must never be fabricated.>

## Failure behaviour
- <Expected error codes and what to present.>
- Never claim the operation succeeded without reading the tool result.

## Expected final response
- <Field the answer must include.>
- <Pagination state, if the skill pages.>

## Guardrails
- Never invent tenant, group, record or dataset identifiers.
- Never expose credentials in any summary.
- Never call a tool this skill does not list.
- Never bypass the API with a direct call to the database or an external system.
```

## Destructive additions

A skill with the destructive flag adds, inside sections 9–11:

- The exact target, named: which dataset, which identities, how many.
- Whether your own product's data is affected. Whether the external system's data is affected.
- The confirmation step, before the call, with wording that states all three facts at once. For
  example: *this affects the external system · it does not delete your records · it does not delete the
  destination dataset.*
- A `force`-style override, if one exists, described as human-requested only and never automatic.
- For a reversal that also removes a local record: two confirmation steps, and the metadata flag
  documented as defaulting to off.

## Placeholders

A document may carry `{{argumentName}}` placeholders that the prompt layer interpolates. Rules:

| Rule | Consequence if broken |
|---|---|
| Every placeholder is a declared prompt argument | an undeclared one renders as itself, or worse, as an empty string |
| An unsupplied placeholder is left intact, never blanked | "validate the tenant " is an instruction with a hole the model fills |
| No conditionals, no loops, no includes | a document whose meaning depends on a condition is two skills |
| The document must read correctly with **no** arguments supplied | a client may call `prompts/get` with none, and often does first |

## What a skill document must never contain

- Executable code, database queries, or HTTP details.
- A credential, in any form, including an example value.
- A tool name that the manifest entry does not list.
- Workflow steps for a different task — that is a second skill.
- An instruction to contact an external system directly.
- A claim about live external state that only a stored record supports.
