# Spec Document Reviewer Prompt Template

Use this template when dispatching an adversarial spec reviewer subagent —
dispatch it as `sdd-spec-reviewer`; the agent definition pins the model and
thinking variant.

**Purpose:** Try to find what is wrong with the spec before implementation
planning locks it in. The reviewer's job is to disprove readiness, not to
validate it. A confident spec is not a correct one.

**Dispatch after:** Spec document is written to `docs/superpowers/specs/` and
after the inline self-review, before the user review gate.

**What the reviewer receives:** the spec file, the confirmed intent restate
from brainstorming — the contract — and the project root with the files or
areas the design touches. The reviewer is read-only and checks the spec's
claims about the current state against the actual code rather than trusting
the spec's description of it. Do NOT pass the author's design reasoning or
the session history; handing over conclusions biases the review toward
agreement.

```
Subagent (sdd-spec-reviewer):
  description: "Adversarially review spec document"
  prompt: |
    Adversarial spec review. Find what is wrong with this spec. Assume the
    author is overconfident. Do NOT validate. Do NOT summarize. Find issues,
    or state explicitly that you cannot find any after thorough examination.

    **Spec to review:** [SPEC_FILE_PATH]

    **Contract (confirmed intent):**
    [RESTATE — Outcome / User / Why now / Success / Constraint / Out of scope]

    **Current state to verify against:** [PROJECT_ROOT plus the files or
    areas the design touches — check the spec's claims about existing code
    and behavior against this code, not against the spec's description of it]

    ## What to Check

    | Category | What to Look For |
    |----------|------------------|
    | Intent traceability | Requirements that do not trace to the contract; promises in the contract missing from the spec |
    | Assumptions | Unvalidated assumptions presented as facts or buried in prose |
    | Current state | Claims about existing code or behavior that the actual code contradicts; hidden dependencies the design does not account for; error handling or edge cases in the touched paths the spec assumes away |
    | Completeness | TODOs, placeholders, "TBD", incomplete sections |
    | Consistency | Internal contradictions, conflicting requirements |
    | Clarity | Requirements ambiguous enough to cause someone to build the wrong thing |
    | Testability | Success criteria that cannot be measured; missing or vague test seams |
    | Scope | Focused enough for a single plan — not covering multiple independent subsystems; out-of-scope explicit |
    | YAGNI | Unrequested features, over-engineering |

    ## Calibration

    Only flag issues that would cause real problems during implementation
    planning. A missing section, a contradiction, an untraceable requirement,
    or an ambiguity that could be read two ways — those are issues. Minor
    wording improvements, stylistic preferences, and uneven detail between
    sections are not.

    Approve unless serious gaps would lead to a flawed plan.

    ## Output Format

    ## Spec Review

    **Status:** Approved | Issues Found

    **Issues (if any):**
    - [Section X]: [specific issue] - [why it matters for planning]

    **Recommendations (advisory, do not block approval):**
    - [suggestions for improvement]
```

**After the review:** reconcile the findings against the spec text rather than
rubber-stamping or dismissing them. Classify each finding, first match wins:

1. **Contract misread** — the reviewer flagged something because the contract
   passed in was unclear. Fix the contract, then re-check.
2. **Actionable** — a real issue. Fix the spec.
3. **Valid trade-off** — real but not worth fixing. Document it in the spec.
4. **Noise** — correct under context the reviewer did not have. Note it and
   move on.

Minor fixes do not need another reviewer pass; re-run it only if the review
prompted a material design change.

Reviewer returns: Status, Issues (if any), Recommendations.
