# skill_lib

A library of Claude Code skills and plugins. One directory per skill; more will be added over time.

## Skills

| Directory | Name | What it does |
| --- | --- | --- |
| `code_graph_structure_skill/` | CodeGraph | Reads a codebase as a dependency graph, then restructures it so every conflict becomes an interface, every interface has replaceable implementations wired at a single composition root, and the folder tree is the graph. Explicit invocation only. |

## Layout

Each skill directory is self-contained and follows the Claude Code plugin/skill layout:

```
<skill_dir>/
  .claude-plugin/plugin.json   # plugin manifest (name, agents)
  skills/<name>/SKILL.md       # skill entry point
  skills/<name>/references/    # reference docs loaded on demand
  skills/<name>/jobs/          # job playbooks
  skills/<name>/specs/         # output format specs
```

## Using a skill

Point Claude Code at a skill directory as a plugin, or copy `skills/<name>/` into
`~/.claude/skills/` (user-level) or `.claude/skills/` (project-level).

## License

MIT
