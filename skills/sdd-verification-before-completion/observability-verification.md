# Observability Verification

**Load this reference when:** you are about to claim a feature that runs in production works — or you cannot tell whether it does from the data the code emits.

Local tests prove the code runs on your machine. A production claim is supported by telemetry: logs, metrics, traces, alerts. If the first user-reported bug becomes archaeology instead of a query, the feature was never verifiable — and therefore never verified.

## Name the Questions First

Telemetry without a question is noise. Before accepting "it's observable", write down 2–4 questions an on-call engineer will ask about this feature and confirm that each signal answers one:

```
FEATURE: checkout payment retry
ON-CALL QUESTIONS:
1. What fraction of payments succeed first attempt vs after retry?
2. When a payment fails permanently, why? (provider error? timeout? validation?)
3. Is the provider slower than usual?
```

If you cannot name the questions, you are not ready to claim production-readiness — you would be adding signals that answer nothing.

## The Induced-Failure Test (Release Readiness)

Force a failure in staging, then find it through telemetry alone: search by request ID, follow the trace, read the structured log line, watch the metric move — **without reading the source**. If locating it takes more than a few minutes or requires code, the claim is not met.

This is the single highest-value readiness check: it exercises every signal end to end, the way an incident will.

It proves the signals work; it does not prove the deployed feature behaves. That claim needs production traffic: the new path served real requests, its RED metrics are healthy, and no new error class appeared. A staging induced failure supports "observable when deployed"; only post-deploy telemetry supports "works in production". Unavailable staging, telemetry access, or real traffic does not downgrade these checks — it prevents the corresponding claim, which you say out loud instead of asserting it.

## What the Telemetry Must Show

**Logs:** JSON with stable event names (not interpolated prose); a correlation/request ID on every line, propagated across async boundaries; an entry-point field wherever several producers write to one sink; no secrets, tokens, or unredacted PII — allowlist fields, never whole request bodies.

**Metrics:** RED (rate, errors, duration) on every new endpoint and external dependency; latency as histograms with p50/p95/p99 queryable, never averages; bounded label sets — route templates, status classes, provider names, never user IDs, emails, raw URLs, or error text (each unique combination is a separate time series).

**Traces:** one request followed end-to-end with no broken spans; context propagated through every async boundary, or the trace dies at the gap.

**Alerts:** symptom-based (error rate, latency, queue age), not cause-based (CPU, disk) — cause alerts page when nothing is wrong and miss what you did not predict. Each has a threshold and duration justified by the SLO or history, a runbook link, and one test-fire before you trust it. Two severities only: page (user-facing, act now) and ticket (degradation, this week).

## Claim to Evidence

| Claim | Requires | Not sufficient |
|---|---|---|
| Feature is release-ready (observable) | Induced failure located via telemetry alone in staging | Staging functional tests, "works locally" |
| Feature works in production | Post-deploy telemetry: real traffic exercised the path, RED metrics healthy, no new error class | The pre-deploy induced-failure test alone |
| Deploy is healthy | Post-deploy RED metrics for the new endpoints; no new error class | CI green |
| Incident is diagnosable | One request reconstructable from its correlation ID | Log lines correlated only by timestamp |
| Alerting works | Each new alert test-fired to the right channel; runbook link resolves | "It's configured" |

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll add logging after it works" | "After" becomes "after the first incident" — the most expensive moment to discover you are blind. |
| "User ID as a label makes debugging easier" | It also takes down the metrics backend. High-cardinality lookups belong in logs and traces. |
| "It works locally, production will be fine" | Local evidence supports local claims. Production claims need production signals. |

## Red Flags

- A production claim supported only by local or staging tests, or by the pre-deploy induced-failure test alone
- An induced failure that could not be found without reading source
- Log lines built by interpolation; no correlation ID
- Metrics labeled with user IDs, raw URLs, or error text
- Latency tracked as an average with no percentiles
- Alerts firing daily and acknowledged without action
- Cause-based alerts paging while user-facing error rate is unmonitored
- Secrets, tokens, or full request bodies in logs

## Checklist

**Release readiness (observable):**
- [ ] On-call questions written; each signal maps to one
- [ ] Induced failure found via telemetry alone in staging
- [ ] Logs structured, with correlation IDs and entry points where needed
- [ ] No secrets or PII in actual log output (spot-checked)
- [ ] RED metrics with bounded labels; percentiles queryable
- [ ] One request follows end-to-end in tracing without broken spans
- [ ] Each new alert test-fired, runbook linked, threshold justified

**Production claim:**
- [ ] Post-deploy telemetry shows the new path exercised, RED healthy, and no new error class

---

Adapted from addyosmani/agent-skills `observability-and-instrumentation`.
Source, not dependency: apply this file directly.
