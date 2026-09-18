# Language idioms — ports, registries, Contexts, roots, no-`else`, per language

Exact syntax for every construct in `doctrine.md`, in **Python · TypeScript · Java · Go · C# · Rust**.
Copy these literally; they compile by inspection. One example throughout, matching `doctrine.md` §3–7:
the port `PriceSource` answers *"which price applies to this line item, for this customer, right
now?"*, resolvers live in `sources/`, the Context is `PricingContext`, the Null Object is `AbsentPrice`.
Roots follow `di-patterns.md` §6, contract suites `testing-contracts.md`.

## 1. The matrix

| | Port | Frozen Context | Registry | Totality mechanism | Mechanical no-`else` rule | "Implements" proof |
|---|---|---|---|---|---|---|
| **Python** | `typing.Protocol` (structural) or ABC | `@dataclass(frozen=True, slots=True)` | `MappingProxyType({...})` | `match` + `typing.assert_never`, checked by mypy/pyright | `ruff` **RET505-508**, **SIM108**; `pylint` **R1705**, **R1720** | none — a registration test |
| **TypeScript** | `interface` | `interface` with `readonly` + `Object.freeze` | `ReadonlyMap` | discriminated union + a `never` sink | `eslint` **no-else-return**; `unicorn/prefer-ternary` | `implements` clause |
| **Java** | `interface`, ≤3 methods | `record` | `EnumMap`, wrapped unmodifiable | **`sealed interface` + `switch` pattern match, no `default`** | none shipped — Sonar **S1126** + a custom PMD XPath rule | `implements` + `@Override` |
| **Go** | `interface` in the **consumer** package | plain `struct`, passed by value | `map[Kind]Port` built in the root | none in the compiler — `exhaustive` linter + registry test | `revive` **indent-error-flow**; `gocritic` **elseif**, **ifElseChain** | `var _ Port = (*Impl)(nil)` |
| **C#** | `interface` | `sealed record`, positional or `required init` | `FrozenDictionary` (.NET 8) | `switch` **expression** on an enum → **CS8509**, promoted to an error | Roslyn **IDE0045/IDE0046**; Sonar **S1126** | `: IPort` |
| **Rust** | `trait` | `struct`, immutable by default, no `&mut` accessor | `HashMap<Kind, Box<dyn Port>>` | **`match` exhaustiveness is compile error E0004** | `clippy::redundant_else`, `clippy::single_match_else` | `impl Port for T` |

The registry literal and an exhaustive `match` over a closed set are the **only** exemptions from the
zero-`else` cap (`SKILL.md`) — they are data. Where the compiler cannot prove totality, `Absent` plus
the registration test is the substitute, as a **build failure**. §9 is what makes each one real.

## 2. Python

```python
# pricing/price_source.py — the PORT, declared beside its caller (Separated Interface)
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Protocol, assert_never   # assert_never: 3.11+
class PriceSource(Protocol):
    """Which price applies to this line item, for this customer, right now?"""
    def price_for(self, ctx: "PricingContext") -> "Money": ...
# pricing/pricing_context.py — the frozen Context; copy with dataclasses.replace(ctx, sku=…)
@dataclass(frozen=True, slots=True)
class PricingContext:
    customer_id: CustomerId
    sku: Sku
    as_of: datetime          # never call the clock inside a resolver
    currency: Currency
    tenant: TenantId         # unused by every resolver today — deliberate headroom
# pricing/sources/contract_price.py — one resolver, one file; guard clause instead of else
class ContractPrice:
    def __init__(self, repo: ContractRepo) -> None:
        self._repo = repo
    def price_for(self, ctx: PricingContext) -> Money:
        agreed = self._repo.find(ctx.customer_id, ctx.sku, ctx.as_of)
        if agreed is None:
            raise PriceUnavailable(f"no contract for {ctx.sku}")
        return agreed.in_currency(ctx.currency)
# pricing/sources/absent_price.py — the Null Object that makes the resolver set total
class AbsentPrice:
    def price_for(self, ctx: PricingContext) -> Money:
        return Money.zero(ctx.currency)                  # neutral answer, never None
# pricing/price_registry.py — the selector: data, not control flow
class PriceRegistry:
    def __init__(self, sources: Mapping[PriceKind, PriceSource], absent: PriceSource) -> None:
        self._sources, self._absent = MappingProxyType(dict(sources)), absent
    def for_kind(self, kind: PriceKind) -> PriceSource:
        return self._sources.get(kind, self._absent)     # total: no else, no KeyError
# config_dependency_injection.py — THE ONE composition root for this deployable
def wire(env: Mapping[str, str]) -> Application:
    repo = PostgresContractRepo(dsn=env["PRICING_DSN"])  # a missing key fails at wire time
    sources = {PriceKind.LIST: ListPrice(),
               PriceKind.CONTRACT: CachedPrice(ContractPrice(repo), ttl_seconds=60)}
    return Application(PricingService(PriceRegistry(sources, AbsentPrice())))
# totality: end every match over a closed set with `assert_never(kind)` as the last statement —
# mypy/pyright then fail the build the moment a PriceKind member is added
```

## 3. TypeScript

```ts
// src/pricing/price-source.ts — the PORT
export interface PriceSource {
  /** Which price applies to this line item, for this customer, right now? */
  priceFor(ctx: PricingContext): Promise<Money>
}
// src/pricing/pricing-context.ts — readonly Context; copy with Object.freeze({ ...ctx, sku })
export interface PricingContext {
  readonly customerId: CustomerId
  readonly sku: Sku
  readonly asOf: Date          // never read the clock inside a resolver
  readonly currency: Currency
  readonly tenant: TenantId    // unused by every resolver today — deliberate headroom
}
// src/pricing/sources/contract-price.ts — one resolver, one file
export class ContractPrice implements PriceSource {
  constructor(private readonly repo: ContractRepo) {}
  async priceFor(ctx: PricingContext): Promise<Money> {
    const agreed = await this.repo.find(ctx.customerId, ctx.sku, ctx.asOf)
    if (!agreed) throw new PriceUnavailable(`no contract for ${ctx.sku}`)
    return agreed.inCurrency(ctx.currency)
  }
}
// src/pricing/sources/absent-price.ts — Null Object
export class AbsentPrice implements PriceSource {
  async priceFor(ctx: PricingContext): Promise<Money> { return Money.zero(ctx.currency) }
}
// src/pricing/price-registry.ts — the selector
export class PriceRegistry {
  constructor(private readonly sources: ReadonlyMap<PriceKind, PriceSource>,
              private readonly absent: PriceSource) {}
  forKind(kind: PriceKind): PriceSource { return this.sources.get(kind) ?? this.absent } // total
}
// src/config_dependency_injection.ts — the single composition root
export function wire(env: NodeJS.ProcessEnv): Application {
  const dsn = env.PRICING_DSN
  if (!dsn) throw new Error('PRICING_DSN is required')   // fail at wire time, not first call
  const sources: ReadonlyMap<PriceKind, PriceSource> = new Map([
    [PriceKind.List, new ListPrice()],
    [PriceKind.Contract, new ContractPrice(new PostgresContractRepo(dsn))],
  ])
  return new Application(new PricingService(new PriceRegistry(sources, new AbsentPrice())))
}
// src/pricing/price-outcome.ts — totality: a discriminated union plus a `never` sink
export type PriceOutcome =
  | { readonly kind: 'quoted'; readonly amount: Money }
  | { readonly kind: 'rejected'; readonly reason: string }
export const unreachable = (x: never): never => { throw new Error(`unhandled: ${String(x)}`) }
// the last arm of every switch over o.kind is then:  default: return unreachable(o)
```

## 4. Java

```java
// pricing/PriceSource.java — the PORT, ≤3 methods
public interface PriceSource {
    /** Which price applies to this line item, for this customer, right now? */
    Money priceFor(PricingContext ctx);            // throws PriceUnavailable, unchecked
}
// pricing/PricingContext.java — a record IS the frozen Context; copy via a with* method
public record PricingContext(CustomerId customerId, Sku sku,
        Instant asOf,          // never read the clock inside a resolver
        Currency currency,
        TenantId tenant) {}    // tenant: unused by every resolver today — deliberate headroom
// pricing/sources/ContractPrice.java — one resolver, one file; one ctor, no logic in it
public final class ContractPrice implements PriceSource {
    private final ContractRepo repo;
    public ContractPrice(ContractRepo repo) { this.repo = Objects.requireNonNull(repo); }
    @Override public Money priceFor(PricingContext ctx) {
        Optional<Agreement> agreed = repo.find(ctx.customerId(), ctx.sku(), ctx.asOf());
        if (agreed.isEmpty()) throw new PriceUnavailable("no contract for " + ctx.sku());
        return agreed.get().inCurrency(ctx.currency());
    }
}
// pricing/sources/AbsentPrice.java — Null Object
public final class AbsentPrice implements PriceSource {
    @Override public Money priceFor(PricingContext ctx) { return Money.zero(ctx.currency()); }
}
// pricing/PriceRegistry.java — EnumMap: the dense, array-backed selector
public record PriceRegistry(Map<PriceKind, PriceSource> sources, PriceSource absent) {
    public PriceRegistry {                     // compact ctor: defensive, unmodifiable copy
        sources = Collections.unmodifiableMap(new EnumMap<>(sources));
    }
    public PriceSource forKind(PriceKind kind) { return sources.getOrDefault(kind, absent); }
}
// PricingConfiguration.java — the composition root (a final class, or one @Configuration)
public static Application wire(Map<String, String> env) {
    var dsn = Objects.requireNonNull(env.get("PRICING_DSN"), "PRICING_DSN is required");
    var sources = new EnumMap<PriceKind, PriceSource>(PriceKind.class);
    sources.put(PriceKind.LIST, new ListPrice());
    sources.put(PriceKind.CONTRACT, new ContractPrice(new PostgresContractRepo(dsn)));
    return new Application(new PricingService(new PriceRegistry(sources, new AbsentPrice())));
}
public sealed interface PriceOutcome permits Quoted, Rejected {}   // records; totality below
static String describe(PriceOutcome outcome) {
    return switch (outcome) {                      // no default: the compiler proves totality
        case Quoted q   -> "quoted " + q.amount();
        case Rejected r -> "rejected: " + r.reason();
    };
}
```

## 5. Go

```go
// pricing/price_source.go — the PORT, declared in the CONSUMER package
package pricing
// PriceSource answers: which price applies to this line item, for this customer, right now?
type PriceSource interface{ PriceFor(ctx Context) (Money, error) }
// pricing/context.go — a value type: copied, never shared. Copy with c2 := c; c2.SKU = other.
type Context struct {
	CustomerID CustomerID
	SKU        SKU
	AsOf       time.Time // never call time.Now() inside a resolver
	Currency   Currency
	Tenant     TenantID // unused by every resolver today — deliberate headroom
}
// pricing/price_registry.go — the selector; the early return is why there is no else
type Registry struct {
	Sources map[PriceKind]PriceSource
	Absent  PriceSource
}
func (r Registry) ForKind(kind PriceKind) PriceSource {
	if s, ok := r.Sources[kind]; ok {
		return s
	}
	return r.Absent // total
}
// pricing/sources/contract_price.go — one resolver, one file (package sources)
var _ pricing.PriceSource = (*ContractPrice)(nil) // compile-time proof of implementation
type ContractPrice struct{ repo pricing.ContractRepo }
func NewContractPrice(r pricing.ContractRepo) *ContractPrice { return &ContractPrice{repo: r} }
func (p *ContractPrice) PriceFor(ctx pricing.Context) (pricing.Money, error) {
	agreed, err := p.repo.Find(ctx.CustomerID, ctx.SKU, ctx.AsOf)
	if err != nil {
		return pricing.Money{}, fmt.Errorf("find contract %s: %w", ctx.SKU, err)
	}
	return agreed.InCurrency(ctx.Currency)
}
// pricing/sources/absent_price.go — Null Object
type AbsentPrice struct{}
func (AbsentPrice) PriceFor(c pricing.Context) (pricing.Money, error) { return pricing.ZeroMoney(c.Currency), nil }
// cmd/pricing/main.go — the single composition root; main reads os.LookupEnv, passes dsn in
func wire(dsn string) (*Application, error) {
	repo, err := postgres.NewContractRepo(dsn)
	if err != nil {
		return nil, fmt.Errorf("contract repo: %w", err)
	}
	registry := pricing.Registry{
		Sources: map[pricing.PriceKind]pricing.PriceSource{
			pricing.KindList:     sources.NewListPrice(),
			pricing.KindContract: decorators.NewCached(sources.NewContractPrice(repo), time.Minute),
		},
		Absent: sources.AbsentPrice{},
	}
	return NewApplication(pricing.NewService(registry)), nil
}
```

## 6. C#

```csharp
// Pricing/IPriceSource.cs — the PORT
public interface IPriceSource
{
    /// <summary>Which price applies to this line item, for this customer, right now?</summary>
    Money PriceFor(PricingContext ctx);
}
// Pricing/PricingContext.cs — sealed record; copy with `ctx with { Sku = other }`. Past four
// positional members, switch to `public required T X { get; init; }` properties.
public sealed record PricingContext(CustomerId CustomerId, Sku Sku,
    DateTimeOffset AsOf,   // never read the clock in a resolver
    Currency Currency,
    TenantId? Tenant);     // unused by every resolver today — deliberate headroom
// Pricing/Sources/ContractPrice.cs — one resolver, one file (primary constructor, C# 12)
public sealed class ContractPrice(IContractRepo repo) : IPriceSource
{
    public Money PriceFor(PricingContext ctx)
    {
        var agreed = repo.Find(ctx.CustomerId, ctx.Sku, ctx.AsOf);
        if (agreed is null) throw new PriceUnavailable($"no contract for {ctx.Sku}");
        return agreed.InCurrency(ctx.Currency);
    }
}
// Pricing/Sources/AbsentPrice.cs — Null Object
public sealed class AbsentPrice : IPriceSource
{
    public Money PriceFor(PricingContext ctx) => Money.Zero(ctx.Currency);
}
// Pricing/PriceRegistry.cs — the selector
public sealed class PriceRegistry(IReadOnlyDictionary<PriceKind, IPriceSource> sources, IPriceSource absent)
{
    public IPriceSource ForKind(PriceKind kind) =>
        sources.TryGetValue(kind, out var source) ? source : absent;   // total
}
// CompositionRoot.cs — the only file naming concrete resolvers (static class CompositionRoot)
public static Application Wire(IConfiguration config)
{
    var dsn = config["PRICING_DSN"] ?? throw new InvalidOperationException("PRICING_DSN required");
    var sources = new Dictionary<PriceKind, IPriceSource>
    {
        [PriceKind.List]     = new ListPrice(),
        [PriceKind.Contract] = new ContractPrice(new PostgresContractRepo(dsn)),
    }.ToFrozenDictionary();                              // System.Collections.Frozen, .NET 8
    return new Application(new PricingService(new PriceRegistry(sources, new AbsentPrice())));
}
// totality: a switch EXPRESSION over a closed set; CS8509 fires on a missing case
static string Describe(PriceOutcome outcome) => outcome switch
{
    Quoted q   => $"quoted {q.Amount}",
    Rejected r => $"rejected: {r.Reason}",
    _          => throw new UnreachableException(),      // System.Diagnostics, .NET 7+
};
```

## 7. Rust

```rust
// src/pricing/price_source.rs — the PORT
pub trait PriceSource {
    /// Which price applies to this line item, for this customer, right now?
    fn price_for(&self, ctx: &PricingContext) -> Result<Money, PriceUnavailable>;
}
// src/pricing/pricing_context.rs — no &mut accessor anywhere; copy with
// PricingContext { sku: other, ..ctx.clone() }
#[derive(Clone, Debug, PartialEq)]
pub struct PricingContext {
    pub customer_id: CustomerId,
    pub sku: Sku,
    pub as_of: OffsetDateTime, // never read the clock inside a resolver
    pub currency: Currency,
    pub tenant: TenantId,      // unused by every resolver today — deliberate headroom
}
// src/pricing/sources/contract_price.rs — `let … else` IS the no-else early return
pub struct ContractPrice<R: ContractRepo> { repo: R }
impl<R: ContractRepo> ContractPrice<R> { pub fn new(repo: R) -> Self { Self { repo } } }
impl<R: ContractRepo> PriceSource for ContractPrice<R> {
    fn price_for(&self, ctx: &PricingContext) -> Result<Money, PriceUnavailable> {
        let Some(agreed) = self.repo.find(&ctx.customer_id, &ctx.sku, ctx.as_of) else {
            return Err(PriceUnavailable::NoContract(ctx.sku.clone()));
        };
        agreed.in_currency(ctx.currency)
    }
}
// src/pricing/sources/absent_price.rs — Null Object
pub struct AbsentPrice;
impl PriceSource for AbsentPrice {
    fn price_for(&self, c: &PricingContext) -> Result<Money, PriceUnavailable> { Ok(Money::zero(c.currency)) }
}
// src/pricing/price_registry.rs — a heterogeneous map needs dynamic dispatch
pub struct PriceRegistry {
    pub sources: HashMap<PriceKind, Box<dyn PriceSource>>,
    pub absent: Box<dyn PriceSource>,
}
impl PriceRegistry {
    pub fn for_kind(&self, kind: PriceKind) -> &dyn PriceSource {   // total, and not a branch
        self.sources.get(&kind).map_or(self.absent.as_ref(), |source| source.as_ref())
    }
}
// src/composition_root.rs — the single composition root
pub fn wire(dsn: &str) -> Result<Application, WireError> {
    let repo = PostgresContractRepo::connect(dsn)?;
    let sources = HashMap::from([
        (PriceKind::List, Box::new(ListPrice) as Box<dyn PriceSource>),
        (PriceKind::Contract, Box::new(ContractPrice::new(repo))),
    ]);
    let registry = PriceRegistry { sources, absent: Box::new(AbsentPrice) };
    Ok(Application::new(PricingService::new(registry)))
}
// totality is free: a missing variant is compile error E0004, "non-exhaustive patterns"
pub enum PriceOutcome { Quoted(Money), Rejected(String) }
pub fn describe(outcome: &PriceOutcome) -> String {
    match outcome {
        PriceOutcome::Quoted(amount) => format!("quoted {amount}"),
        PriceOutcome::Rejected(reason) => format!("rejected: {reason}"),
    }
}
```

**`doctrine.md` §10 applies with full force in Rust:** a closed case set with a growing operation set
already *is* the doctrine — never convert an exhaustive `match` into `dyn Trait` dispatch for a rule.

## 8. Cross-cutting rules that survive every language

1. **The port is declared where it is used**, never with its implementations — Separated Interface.
2. **One resolver per file**, subject + role + answer (`naming.md` §1), importing no sibling resolver.
3. **Every port ships an `Absent` resolver** returning the neutral value or raising the port's declared
   error type — never a bare `None`/`null`/`nil`, never a silent no-op (`patterns.md` §2.7).
4. **The registry is the only `match`/map over the discriminant**; the root is the only place naming
   concrete resolvers, opening connections, and deciding decorator order.
5. **Fail at wire time, not at first call.** Missing configuration raises inside `wire()`. Read tokens
   from the environment or sign the request — never generate a key or certificate in code.
6. **No clock, env var, global, or ambient context inside a resolver** — it is a Context field, put
   there by the caller (`di-patterns.md` §2).
7. **Where the compiler cannot prove totality, a test must** — the registration test, as a build
   failure (`testing-contracts.md` §5).

## 9. Enabling the mechanism — the switch each language needs flipped

| | Totality gate | No-`else` gate | The gotcha |
|---|---|---|---|
| **Python** | `assert_never(x)` as the last statement + mypy/pyright inside the oracle | `ruff` `RET505-508`, `SIM108` — **off by default**, add them to `select` | a `Protocol` has no closed subclass set; the checker is the only proof |
| **TypeScript** | `@typescript-eslint/switch-exhaustiveness-check` (type-aware) + `strict` | `no-else-return` | `default:` and `??` are not `else`; `caps.sh` does not count them |
| **Java** | `-Xlint:all -Werror`, so a non-exhaustive `switch` cannot be warned past | **nothing shipped** bans `else` — Sonar `S1126`, PMD `ConfusingTernary`, or a custom PMD XPath over `//IfStatement` with an else branch | `sealed` + record patterns are Java 17/21 |
| **Go** | `exhaustive` (in `golangci-lint`) + the registration test as a build failure | `revive indent-error-flow`, `gocritic elseif` / `ifElseChain` | the compiler checks nothing; `default:` returns `Absent`, never panics |
| **C#** | `<WarningsAsErrors>CS8509</WarningsAsErrors>` in the `.csproj`, or it is advice | Roslyn `IDE0046`/`IDE0045` raised to warnings in `.editorconfig`; Sonar `S1126` | property injection is Sonar `S6813` and `di-patterns.md` DI5 |
| **Rust** | free — E0004. Deny `clippy::wildcard_enum_match_arm` to keep it free | `clippy::redundant_else`, `clippy::single_match_else` — both `pedantic`, so list them in `[lints.clippy]` | `#[non_exhaustive]` on a foreign enum *forces* a wildcard arm |
