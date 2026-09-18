# Contract-suite cookbook — layer 2, per language

One executable suite per port. Every resolver registered in it. **An unregistered resolver is a
build failure.** These are verified idioms, not sketches.

---

## Python — abstract base class + fixture override

```python
# tests/contracts/price_source_contract.py
import pytest
from decimal import Decimal

class PriceSourceContract:                      # NOT Test*-prefixed → never collected alone
    """Every PriceSource must satisfy this, unmodified."""

    def test_returns_money_in_context_currency(self, source, ctx):
        assert source.price_for(ctx).currency == ctx.currency

    def test_is_idempotent(self, source, ctx):
        assert source.price_for(ctx) == source.price_for(ctx)

    def test_never_returns_negative(self, source, ctx):
        assert source.price_for(ctx).amount >= Decimal(0)

    def test_absent_input_raises_the_port_error(self, source, empty_ctx):
        with pytest.raises(PriceUnavailable):       # same error type from EVERY resolver
            source.price_for(empty_ctx)


# tests/contracts/test_list_price.py
class TestListPrice(PriceSourceContract):
    @pytest.fixture
    def source(self): return ListPrice()

# tests/contracts/test_contract_price.py
class TestContractPrice(PriceSourceContract):
    @pytest.fixture
    def source(self, tmp_path): return ContractPrice(SqliteRepo(tmp_path / "c.db"))
```

**Verified gotcha:** `python_classes` defaults to `["Test"]` and matches by **prefix**, so a base
named `TestPriceSourceContract` *is* collected and runs without the subclass fixture. Two fixes:
the naming discipline above, or `__test__ = False` via a mixin:

```python
class NotATest:
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        cls.__test__ = NotATest not in cls.__bases__
```

Single-class parameterised variant:

```python
@pytest.fixture(params=[ListPrice, ContractPrice, AbsentPrice], ids=lambda c: c.__name__)
def source(request): return request.param()
```

Per-class matrices use `pytest_generate_tests(metafunc)` + `metafunc.parametrize(..., scope="class")`
over `metafunc.cls.scenarios`.

### Registration made unforgettable (Python)

```python
# tests/contracts/test_coverage.py
def test_every_resolver_has_a_contract_suite():
    import pricing.sources                                  # imports all resolver modules
    implementations = {c for c in _all_subclasses(PriceSourceBase)}
    covered = {cls_under_test(t) for t in _contract_subclasses(PriceSourceContract)}
    assert implementations == covered, f"unregistered resolvers: {implementations - covered}"
```

With `Protocol` ports there is no `__subclasses__`, so assert against the **registry** plus a
glob of `sources/*.py`:

```python
def test_registry_covers_every_resolver_file():
    files = {p.stem for p in Path("pricing/sources").glob("*.py")} - {"__init__"}
    registered = {type(r).__module__.rsplit(".", 1)[-1] for r in SOURCES.values()}
    assert files == registered | {"absent_price"}
```

### Property-based, inherited by every resolver

```python
from hypothesis import given, strategies as st

class PriceSourceContract:
    @given(ctx=pricing_contexts())
    def test_total_over_all_contexts(self, source, ctx):
        result = source.price_for(ctx)
        assert result.currency == ctx.currency
```

`hypothesis` CI note: when `CI` is set the `ci` profile activates — `derandomize=True`,
`deadline=None`, `database=None`. History properties use `RuleBasedStateMachine` with `Bundle`,
`@rule(target=…)`, `@initialize`, `@precondition`, `@invariant`; collect via
`TestFoo = FooMachine.TestCase`.

---

## TypeScript / JavaScript — an exported contract runner

Export the suite from the package that owns the **port**, so each resolver's spec is three lines.

```ts
// src/pricing/price-source.contract.ts
import { describe, beforeEach, it, expect } from 'vitest'   // or '@jest/globals'
import type { PriceSource } from './price-source'

export function runPriceSourceContract(name: string, make: () => PriceSource) {
  describe(`PriceSource contract: ${name}`, () => {
    let source: PriceSource
    beforeEach(() => { source = make() })

    it('returns money in the context currency', async () => {
      const ctx = aPricingContext({ currency: 'EUR' })
      expect((await source.priceFor(ctx)).currency).toBe('EUR')
    })

    it('is idempotent', async () => {
      const ctx = aPricingContext()
      expect(await source.priceFor(ctx)).toEqual(await source.priceFor(ctx))
    })

    it('throws PriceUnavailable for an empty context', async () => {
      await expect(source.priceFor(anEmptyContext())).rejects.toThrow(PriceUnavailable)
    })
  })
}
```

```ts
// src/pricing/sources/list-price.spec.ts
import { runPriceSourceContract } from '../price-source.contract'
runPriceSourceContract('ListPrice', () => new ListPrice())
```

Table form when you prefer one file:

```ts
describe.each([
  { impl: 'list',     make: () => new ListPrice() },
  { impl: 'contract', make: () => new ContractPrice(new InMemoryRepo()) },
  { impl: 'absent',   make: () => new AbsentPrice() },
])('PriceSource contract ($impl)', ({ make }) => { /* … */ })
```

Signatures: `describe.each(table)(name, fn, timeout)` plus the tagged-template form. `$variable`
interpolation cannot be mixed with printf tokens except `%%`; `%#` is 0-based index, `%$` is
1-based. **`test.for` and its `TestContext` second argument are Vitest-only** — do not write a
portable helper against it.

### Registration made unforgettable (TS)

```ts
// src/pricing/sources/registry.spec.ts
import { readdirSync } from 'node:fs'
import { SOURCES } from './index'

it('every resolver file is registered', () => {
  const files = readdirSync(__dirname)
    .filter(f => f.endsWith('.ts') && !f.endsWith('.spec.ts') && f !== 'index.ts')
    .map(f => f.replace(/\.ts$/, ''))
  expect(files.sort()).toEqual([...registeredFileNames(SOURCES)].sort())
})
```

Property-based, model-based (the strongest LSP tool available):

```ts
import fc from 'fast-check'
// run the SAME command list against EVERY resolver with the SAME model
await fc.assert(fc.asyncProperty(fc.commands(allCommands, { maxCommands: 50 }), async cmds => {
  await fc.asyncModelRun(() => ({ model: freshModel(), real: make() }), cmds)
}))
```

---

## Java / Kotlin — the contract as an interface with `@Test default` methods

This is the documented mechanism, not a hack.

```java
interface PriceSourceContract {
    PriceSource createSource();                       // each resolver supplies this

    @Test default void returnsMoneyInContextCurrency() {
        var ctx = aPricingContext().withCurrency(EUR).build();
        assertEquals(EUR, createSource().priceFor(ctx).currency());
    }
    @Test default void isIdempotent() {
        var ctx = aPricingContext().build();
        var s = createSource();
        assertEquals(s.priceFor(ctx), s.priceFor(ctx));
    }
    @Test default void emptyContextThrowsPortError() {
        assertThrows(PriceUnavailable.class, () -> createSource().priceFor(EMPTY));
    }
}

class ListPriceTests     implements PriceSourceContract { public PriceSource createSource(){ return new ListPrice(); } }
class ContractPriceTests implements PriceSourceContract { public PriceSource createSource(){ return new ContractPrice(new InMemoryRepo()); } }
```

`@Test`, `@RepeatedTest`, `@ParameterizedTest`, `@TestFactory`, `@TestTemplate`, `@BeforeEach`,
`@AfterEach` are all permitted on interface `default` methods; `@ExtendWith` and `@Tag` on the
interface are inherited. **Most-misremembered detail:** `@BeforeAll`/`@AfterAll` as a `default`
method requires `@TestInstance(Lifecycle.PER_CLASS)`; as a `static` interface method it does not.
Contracts compose — implement two contract interfaces on one test class.

Alternatives: `@ParameterizedTest @MethodSource` over `Stream<Arguments>` of
`named("ListPrice", (Supplier<PriceSource>) ListPrice::new)`; or `@TestFactory` returning
`Stream<DynamicNode>` — but **dynamic tests get no per-test `@BeforeEach`/`@AfterEach`**.
`@ParameterizedClass` + `@Parameter` is the closest analogue to pytest class parametrisation but
is **experimental** and incompatible with `PER_CLASS`.

**Docs URL warning:** the JUnit 5 user guide moved to
`docs.junit.org/<version>/writing-tests/test-interfaces-and-default-methods.html`. The old
`junit.org/junit5/docs/current/user-guide/writing-tests/*` paths 404.

### Registration made unforgettable (Java) — an ArchUnit rule

```java
@ArchTest
static final ArchRule every_resolver_has_a_contract_test =
    classes().that().implement(PriceSource.class).and().areNotInterfaces()
      .should(haveAContractTestImplementing(PriceSourceContract.class));
```

Kotlin: the same shape with a `sealed interface` port plus a `when` over all subclasses gives
compile-time totality; the contract interface then only needs behavioural properties.

---

## Go — a table over a constructor, exported from the port's package

```go
// pricing/pricecontract/contract.go   (exported so every resolver package can call it)
func RunPriceSourceContract(t *testing.T, newSource func(t *testing.T) pricing.PriceSource) {
    t.Helper()
    cases := []struct{ name string; ctx pricing.Context; wantErr error }{
        {"list price", listCtx(), nil},
        {"empty context", pricing.Context{}, pricing.ErrPriceUnavailable},
        {"unicode sku", ctxWithSKU("🔑-1"), nil},
    }
    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            got, err := newSource(t).PriceFor(tc.ctx)
            if !errors.Is(err, tc.wantErr) {
                t.Fatalf("PriceFor(%v) err = %v, want %v", tc.ctx, err, tc.wantErr)
            }
            if err == nil && got.Currency != tc.ctx.Currency {
                t.Errorf("currency = %q, want %q", got.Currency, tc.ctx.Currency)
            }
        })
    }
}
```

```go
// pricing/sources/list_price_test.go
func TestListPrice(t *testing.T) {
    pricecontract.RunPriceSourceContract(t, func(*testing.T) pricing.PriceSource { return NewListPrice() })
}
```

The map-keyed table variant is worth preferring where order-independence matters, precisely
because "map iteration order isn't specified" — it exposes inter-case ordering dependencies.
Loop-variable capture (`tc := tc`) is unnecessary from Go 1.22. The authority for the
exported-contract-package shape is the standard library itself: `testing/fstest.TestFS`,
`testing/iotest`.

### Registration made unforgettable (Go)

```go
func TestRegistryCoversEveryResolver(t *testing.T) {
    files, _ := filepath.Glob("*.go")
    want := map[string]bool{}
    for _, f := range files {
        if !strings.HasSuffix(f, "_test.go") && f != "registry.go" {
            want[strings.TrimSuffix(f, ".go")] = true
        }
    }
    for name := range want {
        if _, ok := Sources[name]; !ok {
            t.Errorf("resolver %s.go is not in the Sources registry", name)
        }
    }
}
```

Plus the compile-time assertion in every resolver file — cheap and catches drift instantly:

```go
var _ pricing.PriceSource = (*ListPrice)(nil)
```

---

## The universal rules

1. **The suite lives with the port**, never with a resolver. It is part of the port's definition.
2. **The suite is never edited to make a resolver pass.** If a resolver cannot pass it, either
   the resolver is wrong or it is not an implementation of that port — make it a different port.
3. **Every resolver, including fakes, in-memory doubles, and the `Absent` resolver, runs the
   suite.** A fake that skips the suite is how fidelity rots.
4. **The suite asserts the same error type** for the same violation from every resolver. Divergent
   error taxonomy is the most common silent LSP break.
5. **One coverage test asserts registry = resolver files.** This is the build failure that makes
   rule 3 real.
6. **Property-based properties live in the suite**, so every resolver inherits them for free.
7. **Never mock the subject at layer 2.** Every resolver runs for real; only its own secondary
   ports may be faked, and only with contract-verified fakes.
