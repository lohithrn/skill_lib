# `.codegraph/oracle.json` — the measurement contract

Written once, in `../jobs/analyze.md` phase 0 step 5. Read by every later phase and by three
agents. It answers one question per dimension: **what command proves a claim about this
dimension, and does that command actually run in this repo?**

It exists because nine files ask for "the oracle command" and parallel agents cannot each invent
the same key names. A dimension with no entry here is `UNVERIFIED` — reported once, never
refined, never scored (`../jobs/refine.md` §R2, `../references/refine-loop.md` §2).

---

## 1. Shape

```jsonc
{
  "schema": "codegraph-oracle/1",
  "generated_at": "2026-02-04T11:20:00Z",
  "root": "/abs/path/to/repo",

  // One entry per TOOL. `command` is run verbatim from `root` — it is the string the surgeon and
  // the refine loop execute, so it carries its own flags, its own offline guards and no shell
  // metacharacters that depend on the caller's shell.
  "tools": {
    "tests":      {"command": "pytest -q", "runs": true,  "baseline": "412 passed", "seconds": 41},
    "types":      {"command": "mypy src", "runs": true,  "baseline": "0 errors", "seconds": 12},
    "lint":       {"command": "ruff check src", "runs": true, "baseline": "0", "seconds": 3},
    // ABSOLUTE, resolved once in phase 0. Not `${CLAUDE_PLUGIN_ROOT}`: this string is executed
    // verbatim by later phases and by subagents, and a variable the next process does not set
    // turns the oracle into `bash /skills/…`.
    "caps":       {"command": "bash /Users/me/.claude/skills/md_codegraph/scripts/caps.sh --json --root .",
                   "runs": true, "baseline": "file_lines_major=12", "seconds": 6},
    "graph":      {"command": "bash /Users/me/.claude/skills/md_codegraph/scripts/graph.sh --json --root .",
                   "runs": true, "baseline": "cycles=4", "seconds": 9},
    // `runs: false` is a first-class answer, and `why` is what makes it actionable. Never omit a
    // tool because it is missing — an absent key and a failing tool are different facts.
    "mutation":   {"command": "mutmut run --paths-to-mutate src", "runs": false,
                   "why": "mutmut not installed; no network install permitted", "baseline": null}
  },

  // One entry per DIMENSION, naming the tools that can verify it. The list may be empty.
  // Empty ⇒ UNVERIFIED, and that is the only correct way to say "I cannot measure this".
  "dimensions": {
    "graph": ["graph"],
    "caps":  ["caps"],
    "cond":  ["tests", "caps"],
    "di":    ["tests", "types"],
    "port":  ["tests", "types"],
    "test":  ["tests", "mutation"],
    "time":  []
  },

  "unverified": ["time"],          // exactly the dimensions whose tool list is empty or all-false
  "degraded":   ["mutation absent: G10 in ../jobs/verify.md cannot be gated, only reported"]
}
```

## 2. Rules

| Rule | Why |
|---|---|
| `command` is the **exact** string, with flags | `../jobs/refine.md` step 7 re-measures with "the same commands, same flags, same root". A paraphrase is a different measurement |
| every command is **offline** | `../references/graph-tooling.md` §0. `npx` carries `--no-install`, go commands carry `GOPROXY=off`, maven/gradle carry `--offline`. A command that resolves a dependency is not an oracle, it is a network call |
| `runs` is set by **running it**, once, in phase 0 | `../jobs/apply.md` step 6 and `../agents/codegraph-surgeon.md` step 6 both refuse to start on an already-red oracle. That refusal needs a recorded green |
| `baseline` is what it printed **before** any change | Gate G10 and the ratchet compare against it. A baseline nobody captured turns every gate into a guess |
| a dimension with an empty list ⇒ in `unverified` | The two must agree. `../jobs/verify.md` step 4: no test command ⇒ the whole run is `UNVERIFIED` |
| never repair a red oracle as part of a slice | It is its own finding. Fixing the measuring instrument inside the change it measures destroys the measurement |
| `command` holds a resolved **absolute** path, never `${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_SKILL_DIR}` | `SKILL.md` §Scripts resolves the skill directory once, in phase 0, by trying `${CLAUDE_PLUGIN_ROOT}/skills/md_codegraph`, then `${CLAUDE_SKILL_DIR}`, then the directory holding `SKILL.md`. This file records the answer. A variable is portable only inside the process that sets it, and this string is executed by other processes; that is also why phase 0 runs it once to set `runs` — the path is proven, not assumed |

## 3. Consumers

`../jobs/analyze.md` (writes) · `../jobs/spec.md` step 4 and §2c (every slice needs a command that
exists here) · `../jobs/verify.md` step 4, G1, G10 · `../jobs/apply.md` step 6, step 3 of §4d ·
`../jobs/fitness.md` step 1 · `../jobs/refine.md` steps 1–2, 7, R4 · `../../agents/codegraph-inspector.md`
· `../../agents/codegraph-surgeon.md` · `../../agents/codegraph-cartographer.md`.

Missing file ⇒ every one of them stops and says "run `/md_codegraph analyze` first". None of them
invents a command.
