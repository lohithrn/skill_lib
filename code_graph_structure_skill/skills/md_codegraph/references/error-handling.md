# Errors, tracebacks, and resilience

The doctrine applied to failure. A `try/except` with a real alternative **is a conflict** — it
belongs in a port. A `try/except` that only reports **is a boundary** — it belongs at the edge, and
it must carry the stack.

**The one rule everything here serves: no failure disappears.** Every caught exception either logs
a full traceback or re-raises with the cause attached. Both is allowed. Neither is a **blocker**.

---

## 1. The five things a catch block may do

There are exactly five legitimate outcomes. Anything else is a finding.

| # | Outcome | When | Must also |
|---|---|---|---|
| 1 | **Re-raise, wrapped** | you can add context the caller lacks | preserve the cause (`from e`, `{cause}`, `%w`, `new E(msg, e)`) |
| 2 | **Translate to a domain error** | crossing an adapter boundary inward | preserve the cause; the port declares the domain error type |
| 3 | **Log with traceback, then re-raise** | at a layer that owns the diagnostic context | log **once** — see §4 |
| 4 | **Log with traceback, then return a fallback** | you have a real alternative | the alternative is a **resolver**, not an inline branch (§6) |
| 5 | **Log with traceback and stop** | only at the error boundary (§5) | the process exit code / HTTP status reflects it |

**Never:** swallow silently · log without the stack · catch the base exception type to keep going ·
`return None` on failure so the caller re-discovers the problem three frames later · assert as
control flow in production.

---

## 2. Per-language: how to get the stack into the log

The single most common defect this skill finds is a log line that names the error but drops the
traceback. `str(e)` is not a traceback.

### Python

```python
# CORRECT — logger.exception attaches the active traceback. Only valid inside `except`.
except PaymentDeclined as e:
    logger.exception("charge failed: order=%s amount=%s", ctx.order_id, ctx.amount)
    raise ChargeUnavailable(f"order {ctx.order_id}") from e     # chains __cause__

# ALSO CORRECT — outside an except block, or on a non-current exception:
logger.error("charge failed", exc_info=e, extra={"order": ctx.order_id})

# WRONG
logger.error(f"charge failed: {e}")            # no stack, and pre-formatted
logger.error("charge failed", e)               # `e` becomes a %-arg, not exc_info
raise ChargeUnavailable(...)                   # bare raise inside except: loses __cause__
except Exception: pass                         # blocker
```

- `logger.exception(...)` == `logger.error(..., exc_info=True)`. Use it; it is shorter and harder
  to get wrong.
- `raise X from e` sets `__cause__` → "The above exception was the direct cause". A bare `raise X`
  inside an `except` sets `__context__` instead → "During handling… another exception occurred".
  Both print, but only `from e` states intent. **Always be explicit**, including `raise X from None`
  when you deliberately hide an internal cause.
- Lazy `%s` args, never f-strings, in log calls — the format cost is skipped when the level is off,
  and structured backends can index the fields.
- `traceback.format_exc()` only when you must put the trace in a non-logger sink (a response body
  in a dev mode, a crash file). Never as a substitute for `logger.exception`.
- Threads and tasks: `concurrent.futures` swallows the exception into the `Future` — someone must
  call `.result()`. For `asyncio`, `gather(..., return_exceptions=True)` turns failures into return
  values that are trivially ignored; if you use it, assert on the results. Install
  `sys.excepthook` / `loop.set_exception_handler` at the composition root so nothing dies quietly.
- `contextlib.suppress(SpecificError)` is acceptable and self-documenting where the exception
  genuinely carries no information. `except Exception: pass` never is.

### TypeScript / JavaScript

```ts
// CORRECT — Error.cause (ES2022) is the chain; the stack is on the Error, so log the Error.
} catch (e) {
  logger.error({ err: e, orderId: ctx.orderId }, "charge failed");   // pino: `err` serialises .stack
  throw new ChargeUnavailable(`order ${ctx.orderId}`, { cause: e });
}

// WRONG
logger.error(`charge failed: ${e}`)     // "Error: boom" — stack gone
catch (e) { }                           // blocker
catch (e) { return null }               // blocker unless a resolver owns the fallback
```

- `catch (e)` is typed `unknown`. Narrow with `e instanceof Error`, and for anything else log
  `String(e)` **plus** a synthetic `new Error()` stack so the site is recoverable — non-Error
  throws have no stack at all.
- `{ cause: e }` is the second constructor arg, and it must be forwarded by every custom error
  subclass: `constructor(msg: string, opts?: ErrorOptions) { super(msg, opts) }`. A subclass that
  drops `opts` silently breaks the whole chain.
- Log the error **object**, not a string. `pino` serialises `err`, `winston` needs the error in the
  message position or `{ stack }` explicitly. Verify your logger prints `.stack` — many do not by
  default.
- `Promise.allSettled` and floating promises are this ecosystem's silent-failure engine. Add
  `process.on('unhandledRejection')` **and** `uncaughtException` at the composition root; both
  should log with the stack and exit non-zero.
- `async` in a `forEach` callback returns a promise nobody awaits. Use `for…of` with `await`, or
  `Promise.all(map(...))`.

### Java / Kotlin

```java
// CORRECT — SLF4J's (String, Throwable) overload prints the stack. The throwable goes LAST,
// and it is NOT a {} placeholder argument.
} catch (SQLException e) {
    log.error("charge failed: order={} amount={}", ctx.orderId(), ctx.amount(), e);
    throw new ChargeUnavailableException("order " + ctx.orderId(), e);   // cause in the ctor
}

// WRONG
log.error("charge failed: " + e.getMessage());   // no stack
log.error("charge failed {}", e);                // e formatted as a message, stack dropped
e.printStackTrace();                             // bypasses the logging config; unroutable
catch (Exception e) { }                          // blocker
```

- SLF4J: a trailing `Throwable` beyond the placeholder count is treated as the exception, not an
  argument. That asymmetry is the single most common misuse — the placeholder count must match the
  *non-throwable* args exactly.
- Every custom exception needs the `(String, Throwable)` constructor and callers must use it.
  `initCause` is the retrofit; prefer the constructor.
- **Never `printStackTrace()`** — it writes to `System.err`, ignores appenders, and is invisible in
  aggregated logs.
- `InterruptedException`: restore the flag (`Thread.currentThread().interrupt()`) before returning,
  or the cancellation is lost.
- Kotlin: coroutine failures cancel the parent scope; a `SupervisorJob` plus a
  `CoroutineExceptionHandler` at the composition root is the boundary. `runCatching` returns a
  `Result` that is easy to discard — treat an unexamined `Result` like an ignored `err`.
- `try`-with-resources over manual `finally`: it records suppressed exceptions rather than losing
  the primary failure to a failing `close()`.

### Go

```go
// CORRECT — %w wraps so errors.Is/As work; the log carries the chain plus the site.
if err != nil {
    return fmt.Errorf("charge order %s: %w", ctx.OrderID, err)
}

// At the boundary only, where the chain stops:
if err != nil {
    slog.Error("charge failed", "order", ctx.OrderID, "err", err,
        "stack", string(debug.Stack()))
    return
}

// WRONG
if err != nil { return err }                       // no context added; useless chain
fmt.Errorf("charge failed: %v", err)               // %v flattens: errors.Is/As stop working
_ = doThing()                                      // ignored error
if err != nil { log.Printf("%v", err); }           // logged AND swallowed
```

- Go has no exceptions and no automatic stack. `%w` builds the chain; `errors.Is` compares sentinel
  values, `errors.As` extracts typed errors. `%v` breaks both — that is why `%w` is not cosmetic.
- Wrap with the **operation**, not with "error": `fmt.Errorf("load config %s: %w", path, err)`.
  Message fragments concatenate into a readable trace as the error rises.
- For a real stack, capture at the origin: `runtime/debug.Stack()` at the boundary, or a wrapper
  library that records a stack at creation. Decide once, at the composition root.
- `defer func(){ if r := recover(); r != nil { … } }()` belongs **only** in a top-level handler
  (server middleware, goroutine wrapper) and must log `r` **and** `debug.Stack()`, then fail the
  request. `recover()` used for flow control is a blocker.
- **Every goroutine needs its own recover.** A panic in a bare `go func()` kills the process with
  no attribution. Wrap goroutine spawning in one utility that recovers and logs.
- `errcheck` / `ineffassign` / `govet` catch ignored errors mechanically. Wire them into the oracle.

---

## 3. Which exception type

| Layer | Raises | Never raises |
|---|---|---|
| common utils | nothing but `ValueError`-class programmer errors | domain or infra types |
| resolver | the **port's declared error type**, only | a driver/library type |
| adapter | translates the library error to a domain type at its own boundary | leaks `psycopg2.Error`, `AxiosError`, `SQLException` upward |
| composition root | nothing; it is the boundary that reports | — |

**All resolvers behind one port must fail with the same type.** If `StripeProcessor` raises
`HTTPError` and `PaypalProcessor` raises `PaypalFault`, the port has not abstracted anything and
every caller needs an `if` — a Liskov breach the contract suite must catch. Assert it there:
*"every resolver raises `ChargeUnavailable`, and nothing else, for an unprocessable ctx."*

Distinguish, and never merge:

- **Programmer error** (a bug: `None` where a value was required, an unregistered key) → fail
  loudly, do not retry, do not catch.
- **Expected operational failure** (network, disk, quota, malformed input) → a declared error type,
  retryable, and its handling is a design decision that belongs in a port.

Prefer **making the failure unrepresentable** over handling it: parse at the boundary, so inner
layers cannot receive the invalid state. See `architecture.md` §3.

---

## 4. Log once, at the layer that owns the context

The second most common defect is the same failure logged at five depths, so the log reads like five
incidents.

**Rule: whoever handles it logs it. Whoever re-raises adds context and stays silent.**

- Wrapping with context (`%w`, `from e`, `new E(msg, {cause})`) is how a lower layer contributes to
  the eventual single log line. That is not a substitute for logging — it is the alternative to it.
- Log at the error boundary (§5), and at any layer that *recovers* — because recovering means no
  one above will ever see it.
- Every log line at ERROR carries: the operation, the identifiers needed to find the record, the
  outcome, and the stack. No message consisting only of `"error"`, `"failed"`, or `str(e)`.
- Never log a secret, token, password, key, full card number, or raw request body. Redact at the
  logger, not at each call site — a per-call-site rule is a rule that leaks.
- Level discipline: **ERROR** = a request/job failed · **WARN** = degraded but served · **INFO** =
  a business event · **DEBUG** = developer detail. A retry that eventually succeeds is WARN, not
  ERROR; an ERROR count that does not match the incident count is a broken signal.

---

## 5. The error boundary is a composition-root concern

One place per deployable turns an exception into an outcome. It is wired at the composition root
and is the only place that catches broadly.

| Deployable | Boundary |
|---|---|
| HTTP service | one middleware / exception handler → status code + correlation id in the body, stack in the log only |
| CLI | `main` wrapper → stderr message + non-zero exit; `--debug` adds the stack to stderr |
| worker / consumer | per-message handler → ack vs nack vs dead-letter, with the attempt count |
| scheduled job | wrapper → exit code, plus a metric so a silent failure is visible |
| goroutine / thread / task | a spawn utility that recovers, logs the stack, and reports |

The boundary is a **Humble Object**: it decides nothing about the domain, so it needs no unit test
beyond "unhandled error becomes a 500 and is logged with a stack".

Also at the root, not scattered: the global hooks. `sys.excepthook` and
`loop.set_exception_handler` · `unhandledRejection` + `uncaughtException` ·
`Thread.setDefaultUncaughtExceptionHandler` · the goroutine wrapper. Missing global hooks is a
finding: it means an entire class of failure never reaches the log.

---

## 6. Resilience is a decorator, never an `if`

Retry, timeout, circuit breaker, bulkhead, fallback, cache — every one of them wraps a port and
implements the same port. They compose, they are individually testable, and they keep the
resolvers ignorant of policy.

```
root: PaymentProcessor = Retry(Timeout(CircuitBreaker(StripeProcessor(http)), 2s), attempts=3)
```

**Order matters, and getting it wrong is a real defect.** Innermost first:

1. **Timeout** closest to the call — it bounds one attempt, and an unbounded attempt makes every
   outer policy meaningless.
2. **Circuit breaker** outside the timeout, so timeouts count as failures and can open it.
3. **Retry** outside the breaker, so a retry sees an open circuit and fails fast instead of
   hammering.
4. **Fallback / cache** outermost — the last resort once retries are exhausted.

Non-negotiables:

- **Every remote call has a timeout.** A missing timeout is a **blocker**: the default in most
  clients is "forever", and one hung dependency exhausts the pool and takes the service down.
- **Retry only idempotent operations**, and only on retryable errors. A retried non-idempotent
  charge double-charges. Carry an idempotency key in the Context.
- **Exponential backoff with jitter.** Fixed-interval retry across many clients synchronises into a
  thundering herd; that is what jitter exists to break.
- **Bound everything**: attempts, total elapsed, queue depth, concurrency. An unbounded retry is an
  outage amplifier.
- **The fallback is a resolver** — `CachedPrice`, `LastKnownGoodPrice`, `AbsentPrice` — selected by
  the registry, not an `except: return default` inline.
- Retry/timeout/breaker each need a **contract test** proving the wrapper is transparent when the
  inner port succeeds, and a **behaviour test** for the failure path (fake clock, fake port).

---

## 7. Detection — what the `err` dimension measures

| ID | Rule | How to find it |
|---|---|---|
| E1 | swallowed exception | `except.*:\s*pass` · `except.*:\s*(continue\|return)` with no log · `catch\s*\([^)]*\)\s*\{\s*\}` · `catch {}` · `_ = f()` in Go · empty `rescue` |
| E2 | log without a stack | a log call inside a catch whose args contain the exception only via interpolation (`f"{e}"`, `+ e.getMessage()`, `%v` in a boundary log, `${e}`) |
| E3 | broad catch | `except Exception`/`except BaseException` · `catch (Throwable\|Exception e)` · `catch (e)` with no narrowing — flagged unless it is the error boundary of §5 |
| E4 | lost cause | `raise X(...)` inside an `except` with no `from` · `new X(msg)` inside a catch with no `cause` · `%v` instead of `%w` · a `(String)`-only exception constructor at a wrap site |
| E5 | inconsistent port errors | two resolvers behind one port raising different types for the same failure |
| E6 | missing timeout | an HTTP/DB/RPC client constructed with no timeout argument |
| E7 | no error boundary | no global hook, no middleware, no `main` wrapper for a deployable |
| E8 | `printStackTrace` / `console.log` for errors | direct string match — bypasses the logging config entirely |
| E9 | retry without backoff, jitter, or a cap | a loop around a remote call with a constant or absent sleep |
| E10 | control-flow exceptions | an exception raised and caught in the same function, or a `recover()` used to return a value |

Severity: **E1, E2, E6, E7 are blockers** — each one means a real failure is invisible or unbounded.
E4, E5 are majors. E3, E8, E9, E10 are majors at a boundary, minors elsewhere.

Existing tooling to prefer over grep, when present: `ruff` `BLE001`/`TRY002`/`TRY300`/`TRY400`
(`TRY400` is precisely "use `logging.exception` instead of `logging.error`") and `S110`;
`eslint` `no-empty`, `@typescript-eslint/no-floating-promises`, `no-return-await`;
PMD `EmptyCatchBlock`, `AvoidPrintStackTrace`, `PreserveStackTrace`; SpotBugs `REC`/`DE`;
`errcheck`, `go vet`, `bodyclose` in Go. **Report the tool's rule ID as the LAW field** — a named
rule the repo can enable itself beats a bespoke finding.

---

## 8. Testing failure

A resilience wrapper with no failure test is decoration. Assert, per port:

1. The declared error type is raised for an unprocessable Context — in the **shared contract
   suite**, so every resolver is held to it.
2. The cause survives: the wrapped error's `__cause__` / `.cause` / `errors.Is(err, sentinel)` is
   the original. Chain-breaking is invisible in production and trivial to catch here.
3. Something was logged with a stack: capture with `caplog` at ERROR and assert `exc_info` is
   present, a spy transport in TS, an SLF4J list appender in Java, a `slog` test handler in Go.
4. The timeout fires — fake clock, never `sleep`.
5. Retry attempts are bounded and backoff grows; a fake port counts calls.
6. The breaker opens after N failures and short-circuits without calling the inner port.
7. The boundary maps each domain error to the right status/exit code — a table test.
8. Failure injection: a `Failing<Port>` resolver, wired in tests, proves the caller degrades rather
   than crashing. It is one more resolver — that is the point of the doctrine.
