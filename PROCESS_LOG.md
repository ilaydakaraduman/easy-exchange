# Process Log

## Step 1: Idea & scope decisions
- Started from a long original idea doc (P2P collector swap app with
  7 categories, Neo4j, message broker, geo search, mobile).
- Judged it too big for the assignment; process matters more than
  the result.
- Decisions: MVP = Pop Culture & Geek (Funko, Lego, TCG). Sports
  category is a stretch goal. Out of scope: Neo4j, message broker,
  mobile app, real-time chat, price estimation.
- Wrote a short English project brief (docs/project-brief.md).

## Step 2: Planning
- Used Cursor Plan Mode with a prompt that set a role, constraints
  (Python, local demo, small scope) and "do not write code yet".
- Agent asked 5 clarifying questions. My answers:
  - Q1 Interest and matching: A, Tinder-style mutual likes (core
    idea of the brief).
  - Q2 Trade shape: A, exactly 1-for-1 with both parties involved.
  - Q3 Browsing and seed data: A, public browse, login to list/like/
    trade, small seed.
  - Q4: [fill in: question and my answer]
  - Q5 Stack: A, Django + server-rendered templates + SQLite JSON.
- Reviewed plan v1 and asked for 5 corrections:
  1. Metadata fields did not match my brief (condition fields were
     missing).
  2. Double-booking used "read, then update" (race-prone); asked for
     an atomic conditional update plus a PostgreSQL upgrade note.
  3. Plan locked items at propose time, not accept time. I accepted
     this as a deliberate deviation and documented it in the plan's
     decision log (it prevents two users locking the same item).
  4. Seed data was vague; asked for 2 users x 3 categories and one
     pre-made reciprocal like pair.
  5. Added a testing approach.
- Approved plan saved as docs/plan.md.

## Step 3: Specs
- Folder: /specs. Agent had produced an early draft of
  01-user-registration.md before planning was done. I reviewed it and
  found 7 problems (stale "stack not chosen", client-side validation
  that does not fit Django templates, no Given/When/Then, no data
  rules, no test cases, no open questions, a meaningless sentence).
  Had it revised with the write-spec skill.
- specs/00-overview.md: agent listed 9 assumptions to confirm. I
  accepted most, moved listing deletion firmly out of scope, and
  turned "edit only while AVAILABLE" and "public status badges" into
  rules. I also found two gaps myself: nowhere for the counterparty
  to see incoming proposals (solved: Matches page also lists trades)
  and a demo step that did not match the seed (solved: show the
  double-booking refusal through the automated test instead).
  Unlike is out of MVP (likes are append-only).
- Status: [01 approved? / 00-overview approved? update here]

## Step 4: Skills used
- Built-in /create-rule: created .cursor/rules/spec-first-workflow.mdc
  (alwaysApply) so the agent does not write application code before
  specs are approved. [Add result of the verification test.]
- Built-in /create-skill: created a project skill write-spec
  (.cursor/skills/write-spec/SKILL.md) that forces one spec template,
  exact names from plan.md, one file per run, no code, no commits.
  disable-model-invocation is on so I stay in control of when it runs.
- Improved the skill after first review: explicit filenames and a
  different section list for the two general docs (00-overview,
  00-architecture).
- Imported skill: [fill in when you add one, see below]

## Step 5: Implementation (per task)
(not started)

## Problems & how I fixed them
- Merge conflict in PR #3 (docs/project-brief.md): the agent and I
  had added the same file on different branches. Resolved in the
  GitHub web editor, keeping the more complete version.
- Plan file was not where I expected: [fill in how you found it].
- Agent made commits even though the rule said not to commit unless
  asked [only write this if it actually happened]. Now I check
  git log after each agent run.
