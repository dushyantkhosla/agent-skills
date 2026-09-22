# Code Guidance

How to write the code that goes inside a plan's fences. The implementer
transcribes this code; nobody redesigns it on the way to a file. The plan is
the last place its quality is decided, so write it to review standard:
minimal, effective, in scope.

**Enforcement.** This guidance is mandatory for the plan author, not
advisory. Read it in full before writing any code into a plan, and apply it
to every code block — implementation and test alike (test-specific design
stays with the downstream test skills). The plan self-review audits every
snippet against it, and the adversarial plan reviewer reads this file
directly. A violation is a plan failure on the same footing as a
placeholder: it is fixed before the plan leaves the author's hands.

## Read fully, then be lazy

The ladder shortens the solution, never the reading. Understand the task and
trace every file the change touches first; then climb. The first solution
that works is the right one — once you actually know what the change has to
touch.

The spec decides what must exist; the ladder only decides how little code
builds it. Anything the spec explicitly requires is not speculative, and the
ladder never talks you out of it.

## The ladder

Stop at the first rung that holds:

1. **Does this need to exist at all?** A speculative need is skipped, and
   the plan says so in one line.
2. **Does something in this repo already do it?** A helper, util, type, or
   pattern that already lives here — reuse it. Re-implementing what is two
   files over is the most common waste. Look before you write.
3. **Does the standard library do it?** Use it.
4. **Does a native platform feature cover it?** `<input type="date">` over a
   date-picker library; a CSS rule over a JS animation; a database
   constraint over application code.
5. **Does an already-installed dependency solve it?** Use it — and never add
   a new dependency for what a few lines can do.
6. **Can it be one line?** One line.
7. **Only then:** the minimum code that works.

Two rungs both work → take the higher one. Two options the same size → take
the one that is correct on the edge cases.

**Deletion beats addition.** When both solutions hold, prefer the one that
removes over the one that adds: fewer new symbols, no new file unless it
carries its own responsibility, smaller diff. This is a tie-breaker for
understood problems, never a shortcut around understanding — the smallest
change in the wrong place is a second bug.

**Bug fix = root cause.** A report names a symptom. Grep every caller of the
function you are about to touch; one guard in the shared function is a
smaller diff than a guard in every caller, and it fixes the sibling callers
the report never mentioned.

## Match the project

Read the neighbors before writing: imports, naming, error handling,
file and function shape. Conventions beat preferences; a "better" style that
diverges from the codebase is churn. If there is no convention to follow,
pick the boring, obvious option and note the choice in the plan.

## No speculative abstraction

- No interface with one implementation, no factory for one product, no
  config for a value that never changes, no scaffolding "for later".
- Three similar lines beat a premature helper. Add the abstraction at the
  third use, not the first.
- The deletion test: if deleting the unit makes complexity vanish, it was a
  pass-through.

## Clarity over cleverness

Boring is what someone reads at 3am.

- Guard clauses over deep nesting.
- No nested ternaries; use an if/else chain or a lookup.
- Name intermediates and results for their content: `validationErrors`, not
  `data` / `result` / `temp`; no abbreviations except universal ones (`id`,
  `url`, `api`).
- One job per function; if the name needs "and", split it.
- Comments explain why, never what. Delete comments that restate the code.

## Stay in scope

The snippet solves this task, nothing else. No drive-by cleanup, no
modernizing syntax in lines you happen to touch, no "while I'm here"
refactors, no unrequested features. Something worth improving outside the
task is a note in the plan's text, never an edit in its code — mark it
`Noticed but not touching: <thing> (<why it can wait>)`.

## Do not simplify away the essentials

Never cut: input validation at trust boundaries, error handling that
prevents data loss, security measures, accessibility basics, or anything the
spec explicitly requires. Do not remove existing error handling because the
shorter version reads cleaner, and never leave an empty catch or a swallowed
failure. New options and flags default to the conservative behavior.

## Keep it testable

Accept dependencies as parameters instead of constructing them inside.
Return results rather than mutating inputs or ambient state. Keep the public
surface small — every extra parameter is test setup. Interface and seam
design is File Structure's job; this is the code-level half.

## Mark deliberate simplifications

When you knowingly cut a corner with a ceiling — a global lock, an O(n²)
scan, a naive heuristic — mark it where the code lives, naming the ceiling
and the upgrade path:

```python
# Deliberate simplification: global lock; per-account locks if throughput matters.
```

A silent shortcut is a bug waiting to be discovered; a marked one is a
decision a reviewer can accept or veto.

## Before the code step leaves the plan

- Every rung of the ladder checked; the highest that holds is the one used.
- Reused what already exists; no new dependency for a few lines.
- No abstraction without a second user.
- Names say what the things are.
- Validation and error handling intact — nothing simplified away.
- No unrelated change snuck in.
- Would this pass review exactly as written?

---

Adapted from ponytail (github.com/DietrichGebert/ponytail, MIT), with
`incremental-implementation` and `code-simplification` from
addyosmani/agent-skills. Those are sources, not dependencies: this file is
the binding guidance for plan code. Apply it directly; do not invoke
another skill, intensity mode, or output style in its place.
