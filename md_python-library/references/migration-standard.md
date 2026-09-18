# The consumer migration standard

The arc-3 rulebook: write, stage and verify an old-to-new import map when the public surface is
refactored. Cited from `SKILL.md` as **arc 3 — migration**.

A router for one job: **a rename of a library's public surface, made survivable for the repos that
import it.** The deliverable is a migration map — a table from every old import path to the thing that
replaced it — plus the order in which a consumer applies it.

The map is *data*, specific to one refactor. This skill is the *procedure* that makes any map
complete, ordered, and provable. Read `jobs/write-the-map.md` before you edit a single consumer.

## The gate — read this first

**No consumer is touched before the map is complete.** A half-written map turns a consumer's
migration into a search: they hit an `ImportError`, guess at the new name, and each consumer guesses
differently. That divergence outlives the refactor.

- **Complete means every row has a right-hand side.** Not blank, not "TBD". The right-hand side may
  be a new import, a method call, an instruction ("construct X directly"), or `REMOVED` with a
  reason — but never nothing.
- **The map records what shipped, not what you meant to ship.** Build it from the library's real
  post-refactor surface, measured, and diff it against the real pre-refactor surface. See
  `jobs/write-the-map.md` §1.
- **A shim is removed last, and only after the consumer's tests are green on the new paths.**
  Removing it earlier converts a migration into an outage, and the outage lands in whichever
  consumer had not migrated yet — the one you did not know about.
- **Never re-add an environment-variable read to the library to make a migration easier.** That is
  the change the refactor was for. Hoisting it back in makes the library untestable again and the
  next migration bigger.

## Route

| You are | Read |
|---|---|
| Planning the refactor, building the map | `jobs/write-the-map.md` |
| Migrating a consumer repo against an existing map | `jobs/execute-the-migration.md` |
| Deciding what kind of row a change deserves | `references/change-classes.md` |
| Staring at an error mid-migration | `references/troubleshooting.md` |
| Writing the map document itself | `assets/migration-map-template.md` |

---

## Non-negotiables

1. **Group the map by destination domain, never alphabetically.** A consumer migrates one subject at
   a time — all the credential imports, then all the client-factory imports. An alphabetical map
   forces them to jump between unrelated parts of their own code and increases the chance a group is
   left half-done.
2. **Every removed module gets a row with a reason.** A "Completely Removed" table with a `Reason`
   column, not silence. Silence reads as an oversight, so the consumer files a bug and waits instead
   of adopting the replacement pattern.
3. **Extras before imports.** A consumer whose optional dependencies are not installed yet cannot
   distinguish "this import moved" from "this dependency is gone", and will migrate an import that
   was fine. Step order is in `jobs/execute-the-migration.md`.
4. **Environment reads move to the consumer's entry point before any import is rewritten.** Do it
   after, and every constructor you touch is missing an argument you have not resolved yet, so you
   rewrite the same call twice.
5. **Prove the absence, do not assert it.** Run `scripts/leftover_imports.sh` over the consumer with
   every old prefix. A grep you ran once by hand is not evidence, and the import you missed is
   always in the module nobody opens.
6. **A shim is a dated loan, not a feature.** Every backward-compatible re-export gets a row saying
   it exists and that it is temporary. A shim with no removal plan becomes the permanent public API,
   and then the refactor bought nothing.
7. **One old path, one new path.** If an old symbol legitimately splits into two, the map has two
   rows and each names the condition that selects it. A row that says "one of these two" makes the
   consumer choose without the information you had.

---

## Verification

```
bash scripts/leftover_imports.sh --root <consumer-repo> --prefix <old.module.path> --text
```

Repeat `--prefix` for every old top-level path in the map. `violations` must reach **0** before the
migration is called done, and the same command with no `--prefix` inventories every module the tree
imports, which is how you find the old paths in the first place.

The script is a **lexical** scan of import statements: it cannot see a module named only at run time
(`importlib`, a string in a config, a plugin registry). It says so in `degraded` on every run. Treat a
clean run as "no static import remains", never as "nothing references it".

---

## Index

| File | Answers |
|---|---|
| `jobs/write-the-map.md` | How to measure the old surface, group the rows, and decide what each row's right-hand side is |
| `jobs/execute-the-migration.md` | The five ordered steps a consumer applies, and what must be true before each |
| `references/change-classes.md` | The five classes of change a map has to express, and the row shape for each |
| `references/troubleshooting.md` | The errors a mid-migration consumer actually hits, with the cause and the fix |
| `assets/migration-map-template.md` | The document skeleton, plus a short worked example |
| `scripts/leftover_imports.sh` | Offline scan: leftover old imports, or an inventory of every module imported |

---

## What this does NOT do

- **It does not carry any real library's map.** A 400-row table from one refactor is data with a
  shelf life of one release; only its shape is reusable. `assets/migration-map-template.md` keeps a
  short worked example and nothing more.
- **It does not rewrite imports for you.** No codemod ships here. A mechanical rewrite that a human
  did not read is how a shim-backed old path gets "migrated" to itself.
- **It does not decide the refactor.** Whether `commons` should become five domain modules is an
  architecture question. This skill starts once that answer exists.
- **It does not resolve dynamic imports.** See the degradation note above. Where a consumer builds
  module names at run time, the map needs a prose row and the consumer needs a human.
