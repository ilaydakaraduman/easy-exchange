# Easy Exchange — Project Brief

Peer-to-peer marketplace for collectors to list, browse, and trade pop-culture items.

## MVP (in scope)

Category: **Pop Culture & Geek** — Funko, Lego, TCG.

Users can:

- Register an account and sign in
- Create and manage listings
- Browse and search listings in MVP categories
- Express interest / start a simple trade or contact flow for a listing

## Stretch (not MVP)

- Sports category

## Out of scope

- Neo4j
- Message broker / event streaming
- Native mobile app
- Payments / checkout
- Real shipping logistics

## Product notes

Easy Exchange is a class assignment (07-ITAI5050). Specs in `/specs` are the source of truth for implementation. Features not listed here or in specs should not be built.
# easy-exchange: Project Brief

## Vision
easy-exchange is a web platform where collectors swap physical
items directly with each other (peer-to-peer), without money. Two
users who both like an item from the other's collection get
matched and can arrange a trade.

## Target users
Collectors in the pop culture and geek community who want to
trade items they own for items they want.

## MVP scope
Only the "Pop Culture & Geek" vertical, with three categories.
Each category has its own metadata fields (dynamic schema):

| Category | Metadata |
|---|---|
| Funko Pop & Figures | box condition (1-10), original box included (yes/no), serial number |
| Lego Sets & Minifigures | MISB / factory sealed (yes/no), missing parts (yes/no), year |
| Trading Card Games (Pokemon, Magic) | grading company and score (PSA/CGC), card condition (Mint / Near Mint / Played) |

## Core features
1. Listings: a user creates a listing with category, photos,
   description, category-specific metadata, and what they want in
   return (simple wishlist).
2. Discovery and matching: users browse listings and like or pass.
   When user A likes user B's listing and user B likes user A's
   listing, a match is created.
3. Trade status: each item moves through
   AVAILABLE -> IN_TRADE -> TRADED, and returns to AVAILABLE if the
   trade is cancelled. An item must never be part of two active
   trades at once.
4. Nearby search (stretch): find listings within a given radius.

## Key design goals
- Adding a new category later should only require a new schema
  definition, not new tables or major code changes.
- Safe handling of concurrent actions (no double-booking an item).

## Out of scope for the MVP
- Graph database, message broker, microservices
- Mobile app (web only)
- Real-time chat (matches only exchange simple contact or
  messages)
- Price estimation or "fair trade" scoring
- Payments or shipping

## Stretch goals
- Sports and nostalgia categories (Hot Wheels, sports cards)
  added as a demo of the dynamic schema
- Map view and radius search

## Open questions for the planning phase
- Tech stack and language
- Authentication approach
- How listing photos are stored
- How matches are communicated between users
