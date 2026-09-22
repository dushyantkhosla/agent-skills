# Spec Template

Structure for the design doc at
`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (architectural path).
User preferences for spec location override that default.

Rules for the finished spec:

- No "TBD", "TODO", or empty sections. Every section is either filled in or
  explicitly "none".
- Requirements are traceable: each one traces to the Confirmed Intent below.
- Implementation decisions carry no file paths or code snippets; they go stale
  quickly. Exception: a prototype snippet that encodes a decision more
  precisely than prose can (state machine, reducer, schema, type shape) —
  inline the decision-rich part and note it came from a prototype.
- The spec is a living document: when a decision changes, update the spec
  first, then the implementation.

---

```markdown
# <Topic> — Design Spec

## Problem Statement
The problem from the user's perspective, not the system's. What is painful or
missing today, and for whom.

## Solution
The solution from the user's perspective. What changes for them.

## User Stories
A long, numbered list covering all aspects of the feature, not just the happy
path. Format:

1. As an <actor>, I want a <feature>, so that <benefit>.

## Confirmed Intent
The restate the human partner approved, copied verbatim:

- Outcome:
- User:
- Why now:
- Success:
- Constraint:
- Out of scope:

## Assumptions
Assumptions surfaced during the session and how they fared: confirmed,
corrected, or still unvalidated. Unvalidated assumptions are marked, never
buried in prose.

## Design Decisions
Implementation-level decisions that were made:

- Modules built or modified, and their responsibilities
- Interfaces and contracts between them (signatures, payload shapes)
- Data flow, schema changes, API contracts
- Error handling behavior
- Architectural decisions, linking ADRs (e.g. `docs/adr/0003-...`)

## Testing Decisions
- What makes a good test for this feature: external behavior, not
  implementation details
- The seams where the feature will be tested: existing seams preferred, the
  highest seam that covers the behavior, as few as possible (one is ideal)
- Which modules get which tests
- Prior art: similar tests already in the codebase to imitate

## Success Criteria
Specific, testable conditions. Vague asks were reframed with the partner
("make it faster" → LCP < 2.5s, initial load < 500ms). Nothing untestable.

Each criterion names how it will be verified: the command or recorded
procedure that proves it, the environment it runs in, and the expected
result. A criterion that cannot name its verification method is not a
criterion yet — tighten it or cut it. `sdd-verification-before-completion` keys
its acceptance checklist to these rows.

## Out of Scope / Not Doing
What is explicitly not being built, and why. This is the trade-off list: say
no to good ideas here so the scope stays honest.

## Open Questions
Anything unresolved that must be answered before or during implementation.

## Further Notes
Anything else the plan author needs.
```
