# skill_lib

A library of Claude Code skills and plugins. One directory per skill; more will be added over time.

Everything here runs **fully offline**. No skill fetches a URL, installs a package, downloads a
vendor tool, or calls a network service at run time. Every threshold and rule is embedded as static
text, so a small local model can apply it from a checkout plus `git log` alone. The only network
access in this repo is `install.sh` cloning it.

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
Codex has no subagent files, so `/codegraph` takes SKILL.md's documented serial fallback there and
says so in its verdict line. If your Codex build wants an explicit slash trigger, add
`trigger: /codegraph` to the skill's frontmatter — Claude Code ignores the key.

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

| Directory | Name | What it does |
| --- | --- | --- |
| `code_graph_structure_skill/` | CodeGraph | Reads a codebase as a dependency graph, then restructures it so every conflict becomes an interface, every interface has replaceable implementations wired at a single composition root, and the folder tree is the graph. Explicit invocation only. |

## Layout

Each skill directory is self-contained and follows the Claude Code plugin/skill layout:

```
<skill_dir>/
  .claude-plugin/plugin.json   # plugin manifest (name, agents)
  agents/                      # bundled subagents
  skills/<name>/SKILL.md       # skill entry point
  skills/<name>/jobs/          # job playbooks
  skills/<name>/references/    # reference docs loaded on demand
  skills/<name>/specs/         # output format specs
  skills/<name>/scripts/       # deterministic measurement scripts, JSON out
  skills/<name>/scripts/lib/   #   the scanners and metric passes they route to
```

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
| OFFLINE | no network call in any script or agent, no agent granted `WebFetch`/`WebSearch`, no third-party Python import, and every *copyable command in the docs* carries its own offline guard (`npx --no-install`, `GOPROXY=off`, `--offline`) |
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
