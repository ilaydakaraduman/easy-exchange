---
name: write-spec
description: Write or revise a single feature spec in /specs for easy-exchange, following the approved plan in docs/plan.md and the project brief. Use when the user asks to draft, write, update, or revise a spec, feature spec, or requirements document for this project.
disable-model-invocation: true
---

# Write a feature spec for easy-exchange

This is a spec-first class assignment. Specs in `/specs` are the source of truth and must be approved by the user before any application code is written. This skill produces exactly one spec file and nothing else.

## Step 1: Read the project context first

Always read these before writing a single line of the spec:

1. `docs/project-brief.md` — the assignment scope
2. `docs/plan.md` — the approved product and architecture plan (data model, metadata fields, state machine, phases, out-of-scope list)
3. Every existing file in `/specs` — to match style, avoid overlap, and reference related specs by filename

Confirm the requested feature is in scope per `docs/plan.md` and `docs/project-brief.md`. If it is not, stop and tell the user instead of writing the spec.

## Step 2: Write the spec

Create or revise only the one file the user asked for, under `/specs`. Follow the existing naming pattern (`NN-feature-name.md`, zero-padded, next free number).

Start the file with a `# Spec: <feature name>` heading and a `**Status:** Draft — awaiting user approval before any application code.` line, then use these sections in this order, every time:

```markdown
## Purpose
## User stories
## Functional requirements
## Acceptance criteria
## Data and business rules
## Out of scope
## Test cases
## Open questions
```

Section guidance:

- **Purpose**: one or two sentences on what the feature does and why it exists for the demo.
- **User stories**: `As a <role>, I want <action> so that <outcome>.` Roles are from the plan: anonymous visitor, logged-in user, listing owner, proposer, counterparty.
- **Functional requirements**: numbered list. Routes, inputs, outputs, error messages, auth requirement (public browse; list / like / trade require login).
- **Acceptance criteria**: Given/When/Then format, one scenario per bullet or block:

  ```markdown
  - **Given** two AVAILABLE matched items, **when** the proposer submits a trade, **then** both items become IN_TRADE and the trade is PROPOSED.
  ```

- **Data and business rules**: models, fields, statuses, uniqueness constraints, state transitions. Copy names exactly from `docs/plan.md` (see below).
- **Out of scope**: what this spec deliberately excludes, plus the brief's global exclusions where relevant (payments, shipping, chat, image upload, OAuth, email verification, sports category, Neo4j, brokers, native mobile).
- **Test cases**: concrete cases mirroring section 5 of `docs/plan.md` where the feature touches the trade service or metadata validation; otherwise list the behaviors a test would assert.
- **Open questions**: anything the plan does not settle that the user must decide.

## Step 3: Use the plan's names exactly

Do not invent fields, statuses, models, routes, or features that are not in `docs/plan.md`. In particular:

**Models**: `User`, `Category`, `Item`, `Like`, `Match`, `Trade`.

**Item status**: `AVAILABLE` | `IN_TRADE` | `TRADED`.
**Trade status**: `PROPOSED` | `ACCEPTED` | `REJECTED` | `CANCELLED`.
**Trade fields**: `item_offered`, `item_requested`, `proposer`, `counterparty`.

**Category metadata keys** (the only allowed keys; no character, line, vaulted, set number, etc.):

| Category (`slug`) | Key | Type | Required | Rule |
| --- | --- | --- | --- | --- |
| `funko` | `box_condition` | int | yes | 1–10 |
| `funko` | `original_box_included` | bool | yes | |
| `funko` | `serial_number` | str | yes | |
| `lego` | `sealed_misb` | bool | yes | |
| `lego` | `missing_parts` | bool | yes | |
| `lego` | `year` | int | yes | |
| `tcg` | `grading` | str | no | e.g. `PSA 10` |
| `tcg` | `card_condition` | str | yes | `Mint` \| `Near Mint` \| `Played` |

`Category.metadata_schema` entries use the keys `key`, `label`, `type`, `required`.

If the feature needs something the plan does not define, put it under **Open questions** rather than adding it to the spec body.

## Step 4: Hard limits

- Write **only** the one spec file requested. Do not touch any other file, including other specs, `docs/`, `PROCESS_LOG.md`, or `.cursor/`.
- Write **no application code**, no scaffolding, no migrations, no tests.
- **Never commit or push.**
- Do not mark the spec as approved; it stays `Draft` until the user says otherwise.

## Step 5: End with assumptions to confirm

Finish the reply with a short list titled **Assumptions to confirm** containing every judgment call you made that the plan did not settle (route names, exact error messages, ordering, edge-case behavior). Each item should be answerable with yes/no or a one-line choice. Then stop and wait for the user's approval or revisions.
