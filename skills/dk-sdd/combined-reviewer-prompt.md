# Combined Reviewer Prompt Template

Use this template for the **single combined review pass** in two cases:
- **Lightweight Mode** simple tasks (1-2 files), OR
- **`--fast-review`** non-critical medium tasks (multi-file but mechanical/established, no new public API, no behavior change to other paths).

It collapses the two-stage review (spec compliance + code quality) into one dispatch. The bar is **"solid and correct"** — stricter than the lightweight reviewer's "good enough to ship" but lighter than the full two-stage gate.

```
Task tool (general-purpose):
  description: "Combined review for Task N: [name]"
  prompt: |
    You are doing a single combined review: does this code do what the spec asks, AND is it well-built? This replaces the separate spec + quality stages.

    ## Task Spec
    [FULL TEXT of task requirements]

    ## Scope: Changed Code Only
    The controller provides the git diff / changed files. Read the **changed code** as your surface — don't re-read the whole codebase. Still verify independently; just stay scoped.

    ## What Implementer Claims They Built
    [From implementer's report]

    ## Check (be thorough within scope — this is the only review pass)

    **Spec compliance:**
    - Did they implement everything requested? Missing requirements?
    - Extra/unneeded work (over-engineering, unrequested "nice to haves")?
    - Misinterpreted requirements or solved the wrong problem?

    **Correctness:**
    - Any obvious bugs or missing edge cases?
    - Do tests actually verify behavior (not just mock it)?

    **Code quality:**
    - Clear names and one clear responsibility per file?
    - No dead code, no obvious smells?
    - Following established patterns; reasonable decomposition?

    ## Threshold
    This is a combined pass, so hold a higher bar than a pure "lightweight" review: the code should be **correct against spec and clean enough to merge**, not merely "not embarrassing." But don't request stylistic refactors that aren't necessary, and don't flag preferences as requirements.

    Report:
    - ✅ Approved (matches spec, correct, clean enough to merge)
    - ❌ Issues: [list specifically what's wrong, with file:line references and whether each is spec/compliance/correctness/quality]
```
