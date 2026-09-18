# The errors a mid-migration consumer hits

Five errors cover almost everything. Four of the five are a step-order mistake in
`jobs/execute-the-migration.md`, not a defect in the map — check this table before concluding the map
is wrong.

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named '<third-party>'` | Using a feature whose dependency is now an **extra**, without installing that extra | Install the extra the map's extras table names for that feature. Step 1, and it is first for exactly this reason |
| `ImportError: cannot import name 'X' from '<pkg>.commons'` | An old import path. `commons` was split into domain modules | Find `X` in the map. If it is not there, the map is incomplete — that is a map bug, report it rather than guessing a new path |
| `TypeError: __init__() missing required argument` | The class now requires explicit configuration instead of reading the environment | Pass the value that used to come from `os.getenv(...)`. If you do not know which one, you skipped step 2 |
| `AttributeError: '<WiredServices>' has no attribute 'X'` | A field on the composition root's result was renamed | Read the wired-services struct's own field list. Do not re-add the old name as an alias |
| `RuntimeError` naming two model or version ids | An artifact was built with one model and is being read with another — not a migration error at all | See the `md_library-lifecycle` skill: the build-time and query-time ids must be equal |

## Errors that mean the map is wrong, not the consumer

Three of them, and each is worth a fix to the map rather than an answer to the consumer:

- **A symbol raises `ImportError` and appears in no row.** The map is incomplete. Add the row, and
  re-run the old-surface measurement from `jobs/write-the-map.md` §1 — a missing symbol is rarely
  alone.
- **A row's new path also raises `ImportError`.** The map records a name that was planned, not the name
  that shipped. Re-measure against the new packages' export lists.
- **Two rows send one old symbol to two different new paths with no condition stated.** The consumer
  cannot choose. Add the condition to both rows or delete one.

## Errors the scanner cannot help with

`scripts/leftover_imports.sh` finds static import statements. It reports its own blindness in
`degraded` on every run, and these are the cases behind that note:

| Pattern | Why it is invisible | What to do |
|---|---|---|
| `importlib.import_module(name)` where `name` is built at run time | The module path is not in the source as a literal | Grep for the old path as a **string**, not as an import |
| A plugin or entry-point registry keyed by dotted path | Same: the path is data, in a config file or a table | Search the configuration, and the database if the registry is stored |
| A module path inside a serialized object or a stored record | The path outlives the code | Migrate the stored data, or keep the shim until it is drained |

The third is the only legitimate reason to keep a shim past the migration, and it must be recorded with
what is still holding the old path — not left in place because removing it felt risky.

## What "done" means

- Every old prefix in the map scans to **0** violations across the consumer.
- The consumer's tests pass on the new import paths, with the shims removed.
- Every `degraded` note from the last scan was read and the dynamic cases were checked by hand.
- No row in the map is still blank, and no error above is still open.

Anything less is a migration in progress, and calling it done is how the second half never happens.
