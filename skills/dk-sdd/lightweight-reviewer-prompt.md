# Lightweight Reviewer Prompt Template

Use this template for the combined spec + quality review in Lightweight Mode. Single reviewer covers both aspects with a "good enough to ship" threshold.

**When to use:** Only after a lightweight implementer subagent reports DONE. See "Lightweight Mode" in SKILL.md for when to use this vs. the two-stage review.

```
Task tool (general-purpose):
  description: "Lightweight review for Task N: [task name]"
  prompt: |
    You are doing a combined review: does this code do what it should, and is it clean?

    ## Task Spec

    [FULL TEXT of task requirements]

    ## What Was Implemented

    [From implementer's report: files changed, what it does]

    ## Scope

    The controller provides the git diff / changed files for this task. Read the **changed code** as your primary surface — don't re-read the whole codebase. You still verify independently; you just stay scoped.

    ## Your Job

    Read the actual changed code (don't just trust the report) and check:

    **Correctness:**
    - Does it implement what the spec asked?
    - Any obvious bugs or missing edge cases?

    **Spec compliance:**
    - Missing requirements?
    - Extra features that weren't requested?

    **Basic quality:**
    - Clear names?
    - Tests exist for new behavior?
    - No dead code or obvious smells?

    ## Threshold

    This is **lightweight mode**. Approve if the code is good enough to ship.
    Don't nitpick style, don't request refactors that aren't necessary, don't
    flag preferences as requirements. Focus on: does it work, and is it not
    embarrassing?

    Report:
    - ✅ Approved (works, matches spec, clean enough to ship)
    - ❌ Issues: [list specifically what's wrong with file:line references]
```

**Key differences from two-stage review:**
- Single reviewer covers both spec and quality (not two separate subagents)
- Lower bar for approval ("good enough to ship" vs "excellent")
- Explicit instruction not to nitpick
- Max 2 rounds before escalating to full mode or human
