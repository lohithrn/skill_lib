# skill_lib

A library of Claude Code skills — **one top-level directory per skill**, and the directory name *is*
the skill name. It is the single home for every skill in this collection, so a new machine needs one
clone.

**Read the repo root and you have read the index.** Every entry is a skill; a skill is the same thing
as a slash command; you execute it directly. `md_codegraph/` is the skill `md_codegraph`, invoked as
`/md_codegraph`. The folder name and the `name:` in that skill's `SKILL.md` frontmatter are identical
— there is no wrapper layer, no manifest to keep in sync, and nothing to translate between what you
see on disk and what you type.

**The rule layer is fully offline.** Every threshold, convention and refusal is embedded as static
text, and the measurement tools under `md_*/scripts/` and every bundled agent are standard library
only: no URL fetched, no package installed, no vendor tool downloaded, no network call. A small local
model can apply the whole policy from a checkout plus `git log`. That is enforced by `tests/smoke.sh`,
not asserted.

**Some skills act on live systems, and that code is quarantined in `assets/`.** Provisioning an IAM
role, deploying a spend guard, publishing an artifact and streaming a rendered avatar all need the
network by definition. Those programs live under `md_<name>/assets/`, never under `scripts/`, so the
offline guarantee above stays a guarantee: the tests draw the line at the directory, and a reviewer
can tell which half of a skill can reach the internet by the path alone.

**A run leaves nothing behind that nobody chose to keep.** Every path a skill writes into your repo is
either scratch — deleted by the run that made it — or durable, which means **committed**, in one
documentation folder, with a semantic commit subject. `.gitignore` is not a third exit: ignoring a
scratch directory keeps it *and* hides it from `git status`, which is how a stale artifact survives to
poison the next run. The contract is `docs/authoring.md` §10–11, each skill's own disposition table is
`md_<name>/references/artifacts.md`, and `tests/smoke.sh` fails the build if a path a job writes is
missing from that table.

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

That installs every `md_<name>/` directory in this repo as `~/.claude/skills/md_<name>/` and every
`md_*/agents/*.md` as `~/.claude/agents/<agent>.md`, so the skills — and the subagents they fan out
to — are available in every project. The default mode is a symlink into the checkout, so your edits
show up immediately; `--copy` installs a detached snapshot instead. Without the agents the pipeline
still runs, but each dimension falls back to `general-purpose` with the job file inlined.

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

**Note: this repo is no longer a Claude Code plugin or marketplace.** The **13** plugin wrapper
directories and their `.claude-plugin/plugin.json` manifests are deleted. `install.sh` is the only
install path — it places skill directories and agent files directly under `~/.claude`. If you were
adding this repo with `/plugin marketplace add`, stop; run `install.sh` instead.

## Skills

**13** skills, grouped by what they are for. Invoke any row by its name.

**The standing doctrine is not a skill.** The **three** contracts that outrank every project
convention — judge code against the **system being built**, not the value in today's snapshot; never
use a machine-generated certificate or private key as an authorization mechanism; and the output
contract (lead with the command or path, number multi-step work, restate progress, concrete time
estimates, cap lists at **5**, no preamble or closers) — belong in a global instruction file
(`~/.claude/CLAUDE.md`, `~/AGENTS.md`) where they are always in context. A rule that only loads when a
matcher fires is not a standing rule. The text to copy is
`md_policy-code-review/references/standing-doctrine.md`, which is also where the review skill cites
them from.

### Conventions — the fleet's standing rules

| Skill | What it does |
| --- | --- |
| `md_service-fleet-blueprint-conventions` | Two arcs over one fleet of services. **review:** the standing conventions — `<prefix>_<resource_role>` naming, the AWS name-length caps and their slug escape hatches, route shape, `urls.{env}.yaml`, epoch-milliseconds, the deploy gates — read a repo, rule on a diff, edit nothing. **build:** stands a new service up to those conventions, `naming.tf` first, from **5** bundled templates. Carries a **resource catalog** — one row per AWS resource kind with its terraform file, its `naming.tf` local, its cap, and whether a legacy repo is exempt — because every rule is marked `all code` or `new only`: existing services are grandfathered, never retrofitted. |

### Review — read a tree, suggest, edit only in the one mode that says so

| Skill | What it does |
| --- | --- |
| `md_codegraph` | Reads a codebase as a dependency graph, then restructures it so every conflict becomes an interface, every interface has replaceable implementations wired at a single composition root, and the folder tree is the graph. Caps fan-out at **7** code files directly in one folder with unlimited subfolders, so a flat pile of files is reported as a question nobody named. Asks first whether to read the uncommitted diff, a commit range, or the whole tree. Explicit invocation only. Bundles **5** subagents. |
| `md_policy-code-review` | Reviews a tree or a diff against the whole standing policy at once — the **40**-rule architecture, dependency-injection and maintainability standard (group `R`), graph structure (`G`), house conventions (`H`), and ordinary change review (`C`) — with a deterministic linter under `scripts/` whose JSON findings are treated as measured ground truth rather than re-eyeballed. `review` and `diff` emit **suggestions only**; the one `refactor` mode applies them, and its gate is inspect-then-plan-then-edit. Holds the standing doctrine as `references/standing-doctrine.md` and cites it as precedence rules 1 and 2. |

### Diagnose — find the cause before touching the code

| Skill | What it does |
| --- | --- |
| `md_bug-diagnosis` | Diagnoses a hard bug or a performance regression, and enforces one gate above all others: **no red-capable command that has already run means no hypothesis.** Phase 1 is the whole skill — a ladder of **10** ways to build a signal that goes red on this exact symptom, then tighten it to seconds and determinism. After that: minimise until every remaining element is load-bearing, rank **3–5** falsifiable hypotheses *before* testing any, one variable per probe behind a taggable `[DEBUG-...]` prefix, and a regression test only at a seam that can actually see the bug — where **no such seam is itself the finding**. Measures a baseline before fixing anything about speed. Redacts every secret out of everything it shows, and never points a loop at production. |

### Build and provision

| Skill | What it does |
| --- | --- |
| `md_upsert-aws-deployment-role` | Takes a local folder or a remote repository URL, reads its terraform, and provisions the IAM deployment role, inline policy and permissions boundary named after the repo. Ships the engine and its tests, not just the prompt. |
| `md_register-sso-app` | Registers an OIDC login client in AWS IAM Identity Center and returns the client id and issuer for the frontend. **Never Cognito** — if Identity Center looks like it is missing a capability, keep investigating Identity Center. |
| `md_create-git-template` | Scaffolds a new repository from the `frontend`, `frontend_lib`, `backend_service` and `backend_lib` templates — **61** template files including `naming.tf` itself. |
| `md_python-library` | The whole life of an in-house **Python** library published as a wheel to S3, in three arcs: **scaffold** (`src/` layout, `setup.py`, the beta/prod publish split, the pipeline), **lifecycle** (build, upload, the baked resource-manifest contract, runtime access), **migration** (measure both surfaces, group by destination, prove zero leftover imports). The npm library path is `md_create-git-template`'s `frontend_lib` type instead. |
| `md_hiatus-bedrock` | A spend circuit breaker for Bedrock usage on an AWS account. |
| `md_mcp-skill-surface` | Exposes a REST/OpenAPI service as an MCP surface: tools generated 1:1 from operations, skills as prompts, documentation as resources. Its hardest rule is **a skill is not a tool** — a skill guides the client, tools execute. |

### Evaluate

| Skill | What it does |
| --- | --- |
| `md_agent-evaluation` | Scores an agent's **outcome, trajectory and risk surface separately**, because a fluent final answer hides a wrong tool call, a bad argument, a wrong mutation or a failed injection defence. **8** metric layers, a stdlib metric calculator with a **24**-check self-test, and launch thresholds. |

### Media

| Skill | What it does |
| --- | --- |
| `md_director` | Interactive video generation: turns a brief into shots and drives the generator. Bundles **1** subagent. |
| `md_deck-builder` | Builds decks from your own PowerPoint template, with a QA gate that refuses to pass a deck it could not measure. |

## Layout

The repo root holds **13** skill directories, the installer, this file, one `docs/` folder, the license
and the tests — nothing else:

```
skill_lib/
  md_<name>/       # one skill; the directory name IS the skill name and the slash command
  install.sh       # the only install path — links or copies each md_*/ into ~/.claude
  README.md        # the index: what each skill is, and where files go
  docs/            # every document about the repo, and the only such folder
    authoring.md   #   how to write the prose inside a skill, and why the caps exist
    codegraph-spec.md  # md_codegraph's design record — rationale, not runtime rule text
  LICENSE
  tests/smoke.sh   # the test suite
```

**`docs/` is deliberately not installed.** `install.sh` copies `md_*/` only, so a design record cannot
leak into a model's context at run time; what a skill needs while running lives inside that skill.

Each skill directory is self-contained. `SKILL.md` is the only required file; every subdirectory is
optional and only present where a skill needs it:

```
md_<name>/
  SKILL.md         # skill entry point — the router, hard cap 250 lines
  references/      # the rules and tables, loaded on demand
  jobs/            # job playbooks: the procedures
  specs/           # output format specs
  scripts/         # OFFLINE stdlib-only measurement tools, JSON out
  scripts/lib/     #   the scanners and metric passes they route to
  agents/          # bundled subagents, installed into ~/.claude/agents/
  assets/          # everything else: templates, and programs that
                   #   legitimately reach AWS or the network
```

`SKILL.md` is capped at **250** lines; every other `.md` file is capped at **600**. Both caps are
enforced by the test suite.

This section is the layout. **`docs/authoring.md` is how to write the prose inside it** — the router
pattern the caps follow from, progressive disclosure and the branching test, context pointers, leading
words, when a prohibition is a guardrail and when it should be a positive, what to prune, what a run is
allowed to leave behind (§10), and the commit-subject and version contracts (§11).

Bundled agents live in exactly two skills: `md_codegraph/agents/` (**5** agents — cartographer,
inspector, architect, adversary, surgeon) and `md_director/agents/` (**1** agent).

The `scripts/` versus `assets/` split is the offline boundary, not a filing preference. The test suite
bans every network reference and third-party import under `scripts/`, so a program that must call AWS
belongs in `assets/` — putting it in `scripts/` does not make it offline, it just breaks the build.

`install.sh` discovers skills by globbing `md_*/SKILL.md` and agents by globbing `md_*/agents/*.md`,
so a new skill or agent needs no installer change: create the directory, name it `md_<name>`, give it
a `SKILL.md` whose frontmatter `name:` matches the directory, and re-run the installer.

## Tests

The offline and safety claims above are enforced, not asserted:

```bash
bash tests/smoke.sh          # run every invariant
bash tests/smoke.sh --list   # list the checks
```

Exit 0 = all pass, 1 = a check failed, 2 = the harness itself broke. **5** groups:

| Group | What it refuses to let regress |
| --- | --- |
| OFFLINE | no network call in any `md_*/scripts/` file or any bundled agent, no agent granted `WebFetch`/`WebSearch`, no third-party Python import there, and every *copyable command in the docs* carries its own offline guard (`npx --no-install`, `GOPROXY=off`, `--offline`). Programs under `assets/` are exempt by design — that is what `assets/` means here |
| SECURITY | no credential-shaped literals, no generated cert/key material or cert-as-auth guidance, no `eval`/`sudo`/`chmod 777`, scripts never modify the analysed tree (verified by hashing its **contents**), installer writes nothing on `--dry-run`, installs every bundled agent readably, and uninstalls cleanly |
| WIRING | every path an index promises exists, every skill's frontmatter `name:` matches its directory, every documented script flag is actually accepted by that script, no reference file is orphaned, `SKILL.md` within **250** lines and every prose file within **600** |
| BEHAVIOR | the measurement scripts find known-seeded violations and a known cycle in a generated fixture, `--cycles` agrees with the full graph, and every `--json` mode emits valid JSON |
| HOSTILE INPUT | a filename cannot inject JSON or execute a command, a symlink cannot read outside the tree, a file that cannot be scanned is declared in `degraded` instead of dropped, a `\|` or `&` in the analysed path cannot fake a clean report, and the analysed repo's own `.git/config` cannot execute anything |

The suite needs `bash` and `python3` (standard library only) and nothing else.

## Using a skill without installing

Copy the one `md_<name>/` directory into `~/.claude/skills/` (user-level) or `.claude/skills/`
(project-level). Keep the directory name — that name is the skill's identity in both hosts.

## License

MIT — see [LICENSE](LICENSE).
