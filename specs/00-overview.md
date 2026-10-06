# Spec: Product overview

**Status:** Approved

## Purpose

Easy Exchange is a small, locally demoable peer-to-peer marketplace where collectors list pop-culture items, like each other's listings, get matched on reciprocal likes, and complete 1-for-1 trades without money. This document is the entry point to `/specs`: it fixes the product scope, the roles, the core flows, and the shared vocabulary that every feature spec uses. Stack, data model, and the trade state machine live in `specs/00-architecture.md`; per-feature behavior lives in the numbered specs.

Source of truth: [../docs/plan.md](../docs/plan.md) (approved plan) and [../docs/project-brief.md](../docs/project-brief.md) (assignment brief). Where this overview and a numbered spec disagree, the numbered spec wins for that feature and this overview should be revised.

## Target users

Collectors in the Pop Culture & Geek community (Funko, Lego, trading card games) who own items they are willing to give up and want items other collectors own. Users act in one of these roles at a given moment:

| Role | Who | What they can do |
| --- | --- | --- |
| Anonymous visitor | Not signed in | Register, sign in, browse and view listings (read-only) |
| Logged-in user | Signed in | Everything a visitor can do, plus create listings and like other users' listings |
| Listing owner | Logged-in user viewing or editing an `Item` they own | Create and edit their own listings; cannot like their own items |
| Proposer | Logged-in user who proposes a trade on a `Match` | Propose a trade offering their own matched item; cancel their `PROPOSED` trade |
| Counterparty | The other owner in a `Match` with a `PROPOSED` trade | Accept or reject the proposed trade |

For the live demo the users are the two seeded accounts from `docs/plan.md` section 4 (plus any account created through registration).

## MVP scope

One vertical, **Pop Culture & Geek**, with exactly three `Category` rows (`slug` values `funko`, `lego`, `tcg`). Each category has fixed metadata fields defined in `Category.metadata_schema` (entries use the keys `key`, `label`, `type`, `required`):

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

These are the only metadata keys in the MVP. Adding a category later means adding a `Category` row with a new `metadata_schema`, not new tables.

MVP features, in implementation order (plan section 6):

1. **Accounts** — register (`specs/01-user-registration.md`), login at `/login` and logout at `/logout` with a session cookie (`specs/02-login-session.md`). Email is unique case-insensitively; passwords are hashed. No OAuth, no email verification.
2. **Catalog** — create and edit a listing (`Item`) with `title`, `description`, `category`, and `metadata` validated against the category's `metadata_schema`; public browse filtered by category; public listing detail. An `Item` can be edited only while its status is `AVAILABLE`. Listings are not deleted in the MVP. Text only, no image upload.
3. **Likes and matches** — a logged-in user likes another user's `Item` (`Like`, unique per `(user, item)`, not allowed on own items). When the owner of item X has liked item Y **and** the owner of item Y has liked item X, a `Match` for the pair `(item_a, item_b)` exists. Likes are append-only: there is no unlike, so a `Match` is never removed. The Matches page lists the pairs the user can propose a trade on and is also the single place where the user's trades are shown (see 4); there is no separate "My trades" page. (`specs/05-likes-matches.md`)
4. **Trades** — exactly one item for one item. Either matched owner proposes; the `Trade` records `item_offered`, `item_requested`, `proposer`, `counterparty`, and `status`. Proposing locks both items `AVAILABLE → IN_TRADE` atomically (double-booking prevention); accept moves them to `TRADED`; reject or cancel returns them to `AVAILABLE`. The Matches page shows the user's trades in three groups: incoming proposals (with accept / reject), outgoing proposals (with cancel), and finished trades (`ACCEPTED`, `REJECTED`, `CANCELLED`, read-only). (`specs/06-trades.md`)
5. **Seed data** — two demo users, one listing per user per category (six `Item` rows, all `AVAILABLE`), and one pre-made reciprocal like pair so a `Match` exists on first load. (`specs/07-seed-data.md`)
6. **Tests** — focused on the trade service: state transitions, double-booking, and lightweight metadata validation (plan section 5). Test cases are carried in the feature specs they belong to.

Spec files for these features: `02-login-session.md`, `03-listings.md`, `04-browse.md`, `05-likes-matches.md`, `06-trades.md`, `07-seed-data.md`.

Access rules for the whole product:

- **Browse is public; list, like, and trade require login.**
- **Status badges are public.** Every listing shows its `status` (`AVAILABLE` | `IN_TRADE` | `TRADED`) on the browse and detail pages to all roles, including anonymous visitors.
- **Edit only while `AVAILABLE`.** A listing owner can edit an `Item` only when its status is `AVAILABLE`; `IN_TRADE` and `TRADED` items are read-only for everyone.

Demo target (must not be cut, plan section 7): registration, login, create listing with the exact category metadata, public browse, seed with two users × three categories and one match, at least one successful 1-for-1 trade, and tests for transitions and double-booking.

## Core flows

Each flow names the roles involved and the end state. Detailed routes, inputs, and error messages belong to the numbered specs.

1. **Register and sign in** (anonymous visitor → logged-in user)
   Visitor opens `/register`, submits display name, email, password, and confirm password. A `User` is created with a hashed password and the visitor is redirected to `/login` without being signed in. Visitor signs in at `/login`; a session cookie is set. `/logout` clears the session.

2. **Create a listing** (logged-in user → listing owner)
   User picks a `Category`; the form shows the fields from that category's `metadata_schema`. User submits `title`, `description`, and the metadata values. The server validates required keys, types, and rules (`box_condition` 1–10, `card_condition` in the allowed set, optional `grading`). On success an `Item` is created with `status = AVAILABLE`. The owner can edit their own listing later, but only while it is still `AVAILABLE`; once it is `IN_TRADE` or `TRADED` the edit action is not offered and an edit request is refused.

3. **Browse listings** (any role)
   Anyone, including anonymous visitors, opens the public browse page, optionally filters by category, and opens a listing detail page. Each listing shows its status badge (`AVAILABLE` | `IN_TRADE` | `TRADED`) on both pages, for anonymous visitors as well as logged-in users. Anonymous visitors see detail read-only; like and trade controls require login.

4. **Like and match** (logged-in user ↔ another listing owner)
   User A likes one of user B's listings. If user B has already liked one of user A's listings, a `Match` for that item pair is created and appears on both users' Matches page. Likes on own items are rejected. Likes cannot be undone (append-only), so a `Match` once created is never removed. Likes on `IN_TRADE` or `TRADED` items are kept for history but cannot start a new trade.

5. **Propose a trade** (proposer → counterparty)
   From a `Match` on the Matches page, the proposer submits a trade offering their own item (`item_offered`) for the other owner's item (`item_requested`). Inside one transaction both items are moved `AVAILABLE → IN_TRADE` with a conditional update; if fewer than two rows were updated, the whole transaction rolls back and the propose is refused. Otherwise a `Trade` is created with `status = PROPOSED`; it appears under outgoing proposals on the proposer's Matches page and under incoming proposals on the counterparty's. Preconditions: proposer owns `item_offered`, a `Match` exists for the pair, and neither item is in a non-terminal trade.

6. **Resolve a trade** (counterparty or proposer)
   All actions are taken from the Matches page.
   - Counterparty **accepts** an incoming proposal: trade → `ACCEPTED`; both items → `TRADED` (terminal).
   - Counterparty **rejects** an incoming proposal: trade → `REJECTED`; both items → `AVAILABLE`.
   - Proposer **cancels** an outgoing proposal while `PROPOSED`: trade → `CANCELLED`; both items → `AVAILABLE`.
   Once a trade is `ACCEPTED`, `REJECTED`, or `CANCELLED` it moves to the finished trades group on both users' Matches page and no further action on it is allowed. After reject or cancel, a new propose on the same pair is allowed.

7. **Demo flow** (two seeded users)
   `migrate` → `seed` → `runserver`. Sign in as demo user A, open Matches, propose on the pre-seeded match; both listings show `IN_TRADE` on the public browse page. Sign in as demo user B, accept the incoming proposal; both listings show `TRADED` and the trade appears under finished trades. Then demonstrate the double-booking lock with the automated tests: run `python manage.py test` and show that the test "second propose on a locked item is refused" passes. The demo does not require a second seeded match.

## Out of scope

Excluded from the MVP by the brief and plan. Do not build these; if a request touches them, flag it instead.

- Payments, checkout, price estimation, or "fair trade" scoring
- Real shipping logistics
- Real-time chat or messaging (matches only expose the pair; no message thread)
- Listing deletion; the MVP supports create and edit only
- Unlike and match removal; likes are append-only, so a `Match` is never removed
- A separate "My trades" page; trades are shown on the Matches page
- Image upload (an optional image URL is Phase 5 polish only, and is cut first if time is short)
- OAuth / social login, email verification, password reset
- Sports and nostalgia categories (Hot Wheels, sports cards) — stretch only, not seeded
- Nearby / radius search and map view — stretch only
- Search beyond filtering by category
- Multi-item or many-to-many trades; a `Trade` is always one `item_offered` for one `item_requested`
- Neo4j or any graph database, message broker / event streaming, microservices
- Native mobile app (web only)
- PostgreSQL (`JSONB`, `SELECT ... FOR UPDATE`) — documented upgrade path, not a requirement
- Cloud deployment; the demo runs locally

## Glossary

Names are exactly those used in `docs/plan.md` and must be used unchanged in every spec and in code.

- **User** — an account with a case-insensitively unique email, a display name, and a password hash.
- **Category** — one of the three MVP collectible types, identified by `slug` (`funko`, `lego`, `tcg`), with a `name` and a `metadata_schema`.
- **`metadata_schema`** — JSON list on `Category` describing the allowed metadata fields; each entry has `key`, `label`, `type`, `required`.
- **Item** (also "listing") — a collectible a `User` owns and offers for trade: `owner`, `category`, `title`, `description`, `status`, `metadata`, `created_at`.
- **`metadata`** — JSON object on `Item` whose keys match the item's category `metadata_schema`.
- **Item status** — `AVAILABLE` (can be liked and traded) | `IN_TRADE` (locked by a `PROPOSED` trade) | `TRADED` (terminal; swapped away).
- **Like** — a logged-in `User` expressing interest in another user's `Item`; unique per `(user, item)`. Append-only: a like cannot be removed, so matches are never removed.
- **Reciprocal pair** — owner of item X has liked item Y and owner of item Y has liked item X.
- **Match** — a stored pair `(item_a, item_b)` with `item_a_id < item_b_id`, created when a reciprocal pair exists. A match is the only starting point for a trade.
- **Matches page** — the logged-in user's single view of their matches (pairs to propose on) and their trades: incoming proposals (accept / reject), outgoing proposals (cancel), and finished trades.
- **Trade** — a 1-for-1 swap proposal between two matched items: `item_offered`, `item_requested`, `proposer`, `counterparty`, `status`, timestamps.
- **Trade status** — `PROPOSED` (awaiting counterparty) | `ACCEPTED` (items are `TRADED`) | `REJECTED` (counterparty declined) | `CANCELLED` (proposer withdrew). All except `PROPOSED` are terminal.
- **Proposer** — the `User` who creates a trade; owns `item_offered`.
- **Counterparty** — the other owner in the match; owns `item_requested`; can accept or reject.
- **Double-booking** — the same `Item` being part of two non-terminal trades at once. Prevented by the atomic conditional update at propose time (plan section 3).
- **Lock at propose** — the accepted deviation from the brief: items become `IN_TRADE` when a trade is proposed, not when it is accepted.
- **Seed** — the management command that creates the two demo users, six listings, and one reciprocal like pair after `migrate`.

## Open questions

None for now.