# Plan Document Reviewer Prompt Template

Use this template when dispatching an adversarial plan reviewer subagent —
dispatch it as `sdd-plan-reviewer`; the agent definition pins the model and
thinking variant.

**Purpose:** Try to find what is wrong with the implementation plan before
execution starts. The reviewer's job is to disprove readiness, not to
validate it. A confident plan is not a correct one.

**Dispatch after:** The plan is saved and self-reviewed — for architectural
plans (cross-module interfaces, many tasks, high risk) and before the
execution handoff. Small mechanical plans do not need it.

**What the reviewer receives:** the plan file, the spec it implements, and
the path to `code-guidance.md`. Do NOT pass the author's design reasoning or
the session history; handing over conclusions biases the review toward
agreement.

```
Subagent (sdd-plan-reviewer):
  description: "Adversarially review plan document"
  prompt: |
    Adversarial plan review. Find what is wrong with this plan. Assume the
    author is overconfident. Do NOT validate. Do NOT summarize. Find issues,
    or state explicitly that you cannot find any after thorough examination.

    **Plan to review:** [PLAN_FILE_PATH]

    **Spec (contract):** [SPEC_FILE_PATH]

    **Code guidance:** [CODE_GUIDANCE_PATH]

    Read the code guidance file before judging code quality, and audit
    every code block in the plan against it.

    ## What to Check

    | Category | What to Look For |
    |----------|------------------|
    | Spec coverage | Spec requirements with no task; tasks implementing nothing in the spec; plan choices that contradict the spec or its Confirmed Intent |
    | Interfaces | `Produces`/`Consumes` pairs whose signatures disagree; types or functions used in later tasks but defined differently or nowhere |
    | Testing seams | A task that adds behavior with no `Testing seam`; a seam that contradicts the spec's Testing Decisions or the plan's File Structure; a seam that is a test-only entrance rather than a boundary callers cross |
    | Dependencies | Missing or incorrect `Depends on` edges; cycles; a task using a value that only exists in a later task |
    | Placeholders | TBD/TODO, "add error handling", "similar to Task N", steps missing code, commands, or expected output |
    | Commands | Commands that do not match the repo's actual tooling; command steps with no `Expected:` line |
    | Test quality | Tests that assert nothing, assert implementation details, or cannot fail; Review Focus lines with no test owning them |
    | Brief self-containment | Task text that needs another task's text to be actionable; missing exact values (signatures, test cases, paths) |
    | Ordering and slicing | Horizontal slices whose tasks are not verifiable alone; risky or uncertain work scheduled last; wide mechanical refactors forced into a green vertical slice |
    | Code quality | Every code block audited against the code guidance: a lower ladder rung that would hold, speculative abstraction (interface, factory, or config with one user), drive-by changes outside the task, removed or weakened error handling or trust-boundary validation, names that obscure content, silent shortcuts with no deliberate-simplification marker. A violation is an Issue, not a suggestion |
    | Unverified APIs | Framework-specific code written from memory instead of cited documentation, with no unverified marker |

    ## Calibration

    Only flag issues that would cause real problems during execution. A
    missing task, a contradictory interface, a dependency cycle, a step that
    cannot run — those are issues. Stylistic preferences and wording are
    not. Approve unless serious gaps would derail implementation.

    ## Output Format

    ## Plan Review

    **Status:** Approved | Issues Found

    **Issues (if any):**
    - [Task N / Section]: [specific issue] - [why it matters for execution]

    **Recommendations (advisory, do not block approval):**
    - [suggestions for improvement]
```

**After the review:** reconcile the findings against the plan text rather than
rubber-stamping or dismissing them. Classify each finding, first match wins:

1. **Contract misread** — the reviewer flagged something because the plan or
   spec text was unclear. Fix the text, then re-check.
2. **Actionable** — a real issue. Fix the plan.
3. **Valid trade-off** — real but not worth fixing. Document it in the plan.
4. **Noise** — correct under context the reviewer did not have. Note it and
   move on.

A finding that conflicts with what the spec mandates is a decision for your
human partner, not a silent edit.

Reviewer returns: Status, Issues (if any), Recommendations.
