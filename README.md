# skill_lib

A library of Claude Code skills and plugins — one directory per plugin, one subdirectory per skill.
It is the single home for every skill in this collection, so a new machine needs one clone.

**The rule layer is fully offline.** Every threshold, convention and refusal is embedded as static
text, and the measurement tools under `skills/*/scripts/` and every bundled agent are standard
library only: no URL fetched, no package installed, no vendor tool downloaded, no network call. A
small local model can apply the whole policy from a checkout plus `git log`. That is enforced by
`tests/smoke.sh`, not asserted.

**Some skills act on live systems, and that code is quarantined in `assets/`.** Provisioning an IAM
role, deploying a spend guard, publishing an artifact and streaming a rendered avatar all need the
network by definition. Those programs live under `skills/<name>/assets/`, never under `scripts/`, so
the offline guarantee above stays a guarantee: the tests draw the line at the directory, and a
reviewer can tell which half of a skill can reach the internet by the path alone.

## Install

```bash
git clone https://github.com/lohithrn/skill_lib.git
cd skill_lib
bash install.sh
```

Or without a checkout:

```bash
curl -fsSL https://raw.githubusercontent.com/lohithrn/skill_lib/main/install.sh | bash
```

That symlinks every `*/skills/<name>/` in this repo into `~/.claude/skills/<name>/` and every
`*/agents/*.md` into `~/.claude/agents/`, so the skills — and the subagents they fan out to — are
available in every project. Without the agents the pipeline still runs, but each dimension falls
back to `general-purpose` with the job file inlined.

**Codex gets the same skill.** Codex reads the identical layout — `<codex home>/skills/<name>/SKILL.md`
with `name` + `description` frontmatter — so when `~/.codex` already exists the installer links the
**same directory** there too: one source of truth, no second copy to drift. `--codex` installs there
even if the directory has to be created, `--no-codex` skips it, and `CODEX_HOME` relocates it.
Codex has no subagent files, so `/md_codegraph` takes SKILL.md's documented serial fallback there and
says so in its verdict line. If your Codex build wants an explicit slash trigger, add
`trigger: /md_codegraph` to the skill's frontmatter — Claude Code ignores the key.

| Command | Effect |
| --- | --- |
| `bash install.sh` | install (symlink into the checkout — edits show up immediately) |
| `bash install.sh --codex` | also install into Codex, creating `~/.codex/skills/` if needed |
| `bash install.sh --no-codex` | Claude Code only, even if `~/.codex` exists |
| `bash install.sh --update` | `git pull` (or clone into `~/.claude/skill_lib`), then install |
| `bash install.sh --copy` | install a detached snapshot instead of a symlink |
| `bash install.sh --list` | show what is installed and where it points |
| `bash install.sh --dry-run` | print every action, change nothing |
| `bash install.sh --uninstall` | remove the symlinks this installer created |
| `bash install.sh --help` | all options |

Overridable: `CLAUDE_CONFIG_DIR` (default `~/.claude`), `CODEX_HOME` (default `~/.codex`),
`SKILL_LIB_REPO`, `SKILL_LIB_BRANCH`.
The installer writes only under those two roots, never needs `sudo`, never executes code from
the repo it installs, and moves any pre-existing skill of the same name aside to
`<name>.backup.<timestamp>` rather than overwriting it.

## Skills

Grouped by what they are for. Every row is a skill you can invoke by name.

### Doctrine — the rules everything else defers to

| Directory | Skill | What it does |
| --- | --- | --- |
| `global_doctrine_skill/` | `md_standing-doctrine` | The two rules that outrank every project convention: judge code against the **system being built**, not the value in today's snapshot; and never use a machine-generated certificate or private key as an authorization mechanism. |
| `global_doctrine_skill/` | `md_adhd-output-style` | The output contract — lead with the command or path, number multi-step work, restate progress, concrete time estimates, cap lists at five, no preamble or closers. Applies to reports, not just chat. |
| `house_conventions_skill/` | `md_fleet-conventions` | The standing conventions for a fleet of services: `<prefix>_<resource_role>` naming, the AWS name-length caps and their slug escape hatches, route shape, `urls.{env}.yaml`, epoch-milliseconds, the deploy gates. |
| `house_conventions_skill/` | `md_service-blueprint` | Builds a new service to those conventions, `naming.tf` first. |

### Review — read a tree, suggest, never edit

| Directory | Skill | What it does |
| --- | --- | --- |
| `code_graph_structure_skill/` | `md_codegraph` | Reads a codebase as a dependency graph, then restructures it so every conflict becomes an interface, every interface has replaceable implementations wired at a single composition root, and the folder tree is the graph. Explicit invocation only. |
| `policy_code_review/` | `md_policy-code-review` | Reviews a tree or a diff against the whole standing policy — graph structure, house conventions, and ordinary change review — and emits **suggestions only**. Has no write tools. |
| `architecture_refactoring_skill/` | `md_coding-rules` | The 40-rule architecture, dependency-injection and maintainability standard, with a deterministic linter under `scripts/` whose JSON findings are treated as measured ground truth rather than re-eyeballed. |

### Build and provision

| Directory | Skill | What it does |
| --- | --- | --- |
| `deployment_scaffolding_skill/` | `md_upsert-aws-deployment-role` | Takes a local folder or a remote repository URL, reads its terraform, and provisions the IAM deployment role, inline policy and permissions boundary named after the repo. Ships the engine and its tests, not just the prompt. |
| `deployment_scaffolding_skill/` | `md_register-sso-app` | Registers an OIDC login client in AWS IAM Identity Center and returns the client id and issuer for the frontend. **Never Cognito** — if Identity Center looks like it is missing a capability, keep investigating Identity Center. |
| `deployment_scaffolding_skill/` | `md_create-git-template` | Scaffolds a new repository from the `frontend`, `frontend_lib`, `backend_service` and `backend_lib` templates — 61 template files including `naming.tf` itself. |
| `python_library_patterns_skill/` | `md_library-scaffold` | Scaffolds and audits a shared Python library: `src/` layout, `setup.py`, the beta/prod publish split, the pipeline. |
| `python_library_patterns_skill/` | `md_library-lifecycle` | The artifact lifecycle for such a library — build, upload, the resource manifest contract, runtime access. |
| `python_library_patterns_skill/` | `md_library-migration` | Migrates callers off a library surface: measure both surfaces, group by destination, verify zero leftover imports. |
| `bedrock_spend_guard_skill/` | `md_hiatus-bedrock` | A spend circuit breaker for Bedrock usage on an AWS account. |
| `mcp_surface_skill/` | `md_mcp-skill-surface` | Exposes a REST/OpenAPI service as an MCP surface: tools generated 1:1 from operations, skills as prompts, documentation as resources. Its hardest rule is **a skill is not a tool** — a skill guides the client, tools execute. |

### Evaluate

| Directory | Skill | What it does |
| --- | --- | --- |
| `agent_evaluation_skill/` | `md_agent-evaluation` | Scores an agent's **outcome, trajectory and risk surface separately**, because a fluent final answer hides a wrong tool call, a bad argument, a wrong mutation or a failed injection defence. Eight metric layers, a stdlib metric calculator with a 24-check self-test, and launch thresholds. |

### Media

| Directory | Skill | What it does |
| --- | --- | --- |
| `director_skill/` | `md_director` | Interactive video generation: turns a brief into shots and drives the generator. |
| `talking_avatar_skill/` | `md_talking-avatar` | Portrait to photoreal talking avatar over HLS — GPU bake, CPU replay, no request-time inference. |
| `deck_builder_skill/` | `md_deck-builder` | Builds decks from your own PowerPoint template, with a QA gate that refuses to pass a deck it could not measure. |

## Layout

Each skill directory is self-contained and follows the Claude Code plugin/skill layout:

```
<plugin_dir>/
  .claude-plugin/plugin.json   # plugin manifest (name, description, keywords)
  agents/                      # bundled subagents
  references/                  # docs shared by every skill in this plugin
  skills/<name>/SKILL.md       # skill entry point — the router, hard cap 250 lines
  skills/<name>/jobs/          # job playbooks: the procedures
  skills/<name>/references/    # the rules and tables, loaded on demand
  skills/<name>/specs/         # output format specs
  skills/<name>/scripts/       # OFFLINE stdlib-only measurement tools, JSON out
  skills/<name>/scripts/lib/   #   the scanners and metric passes they route to
  skills/<name>/assets/        # everything else: templates, and programs that
                               #   legitimately reach AWS or the network
```

The `scripts/` versus `assets/` split is the offline boundary, not a filing preference. The test suite
bans every network reference and third-party import under `scripts/`, so a program that must call AWS
belongs in `assets/` — putting it in `scripts/` does not make it offline, it just breaks the build.

`install.sh` discovers skills by globbing `*/skills/*/SKILL.md` and agents by globbing
`*/agents/*.md`, so a new skill or agent needs no installer change.

## Tests

The offline and safety claims above are enforced, not asserted:

```bash
bash tests/smoke.sh          # run every invariant
bash tests/smoke.sh --list   # list the checks
```

Exit 0 = all pass, 1 = a check failed, 2 = the harness itself broke. Five groups:

| Group | What it refuses to let regress |
| --- | --- |
| OFFLINE | no network call in any `skills/*/scripts/` file or any bundled agent, no agent granted `WebFetch`/`WebSearch`, no third-party Python import there, and every *copyable command in the docs* carries its own offline guard (`npx --no-install`, `GOPROXY=off`, `--offline`). Programs under `assets/` are exempt by design — that is what `assets/` means here |
| SECURITY | no credential-shaped literals, no generated cert/key material or cert-as-auth guidance, no `eval`/`sudo`/`chmod 777`, scripts never modify the analysed tree (verified by hashing its **contents**), installer writes nothing on `--dry-run`, installs every bundled agent readably, and uninstalls cleanly |
| WIRING | every path a manifest or index promises exists, every documented script flag is actually accepted by that script, no reference file is orphaned, `SKILL.md` within 250 lines and every prose file within 600 |
| BEHAVIOR | the measurement scripts find known-seeded violations and a known cycle in a generated fixture, `--cycles` agrees with the full graph, and every `--json` mode emits valid JSON |
| HOSTILE INPUT | a filename cannot inject JSON or execute a command, a symlink cannot read outside the tree, a file that cannot be scanned is declared in `degraded` instead of dropped, a `\|` or `&` in the analysed path cannot fake a clean report, and the analysed repo's own `.git/config` cannot execute anything |

The suite needs `bash` and `python3` (standard library only) and nothing else.

## Using a skill without installing

Point Claude Code at a skill directory as a plugin, or copy `skills/<name>/` into
`~/.claude/skills/` (user-level) or `.claude/skills/` (project-level).

## License

MIT
