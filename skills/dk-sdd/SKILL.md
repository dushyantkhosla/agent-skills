---
name: dk-sdd
description: Fast subagent-driven development for executing implementation plans. Fresh subagent per task with lightweight-by-default review (auto-classified), role-graded models, and diff-scoped reviews. Opt-in flags --parallel (concurrent worktree implementation) and --fast-review (collapsed single-pass review for non-critical tasks). Use when executing implementation plans with independent tasks in the current session.
---

# Fast Subagent-Driven Development (dk-sdd)

Execute plan by dispatching fresh subagent per task, with review after each. Built for speed: tasks are **auto-classified** and simple ones use a single lightweight review by default (not the full two-stage gate), reviews run on **role-graded models** (only the final integration pass needs the most capable model), and reviewers verify against the **provided diff** rather than re-reading the whole codebase.

## Speed Design (what makes dk-sdd fast)

dk-sdd is a speed-tuned fork of `sp-subagent-driven-development`. Four Wave 1 tunings:

1. **Lightweight-by-default (auto-classified).** Every task is auto-classified before dispatch. Tasks that meet the lightweight criteria (1-2 files, unambiguous spec, established pattern, no cross-module integration, no architectural decisions) go straight to single-pass review — no human-in-loop mode decision, no two-stage gate.
2. **Role-graded models.** Implementers use cheap/standard models; spec and code-quality reviewers use a **standard** model (verification against a clear spec, not open-ended reasoning). The **most capable** model is reserved for the final integration-seam review and genuinely hard tasks only.
3. **Diff-scoped reviews.** Reviewers verify against the **git diff + changed files** you provide, not the whole codebase. They still distrust the implementer's report — they just don't re-read unrelated code.
4. **Lighter final reviewer.** The end-of-plan review is scoped to **integration seams** (where tasks meet: shared interfaces, cross-module calls, merge points), not a full re-read of every file.

**Wave 2 tunings (opt-in flags):**

5. **Parallel worktree execution (`--parallel`).** Independent implementation tasks are fanned out **in parallel**, each in its own git worktree (the harness `subagent` tool supports `worktree: true`). This moves the longest phase — implementation — off the critical path. Reviews still run post-merge to catch integration breakage the isolation hid.
6. **Collapsed review for medium tasks (`--fast-review`).** Non-critical tasks (multi-file but mechanical/established, no new public API, no behavior change to other paths) use a **single combined reviewer** instead of two serial stages. The two-stage gate stays for tasks that touch other code paths or design new interfaces.

Wave 1 cuts per-task dispatch count and moves the highest-volume calls off the slowest model. Wave 2 (when enabled) additionally parallelizes implementation and collapses review stages, while keeping context isolation and quality gates.

## Quick Start / Flag Decision

| If your plan is… | Use | Flags |
|---|---|---|
| Tightly coupled, risky, or you're unsure | Default — serial, full two-stage for non-lightweight tasks | none (safest) |
| Mostly simple 1-2 file tasks | Lightweight auto-classified | none — on by default |
| Many independent tasks | Parallel implementation | `--parallel` |
| Many non-critical medium tasks | Collapsed single review | `--fast-review` |
| Well-decomposed + low risk, want max speed | Both of the above | `--parallel --fast-review` |

Flags are **off by default**. Start without them; add `--parallel` and/or `--fast-review` once you've confirmed the plan decomposes into independent, low-risk tasks. The final **integration-seam review is always mandatory** — and required in `--parallel` mode.

**Why subagents:** You delegate tasks to specialized agents with isolated context. By precisely crafting their instructions and context, you ensure they stay focused and succeed at their task. They should never inherit your session's context or history — you construct exactly what they need. This also preserves your own context for coordination work.

**Core principle:** Fresh subagent per task + review after each (two-stage for full-mode tasks, single-pass for lightweight-auto tasks) = high quality, fast iteration

**Continuous execution:** Do not pause to check in with your human partner between tasks. Execute all tasks from the plan without stopping. The only reasons to stop are: BLOCKED status you cannot resolve, ambiguity that genuinely prevents progress, or all tasks complete. "Should I continue?" prompts and progress summaries waste their time — they asked you to execute the plan, so execute it.

## When to Use

```dot
digraph when_to_use {
    "Have implementation plan?" [shape=diamond];
    "Tasks mostly independent?" [shape=diamond];
    "Stay in this session?" [shape=diamond];
    "dk-sdd" [shape=box];
    "executing-plans" [shape=box];
    "Manual execution or brainstorm first" [shape=box];

    "Have implementation plan?" -> "Tasks mostly independent?" [label="yes"];
    "Have implementation plan?" -> "Manual execution or brainstorm first" [label="no"];
    "Tasks mostly independent?" -> "Stay in this session?" [label="yes"];
    "Tasks mostly independent?" -> "Manual execution or brainstorm first" [label="no - tightly coupled"];
    "Stay in this session?" -> "dk-sdd" [label="yes"];
    "Stay in this session?" -> "executing-plans" [label="no - parallel session"];
}
```

**vs. Executing Plans (parallel session):**

- Same session (no context switch)
- Fresh subagent per task (no context pollution)
- Review after each task: two-stage (spec then quality) for full mode, single-pass for lightweight-auto tasks
- Faster iteration (no human-in-loop between tasks)

## The Process

```dot
digraph process {
    rankdir=TB;

    subgraph cluster_per_task {
        label="Per Task";
        "Dispatch implementer subagent (./implementer-prompt.md)" [shape=box];
        "Implementer subagent asks questions?" [shape=diamond];
        "Answer questions, provide context" [shape=box];
        "Implementer subagent implements, tests, commits, self-reviews" [shape=box];
        "Dispatch spec reviewer subagent (./spec-reviewer-prompt.md)" [shape=box];
        "Spec reviewer subagent confirms code matches spec?" [shape=diamond];
        "Spec review round < MAX (3)?" [shape=diamond];
        "Implementer subagent fixes spec gaps" [shape=box];
        "Dispatch code quality reviewer subagent (./code-quality-reviewer-prompt.md)" [shape=box];
        "Code quality reviewer subagent approves?" [shape=diamond];
        "Quality review round < MAX (3)?" [shape=diamond];
        "Implementer subagent fixes quality issues" [shape=box];
        "Mark task complete in TodoWrite" [shape=box];
    }

    "Read plan, extract all tasks with full text, note context, create TodoWrite" [shape=box];
    "More tasks remain?" [shape=diamond];
    "Dispatch final integration-seam reviewer (most capable, diff-scoped)" [shape=box];
    "Use superpowers:finishing-a-development-branch" [shape=box style=filled fillcolor=lightgreen];

    "Read plan, extract all tasks with full text, note context, create TodoWrite" -> "Dispatch implementer subagent (./implementer-prompt.md)";
    "Dispatch implementer subagent (./implementer-prompt.md)" -> "Implementer subagent asks questions?";
    "Implementer subagent asks questions?" -> "Answer questions, provide context" [label="yes"];
    "Answer questions, provide context" -> "Dispatch implementer subagent (./implementer-prompt.md)";
    "Implementer subagent asks questions?" -> "Implementer subagent implements, tests, commits, self-reviews" [label="no"];
    "Implementer subagent implements, tests, commits, self-reviews" -> "Dispatch spec reviewer subagent (./spec-reviewer-prompt.md)";
    "Dispatch spec reviewer subagent (./spec-reviewer-prompt.md)" -> "Spec reviewer subagent confirms code matches spec?";
    "Spec reviewer subagent confirms code matches spec?" -> "Spec review round < MAX (3)?" [label="no"];
    "Spec review round < MAX (3)?" -> "Implementer subagent fixes spec gaps" [label="yes"];
    "Spec review round < MAX (3)?" -> "ESCALATE: Spec review stuck, human intervention needed" [label="no - max reached"];
    "Implementer subagent fixes spec gaps" -> "Dispatch spec reviewer subagent (./spec-reviewer-prompt.md)" [label="re-review"];
    "Spec reviewer subagent confirms code matches spec?" -> "Dispatch code quality reviewer subagent (./code-quality-reviewer-prompt.md)" [label="yes"];
    "Dispatch code quality reviewer subagent (./code-quality-reviewer-prompt.md)" -> "Code quality reviewer subagent approves?";
    "Code quality reviewer subagent approves?" -> "Quality review round < MAX (3)?" [label="no"];
    "Quality review round < MAX (3)?" -> "Implementer subagent fixes quality issues" [label="yes"];
    "Quality review round < MAX (3)?" -> "ESCALATE: Quality review stuck, human intervention needed" [label="no - max reached"];
    "Implementer subagent fixes quality issues" -> "Dispatch code quality reviewer subagent (./code-quality-reviewer-prompt.md)" [label="re-review"];
    "Code quality reviewer subagent approves?" -> "Mark task complete in TodoWrite" [label="yes"];
    "Mark task complete in TodoWrite" -> "More tasks remain?";
    "More tasks remain?" -> "Dispatch implementer subagent (./implementer-prompt.md)" [label="yes"];
    "More tasks remain?" -> "Dispatch final integration-seam reviewer (most capable, diff-scoped)" [label="no"];
    "Dispatch final integration-seam reviewer (most capable, diff-scoped)" -> "Use superpowers:finishing-a-development-branch";
}
```

### Execution Variants (default, `--parallel`, `--fast-review`)

The diagram above is the **default serial flow** (one task at a time, fully reviewed before the next). Two opt-in flags change the shape:

- **`--parallel`** — Implementation is fanned out across tasks in parallel worktrees (see "Parallel Execution"). Reviews still happen, but after merge, so the long implementation phase runs concurrently.
- **`--fast-review`** — Non-critical tasks use a single combined reviewer instead of two serial stages (see "Fast Review"). Pairs with `--parallel` for maximum speed on well-decomposed, low-risk plans.

Both flags are **off by default**. Enable them only when the plan is well-decomposed into independent tasks and you can tolerate a post-merge integration check.

## Model Selection

Use the least powerful model that can handle each role to conserve cost and increase speed. **Crucially, role-grade the models** — do not put every review on the most capable (slowest) model. The highest-volume calls are the per-task reviewers, so keep them on a standard model.

**Per-role model assignment:**

| Role | Model | Why |
|------|-------|-----|
| Implementer (mechanical: 1-2 files, clear spec) | Cheap / fast | Isolated, well-specified work |
| Implementer (integration/judgment: multi-file, debugging) | Standard | Needs coordination reasoning |
| Spec compliance reviewer | **Standard** | Verification against a clear spec, not open-ended design |
| Code quality reviewer | **Standard** | Pattern/cleanliness checks on a known diff |
| Combined reviewer (`--fast-review` medium) | **Standard** | Single combined spec+quality pass on a known diff |
| Final integration-seam reviewer | **Most capable** | Only pass that needs broad judgment |
| Any task that's ambiguous or stuck | Most capable (escalate) | When cheaper models fail, upgrade — never retry identically |

**Task complexity signals (for the implementer):**

- Touches 1-2 files with a complete spec → cheap model
- Touches multiple files with integration concerns → standard model
- Requires design judgment or broad codebase understanding → most capable model

**Reviewers are verification, not design.** Keep spec/quality reviewers on a standard model; reserve the most capable model for the final pass and for tasks that actually need it (the escalation path).

## Lightweight Mode for Simple Tasks

For tasks that are **non-trivial** (need testing, have some logic) but **simple enough** that full two-stage review is overkill, use **Lightweight Mode**. This cuts overhead by ~60% while keeping quality guarantees.

### When to Use Lightweight Mode

**Use lightweight mode when ALL of these are true:**

- **1-2 files** affected (highly localized change)
- **Spec is unambiguous** (no judgment calls about requirements)
- **No cross-system integration** (no coordination with other modules)
- **Pattern is established** (clear how it should fit in the codebase)
- **No architectural decisions** (just implementing what the plan specifies)

**Auto-classification (default to lightweight):** Before dispatching each task, check the five criteria above. **If ALL are true, use Lightweight Mode automatically** — do not ask, do not default to full mode. Only use Full Mode when at least one criterion fails (see "Stay in full mode if" below). This is the default behavior in dk-sdd, not an opt-in: most well-specified plan tasks are mechanical and qualify.

**Common candidates:**
- Adding a single function/method with clear inputs/outputs
- Bug fix where root cause is obvious
- Small refactor (rename, extract helper, simplify logic)
- Adding a validation rule with clear criteria
- Adding a new endpoint handler that follows existing patterns

**Stay in full mode if:**
- Multiple files or cross-module changes
- Spec has open questions or ambiguity
- Requires choosing between approaches
- New public API or interface design
- Changes affect existing behavior of other code paths

### How Lightweight Mode Differs

| Aspect | Full Mode | Lightweight Mode |
|--------|-----------|------------------|
| **Review stages** | 2 (spec + quality) | 1 (combined check) |
| **Max review rounds** | 3 per stage (6 total) | 2 total |
| **Reviewer focus** | Spec compliance + code quality | "Does it work and is it clean?" |
| **Reviewer model** | Most capable | Standard |
| **Implementer model** | Standard or cheap | Cheap (mechanical) |
| **Self-review depth** | Thorough (4 categories) | Light (does it work + obvious issues) |
| **Escalation path** | Continue rounds or escalate to human | Round 2 fails → switch to full mode or escalate |

### Lightweight Mode Process

```dot
digraph lightweight_process {
    rankdir=TB;

    subgraph cluster_lightweight {
        label="Per Task (Lightweight)";
        "Dispatch implementer subagent (lightweight prompt)" [shape=box];
        "Questions?" [shape=diamond];
        "Answer & re-dispatch" [shape=box];
        "Implement, test, commit, light self-review" [shape=box];
        "Dispatch single reviewer subagent (combined check)" [shape=box];
        "Reviewer approves?" [shape=diamond];
        "Round < MAX (2)?" [shape=diamond];
        "Implementer fixes issues" [shape=box];
        "Mark task complete" [shape=box];
        "ESCALATE: Switch to full mode or ask human" [shape=box style=filled fillcolor="#ffcccc"];
    }

    "Dispatch implementer subagent (lightweight prompt)" -> "Questions?";
    "Questions?" -> "Answer & re-dispatch" [label="yes"];
    "Answer & re-dispatch" -> "Dispatch implementer subagent (lightweight prompt)";
    "Questions?" -> "Implement, test, commit, light self-review" [label="no"];
    "Implement, test, commit, light self-review" -> "Dispatch single reviewer subagent (combined check)";
    "Dispatch single reviewer subagent (combined check)" -> "Reviewer approves?";
    "Reviewer approves?" -> "Mark task complete" [label="yes"];
    "Reviewer approves?" -> "Round < MAX (2)?" [label="no"];
    "Round < MAX (2)?" -> "Implementer fixes issues" [label="yes"];
    "Round < MAX (2)?" -> "ESCALATE: Switch to full mode or ask human" [label="no - max reached"];
    "Implementer fixes issues" -> "Dispatch single reviewer subagent (combined check)" [label="re-review"];
}
```

### Lightweight Reviewer Prompt

```
Task tool (general-purpose):
  description: "Lightweight review for Task N: [name]"
  prompt: |
    You are doing a combined review: does this code do what it should, and is it clean?

    ## Task Spec
    [FULL TEXT of task requirements]

    ## Changes
    [git diff or list of files changed]

    ## Check
    1. **Correctness:** Does it implement the spec? Any obvious bugs?
    2. **Spec compliance:** Missing requirements? Extra features?
    3. **Basic quality:** Clear names? No dead code? Tests exist for new behavior?

    Report:
    - ✅ Approved (works, matches spec, clean enough)
    - ❌ Issues: [list specifically what's wrong]

    Don't nitpick style. Focus on whether this is good enough to ship.
```

### When to Escalate from Lightweight to Full

**Escalation triggers (switch to full mode mid-task):**

- Reviewer finds issues that suggest **spec ambiguity** (not just code problems)
- Fix in round 1 reveals the task is **larger than expected** (touched 3+ files, broke other things)
- Reviewer says **"this needs architectural review"** or similar
- You're about to dispatch round 2 — pause and ask: is this still a simple task?

**How to switch:** Note in TodoWrite that this task upgraded to full mode, then follow the full two-stage review process for subsequent rounds.

### Lightweight Mode Tradeoffs

**What you save:**
- ~60% reduction in review overhead (1 reviewer vs 2, 2 rounds vs 6)
- Cheaper models for both implementer and reviewer
- Faster iteration on simple tasks

**What you risk:**
- Single reviewer might miss issues a two-stage review would catch
- "Good enough" threshold means minor issues may slip through
- False sense of security for tasks that were actually more complex than they seemed

**Mitigation:** The escalation triggers catch the cases where lightweight mode was the wrong choice. Trust them.

## Parallel Execution (opt-in: `--parallel`)

The dominant cost in the default flow is that tasks run **serially** — the whole review chain for task N must finish before task N+1 starts. The harness `subagent` tool can isolate each task in its own git worktree (`worktree: true`), so independent implementation can run **concurrently** without file/git conflicts.

**When `--parallel` is on, execute in two phases:**

**Phase 1 — Fan-out implementation.** For each independent task (or a concurrency-bounded batch), dispatch an implementer subagent in its **own worktree**. It implements, tests, commits, and self-reviews in isolation (following mtpk-tdd via `superpowers:test-driven-development`). Implementers do **not** review each other.

**Phase 2 — Merge & review.** Sequentially merge each completed worktree into the working branch, then run the review on the **merged** code:
1. Per-task review (auto-classified lightweight/full, role-graded, diff-scoped) on the merged result.
2. The final **integration-seam** reviewer (most capable) across the merged whole — this is where cross-task breakage the isolation hid gets caught.

**Conflict handling:** If a merge conflicts, the two tasks weren't truly independent. Serialize the remainder: merge one, resolve, then the other (or re-run the conflicting task serially). This is rare when the plan was well-decomposed.

**Use `--parallel` when:** the plan has many independent tasks and git state is clean.
**Avoid `--parallel` when:** tasks share files/interfaces heavily, or you can't absorb a post-merge integration surprise. The final integration-seam review is **mandatory** in this mode — never skip it.

## Fast Review (opt-in: `--fast-review`)

Lightweight Mode already collapses review to one pass for 1-2 file simple tasks. `--fast-review` extends the **single combined reviewer** to **non-critical medium tasks** that would otherwise pay the full two-stage price:

- **Eligible:** Multi-file but mechanical/established pattern; no new public API; does **not** change behavior of other code paths; spec is clear.
- **Ineligible (keep full two-stage):** Touches behavior of other code paths, designs a new interface/API, or a defect would be costly.

For eligible tasks, dispatch **one** combined reviewer (`./combined-reviewer-prompt.md`) instead of spec-then-quality. One read, one dispatch, same coverage.

**Pairing:** `--fast-review` + `--parallel` gives maximum speed. Use together on well-decomposed, low-risk plans; keep full two-stage + serial for the risky ones.

## Handling Implementer Status

Implementer subagents report one of four statuses. Handle each appropriately:

**DONE:** Proceed to spec compliance review.

**DONE_WITH_CONCERNS:** The implementer completed the work but flagged doubts. Read the concerns before proceeding. If the concerns are about correctness or scope, address them before review. If they're observations (e.g., "this file is getting large"), note them and proceed to review.

**NEEDS_CONTEXT:** The implementer needs information that wasn't provided. Provide the missing context and re-dispatch.

**BLOCKED:** The implementer cannot complete the task. Assess the blocker:

1. If it's a context problem, provide more context and re-dispatch with the same model
2. If the task requires more reasoning, re-dispatch with a more capable model
3. If the task is too large, break it into smaller pieces
4. If the plan itself is wrong, escalate to the human

**Never** ignore an escalation or force the same model to retry without changes. If the implementer said it's stuck, something needs to change.

## Review Loop Limits

Review loops have a **maximum of 3 rounds per stage** to prevent runaway iterations. After 3 failed reviews at the same stage, **escalate to the human** — the plan or spec may need revision.

| Stage | Max Rounds | Escalation Action |
|-------|------------|-------------------|
| Spec compliance | 3 | Plan is ambiguous or wrong. Pause and ask human to clarify spec or break task into smaller pieces. |
| Code quality | 3 | Implementation may need architectural rethink. Pause and ask human to decide: accept with documented exceptions, or redesign. |

**How to track rounds:** Increment a counter each time you re-dispatch the same reviewer for the same stage on the same task. When the counter hits 3, stop and escalate.

**Escalation format:** Report to the human with:
- Which stage is stuck (spec or quality)
- How many rounds have been attempted
- What issues remain unresolved
- Your assessment: is the spec wrong, or does the implementation need a different approach?

## Prompt Templates

**Full mode (default):**
- `./implementer-prompt.md` - Dispatch implementer subagent
- `./spec-reviewer-prompt.md` - Dispatch spec compliance reviewer subagent
- `./code-quality-reviewer-prompt.md` - Dispatch code quality reviewer subagent

**Lightweight mode (for simple 1-2 file tasks):**
- `./lightweight-implementer-prompt.md` - Dispatch implementer with lighter requirements
- `./lightweight-reviewer-prompt.md` - Single combined review pass (loosest bar)

**Fast review mode (`--fast-review`, non-critical medium tasks):**
- `./combined-reviewer-prompt.md` - Single combined spec+quality pass (hardened bar)

See "Lightweight Mode" and "Fast Review" for when to use which set. `--parallel` does not change which prompt is used; it changes how implementation is *scheduled* (concurrent worktrees).

## Example Workflow

```
You: I'm using Subagent-Driven Development to execute this plan.

[Read plan file once: docs/superpowers/plans/feature-plan.md]
[Extract all 5 tasks with full text and context]
[Create TodoWrite with all tasks]

Task 1: Hook installation script

[Get Task 1 text and context (already extracted)]
[Dispatch implementation subagent with full task text + context]

Implementer: "Before I begin - should the hook be installed at user or system level?"

You: "User level (~/.config/superpowers/hooks/)"

Implementer: "Got it. Implementing now..."
[Later] Implementer:
  - Implemented install-hook command
  - Added tests, 5/5 passing
  - Self-review: Found I missed --force flag, added it
  - Committed

[Dispatch spec compliance reviewer]
Spec reviewer: ✅ Spec compliant - all requirements met, nothing extra

[Get git SHAs, dispatch code quality reviewer]
Code reviewer: Strengths: Good test coverage, clean. Issues: None. Approved.

[Mark Task 1 complete]

Task 2: Recovery modes

[Get Task 2 text and context (already extracted)]
[Dispatch implementation subagent with full task text + context]

Implementer: [No questions, proceeds]
Implementer:
  - Added verify/repair modes
  - 8/8 tests passing
  - Self-review: All good
  - Committed

[Dispatch spec compliance reviewer]
Spec reviewer: ❌ Issues:
  - Missing: Progress reporting (spec says "report every 100 items")
  - Extra: Added --json flag (not requested)

[Implementer fixes issues]
Implementer: Removed --json flag, added progress reporting

[Spec reviewer reviews again]
Spec reviewer: ✅ Spec compliant now

[Dispatch code quality reviewer]
Code reviewer: Strengths: Solid. Issues (Important): Magic number (100)

[Implementer fixes]
Implementer: Extracted PROGRESS_INTERVAL constant

[Code reviewer reviews again]
Code reviewer: ✅ Approved

[Mark Task 2 complete]

...

[After all tasks]
[Dispatch final integration-seam reviewer — most capable model, scoped to where tasks meet
 (shared interfaces, cross-module calls, merge points), not a full re-read]
Final reviewer: Integration seams clean, ready to merge

Done!
```

### Parallel variant (with `--parallel`)

Instead of dispatching tasks one at a time, fan out all independent implementers in parallel worktrees, then merge and run the (per-task + final integration-seam) reviews serially on the merged result:

[Read plan, extract all 5 tasks, classify each]
[--parallel ON] Fan out implementers for Tasks 1-5, each in its own worktree
  (all five implement concurrently, each follows mtpk-tdd)
[Each completes: implemented, tested, committed, self-reviewed]
[Serially merge worktrees -> working branch]
[Run per-task review on merged code (auto-classified, diff-scoped)]
[Dispatch final integration-seam reviewer across merged whole]
Final reviewer: Integration seams clean, ready to merge

## Advantages

**vs. Manual execution:**

- Subagents follow TDD naturally
- Fresh context per task (no confusion)
- Parallel-safe (subagents don't interfere)
- Subagent can ask questions (before AND during work)

**vs. Executing Plans:**

- Same session (no handoff)
- Continuous progress (no waiting)
- Review checkpoints automatic

**Efficiency gains:**

- No file reading overhead (controller provides full text)
- Controller curates exactly what context is needed
- Subagent gets complete information upfront
- Questions surfaced before work begins (not after)

**Quality gates:**

- Self-review catches issues before handoff
- Review after each task: two-stage (spec then quality) for full mode; single combined pass for lightweight and `--fast-review` tasks
- Review loops ensure fixes actually work
- Spec compliance prevents over/under-building
- Code quality ensures implementation is well-built

**Cost:**

- More subagent invocations than manual execution (implementer + reviewer(s) per task) — but lightweight/combined modes and `--fast-review` cut this, and `--parallel` overlaps implementation across tasks
- Controller does more prep work (extracting all tasks upfront)
- Review loops add iterations (capped at 3 per stage to prevent runaway costs)
- But catches issues early (cheaper than debugging later)

## Red Flags

**Never:**

- Start implementation on main/master branch without explicit user consent
- Skip reviews (spec compliance OR code quality)
- Proceed with unfixed issues
- Dispatch multiple implementation subagents in the **same** worktree/branch in parallel (file/git conflicts). Parallel implementation in **isolated worktrees** is allowed under `--parallel` — that's the whole point of the flag.
- Make subagent read plan file (provide full text instead)
- Skip scene-setting context (subagent needs to understand where task fits)
- Ignore subagent questions (answer before letting them proceed)
- Accept "close enough" on spec compliance (spec reviewer found issues = not done)
- Skip review loops (reviewer found issues = implementer fixes = review again)
- Let implementer self-review replace actual review (both are needed)
- **Start code quality review before spec compliance is ✅** (wrong order)
- Move to next task while either review has open issues

**If subagent asks questions:**

- Answer clearly and completely
- Provide additional context if needed
- Don't rush them into implementation

**If reviewer finds issues:**

- Implementer (same subagent) fixes them
- Reviewer reviews again
- Repeat until approved or **max 3 rounds per stage** — then escalate to human
- Don't skip the re-review

**If subagent fails task:**

- Dispatch fix subagent with specific instructions
- Don't try to fix manually (context pollution)

## Integration

**Required workflow skills:**

- **superpowers:using-git-worktrees** - Ensures isolated workspace (creates one or verifies existing)
- **superpowers:writing-plans** - Creates the plan this skill executes
- **superpowers:requesting-code-review** - Code review template for reviewer subagents
- **superpowers:finishing-a-development-branch** - Complete development after all tasks

**Subagents should use:**

- **superpowers:test-driven-development** - Subagents follow TDD for each task

**Alternative workflow:**

- **superpowers:executing-plans** - Use for parallel session instead of same-session execution
