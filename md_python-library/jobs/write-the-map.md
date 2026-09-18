# Writing the map

Before a single consumer is edited. Output: one document, shaped like
`assets/migration-map-template.md`, that a consumer can migrate against without asking you anything.

## 1. Measure both surfaces

Never write the map from memory of the refactor. Measure.

**The old surface** — what consumers actually import today, at the pre-refactor commit:

```
bash scripts/leftover_imports.sh --root <library-checkout-at-old-commit> --text
bash scripts/leftover_imports.sh --root <consumer-repo> --text
```

The first tells you what the library exposed; the second tells you what is *used*, with counts. Both
matter and they differ: a module imported by no consumer still needs a row (there is always a
consumer you do not know about), and a module imported 60 times needs its row to be right.

**The new surface** — read the new packages' `__init__.py` export lists. Those exports *are* the
public API; anything a consumer has to reach past `__init__` for is a gap in the new design, not a
map row.

**Then reconcile.** Every symbol in the old surface gets exactly one row. A symbol with no row is the
defect this step exists to catch — it is the one that will be found by a consumer, at run time, in
whichever module nobody opens.

## 2. Group by destination, not by source

One section per **new** domain module: the credentials section, the client-factory section, the
cleanup section. Name the section after where things are going.

Two reasons, and the second is the one people miss:

1. A consumer migrates one subject at a time. Grouping by destination means one section is one
   coherent edit to their code.
2. It makes an over-broad destination visible. If one section holds thirty rows from four unrelated
   old modules, the new module is the old god-file with a better name, and you would rather learn
   that while writing the map than after publishing it.

Order the sections by how many consumer imports they cover, heaviest first. The consumer's first hour
should remove the most errors.

## 3. Decide each row's right-hand side

Five kinds, and the choice is not stylistic — it tells the consumer how much work the row is. The
shapes and the exact wording for each are in `references/change-classes.md`:

| Kind | Right-hand side looks like |
|---|---|
| Moved | a new import path |
| Renamed | a new import path with a different symbol name |
| Became a method | `<Class>.<method>(...)` — no import; the symbol is now behaviour on an instance |
| Became the consumer's job | an instruction: construct it directly, or implement a named protocol |
| Removed | `REMOVED` plus the reason, in the removed table |

A row whose right-hand side is a new import path is a five-second edit. A row whose right-hand side
is an instruction is an afternoon. Never write the second as if it were the first — a consumer who
budgets from the map's shape and finds an afternoon of injection work in row 40 stops trusting the
map.

## 4. The removed table

Separate from the moved rows, with two columns: `Old Module` and `Reason`. Reasons that are enough:

- the capability is banned now, and why (naming the ban is the point of the row),
- it was app-specific and belongs in the consumer,
- it was provider-specific — implement the named protocol instead,
- it was a god-file, split into per-domain models,
- the dependency it existed to wrap is no longer used by the library at all.

"Deleted" is not a reason. A consumer reading "deleted" opens a ticket; a consumer reading "env-var
checking is banned — the library no longer reads the environment" changes their entry point.

## 5. The shim rows

Where the old import path still works through a re-export, say so **in the section it belongs to**,
as a note under the table:

> The old `<old.package>.<module>` paths still work via backward-compatible shims. They re-export from
> the new locations. Migrate at your own pace; the shims will be removed.

A shim changes the consumer's priority for that whole section from "today" to "this quarter", and that
is information they cannot get any other way. Also state, in the same note, that the shim is temporary
— every shim with no stated end becomes the permanent API.

## 6. Before/after code pairs

One pair per **calling-pattern** change, not one per row. A row that only moves an import needs no
code; a row that turns a free function into a method on an injected instance needs exactly one pair,
and every other row in that class points at it.

Each pair is a `# BEFORE` block and an `# AFTER` block, complete enough to paste, with the values that
used to come from the environment marked as such:

```python
# BEFORE — standalone function, read its configuration from the environment
token = generate_token(room_name="<room>", identity="<id>")

# AFTER — construct once with explicit values, then call methods on it
generator = TokenGenerator(
    api_key="<api-key>",        # previously read from the environment
    api_secret="<api-secret>",  # previously read from the environment
    url="<service-url>",        # previously read from the environment
)
token = generator.generate_participant_token(room="<room>", identity="<id>")
```

Six to eight pairs covers a large refactor. Twenty means the map is documenting the library instead of
the migration.

## 7. Where the map lives

**In the library repo, in `documentation/`, committed — never at the repo root and never in a scratch
directory.** `documentation/migration-<old>-to-<new>.md`, named for the two versions it spans.

The map is **durable**: it records a decision (what moved where, and why) that outlives the run, and a
consumer will open it months after the refactor. That makes it the opposite of the measurements it was
built from — the `leftover_imports.sh` output is scratch, spent once the rows are written, and belongs
in `/tmp` or nowhere.

- **A `MIGRATION.md` dropped beside the `README.md` is the most expensive kind of litter**, because it
  looks official and nobody dares delete it after the migration is over. One documentation folder, one
  file per version pair, and the pair in the filename is what tells a reader which maps are historical.
- It ships with the major bump, in the same commit or the one before it:
  `docs(migration): map 1.x imports to 2.0`. `references/deploy-and-publish.md` §The version number.
- **Do not delete a superseded map.** A consumer three versions behind migrates through both.

## 8. Review the map before publishing

- [ ] Every symbol in the measured old surface has exactly one row
- [ ] No right-hand side is blank, "TBD", or "one of these two"
- [ ] Sections are named after destinations and ordered by consumer import count
- [ ] Every removed module has a reason a consumer can act on
- [ ] Every shim is named, scoped to its section, and marked temporary
- [ ] Every calling-pattern change has exactly one before/after pair
- [ ] The extras table lists which optional dependency set each feature needs
- [ ] `references/troubleshooting.md`'s error table is filled in for *this* refactor's errors
- [ ] The ordered procedure from `jobs/execute-the-migration.md` is included, or linked, at the top

The last item is the one that gets dropped. A map with no procedure gets applied top to bottom, which
is the one order guaranteed to break the consumer's app in the middle.
