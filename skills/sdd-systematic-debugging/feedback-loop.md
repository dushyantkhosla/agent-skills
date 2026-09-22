# Building a Feedback Loop

**Load this reference when:** you are about to debug and no tight pass/fail signal exists yet, or the bug will not reproduce reliably.

A debugging session's speed is set by the quality of its loop. A tight, red-capable command turns the problem into bisection and hypothesis-testing. Without one, no amount of code-reading finds the cause reliably. Build the loop before forming a theory.

## Ways to construct one, in roughly this order

1. **Failing test** at whatever seam reaches the bug: unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright / Puppeteer) driving the UI and asserting on DOM, console, or network.
5. **Replay a captured trace.** Save a real request, payload, or event log to disk and replay it through the code path in isolation.
6. **Throwaway harness.** A minimal subset of the system (one service, mocked deps) exercising the bug path in a single function call.
7. **Property / fuzz loop.** "Sometimes wrong output" → run many random inputs and look for the failure mode.
8. **Bisection harness.** Bug appeared between two known states? Automate "boot at state X, check, repeat" so `git bisect run` can use it.
9. **Differential loop.** Same input through old vs new version (or two configs), diff the outputs.
10. **HITL script.** Last resort. If a human must click, drive them with a structured script so the loop stays structured, and feed the captured output back.

## Tighten the loop

Treat the loop as a product. Once you have one:

- **Faster?** Cache setup, skip unrelated init, narrow the scope.
- **Sharper?** Assert the specific symptom, not "didn't crash".
- **More deterministic?** Pin time, seed RNG, isolate the filesystem, freeze the network.

A 30-second flaky loop is barely better than none; a 2-second deterministic one is a debugging superpower.

## Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**: loop the trigger many times, parallelise, add stress, narrow timing windows, inject sleeps. A 50% flake is debuggable; 1% is not — keep raising the rate until it is.

## When the bug will not reproduce

- **Timing-dependent?** Add timestamps around the suspected area; widen race windows with artificial delays; run under load or concurrency.
- **Environment-dependent?** Compare runtime versions, OS, and environment variables; compare data (empty vs populated); try CI's clean environment.
- **State-dependent?** Check for leaked state between tests or requests; look for globals, singletons, shared caches; run the scenario in isolation vs after other operations.
- **Truly random?** Add defensive logging at the suspected location, set an alert on the error signature, document the conditions, and revisit when it recurs.

## When you genuinely cannot build a loop

Stop and say so explicitly. List what you tried.

- **Subagent:** report BLOCKED or NEEDS_CONTEXT with what you tried and what would unblock you.
- **Human session:** ask your human partner for (a) access to an environment that reproduces it, (b) a redacted captured artifact (HAR file, log dump, core dump, recording with timestamps), or (c) permission to add temporary instrumentation.

Do **not** proceed to hypotheses without a loop.
