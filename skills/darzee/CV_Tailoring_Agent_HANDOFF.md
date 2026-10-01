# Tailor-CV Agent Skill — Project Handoff

## 1. Project Goal

Build a portable **Agent Skill** named `tailor-cv` for coding-agent harnesses such as Codex and Claude Code.

The harness is the application and conversational interface. This project does **not** need its own web app, backend API, authentication layer, database, or UI.

The user should be able to say something like:

> My CV is attached. Here is the job description. Use the `tailor-cv` skill and give me a tailored PDF and a motivation letter as a Markdown file.

The skill should then:

1. Read the user's source CV.
2. Read the full copy-pasted job description.
3. Convert the CV into a structured RenderCV representation.
4. Analyze and prioritize the job requirements.
5. Map those requirements to evidence in the user's CV.
6. Tailor the CV under strict truthfulness constraints.
7. Optionally ask targeted clarification questions.
8. Validate the tailored CV.
9. Render the final PDF with RenderCV.
10. Write a matching motivation/cover letter.
11. Return the generated artifacts to the user.

The core principle is:

> Given factual career history X and opportunity Y, construct the strongest truthful representation of X for Y.

The skill must optimize for relevance, clarity, evidence, and ATS readability without inventing experience, outcomes, tools, seniority, metrics, or responsibilities.

---

## 2. MVP Definition

The MVP is **not an application**.

It is a self-contained Agent Skill that can be installed into a compatible coding-agent harness.

The MVP should support this workflow:

```text
User
 |
 +--> attaches CV / LinkedIn PDF / RenderCV YAML
 |
 +--> pastes full job description
 |
 +--> invokes `tailor-cv`
 |
 +--> optionally specifies:
 |      - one-shot mode
 |      - interactive mode
 |
 v
Agent Skill
 |
 +--> ingest CV
 +--> convert to RenderCV YAML
 +--> analyze job description
 +--> build evidence map
 +--> tailor CV
 +--> validate claims
 +--> render PDF
 +--> write motivation letter
 +--> write tailoring report
 |
 v
Artifacts returned to user
```

Expected primary outputs:

```text
tailored_cv.pdf
tailored_cv.yaml
motivation_letter.md
tailoring_report.md
```

The skill may create intermediate structured files when useful, but the user-facing experience should remain simple.

---

## 3. Intended User Experience

### Standard invocation

Example:

> My CV is attached. Here is the job description below. Use the `tailor-cv` skill and give me a tailored CV PDF and motivation letter as Markdown.

The user then pastes the full job description.

The skill should infer the normal workflow without requiring a command-line interface or form.

---

### One-shot invocation

Example:

> Use one-shot mode. Do not ask me questions.

The skill must use only facts already present in the source CV.

---

### Interactive invocation

Example:

> Use interactive mode and ask me if important evidence is missing.

The skill should identify only high-value ambiguities or gaps and ask targeted questions before completing the final artifacts.

The conversation itself is the state machine. No separate interaction framework is needed.

---

## 4. Required Inputs

### A. Source CV

Accept, where the harness supports them:

- PDF
- DOCX
- LinkedIn profile PDF
- Existing RenderCV YAML

Recommended onboarding language:

> Attach your current CV. If you do not have one handy, export your LinkedIn profile as a PDF and attach that instead.

An existing CV should be preferred over LinkedIn when both are available, since it may contain richer or more application-relevant detail.

---

### B. Full Job Description

The skill must ask for a **copy-paste of the full job description** if one has not already been provided.

Suggested prompt:

> Paste the full job description for the role you want to apply to.

The pasted job description is the authoritative tailoring input.

A job-posting URL may be used as supplemental context, but it should not be required and should not replace the pasted text.

Reasons:

- Job pages disappear.
- Some require authentication.
- Some block scraping.
- Page content may change.
- The harness may not always have browser access.
- A pasted description makes the skill portable and deterministic.

Optional metadata that may be inferred from the description:

- Company
- Role title
- Location
- Application language

Do not ask for metadata that is already obvious from the job description.

---

## 5. Recommended Repository Structure

Keep the project small.

```text
tailor-cv/
├── SKILL.md
├── references/
│   ├── tailoring-principles.md
│   ├── evidence-rules.md
│   └── rendercv-notes.md
├── scripts/
│   ├── validate_rendercv.py
│   ├── render_cv.py
│   └── extract_cv.py          # only if deterministic extraction adds value
├── tests/
│   ├── test_truthfulness.py
│   ├── test_rendering.py
│   └── fixtures/
└── examples/
    └── ...
```

Do not add infrastructure unless a real need appears.

No MVP requirement for:

- FastAPI
- SvelteKit
- React
- database
- authentication
- user accounts
- cloud storage
- queues
- job-board scraping
- application tracking

The coding-agent harness provides the runtime, user interaction, file handling, and conversational state.

---

## 6. Separation of Responsibilities

The skill should separate **reasoning policy** from **deterministic mechanics**.

### `SKILL.md` and reference files own:

- Job-description analysis
- Evidence matching
- Tailoring methodology
- One-shot behavior
- Interactive behavior
- Truthfulness policy
- What may and may not be rewritten
- Cover-letter policy
- Final quality checks

### Helper scripts own:

- File extraction where useful
- RenderCV validation
- RenderCV rendering
- Deterministic file generation
- Mechanical schema checks

Do not bury the tailoring methodology inside Python.

The agent should reason using the skill instructions. Scripts should be used where deterministic tooling is safer than free-form model behavior.

---

## 7. RenderCV's Role

RenderCV should be treated as the structured CV and publication layer.

RenderCV owns:

- CV schema
- Validation
- Layout
- Typesetting
- PDF generation
- Supported export formats

The custom skill owns:

- Understanding the job
- Matching requirements to evidence
- Selecting relevant material
- Reordering content
- Rewriting content truthfully
- Identifying evidence gaps
- Verifying claims
- Writing the motivation letter

Conceptually:

```text
tailor-cv skill
     |
     +--> RenderCV schema / skill / CLI
              |
              +--> validate
              +--> render
              +--> PDF
```

If RenderCV provides an Agent Skill compatible with the harness, prefer using or delegating to it for RenderCV-specific mechanics rather than duplicating its full instructions.

---

## 8. Canonical CV Representation

Convert the source CV into valid RenderCV YAML before tailoring.

Example working artifact:

```text
master_cv.yaml
```

For a single execution, this is the factual source of truth.

The import process should preserve:

- Name and contact details
- Summary/profile
- Work experience
- Education
- Projects
- Skills
- Certifications
- Publications
- Awards
- Languages
- Dates
- Locations
- Existing metrics
- Existing quantified outcomes
- Other relevant sections

The agent may normalize formatting and wording.

It may not invent facts during conversion.

If extraction is ambiguous, preserve or surface the ambiguity instead of silently resolving it.

Examples:

- Unclear dates
- Unclear employer/role association
- Broken PDF extraction
- Ambiguous bullet ownership
- Unreadable characters

A technology must not be inferred merely because it would commonly be used in a particular project.

---

## 9. Core Skill Workflow

```text
[1] INGEST
    Read attached CV
    Convert into RenderCV YAML
    Validate extraction

        |
        v

[2] ANALYZE JOB DESCRIPTION
    Extract and prioritize real hiring signals

        |
        v

[3] BUILD EVIDENCE MAP
    Requirement -> CV evidence

        |
        +----------------------+
        |                      |
        v                      v

    ONE-SHOT              INTERACTIVE
        |                      |
        |                Ask targeted
        |                high-value
        |                questions
        |                      |
        +----------+-----------+
                   |
                   v

[4] TAILOR CV
    Select
    Remove
    Reorder
    Rewrite
    Align terminology

        |
        v

[5] TRUTHFULNESS CHECK
    Compare tailored claims
    against source evidence

        |
        v

[6] RENDERCV VALIDATION
    Validate schema
    Repair structural issues only

        |
        v

[7] RENDER PDF

        |
        v

[8] WRITE MOTIVATION LETTER

        |
        v

[9] WRITE TAILORING REPORT

        |
        v

[10] RETURN ARTIFACTS
```

---

## 10. Job Description Analysis

The first reasoning task is **not rewriting the CV**.

It is understanding what the employer actually cares about.

Extract and deduplicate the following.

### Core responsibilities

Identify the small number of responsibilities that define the role.

Target roughly 3–6 meaningful responsibilities rather than treating every sentence equally.

---

### Required qualifications

Examples:

- Type or years of experience
- Domain knowledge
- Technical tools
- Leadership responsibility
- Education
- Certifications
- Languages
- Location/work authorization requirements

---

### Preferred qualifications

Keep these separate from required qualifications.

Do not silently promote a preferred qualification into a hard requirement.

---

### Repeated or emphasized signals

Pay attention to:

- Repeated skills
- Repeated outcomes
- Repeated domains
- Role-title language
- Requirements appearing early
- Responsibilities receiving unusually detailed treatment

---

### Relevant terminology

Capture exact terminology where useful, especially:

- Technologies
- Frameworks
- Methodologies
- Industry/domain terms
- Credentials
- Product categories
- Regulatory concepts

Do not blindly reproduce buzzwords.

---

## 11. Evidence Mapping

Before rewriting anything, construct an internal evidence map.

Example:

```yaml
- requirement: "Lead cross-functional AI product initiatives"
  importance: high
  evidence:
    - source: "Experience > Company A > bullet 2"
      strength: strong
      notes: "Owned delivery across product, data, and engineering"
  status: strong

- requirement: "AWS deployment experience"
  importance: medium
  evidence: []
  status: absent
```

Recommended statuses:

```text
strong
partial
absent
ambiguous
```

Every important job requirement should be evaluated against the source CV.

The evidence map is the control layer that prevents tailoring from becoming creative writing.

---

## 12. Truthfulness Invariant

This is the most important rule in the skill.

> Tailoring may change selection, ordering, emphasis, and wording. It may never introduce a new factual claim without user confirmation.

Allowed transformations:

- Reorder bullets
- Remove irrelevant bullets
- Shorten verbose bullets
- Rewrite for clarity
- Surface stronger existing evidence
- Use equivalent employer terminology
- Reframe an existing achievement around a relevant outcome
- Move relevant skills higher
- Quantify using metrics already present
- Add facts explicitly confirmed by the user in interactive mode

Not allowed without confirmation:

- Add a tool or technology
- Add people-management responsibility
- Add project ownership
- Add deployment responsibility
- Add an industry/domain
- Add a metric
- Add customer count
- Add revenue impact
- Add cost savings
- Add team size
- Add certifications
- Inflate project scope
- Change historical job titles
- Convert participation into leadership

Example:

Source CV:

> Built forecasting models for customer demand.

Job description:

> Experience deploying ML models in AWS.

Forbidden rewrite:

> Built and deployed forecasting models in AWS.

Correct one-shot behavior:

> Do not claim AWS.

Correct interactive behavior:

> Ask whether the user actually deployed the models in AWS.

Only incorporate AWS if the user confirms it.

---

## 13. Tailoring Principles

These rules are the consolidated, verified methodology the skill should follow.

### A. Start with employer priorities

Identify the most important requirements before editing the CV.

Do not optimize against every sentence equally.

---

### B. Map requirements to truthful evidence

For each important requirement, identify what evidence exists in the user's career history.

No evidence -> no claim.

---

### C. Select by relevance

Remove or shorten impressive but irrelevant material when it competes with stronger evidence.

Tailoring is partly subtraction.

---

### D. Reorder by relevance

Within each role, move the strongest job-relevant achievements toward the top.

The original order is not sacred.

---

### E. Tailor the top of the first page

Where appropriate:

- Use a truthful target headline
- Rewrite the professional summary
- Surface the most relevant skills
- Make role fit obvious quickly

Do not change historical job titles to mimic the target job.

---

### F. Use employer terminology where truthful

Prefer exact terminology for relevant:

- Tools
- Technologies
- Methods
- Skills
- Credentials
- Industry concepts

Use terminology naturally.

Do not keyword-stuff.

---

### G. Write evidence-oriented bullets

Prefer:

```text
Action + what was done + scope/context + outcome
```

Quantify when meaningful and supported.

Do not force every bullet to contain a number.

If no metric exists, describe scope or outcome precisely.

---

### H. Demonstrate soft skills through evidence

Avoid empty claims such as:

- team player
- strategic
- self-starter
- excellent communicator

Show these traits through accomplishments where possible.

---

### I. Use precise verbs, not seniority-coded verb rules

Do not use a rigid taxonomy such as:

```text
senior -> owned / drove
junior -> assisted / supported
```

Use the verb that most accurately describes what the candidate did.

Seniority should emerge from scope, ownership, and outcomes.

---

### J. Keep the result ATS-readable

Prefer simple conventional structure.

Focus on:

- Parseable sections
- Clear headings
- Conventional dates
- Exact terminology where useful
- Relevant skills in context
- Relevant skills in the skills section
- Minimal decorative complexity

Do not optimize for fictional ATS folklore.

---

## 14. One-Shot Mode

Purpose:

Produce the strongest truthful application without interrupting the user.

Rules:

```text
Use only facts already present in the source CV.
Never infer missing facts.
Never invent metrics.
Never upgrade responsibility.
Never manufacture keyword matches.
```

If a requirement has no evidence:

- Do not claim it.
- Do not ask the user about it.
- Record it in the tailoring report if materially relevant.

The agent may emphasize adjacent or transferable experience.

Example:

If the JD asks for healthcare experience and the candidate has fintech experience, the agent may emphasize regulated-data experience if present.

It may not call that healthcare experience.

---

## 15. Interactive Mode

Interactive mode exists to uncover high-value missing evidence.

It should **not** interview the user about their entire career.

After building the evidence map:

1. Identify important requirements marked `partial`, `absent`, or `ambiguous`.
2. Decide whether clarification could materially improve the application.
3. Ask only a small number of targeted questions.
4. Incorporate only confirmed facts.
5. Continue tailoring after receiving the answers.

Examples:

> This role emphasizes team leadership. Your CV says you delivered the analytics platform but doesn't specify your role. Did you lead the initiative, co-lead it, or contribute as an individual contributor?

> The job asks for measurable operational impact. Your CV says you automated reporting. Do you know approximately how much time this saved?

> The role asks for AWS experience. Did any of the projects already listed in your CV run on AWS?

Avoid low-value questions.

Do not ask for a metric merely because metrics look good on resumes.

---

## 16. Motivation / Cover Letter

Generate the motivation letter **after the tailored CV is finalized**.

Inputs:

- Source CV
- Tailored CV
- Evidence map
- Job description
- Role title
- Company
- Confirmed answers from interactive mode

The letter should:

- Be specific to the role
- Highlight roughly 2–4 strongest evidence-backed matches
- Explain motivation only where there is evidence/context
- Avoid repeating the CV line by line
- Avoid generic enthusiasm filler
- Avoid invented claims about the employer
- Avoid invented personal motivations
- Remain concise by default

If motivation is unknown in one-shot mode, use restrained factual language rather than fabricating a personal story.

In interactive mode, the agent may ask:

> Why does this role or company interest you?

Only ask if the answer would materially improve the letter.

Default output:

```text
motivation_letter.md
```

---

## 17. Tailoring Report

Every run should produce a short audit trail.

Example:

```markdown
# Tailoring Summary

## Top requirements identified

1. Product leadership
2. Applied AI / machine learning
3. Stakeholder management
4. Python and data expertise
5. Financial-services experience

## Changes made

- Moved AI product work above general analytics work.
- Reordered six bullets to foreground relevant achievements.
- Rewrote four bullets to clarify ownership and outcomes.
- Used exact "machine learning" terminology where supported.
- Reordered the skills section around role priorities.
- Removed three low-relevance bullets.

## Unresolved gaps

- No evidence of direct people management.
- No evidence of AWS deployment experience.
- No quantified revenue impact available.

## Integrity check

No unsupported factual claims were added.
```

This report is both:

- a trust feature for the user
- a debugging artifact for skill development

Default output:

```text
tailoring_report.md
```

---

## 18. Output Artifacts

Required MVP outputs:

```text
tailored_cv.pdf
tailored_cv.yaml
motivation_letter.md
tailoring_report.md
```

Optional debug/development outputs:

```text
job_analysis.yaml
evidence_map.yaml
master_cv.yaml
```

The skill should return clear paths/links to the final user-facing artifacts according to the host harness's conventions.

---

## 19. Suggested `SKILL.md` Responsibilities

The top-level skill should remain concise enough for agents to follow reliably.

Recommended conceptual sections:

```text
---
name: tailor-cv
description: Use when the user provides a CV and job description and wants a truthful role-specific CV and motivation letter.
---

# Tailor CV

## Inputs
## Workflow
## Non-negotiable truthfulness rules
## Job analysis
## Evidence matching
## One-shot mode
## Interactive mode
## Tailoring rules
## RenderCV handoff
## Motivation letter
## Validation
## Outputs
```

Put detailed supporting material into `references/` rather than bloating `SKILL.md`.

Use progressive disclosure.

---

## 20. Reference Files

### `references/tailoring-principles.md`

Contains:

- Consolidated research-backed tailoring advice
- Prioritization rules
- Bullet-writing guidance
- ATS guidance
- Skills-section guidance
- Summary/headline guidance

---

### `references/evidence-rules.md`

Contains:

- Truthfulness invariant
- Allowed transformations
- Forbidden transformations
- Evidence status definitions
- Interactive clarification policy
- Examples of acceptable/unacceptable rewrites

---

### `references/rendercv-notes.md`

Contains only what the custom skill needs to use RenderCV safely:

- Expected YAML flow
- Validation workflow
- Rendering workflow
- Known integration conventions
- Relevant CLI commands

Do not copy the entire RenderCV schema into this project if it can be delegated to RenderCV itself.

---

## 21. Helper Scripts

Helper scripts should exist only where deterministic behavior improves reliability.

### `validate_rendercv.py`

Responsibilities:

- Validate YAML
- Surface schema errors clearly
- Exit non-zero on invalid output

---

### `render_cv.py`

Responsibilities:

- Invoke RenderCV
- Produce PDF
- Surface rendering errors
- Avoid changing CV content

---

### `extract_cv.py`

Optional.

Use only if deterministic extraction provides value beyond what the harness can already read.

Responsibilities may include:

- PDF text extraction
- DOCX text extraction
- Basic cleanup

The agent should still perform semantic reconstruction into RenderCV format.

Do not over-engineer document extraction for MVP.

---

## 22. Validation Pipeline

Before returning artifacts, run four checks.

### 1. Factual consistency

Compare the tailored CV against:

- source/master CV
- confirmed user answers

Flag or remove every unsupported factual proposition.

This check should be conservative.

---

### 2. Evidence coverage

For major job requirements, confirm that:

- strong evidence is surfaced prominently
- partial evidence is not exaggerated
- absent evidence is not fabricated

---

### 3. RenderCV structural validation

Validate the generated YAML.

Repair structural/schema issues without modifying career facts.

---

### 4. Presentation sanity check

Check for:

- excessive length
- duplicate bullets
- awkward ordering
- malformed dates
- broken rendering
- orphan headings
- keyword stuffing
- repetitive wording
- obvious extraction errors

---

## 23. Failure Modes to Prevent

### Hallucinated achievements

Highest-priority failure.

---

### Invented metrics

Never generate plausible numbers.

---

### Technology inference

Do not infer AWS, Azure, Kubernetes, SQL, Python, etc. because they seem likely.

---

### Responsibility inflation

Do not turn:

```text
participated -> led
contributed -> owned
helped -> managed
analyzed -> defined strategy
```

unless the evidence supports it.

---

### Historical job-title rewriting

Do not rename prior roles to mirror the target role.

A truthful target headline is allowed.

---

### Over-tailoring

Do not make the CV read like a copy of the job description.

---

### Keyword stuffing

Exact terminology is useful.

Mechanical repetition is not.

---

### Excessive questioning

Interactive mode should ask only questions that could materially improve the application.

---

### Cover-letter fabrication

Do not invent:

- motivations
- company knowledge
- personal stories
- employer facts
- enthusiasm claims

---

## 24. Tests Worth Writing Early

### Truthfulness test

Given:

```text
CV: "Built forecasting models."
JD: "Deploy ML systems to AWS."
```

Assert:

```text
final CV does not mention AWS
```

---

### Responsibility test

Given:

```text
CV: "Contributed to analytics platform."
JD: "Own analytics platform strategy."
```

Assert:

```text
final CV does not claim ownership
```

---

### Metric test

Given no time-saving metric:

```text
assert no time-saving number is invented
```

---

### Exact terminology test

Given:

```text
CV: "PostgreSQL"
JD: "Postgres"
```

Equivalent terminology normalization is allowed.

---

### Interactive confirmation test

If the user confirms:

```text
"Yes, I deployed those models to AWS SageMaker."
```

then that fact may be incorporated.

---

### Historical-title test

Previous job titles must remain unchanged.

---

### Render test

Generated YAML must validate and successfully render to PDF.

---

### Cover-letter consistency test

Every substantive career claim in the letter must exist in:

- source CV
- tailored CV
- or confirmed user answers

---

## 25. MVP Acceptance Criteria

The MVP is successful when a user can provide:

1. an attached CV, and
2. a copy-pasted job description,

and the harness can invoke `tailor-cv` to produce a complete application package.

### Input handling

- Reads a normal CV PDF.
- Reads a LinkedIn-exported PDF.
- Accepts RenderCV YAML directly.
- Detects material extraction ambiguity.

### Job analysis

- Produces a deduplicated, prioritized requirement set.
- Distinguishes required from preferred qualifications.
- Captures useful exact terminology.

### Evidence matching

- Maps major requirements to actual CV evidence.
- Marks each as strong, partial, absent, or ambiguous.

### One-shot mode

- Introduces no unsupported factual claims.
- Reorders and rewrites relevant material effectively.
- Leaves missing requirements unclaimed.

### Interactive mode

- Asks only targeted high-value questions.
- Incorporates only confirmed information.

### Rendering

- Produces valid RenderCV YAML.
- Produces a readable PDF.

### Motivation letter

- Is role-specific.
- Uses the same evidence base as the CV.
- Introduces no unsupported career facts or invented motivation.

### Auditability

- Produces a concise tailoring report.
- Lists unresolved gaps.
- Confirms whether unsupported claims were prevented.

---

## 26. Non-Goals for MVP

Do not build:

- Web UI
- Backend API
- Authentication
- User accounts
- Database
- Job-board scraping
- Automated job application
- LinkedIn account integration
- Recruiter outreach
- Interview preparation
- Applicant tracking
- Job recommendation
- Proprietary ATS scoring
- SaaS infrastructure

The harness already provides the user-facing application surface.

---

## 27. Recommended Build Order

### Phase 1 — Skill skeleton

Create:

```text
SKILL.md
references/
scripts/
tests/
```

Define the basic invocation contract and outputs.

---

### Phase 2 — RenderCV round trip

Prove:

```text
source CV
   ->
RenderCV YAML
   ->
validated YAML
   ->
PDF
```

Do this before adding sophisticated tailoring.

---

### Phase 3 — Job analysis

Implement instructions and structured output for:

- requirement extraction
- prioritization
- deduplication
- required vs preferred
- terminology extraction

---

### Phase 4 — Evidence mapping

Implement:

```text
requirement -> source evidence -> status
```

Make traceability explicit.

---

### Phase 5 — One-shot tailoring

Implement:

- selection
- subtraction
- reordering
- rewriting
- skills alignment
- top-of-page tailoring
- factual consistency check

This is the core MVP behavior.

---

### Phase 6 — Interactive mode

Add:

- gap prioritization
- targeted questions
- user-confirmed facts
- evidence-map updates
- resume tailoring after clarification

---

### Phase 7 — Motivation letter + report

Generate:

```text
motivation_letter.md
tailoring_report.md
```

from the same evidence base.

---

### Phase 8 — Hardening

Test:

- hallucinations
- poor PDF extraction
- sparse CVs
- long CVs
- ambiguous dates
- irrelevant JDs
- repeated applications
- RenderCV failures

---

## 28. Definition of Done

Given a compatible agent harness, a user should be able to say:

> My CV is attached. Here is the job description. Use the `tailor-cv` skill and give me a tailored PDF and motivation letter as a Markdown file.

The skill should then:

1. Read the attached CV.
2. Read the pasted job description.
3. Convert the CV into structured RenderCV YAML.
4. Analyze the role.
5. Build a requirement-to-evidence map.
6. Tailor the CV in one-shot or interactive mode.
7. Ensure no unsupported factual claim was introduced.
8. Validate the RenderCV document.
9. Render the final CV PDF.
10. Write the motivation letter.
11. Write a short tailoring report.
12. Return the generated artifacts through the harness.

There is no separate application to operate.

The coding-agent harness **is** the application.

The quality bar is not:

> Does the CV contain enough keywords?

The quality bar is:

> Does this application surface the strongest truthful evidence for this specific role while making unsupported claims impossible or obvious?
