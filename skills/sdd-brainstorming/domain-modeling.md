# Domain Modeling Companion

Companion to brainstorming. The active discipline: challenge terminology,
stress-test concepts with concrete scenarios, and record the glossary and
decisions the moment they crystallise — never in a batch at the end.

Merely reading `CONTEXT.md` for vocabulary is not this skill; that is a
one-line habit any skill can do. This skill is for when the model is changing,
not just being consumed.

## Files

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   ├── adr/
│   │   ├── 0001-event-sourced-orders.md
│   │   └── 0002-postgres-for-write-model.md
│   └── superpowers/
│       └── specs/
│           └── YYYY-MM-DD-<topic>-design.md
└── src/
```

If a `CONTEXT-MAP.md` exists at the root, the repo has multiple contexts. The
map points to where each one lives:

```
/
├── CONTEXT-MAP.md
├── docs/adr/                      ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/              ← context-specific decisions
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

Create files lazily: only when you have something to write. No `CONTEXT.md`
until the first term is resolved; no `docs/adr/` until the first ADR is
needed. If the repo already has a glossary or ADR convention, match it
instead of introducing a second scheme.

## Glossary: `CONTEXT.md`

`CONTEXT.md` is a glossary and nothing else. It is totally devoid of
implementation details — not a spec, not a scratch pad, not a store for
decisions. Decisions go in ADRs; behavior goes in the spec.

During the session:

- **Challenge against the glossary.** When a term conflicts with the existing
  language, call it out immediately: "Your glossary defines 'cancellation' as
  X, but you seem to mean Y. Which is it?"
- **Sharpen fuzzy language.** When a term is vague or overloaded, propose a
  precise canonical one: "You're saying 'account': do you mean the Customer or
  the User? Those are different things."
- **Discuss concrete scenarios.** Stress-test relationships with specific
  edge-case scenarios that force precision about the boundaries between
  concepts.
- **Cross-reference with code.** When your partner states how something
  works, check whether the code agrees. Surface contradictions: "Your code
  cancels entire Orders, but you just said partial cancellation is possible.
  Which is right?"
- **Update inline.** When a term is resolved, write it to `CONTEXT.md` right
  there, in the same exchange. Do not batch.

A workable entry format:

```markdown
## Order
A customer's request to purchase one or more items. An Order progresses
through Draft → Placed → Fulfilled; cancellation applies to the whole Order
(see Cancellation). Related: Line Item, Shipment, Customer.
```

## ADRs

Offer an ADR only when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful.
2. **Surprising without context** — a future reader will wonder "why did they
   do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and
   one was picked for specific reasons.

If any one is missing, skip the ADR. A reversible, unsurprising choice does
not earn one, and an ADR for every decision is noise that buries the ones
that matter. Decisions that pass the gate are captured inline as they are
made, not swept up at the end.

Default location `docs/adr/NNNN-<slug>.md` with sequential numbering, unless
the repo already uses another convention (match its directory, filenames,
numbering, and section headings).

Template:

```markdown
# ADR-001: Use PostgreSQL for primary database

## Status
Accepted | Superseded by ADR-XXX | Deprecated

## Date
YYYY-MM-DD

## Context
The forces at play: requirements, constraints, and what makes this decision
necessary now.

## Decision
What was decided, in one or two sentences.

## Alternatives Considered
- **[Alternative]**: pros, cons, and why it was rejected.

## Consequences
What becomes easier, what becomes harder, and what follows from this.
```

Lifecycle: PROPOSED → ACCEPTED → (SUPERSEDED or DEPRECATED). Never delete an
old ADR — it captures historical context. When a decision changes, write a
new ADR that references and supersedes the old one.

## Spec handoff

The spec's Design Decisions section references the ADRs created during the
session, and the spec's vocabulary matches `CONTEXT.md`. Neither the glossary
nor the ADRs restate implementation detail — the spec and the plan own that.
