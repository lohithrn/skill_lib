# Naming — the path is the documentation

In this doctrine the folder tree **is** the dependency graph, so a path is not decoration: it is the
node label. A reader who cannot infer a file's role from its path cannot read the graph.

**The test: the file name must still be unambiguous when seen alone** — in an editor tab, an import
line, a `grep` result, a stack frame, a PR diff header. The folder supplies context, but the name
must not *depend* on it.

---

## 1. Every path names three things

| Part | Question it answers | Example |
|---|---|---|
| **subject** | which domain concept? | `payment`, `order`, `token` |
| **role** | which architectural position? | `interface`, `processor`, `repository`, `validator`, `parser`, `context`, `registry` |
| **answer** | which of the several possible? | `stripe`, `paypal`, `postgres`, `absent`, `cached` |

```
payment/
  interfaces/
    payment_processor_interface.py      subject+role  — the port
  processors/
    stripe_payment_processor.py         answer+subject+role
    paypal_payment_processor.py
    absent_payment_processor.py         the Null resolver — total set, no else
```

Not this:

```
payment/
  interfaces/processor.py               role only. "processor" of what?
  processors/stripe.py                  answer only. a stack frame says `stripe.py:41` — of what?
```

The second tree reads fine *in the tree*. It reads as nothing in a traceback, and a traceback is
where you need it most.

Accepted shapes: `subject_role` · `answer_subject_role` · `subject_action` · `action_subject` ·
`provider_subject_role` · `subject_context`.

---

## 2. Banned names

As a **file** name or a **folder** name, these carry no information:

`utils` · `helpers` · `common` · `misc` · `shared` · `lib` · `core` · `base` · `logic` ·
`manager` · `handler` (alone) · `service` (alone) · `processor` (alone) · `data` · `models` (as a
dumping ground) · `impl` · `stuff` · `temp` · `new_*` · `*_v2` · `*_old` · `*_final`

**The `utils` reconciliation.** The doctrine requires a pure sink node — zero project imports, no
I/O, a leaf in the graph (`doctrine.md` §8). That requirement is about *edges*, not about the word.
A sink node must still be named for its concept:

| Instead of | Use |
|---|---|
| `utils/date_utils.py` | `time/clock_arithmetic.py` |
| `utils/string_helpers.py` | `text/slug_formatting.py` |
| `common/money.py` | `money/money.py` (a Value Object, not a util) |
| `helpers/validation.py` | one validator per rule, under `validation/` |

If you cannot name the concept, the file has no concept — it has accumulation. Split it by the
concepts inside, and delete what nothing imports (`dead-code.md`).

**`base`** is a special case: it almost always marks a hierarchy that should be an interface plus
composition. `BaseService` inherited by nine concrete services is the implementation-inheritance
smell (`laws.md`, Refused Bequest). Name the port for the question, not `Base*`.

---

## 3. Naming the port — as a question

A port exists because a question has several answers. Its name should be the question's noun form,
and its **docstring is the question in the user's words**.

| Conflict | Port | Method | Docstring |
|---|---|---|---|
| which discount for this tier? | `DiscountPolicy` | `discount_for(ctx)` | "Which discount applies to this customer's tier, for this subtotal, right now?" |
| where do orders live? | `OrderRepository` | `find(ctx)` | "Where is this order stored, and how is it retrieved?" |
| how is this charged? | `PaymentProcessor` | `charge(ctx)` | "Which provider settles this payment?" |

Rules:

- Name the port for **the question**, never for the first answer. `StripeGateway` as an interface
  name means the abstraction is Stripe-shaped and the second resolver will not fit.
- Never name it for the number of implementations (`ISingleProcessor`) or its own genericity
  (`AbstractGenericHandlerBase`).
- Hungarian `I`-prefixes: follow the language, not a preference. C#/TS codebases commonly use
  `IPaymentProcessor`; Python (`Protocol`), Java, and Go do not. **Match the repo.** A rename purely
  to change convention is churn, and churn is not a finding.
- Go inverts the emphasis by convention: small, consumer-side, often single-method interfaces named
  for the behaviour — `PriceFetcher`, `Charger` — declared next to the caller. That *is* Separated
  Interface, done idiomatically. Do not rename Go interfaces to `*Interface`.
- **Method names take the Context, so they need no argument-describing suffix.**
  `discount_for(ctx)`, not `calculate_discount_for_tier_and_subtotal(tier, subtotal)`.

---

## 4. Naming resolvers, contexts, registries, roots

| Node | Convention | Example |
|---|---|---|
| resolver | `<answer>_<subject>_<role>` | `gold_discount_policy.py` |
| Null / absent resolver | `absent_` or `no_` prefix — never `default_` | `absent_discount_policy.py` |
| decorator resolver | the **policy** first | `cached_price_source.py`, `retrying_payment_processor.py` |
| fake/stub for tests | `fake_`, `in_memory_`, `failing_` | `in_memory_order_repository.py`, `failing_payment_processor.py` |
| Context | `<subject>_context` | `billing_context.py` |
| registry | `<subject>_<role>_registry`, or the package `__init__` | `payment_processor_registry.py` |
| composition root | `config_dependency_injection.py` | class `ConfigDependencyInjection` |
| contract suite | `<subject>_<role>_contract` | `payment_processor_contract.py` |
| fitness test | `test_<claim>` under `tests/fitness/` | `test_no_cycles.py` |

`default_*` is banned as a resolver name for a real reason: it hides *which* answer it is. When the
fourth tier arrives, "default" is ambiguous between "the neutral one" and "the common one". Name the
neutral one `absent_`/`no_` and the common one for its actual case (`standard_`).

---

## 5. Naming methods

- **Public methods say what**, private methods say **how**. A class reads top-down: one public
  orchestration method, then the private steps it calls, in call order.
- Extracted methods must **name the responsibility**, not the mechanics. `_validate_tier(ctx)`,
  `_apply_rounding(amount)` — never `_do_stuff`, `_handle`, `_process`, `_step2`, `_helper`,
  `_finalize`, `_execute`, `_run_logic`.
- **A meaningless extraction is worse than the nesting it removed.** If you cannot name the
  extracted block, you have not found a responsibility — reconsider the seam. That is the one
  legitimate reason to leave a method at the warn threshold.
- Boolean-returning methods read as predicates: `is_`, `has_`, `can_`, `should_`. A boolean
  *parameter* is a conflict, not a name problem — promote it (`doctrine.md` §1, C4).
- One verb per concept across the codebase. `fetch`/`get`/`load`/`retrieve` used interchangeably for
  the same operation is **connascence of meaning** (`laws.md` §D) — the reader has to learn four
  words for one idea.
- Loop bodies extracted per the 8-line rule are named for the **per-item** behaviour:
  `_map_token(token)`, `_dispatch_event(event)`. The loop then shows repetition and nothing else.

---

## 6. Renaming safely

A rename is a real change with a real blast radius. It is never bundled with a refactor.

1. **One slice, renames only.** Never mix a rename with an extraction — a reviewer cannot see
   whether behaviour moved.
2. **Use the tool, not sed.** IDE refactor, `libcst`/`rope`, `ts-morph`, OpenRewrite, `gorename`.
   A regex rename silently edits strings, comments, and unrelated identifiers.
3. **Then grep for the string form.** Dynamic imports, `getattr`, DI keys, config files, template
   names, serialised class names, log-based alerts, and dashboard queries hold the old name as a
   *string* and no refactoring tool will find them. This is `dead-code.md` §2 in reverse.
4. **Public API and file paths in a published package are a breaking change.** Keep an alias with a
   deprecation for one release, or say in the spec that it breaks.
5. **`git mv`, one file per commit,** so history follows. A rename plus an edit in one commit defeats
   `--follow` and blame.
6. **Renames that are only about convention are churn.** Only rename when the current name is
   actively wrong, ambiguous in a stack trace, or on the banned list.

---

## 7. Detection — what the `name` dimension measures

| ID | Rule | Severity |
|---|---|---|
| N1 | a file or folder on the banned list (§2) | major if it is a folder with >3 files, else minor |
| N2 | a file name that is only a role (`handler.py`) or only an answer (`stripe.py`) | minor, batched |
| N3 | a port named after its first implementation | **major** — the abstraction is provider-shaped |
| N4 | a resolver named `default_*` | minor |
| N5 | an extracted method named `_process`/`_handle`/`_do_*`/`_step*` | minor |
| N6 | four names for one operation across the codebase (connascence of meaning) | major |
| N7 | `Base*`/`Abstract*` class inherited by ≥3 concretes with shared state | **major** — see `laws.md` |
| N8 | `*_v2`, `*_old`, `*_new`, `*_final`, `*_copy` | **major** — this is a dead-code signal, cross-check `dead-code.md` |

**Not findings.** The repo's own established convention, applied consistently — even if this file
would have chosen differently. Idiomatic short names in a small, local scope (`i`, `err`, `ctx`,
`_`). Test files named for the unit under test. Framework-mandated names (`__init__.py`,
`conftest.py`, `page.tsx`, `main.go`, `AppModule`). Language-idiomatic brevity in Go. **Report a
naming finding only when the name would mislead a reader who sees it alone** — that is the whole
standard, and "I would have named it differently" does not meet it.
