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
  - Q4: [TODO: write the question and my answer]
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
- Folder: /specs. Eight approved specs: 00-overview, 00-architecture,
  01 registration, 02 login/session, 03 listings, 04 browse,
  05 likes and matches, 06 trades, 07 seed data. [TODO: confirm all
  show Status: Approved with Select-String -Path specs\*.md
  -Pattern "Status:"]
- Agent had produced an early draft of 01-user-registration.md before
  planning was done. I reviewed it and found 7 problems (stale "stack
  not chosen", client-side validation that does not fit Django
  templates, no Given/When/Then, no data rules, no test cases, no
  open questions, a meaningless sentence). Had it revised with the
  write-spec skill.
- specs/00-overview.md: agent listed 9 assumptions to confirm. I
  accepted most, moved listing deletion firmly out of scope, and
  turned "edit only while AVAILABLE" and "public status badges" into
  rules. I also found two gaps myself: nowhere for the counterparty
  to see incoming proposals (solved: Matches page also lists trades)
  and a demo step that did not match the seed (solved: show the
  double-booking refusal through the automated test instead).
  Unlike is out of MVP (likes are append-only).
- specs/00-architecture.md: fixes the stack, three apps (accounts,
  catalog, trades), the six models, the state machines and the
  double-booking lock. Decisions during its review:
  - The agent proposed hard-coding value rules (box_condition 1-10,
    card_condition values) in the Python validator. That contradicts
    the brief's goal "a new category is only a new schema". I had
    metadata_schema entries extended with optional min, max, choices
    so the validator stays generic; invalid combinations (min/max on
    a str field, choices on an int field) raise an error when the
    schema is loaded instead of being ignored silently.
  - Two rules written down as business rules: all Item.status and
    Trade.status changes happen only in trades/services.py, and
    AUTH_USER_MODEL is set before the first migration.
  - The extension made three documents disagree (architecture had
    min/max/choices; overview and plan did not). Found with
    Select-String, fixed by hand, and recorded in the plan's
    decision log instead of rewriting the approved plan.
- Spec 02 (login): I caught a flaw in the agent's assumption about
  anonymous POSTs: redirecting a POST-only action to
  /login?next=<action> would make the post-login GET return 405.
  Decision: next is used for GET pages only; anonymous POST to an
  action route goes to /login without next.
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
    rule). Done as a separate, minimal commit: a change to an
    approved document should be deliberate and visible in git.
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
  locked item is refused" demo test are must-have; the parallel
  race test and some view tests are nice-to-have.
- Spec 07 (seed data): two demo users (ada@example.com,
  ben@example.com), one listing per user per category, one
  pre-made reciprocal like pair (the two Funko items) created only
  through like_item, idempotent, one success line, no trades.
  [TODO: write anything I changed in the agent's assumptions, and
  that the open questions were turned into "Decided"]
- Consistency checks: docs/plan.md still said "unlike" and "match
  removed" in Phase 3, which contradicted the append-only decision.
  Aligned plan and overview with the approved specs (min/max/choices
  wording, append-only likes, the like rule on locked items) in a
  documentation commit. The protected-routes table in
  02-login-session.md now names the four trade routes.
- Spec 05 and spec 06 disagreed about the query count on the
  Matches page (three extra queries vs one shared trade query).
  Found while writing tests; the code follows spec 06 (4 queries in
  total). [TODO: confirm I corrected the wording in spec 05 case 38]

## Step 4: Skills used
- Built-in /create-rule: created .cursor/rules/spec-first-workflow.mdc
  (alwaysApply) so the agent does not write application code before
  specs are approved. After the specs were approved I rewrote it for
  the implementation phase: specs are the source of truth, work
  task by task from docs/tasks.md for the range I name, write tests
  only when asked, status changes only in trades/services.py, never
  commit or push. [TODO: add the result of the verification test:
  I asked for "Build the user registration page" before approval,
  did the agent refuse?]
- Built-in /create-skill: created a project skill write-spec
  (.cursor/skills/write-spec/SKILL.md) that forces one spec template,
  exact names from plan.md, one file per run, no code, no commits.
  disable-model-invocation is on so I stay in control of when it runs.
- Improved the skill after first use: explicit filenames and a
  different section list for the two general docs (00-overview,
  00-architecture).
- Imported skill: django-tdd from the open-source repository
  affaan-m/ECC (skills/django-tdd/SKILL.md), added as
  .cursor/skills/django-tdd/SKILL.md. I read the whole file before
  adding it; the directory page showed 2 of 3 security scanners
  passing, so I checked that it asks for no commands or downloads.
  It targets pytest, factory_boy, DRF and Celery, but the specs
  require Django's own test runner. I added a "Project adaptation"
  note under its header: use django.test.TestCase and
  python manage.py test only, no pytest or new dependencies, ignore
  the DRF/Celery/payment parts, keep its general patterns (one
  behavior per test, descriptive names, isolation, helper
  functions, edge cases and permissions). [TODO: write one
  concrete effect the skill had on the tests, for example the test
  naming or the helper functions]
- Not done: a project skill "exchange-domain-conventions" (the rule
  file already holds the status-change and no-commit rules).

## Step 5: Implementation
- Planning the work: in Plan Mode the agent wrote docs/tasks.md (16
  tasks, T0 to T15, each with specs, files, tests and a "done when"
  check). It noticed a dependency I had missed: seed must call
  like_item, so the like service (T8) comes before seed (T9). I
  followed its order instead of my own phase order.
- Prompt technique used for every run: role ("senior Django
  engineer"), context through @-references to plan, tasks and all
  specs, a precise goal (task range), hard rules (specs win, exact
  names and messages, no edits to specs/docs, never commit),
  a per-task check (check, makemigrations, migrate), an ambiguity
  rule (choose the smallest option consistent with the specs and
  report it), a stop rule ("continue from Task N"), and a short
  fixed reply format (files, commands, deviations, not implemented).
- Three runs, each followed by my own manual check and my own
  commit:
  1. Tasks 0-2 (setup, custom user, register, login/logout). Agent
     deviations I accepted: login email as CharField so a bad
     format gets the same generic error; message "Passwords do not
     match." and the button texts Register / Sign in (not named in
     the specs); brand text not a link until task 6.
  2. Tasks 3-9 (Category/Item/validator, create and edit listing,
     browse, detail, like_item, seed). About 24 minutes of agent
     work. Seed run twice gives the same success line.
     [TODO: paste the agent's deviation list for this run]
  3. Tasks 10-15 (like button, Matches page, propose, accept,
     reject, cancel, trade sections). Deviations I accepted:
     created_at/updated_at are set in the service because
     QuerySet.update() ignores auto_now; if the clock has not moved,
     updated_at is created_at plus one microsecond so it stays
     strictly later; 403 and 409 bodies are plain text; one trade
     query for the Matches page.
- My checks: demo flow by hand (Ada proposes on the seeded match,
  both Funko items show IN_TRADE, Ben accepts, both TRADED, both
  Matches pages list the trade under Finished trades); a manual
  reading of trades/services.py against spec 06 requirements 10-16
  (conditional UPDATE, row count 2, transaction.atomic, authorization
  before state, no select_for_update).

### Tests (written after the code, as a separate session)
- Decision: code first, then tests from each task's "Tests" line in
  docs/tasks.md. Rule for the agent: never change application code
  while writing tests; if a test fails because of a bug, stop and
  report it with the spec requirement.
- Slice 1 (trade service, tasks 12-13): 32 tests. The demo test is
  test_second_propose_on_a_locked_item_is_refused. Every test
  docstring names its spec case number.
- Slice 2 (likes, matches, trade views): 119 tests in trades.
  Cursor produced two answers (A and B); both passed, I kept one.
  Notes from the agent: Match.objects.create is used only to test
  the constraints (successful matches come from like_item); the
  query-count test asserts 4 queries, which exposed the spec 05 vs
  06 disagreement above.
- Slice 3 (accounts, catalog, seed): total 261 tests, all OK.
- Deliberate-break check: I removed the status filter in
  propose_trade and ran the propose tests. [TODO: fill in how many
  tests failed and which; then reverted with git checkout and the
  suite was green again. The first attempt passed because the edit
  was not saved, so I now check git diff before running.]
- Known weakness: fixture helpers are imported from
  trades/tests/test_propose.py; moving them to a shared module is a
  possible improvement.

### UI work
- CSS polish (static/css/base.css only, no templates, so the
  assertions on texts and class names stay valid). I ran this before
  the last test run, so CSS and the final test files ended up in one
  commit; the tests written against the markup still passed, which
  confirms the CSS did not change markup.
- Checking the phone view in DevTools showed a shrunken desktop
  layout: the viewport meta tag was missing from base.html, so the
  media queries never applied. (The red console errors came from
  browser extensions, not from the app.)
- Change requests handled spec-first: [TODO: list what was actually
  merged: spec 08 (search, listing photo, category illustrations,
  TCG fields) and/or spec 09 (visual polish). For each: the spec was
  written and approved before any code, the older specs only got a
  "Superseded by" pointer, and existing tests stayed green except
  those the new spec explicitly superseded.]

## Problems & how I fixed them
- Merge conflict in PR #3 (docs/project-brief.md): the agent and I
  had added the same file on different branches. Resolved in the
  GitHub web editor, keeping the more complete version.
- docs/tasks.md was committed by the agent on the old spec branch,
  so it was missing after the PR merge. Found it with
  git log --all -- docs/tasks.md and brought it into the
  implementation branch file by file instead of a blind merge (the
  branches had diverged in plan.md and the specs).
- A commit message said "approve" but the specs still had
  Status: Draft. Now I check the file content with Select-String,
  not the commit message.
- First draft of spec 06 assumed things 05 later fixed differently
  (route style, 405 handling, how refusals are shown). Fixed by
  reading it against 05 before approval, not after.
- docs/plan.md contradicted an approved spec (unlike / match
  removal) and the approved architecture spec contradicted the
  overview after the min/max/choices change. Fixed with separate
  documentation commits instead of editing silently.
- Cursor's PR and Commit & Push buttons merged the test branch into
  main and pushed to the branch while my local branch lagged; my
  push was rejected ("fetch first"). I used git fetch, status -sb
  and log --graph to see the state and pulled instead of forcing
  the push.
- Agent commits: [TODO: only write this if it happened: the agent
  committed although the rule says not to. Now I check git log
  after every agent run.]
- Demo data got dirty during manual tests (an item stayed IN_TRADE).
  Before the demo I delete db.sqlite3, run migrate and seed.
- PowerShell shows mangled characters (for example the curly
  apostrophe) when printing UTF-8 files; the files are fine, I read
  them in the editor.
- Free-tier usage ran out once; I paid for extra usage and did the
  plain git work (add, commit, push) by hand to save requests.

## What I would do next
- Move shared test helpers into one module, add the nice-to-have
  tests (parallel race, query counts), and run /review and
  /review-security.
- Add real listing photos and a Pokémon filter as TCG schema entries
  (new fields need only a schema change, no new tables).
- Switch to PostgreSQL (SELECT ... FOR UPDATE on both item rows in id
  order) as described in the architecture spec.
