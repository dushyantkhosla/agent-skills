# Lightweight Implementer Prompt Template

Use this template for simple, well-scoped tasks (1-2 files, unambiguous spec, established patterns). Pairs with `lightweight-reviewer-prompt.md` for a single combined review pass.

**When to use:** See the "Lightweight Mode" section in SKILL.md for criteria.

```
Task tool (general-purpose):
  description: "Implement Task N (lightweight): [task name]"
  prompt: |
    You are implementing a simple, well-scoped task.

    ## Task Description

    [FULL TEXT of task from plan - paste it here]

    ## Context

    [Brief scene-setting: which file(s), what pattern to follow, any constraints]

    ## Your Job

    1. Write a test for the new behavior (test-first)
    2. Implement minimal code to pass
    3. Verify tests pass
    4. Commit
    5. Report back

    Work from: [directory]

    **If unclear:** Ask one focused question. Don't guess.

    ## Light Self-Review

    Before reporting back, check:
    - Does it do what the task asked?
    - Do tests exist for the new behavior?
    - Did I add anything not requested?
    - Are names clear?

    That's it. Don't do a full 4-category review — this is lightweight mode.

    ## Report Format

    - **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
    - What you implemented
    - Test results
    - Files changed
    - Any concerns (keep brief)
```

**Key differences from full implementer prompt:**
- No detailed "Code Organization" section (assumes pattern is established)
- Lighter self-review (4 quick checks vs 4 categories)
- Shorter context requirements
- Designed to be dispatched with cheaper models
