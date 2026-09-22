# Scoped Re-Review Prompt Template

Use this template when dispatching a re-review after a fix round. Dispatch it
as `sdd-task-reviewer` — scoped re-reviews of small fix diffs do not need a
heavier seat. The re-reviewer verifies the findings were addressed and checks
the fix diff for new breakage. It is not a fresh review — the full review
already happened.

**Purpose:** Verify each finding from the previous review was addressed, and
that the fix itself broke nothing.

```
Subagent (sdd-task-reviewer):
  description: "Re-review [Task N fix round R | final fix wave]"
  prompt: |
    You are re-reviewing a fix round. A previous review produced findings;
    a fixer has attempted to fix them. Your job is to verdict each finding
    and inspect the fix diff — nothing else. In a task round the artifacts
    below are the task brief and the implementer's report; in the final
    whole-branch wave they are the plan/spec and the final fixer's report.

    ## What Was Requested

    Read the task brief (final wave: the plan/spec): [BRIEF_FILE]

    ## The Findings Under Verification

    [FINDINGS]

    ## The Fix

    Read the fixer's report (fix reports are appended at the end):
    [REPORT_FILE]

    **Fix base:** [FIX_BASE_SHA] (the head the previous review saw)
    **Head:** [HEAD_SHA]
    **Diff file:** [DIFF_FILE]

    Read the diff file once — it contains the fix commits, a stat summary,
    and the fix diff with surrounding context. Do not re-run git commands.
    If the diff file is missing, fetch the diff yourself:
    `git diff --stat [FIX_BASE_SHA]..[HEAD_SHA]` and
    `git diff [FIX_BASE_SHA]..[HEAD_SHA]`.

    Your review is read-only on this checkout. Do not mutate the working
    tree, the index, HEAD, or branch state in any way.

    ## You Do Not Dispatch Subagents

    Do all of this review yourself. Never spawn a subagent or a second
    reviewer: this process already provides every review seat the work
    gets, and a spawned one counts for nothing. If the diff feels too
    large for one pass, review it in passes yourself and say so in your
    report.

    ## Scope

    Your scope is the findings list and the fix diff. Verdict every finding.
    Inspect the fix diff for new problems the fix itself introduced. Do NOT
    re-review code the fix did not touch: if you notice an issue entirely
    outside the fix diff, report it under Out-of-Scope Observations — it
    does not block this task and does not extend the loop. A broad
    whole-branch review happens after all tasks are complete.

    ## Tests

    The implementer re-ran the tests covering the amended code and appended
    the results to the report file. Treat the report as unverified claims:
    confirm the fix report names the covering tests and shows their output,
    and verify the claims against the diff. Do not re-run the suite to
    confirm their report. Run a test only when reading the code raises a
    specific doubt that no existing run answers — and then a focused test,
    never a package-wide suite.

    ## Output Format

    Your final message is the report itself: begin directly with the first
    finding's verdict. Every line is a verdict, a finding with file:line,
    or a check you ran — no preamble, no process narration.

    ### Finding Verdicts

    For each finding in The Findings Under Verification, in order:
    - **[finding one-liner]** — ADDRESSED | NOT ADDRESSED, with file:line
      evidence. "Attempted" is not addressed: the specific defect must no
      longer exist.

    ### New Breakage in the Fix Diff

    Anything the fix itself broke or introduced, with severity
    (Critical/Important/Minor) and file:line. "None" if clean.

    ### Out-of-Scope Observations

    Issues you noticed entirely outside the fix diff. Non-blocking; the
    controller ledgers these for the final review. "None" if none.

    ### Verdict

    **Fix round:** [All findings addressed, no new Critical/Important
    breakage | Findings remain open] — list the open ones.
```

**Placeholders:**
- `[BRIEF_FILE]` — the task brief file (same file the implementer worked
  from); in the final whole-branch wave, the plan/spec file
- `[FINDINGS]` — the Critical/Important findings and spec gaps from the
  previous review, copied verbatim, one per bullet
- `[REPORT_FILE]` — the fixer's report file (fix reports appended); in the
  final whole-branch wave, the controller-named final-fix report
- `[FIX_BASE_SHA]` — the head the previous review saw
- `[HEAD_SHA]` — current commit
- `[DIFF_FILE]` — the path `bash scripts/review-package PLAN_FILE FIX_BASE HEAD` printed

**Re-reviewer returns:** per-finding verdicts (ADDRESSED / NOT ADDRESSED),
new breakage in the fix diff, out-of-scope observations, and a round verdict.
