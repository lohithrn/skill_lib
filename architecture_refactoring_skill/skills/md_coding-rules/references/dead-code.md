# Dead code, and the lexical/parser cleanup

Answers: *may I delete this, and what do I check first?*

Three rules: **16** (delete dead code), **17** (the dynamic-usage safelist that stops you), **18** (the
lexer/parser/tokenizer sweep, which is where dead code hides longest).

---

### 16. Remove dead code

Remove unused code instead of preserving it for the future.

Delete:

- Unused methods.
- Unused classes.
- Unused variables.
- Unused imports.
- Commented-out old logic.
- Duplicate implementations that are not wired or tested.
- Speculative future code.
- Unreachable branches.
- Obsolete adapters.
- Old parser paths.
- Unused lexical/tokenization logic.

Version control preserves history. The active codebase should preserve active truth.

**Consequence without it:** every reader pays to understand code that runs nowhere, and every
refactor pays to keep it compiling.

---

### 17. Be careful with apparently unused code

Before deleting code, check whether it may be used by:

- Dynamic imports.
- Framework hooks.
- Reflection.
- CLI entry points.
- Plugin systems.
- Configuration-driven execution.
- External callers.
- Tests.
- Generated code.
- Migration systems.

If usage cannot be confirmed, mark it as **suspicious** instead of deleting blindly.

**That ten-item list is a safelist, not advice.** Static absence of callers is not proof of absence of
callers. A deletion that passes the suite and breaks a config-driven dispatch in production is the
normal failure here, and it is not caught by the compiler.

---

## Lexical, parser, and tokenization cleanup

### 18. Clean up lexical logic

Review lexer, parser, tokenizer, grammar, and interpreter-related code carefully.

Look for:

- Dead token types.
- Unused token handlers.
- Unused parser branches.
- Duplicated parsing logic.
- Large conditional chains.
- Mixed tokenizer/parser responsibilities.
- Parser logic embedded in unrelated services.
- Old lexical code not connected to the active system.
- Speculative grammar support that is not used.

If lexical logic is still needed, separate responsibilities:

- Token model.
- Tokenizer interface.
- Tokenizer implementation.
- Parser interface.
- Parser implementation.
- Parse result model.
- Validator.
- Interpreter or dispatcher.

If lexical logic is no longer needed, remove it fully.

**Why this area gets its own rule:** a grammar accretes support for syntax that was never shipped, and
its dispatch is usually one long conditional chain over token kinds — so it accumulates both of the
problems this skill cares about at once (dead code, and behaviour-selection branching per rule 13 in
`references/doctrine.md`). "Remove it fully" means the token type, its handler, its parser branch and
its tests, not just the call site.
