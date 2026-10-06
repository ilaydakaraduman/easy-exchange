## Process Log
 
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
- specs/00-architecture.md (approved): fixes the stack, three apps
  (accounts, catalog, trades), the six models, the state machines
  and the double-booking lock. Two decisions during its review:
  - metadata_schema entries get optional min, max, choices, so value
    rules (box_condition 1-10, card_condition choices) live in the
    schema data and the validator stays generic. A schema check
    rejects invalid combinations.
  - I had two rules written down as business rules: all Item.status
    and Trade.status changes only in trades/services.py, and
    AUTH_USER_MODEL is set before the first migration.
- Specs 03 and 04: agent proposed hard-to-test view case counts
  (20+ cases); I asked it to mark must-have vs nice-to-have. I added
  a privacy rule the agent had not listed: public pages show only
  the owner's display_name, never the email, with a test (04).
- Spec 05 (likes and matches): I answered 12 of the agent's 14
  assumptions with "yes". Two were real decisions:
  - Q13, new likes on locked items. The plan is silent on new likes.
    I chose a hybrid: likes on IN_TRADE items are allowed (the item
    can return to AVAILABLE); likes on TRADED items are refused by
    like_item (LikeNotAllowed, "This listing has already been
    traded.") and the Like form is hidden. TRADED is terminal and
    would create dead matches in the demo.
  - Q14, the approved architecture spec needed two small edits
    (duplicate like becomes idempotent; the TRADED / IN_TRADE like
    rule with tests 12a and 12b). Done as a separate, minimal
    commit: a numbered spec wins over the architecture spec, and a
    change to an approved document should be deliberate and visible
    in git.
- Spec 06 (trades): drafted with Claude in a chat, using
  docs/plan.md, 00-architecture.md and 05-likes-matches.md as input
  (the first draft was written before I had shared 05). After
  reading 05 I had it corrected in four places:
  - routes use 05's style (no trailing slash);
  - non-POST returns 405 even for anonymous visitors, and anonymous
    POST goes to /login with no next;
  - refusals return the HTTP status with the fixed message in the
    body (like the like route) instead of re-rendering the page;
  - the Matches page shows the trade sections even when the user
    has no matches.
  Test priorities: service tests and the "second propose on a
  locked item is refused" demo test are must-have; view tests are
  mostly nice-to-have, except one 403 check.
- Spec 07 (seed data): merged. [fill in: demo account emails and
  anything I changed in the agent's assumptions]
- Consistency check: while reading 05 I noticed docs/plan.md still
  says "unlike" and "match removed" in Phase 3, which contradicts
  the append-only decision. I prepared one prompt that aligns
  docs/plan.md and specs/00-overview.md with the approved specs
  (min/max/choices wording, append-only likes, the like rule on
  locked items) and lists remaining contradictions without editing
  them. [update when run: diff result and contradiction list]
- Follow-ups noted in 06: protected-routes table in
  02-login-session.md needs the four trade routes; the query-count
  test in 05 changes by three once the trade sections exist.
  [update when done]
- Status: [01 approved? / 00-overview approved? / 06 approved?
  update here]
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
- Planned: a project skill exchange-domain-conventions (status
  changes only in services.py, fixed error messages from the specs,
  tests call services, AUTH_USER_MODEL first). [fill in when created]
- Imported skill: [fill in when you add one]
## Step 5: Implementation (per task)
(not started)
- Plan: write specs/TASKS.md from plan section 6, then implement
  phase by phase (1 skeleton + auth, 2 catalog and browse, 3 likes,
  matches and seed, 4 trades, 5 polish). Tests first for each task;
  after each task run python manage.py test, read the diff and
  commit. Then run /review and /review-security and update specs
  where code and specs drift.
## Problems & how I fixed them
- Merge conflict in PR #3 (docs/project-brief.md): the agent and I
  had added the same file on different branches. Resolved in the
  GitHub web editor, keeping the more complete version.
- Plan file was not where I expected: [fill in how you found it].
- Agent made commits even though the rule said not to commit unless
  asked [only write this if it actually happened]. Now I check
  git log after each agent run.
- First draft of spec 06 assumed things 05 later fixed differently
  (route style, 405 handling, how refusals are shown). Fixed by
  reading it against 05 before approval, not after.
- docs/plan.md contradicted an approved spec (unlike / match
  removal). Fixed with a separate documentation commit instead of
  editing silently.
