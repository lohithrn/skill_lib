# The five classes of change a map must express

A migration map is not a list of renames. Five different things happen to a symbol in a refactor of
this kind, they cost the consumer wildly different amounts of work, and the row must say which one it
is. Getting the class right is what makes the map's shape a usable estimate.

| Class | Right-hand side | Consumer cost | Row shape |
|---|---|---|---|
| **Moved** | a new import path | seconds | `from <new.module> import <SameName>` |
| **Renamed** | a new path, a new symbol | seconds, plus one search | `from <new.module> import <NewName>` |
| **Became a method** | no import at all | minutes per call site | `<Class>.<method>(...)` |
| **Became the consumer's job** | an instruction | an afternoon | `Construct <Class> directly (no environment reads)` / `Implement the <Name> protocol in your app` |
| **Removed** | `REMOVED` + reason | varies; sometimes zero | a row in the removed table |

Never write the third, fourth or fifth as if it were the first. A consumer who reads a table of import
paths, budgets an hour, and hits an injection rewrite in row 40 will stop reading the map and start
guessing — and every consumer guesses differently.

## Class 3 in detail — became a method

The dominant class in a dependency-injection refactor. The old symbol was a module-level function that
resolved its own configuration; the new symbol is a method on a class the consumer constructs.

The row names the method, not the module:

```
| from <old.module> import <old_function>  |  <Class>.<new_method>(...)                  |
| from <old.module> import <resolve_fn>    |  Constructor injection on <Class>           |
```

The second row is the one to notice: a *resolver* function usually has no replacement at all, because
resolving is what the constructor now does. Say "constructor injection on `<Class>`" rather than
leaving it blank, and point at the before/after pair.

## Class 4 in detail — became the consumer's job

Two sub-shapes, and they are different work:

- **Construct it directly.** The old factory function (`get_<thing>()`, `get_<thing>_with_<options>()`)
  is gone because it existed only to read configuration. The row says `Construct <Class> directly`,
  and, where the arguments are not obvious, spells the signature:
  `<Class>(table_name, resource, tenant, group)`.
- **Implement a protocol.** A provider-specific integration left the library. The row says
  `Implement the <Name> protocol in your app` and the before/after pair shows the two methods the
  protocol needs. This is the most expensive row type in any map; it deserves its own pair even if it
  is the only row in its class.

## The five behavioural changes to state once, at the top

These are properties of the whole refactor, not of any row. State them once, above the tables, or
every reader re-derives them from forty rows.

1. **No environment variables.** Every value that was `os.getenv(...)` is now a constructor parameter.
   The consumer's entry point resolves the environment and passes values in. *Consequence:* the
   library becomes testable without a process environment, and a misconfiguration fails at startup
   instead of on the first call that needed it.
2. **No free-form dicts in public APIs.** Every method input and output is a frozen dataclass.
   *Consequence:* editor autocomplete works, and a typo in a key is a construction error instead of a
   silent `None`.
3. **Constructor injection everywhere.** Nothing creates its own dependencies — credential stores,
   client factories, bucket names all arrive through constructors. *Consequence:* one place in the app
   decides what the real dependencies are, so a test can substitute them without patching imports.
4. **Null-object implementations for testing.** A `noop` module ships `NoOp...` implementations of each
   public port. *Consequence:* consumers stop hand-writing mocks that drift from the interface, which
   is how a test suite stays green against a signature that changed.
5. **Backward-compatible shims where they exist.** Some old import paths still work as re-exports.
   *Consequence:* the migration can be staged instead of atomic — but a shim with no removal date
   becomes the permanent public API, so every shim row says it is temporary.

## Rows that are not import rows

Three right-hand sides that look wrong but are correct, and each needs its reason on the row:

| Right-hand side | When it is correct |
|---|---|
| `Use the standard library directly` | The old helper wrapped something the standard library already does well (an async utility, a thread-safe container). Name the stdlib module |
| `REMOVED (<capability> is banned)` | The capability itself is disallowed now. The row is where the ban gets communicated, so name the ban, not just the deletion |
| `Split into per-domain models` | The old symbol was a god-file of constants or types. Point at the new folder, and let the consumer's import errors lead them to the specific model |

The last of these is the only row type allowed to be imprecise, and only because a god-file's contents
are not a public API worth enumerating. Every other row names a destination exactly.

## Dependency changes belong in the map too

A dependency that stopped being bundled is a migration row, not a footnote: the consumer's install
breaks before any import does. Give the extras their own small table — feature, extra, what fails
without it — and put it above the import tables, matching step 1 of
`jobs/execute-the-migration.md`. A removed dependency (`REMOVED — the library no longer reads the
environment, so the dotenv loader is gone`) goes in the removed table with the others.
