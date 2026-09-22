# Performance Verification

**Load this reference when:** you are about to claim a change makes something faster, smaller, or lighter — or a spec or plan sets a performance budget (LCP, INP, CLS, p95 latency, bundle size).

A performance change is a hypothesis until it is re-measured. The number that matters is the one measured after the change, the same way it was measured before it, with a delta that beats run-to-run noise. "Obviously faster" is not a measurement, and an unmeasured optimization is complexity you maintain forever for nothing.

## The Measurement Protocol

1. **Baseline first.** Record the number before touching the code, with the exact command, conditions, and budget (wall-clock, sample count, or request count). Say whether it is synthetic (Lighthouse, DevTools Performance, profiler) or field data (RUM, web-vitals) — they answer different questions and are not interchangeable.
2. **Change one thing.** Three optimizations landed together produce one number you cannot attribute. If they must ship together, measure each in isolation first.
3. **Re-measure the same way.** Same command, same conditions, same budget. A cold-cache baseline against a warm-cache result measures the cache, not your change.
4. **Beat the noise, not the mean.** Repeat the measurement and compare the delta against run-to-run variance. A 3% gain inside ±5% variance is not a gain; it is a different sample.
5. **Decide by the table below**, and record the decision either way.

## Keep or Revert

| Result vs baseline | Action |
|---|---|
| Past the threshold, tests green | **Keep.** Commit with the before/after numbers in the message. |
| Within noise (no measurable change) | **Revert.** Neutral is not a win. |
| Worse | **Revert.** |
| Improved, but a test went red | **Revert.** A regression wearing a win's clothing. |

**Correctness gates the metric.** The suite stays green *and* the number moves. An "optimization" that wins by dropping work the product needed — skipping a validation, caching something that must be fresh, removing a load-bearing `await` — is a regression, not a win.

## Log Every Attempt

Reverted work leaves no trace in git, which is why the same dead idea returns next quarter. Keep a short ledger in the PR description, a `PERF.md`, or the plan workspace so the next person (or agent) does not re-run a failed experiment:

| Idea | Baseline → Result | Verdict | Why |
|---|---|---|---|
| Memoize the row component | INP 240ms → 235ms | reverted | Inside noise (±15ms); rows were not the bottleneck. |
| Virtualize the list | INP 240ms → 90ms | kept | Long tasks gone from the trace. |

## Guard Against Regression

Guard the metric the user actually feels — the same LCP, INP, p95, or other primary number that justified the change. Two complementary layers when the surface is user-facing:

- **Synthetic CI gate:** a budget that catches reproducible regressions before merge. Repeat noisy measurements or compare a median/trend so normal variance does not make the gate flaky.
- **Field monitoring:** alert on a meaningful p75 movement in RUM data; use attributed `web-vitals` data to locate the cause and treat CrUX as confirmation, not an immediate page.

Budgets live in the spec's Success Criteria and in CI; the plan's `Commands` block carries the measurement command. Use the project's numbers — the common Core Web Vitals thresholds are LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1. When a guard fires, establish a fresh baseline before proposing another fix.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This optimization is obvious" | If you did not measure, you do not know. Profile first. |
| "It didn't help much, but it doesn't hurt" | Neutral changes are complexity you maintain forever and got nothing back from. Revert. |
| "We already wrote it, may as well keep it" | Sunk cost. The measurement does not care how long the change took to write. |
| "The improvement is obvious, no need to re-measure" | Then re-measuring is cheap and proves it. Unmeasured wins are how neutral complexity lands. |

## Red Flags

- Optimization without a baseline measurement
- Before/after measured with different commands, conditions, or budgets (cold vs warm cache)
- Several changes bundled into one measurement, so none can be attributed
- A "win" that required a test to be changed, skipped, or deleted
- Improvements kept without a re-measurement
- No regression guard on the metric that justified the change
- The same failed optimization attempted twice because nobody logged the first

## Checklist

- [ ] Before and after numbers exist, measured the same way
- [ ] The delta exceeds run-to-run variance, not just the mean
- [ ] Neutral or worse changes were reverted, not kept
- [ ] Attempts are logged, kept and reverted alike
- [ ] Tests still pass after the change
- [ ] The metric has a regression guard — both a synthetic CI budget and a field monitor for user-facing surfaces, at least one otherwise

---

Adapted from addyosmani/agent-skills `performance-optimization`.
Source, not dependency: apply this file directly.
