# Spec: Trades (propose, accept, reject, cancel)

**Status:** Approved

## Purpose

A matched owner proposes a 1-for-1 trade on a `Match` from the Matches page; the other owner accepts or rejects it, or the proposer cancels it. Proposing locks both items `AVAILABLE → IN_TRADE` in one atomic conditional update so the same item can never be in two live trades (double-booking prevention); accepting moves both items to `TRADED`; rejecting or cancelling returns them to `AVAILABLE`. This is plan Phase 4 ("Trades (core state machine)"), the brief's "an item must never be part of two active trades at once", and the part of the demo where the state machine is shown both in the UI and by the test "second propose on a locked item is refused".

Stack per [00-architecture.md](00-architecture.md): Django, server-rendered templates, SQLite, the `trades` app (`Trade` model, `trades/services.py`). Login gating per [02-login-session.md](02-login-session.md). The `Match` rows and the Matches page — including the per-row `match_actions` block and the page-level `matches_trades` block that this spec fills — per [05-likes-matches.md](05-likes-matches.md). Status badges per [04-browse.md](04-browse.md) requirement 13. This spec defines the four trade service functions, the four `POST` routes that call them, who may do what, the fixed error messages and HTTP status codes, and the trade sections of the Matches page. The `seed` command (`07-seed-data.md`) creates no trades.

## User stories

- As a proposer, I want to propose a trade on one of my matches with one click so that the other collector sees a concrete offer: my item for theirs.
- As a proposer, I want both items to be locked the moment I propose so that nobody else can book either item while the other collector decides.
- As a proposer, I want to cancel my proposal while it is still pending so that both items go back on the market if I change my mind.
- As a counterparty, I want to see incoming proposals on my Matches page with Accept and Reject so that I can decide without leaving the page.
- As a counterparty, I want accepting to mark both items `TRADED` so that the swap is final and neither item can be traded again.
- As a counterparty, I want rejecting to free both items so that either of us can trade them elsewhere.
- As a logged-in user, I want finished trades (accepted, rejected, cancelled) listed read-only so that I can see what happened to each proposal.
- As a logged-in user, I want a refused propose on an item that was just locked by someone else to be a clear message, not a silent failure or a duplicate trade, so that I trust the marketplace.
- As an anonymous visitor, I want to be sent to `/login` if I hit any trade action so that I know trading needs an account.

## Functional requirements

### Roles and permissions

1. All four actions require login. `Proposer` and `counterparty` are the two owners of the matched pair: whichever owner submits the propose is the `proposer` and owns `item_offered`; the other owner is the `counterparty` and owns `item_requested`. Either matched owner may propose (plan section 3, "Either matched user proposes").
2. Permission matrix. Any other actor receives `403` with the fixed message in requirement 17; nothing changes.

   | Action | Allowed actor | Trade must be |
   | --- | --- | --- |
   | Propose | Either owner in the `Match`, offering their own item | — (no trade yet) |
   | Accept | `trade.counterparty` only | `PROPOSED` |
   | Reject | `trade.counterparty` only | `PROPOSED` |
   | Cancel | `trade.proposer` only | `PROPOSED` |

   The proposer can never accept or reject their own proposal; the counterparty can never cancel; a third user can do none of these.

### Routes

3. Four action routes, all `POST`-only, all in the `trades` app:

   | Route | Action | Success response |
   | --- | --- | --- |
   | `POST /matches/<match_id>/propose` | Propose a trade on that `Match` | `302` to `/matches` |
   | `POST /trades/<trade_id>/accept` | Accept | `302` to `/matches` |
   | `POST /trades/<trade_id>/reject` | Reject | `302` to `/matches` |
   | `POST /trades/<trade_id>/cancel` | Cancel | `302` to `/matches` |

4. `GET` on any of the four routes returns `405 Method Not Allowed` and changes nothing.
5. An anonymous `POST` to any of the four routes is redirected to `/login` with **no** `next` parameter and nothing is written (02-login-session requirement 20).
6. If no `Match` with `match_id` (propose) or no `Trade` with `trade_id` (accept / reject / cancel) exists, return `404`. The existence check happens before any permission check.
7. Every action form includes Django's CSRF token; a `POST` without a valid token is rejected and nothing is written.
8. The propose view resolves the pair from the `Match`: if `request.user` owns `match.item_a`, then `item_offered = item_a` and `item_requested = item_b`; if `request.user` owns `item_b`, the reverse; if the user owns neither, return `403` with `You are not part of this match.` and call nothing. There is no request body beyond the CSRF token: the pair is fully determined by the `Match` and the actor, so there are no `item_offered` / `item_requested` inputs to tamper with.
9. Each view then calls exactly one service function (`propose_trade`, `accept_trade`, `reject_trade`, `cancel_trade`; requirements 10–16) and maps its exceptions to responses (requirement 17). Views never read-modify-write or set `Item.status` or `Trade.status` themselves and never create `Trade` rows directly (architecture business rule).

### Service: preconditions for propose

10. `propose_trade(user, item_offered, item_requested)` in `trades/services.py` is the **only** code path that creates a `Trade` row. Before touching any status it checks these preconditions **in this order**; each failure raises `TradeNotAllowed` with the fixed message and writes nothing:

    | # | Condition checked | Message |
    | --- | --- | --- |
    | a | `user != item_offered.owner` | `You can only offer your own listing.` |
    | b | `item_offered.id == item_requested.id` **or** `item_offered.owner == item_requested.owner` | `You cannot trade with yourself.` |
    | c | No `Match` exists for the pair `(min(id), max(id))` | `These listings are not matched.` |

    The view already guarantees a–c when the request comes from the Matches page (requirement 8); the service checks them again so that direct callers (tests, any future caller) cannot bypass them.
11. The remaining two preconditions from the plan — **both items are `AVAILABLE`** and **neither item is in a `PROPOSED` trade** — are deliberately **not** pre-checked by reading status. They are enforced by the conditional update in requirement 12: an item in a `PROPOSED` trade is always `IN_TRADE` (architecture invariant), so "both rows updated from `AVAILABLE`" is exactly "both available and neither in a live trade". A read-then-write check would reintroduce the race the lock exists to close.

### Service: propose (the lock)

12. After the preconditions pass, everything else happens inside **one** `transaction.atomic()` block:

    1. Run a single conditional update over both rows: `Item.objects.filter(id__in=[item_offered.id, item_requested.id], status=AVAILABLE).update(status=IN_TRADE)` — in SQL, `UPDATE item SET status='IN_TRADE' WHERE id IN (?, ?) AND status='AVAILABLE'`.
    2. Read the affected row count returned by `update()`.
    3. If the row count is **not exactly 2**, raise `TradeConflict` with the message `One of these listings is no longer available.` inside the block. The exception leaves the `atomic()` block, so the whole transaction rolls back: if one of the two rows had been updated, it is reverted to `AVAILABLE`. No `Trade` row is written.
    4. If the row count is 2, create the `Trade` with `item_offered`, `item_requested`, `proposer = user`, `counterparty = item_requested.owner`, `status = PROPOSED`, `created_at` and `updated_at` set to now, and commit.
13. `propose_trade` returns the created `Trade`. After it returns, both items are `IN_TRADE` and the trade is `PROPOSED`; there is never a committed state in which an item is `IN_TRADE` without a `PROPOSED` trade, or in which two `PROPOSED` trades share an item.

### Service: accept, reject, cancel

14. `accept_trade(user, trade)`, `reject_trade(user, trade)`, and `cancel_trade(user, trade)` first check the actor **before** any status check, raising `TradeNotAllowed` with the fixed message and writing nothing:

    | Function | Condition | Message |
    | --- | --- | --- |
    | `accept_trade`, `reject_trade` | `user != trade.counterparty` | `Only the counterparty can accept or reject this trade.` |
    | `cancel_trade` | `user != trade.proposer` | `Only the proposer can cancel this trade.` |

    Authorization is checked first so that a third user, or the wrong party, always gets `403`, never a `409` that leaks whether the trade is still open.
15. Then, inside **one** `transaction.atomic()` block, using the same conditional pattern as propose:

    1. Conditional update on the trade row: `Trade.objects.filter(id=trade.id, status=PROPOSED).update(status=<new>, updated_at=now())` where `<new>` is `ACCEPTED` (accept), `REJECTED` (reject), or `CANCELLED` (cancel). The `updated_at` write is part of the same `update()` call.
    2. If the row count is **not exactly 1**, raise `TradeConflict` with the message `This trade has already been resolved.` — the trade was already accepted, rejected, or cancelled (possibly by the other party a moment earlier). The transaction rolls back and nothing changes.
    3. Conditional update on both items: `Item.objects.filter(id__in=[trade.item_offered_id, trade.item_requested_id], status=IN_TRADE).update(status=<item_status>)` where `<item_status>` is `TRADED` for accept and `AVAILABLE` for reject and cancel.
    4. If that row count is **not exactly 2**, raise `TradeInvariantError` (a developer-facing exception, not caught by the views). Items in a `PROPOSED` trade are always `IN_TRADE`, so this can only happen if a status was changed outside the service; the transaction rolls back, including the trade-row update from step 1, so the trade stays `PROPOSED`.
16. Each function returns the refreshed `Trade`. `ACCEPTED`, `REJECTED`, and `CANCELLED` are terminal: a second accept / reject / cancel on the same trade fails step 2 with `TradeConflict`. After `REJECTED` or `CANCELLED` both items are `AVAILABLE` again and a new `propose_trade` on the same `Match` succeeds, creating a **new** `Trade` row; the old row is never reused or edited. After `ACCEPTED` both items are `TRADED`, which is terminal for the items as well: no transition out, and every other `Match` involving either item is dead.

### Error handling in views

17. The views map service exceptions to responses with fixed messages. The message is shown in the response body as plain text on a simple error page (same pattern as the `403` pages in 03-listings and 05-likes-matches; there is no flash-message mechanism until Phase 5).

    | Exception / situation | HTTP status | Message in body |
    | --- | --- | --- |
    | Anonymous `POST` | `302` to `/login` (no `next`) | — |
    | `GET` on an action route | `405` | — |
    | Unknown `match_id` / `trade_id` | `404` | — |
    | Propose by a user who owns neither item of the `Match` (view check, requirement 8) | `403` | `You are not part of this match.` |
    | `TradeNotAllowed` from `propose_trade` (requirement 10) | `403` | `You can only offer your own listing.` / `You cannot trade with yourself.` / `These listings are not matched.` |
    | `TradeNotAllowed` from accept / reject | `403` | `Only the counterparty can accept or reject this trade.` |
    | `TradeNotAllowed` from cancel | `403` | `Only the proposer can cancel this trade.` |
    | `TradeConflict` from propose (lock refused) | `409` | `One of these listings is no longer available.` |
    | `TradeConflict` from accept / reject / cancel (already resolved) | `409` | `This trade has already been resolved.` |
    | `TradeInvariantError` | not caught (Django's `500` handling) | — |

    `403` means "you may never do this"; `409` means "you may, but the state has moved on — reload the Matches page". In every non-`302` case nothing has been written.

### Matches page: `match_actions` block (per pair row)

18. 05-likes-matches requirement 16 reserves a per-row `match_actions` region. This spec fills it as follows:

    | Row state | Rendered in `match_actions` |
    | --- | --- |
    | Both items `AVAILABLE` | A `<form method="post" action="/matches/<match_id>/propose">` with `{% csrf_token %}` and a single submit button with the text `Propose trade`. |
    | Any other combination (either item `IN_TRADE` or `TRADED`) | Nothing. No disabled button, no explanatory text; the two status badges already on the row (05-likes-matches requirement 16) explain why. |

    The "both `AVAILABLE`" check is a render-time read of the two statuses already loaded for the row; it decides only whether to show the button. The lock in requirement 12 is the real guard, so a stale page whose items were locked a moment ago simply gets the `409` from requirement 17.
19. No propose control is rendered on the listing detail page: this spec adds **nothing** to the `listing_actions` block reserved by 04-browse requirement 17 (04-browse Open question 4). Proposing happens on the Matches page only, which the `See match` link from 05-likes-matches requirement 7 already points to. (Proposed; see Open question 2.)

### Matches page: `matches_trades` block (page level)

20. 05-likes-matches requirement 18 reserves a page-level `matches_trades` block rendered after the pair list. This spec fills it with three sections, in this order, each with its own heading. All three headings are always rendered, even when a section is empty, so the page shape is stable during the demo.

    | Section heading | Contents | Per-row actions |
    | --- | --- | --- |
    | `Incoming proposals` | Every `Trade` with `status = PROPOSED` and `counterparty = request.user` | `Accept` and `Reject` buttons |
    | `Outgoing proposals` | Every `Trade` with `status = PROPOSED` and `proposer = request.user` | `Cancel` button |
    | `Finished trades` | Every `Trade` with `status` in `ACCEPTED`, `REJECTED`, `CANCELLED` where the user is `proposer` or `counterparty` | None (read-only) |

21. Each trade row shows, in this order:

    | Element | Source / rule |
    | --- | --- |
    | **Your item**: title as a link to `/listings/<id>`, status badge | whichever of `item_offered` / `item_requested` the viewer owns; badge per 04-browse requirement 13 |
    | **Their item**: title as a link to `/listings/<id>`, status badge | the other item |
    | **Other party** | the other user's `display_name` (text only, never the email) |
    | **Proposed by** | `You` if the viewer is the proposer, otherwise the proposer's `display_name` |
    | **Trade status** | the raw `Trade.status` value (`PROPOSED`, `ACCEPTED`, `REJECTED`, `CANCELLED`) in a `<span class="trade-status trade-status-<status lowercased>">` |
    | **Date** | `created_at` for `PROPOSED` rows; `updated_at` (when it was resolved) for finished rows; Django's default `date` filter |
    | Actions | per requirement 20; see requirement 22 |

22. Action controls are plain `POST` forms with `{% csrf_token %}` and a single submit button each:
    - Incoming: `<form method="post" action="/trades/<id>/accept">` with button `Accept`, and `<form method="post" action="/trades/<id>/reject">` with button `Reject`.
    - Outgoing: `<form method="post" action="/trades/<id>/cancel">` with button `Cancel`.
    - Finished: no form.
    Forms are rendered only for the role allowed to use them (incoming rows are by definition the viewer's as counterparty; outgoing rows the viewer's as proposer), so the viewer never sees a button the server would refuse.
23. **Ordering.** `Incoming proposals` and `Outgoing proposals` are ordered oldest first (`created_at` ascending, `id` ascending tie-break) so the longest-waiting proposal is at the top. `Finished trades` are ordered most recently resolved first (`updated_at` descending, `id` descending tie-break). (Proposed; see Open question 3.)
24. **Empty states.** When a section has no rows, its heading is followed by one line of text: `No incoming proposals.`, `No outgoing proposals.`, or `No finished trades.` The 05-likes-matches empty state for the pair list (`No matches yet. …`) is unchanged and independent of these.
25. The Matches page remains read-only (05-likes-matches requirement 19): rendering it never creates or changes `Trade` or `Item` rows. All writes happen in the four `POST` views via the service.

### Navigation and other pages

26. No new navigation. The `Matches` header link from 05-likes-matches requirement 20 is the entry point to everything in this spec. There is no separate "My trades" page and no trade detail page (00-overview *Out of scope*).
27. The public browse and detail pages (04-browse) need no change: they already show the status badge, so after a propose both items read `IN_TRADE` and after an accept `TRADED` (00-overview *Core flows* 7). The edit page (03-listings) already refuses edits on `IN_TRADE` / `TRADED` items and its stale-edit conditional update already loses to the lock here.

## Acceptance criteria

### Propose — service

- **Given** two `AVAILABLE` matched items X (owner A) and Y (owner B), **when** A calls `propose_trade(A, X, Y)`, **then** X and Y are both `IN_TRADE`, exactly one `Trade` exists with `item_offered = X`, `item_requested = Y`, `proposer = A`, `counterparty = B`, `status = PROPOSED`, and `created_at == updated_at`.
- **Given** the same match, **when** B calls `propose_trade(B, Y, X)` instead, **then** the trade has `item_offered = Y`, `item_requested = X`, `proposer = B`, `counterparty = A` (either owner may propose).
- **Given** A does not own X, **when** `propose_trade(A, X, Y)` is called, **then** `TradeNotAllowed` is raised with `You can only offer your own listing.`, no `Trade` exists, and both statuses are unchanged.
- **Given** A owns both X and X2, **when** `propose_trade(A, X, X2)` is called (with or without a `Match` row), **then** `TradeNotAllowed` with `You cannot trade with yourself.` and nothing changes. Same for `propose_trade(A, X, X)`.
- **Given** A owns X and B owns Y but no `Match` exists for `{X, Y}`, **when** `propose_trade(A, X, Y)` is called, **then** `TradeNotAllowed` with `These listings are not matched.` and nothing changes.

### Propose — double-booking lock

- **Given** `propose_trade(A, X, Y)` has succeeded (X, Y `IN_TRADE`) and a `Match` exists for `{X, Z}` where C owns Z, **when** C calls `propose_trade(C, Z, X)` (or A calls `propose_trade(A, X, Z)`), **then** `TradeConflict` is raised with `One of these listings is no longer available.`, Z is still `AVAILABLE` (the single updated row was rolled back), X and Y are still `IN_TRADE`, the first trade is still `PROPOSED`, and exactly one `Trade` row exists. **This is the demo test, "second propose on a locked item is refused".**
- **Given** the same first trade and a `Match` for `{Y, W}` where D owns W, **when** D calls `propose_trade(D, W, Y)`, **then** the same refusal: `item_requested` of a live trade is just as locked as `item_offered`.
- **Given** X is `TRADED` and Z is `AVAILABLE` with a `Match` for `{X, Z}`, **when** C calls `propose_trade(C, Z, X)`, **then** `TradeConflict` is raised, Z is still `AVAILABLE`, X is still `TRADED`, and no `Trade` is created.
- **Given** the `Trade` insert inside `propose_trade` is made to raise after the item update succeeded (test patch), **when** `propose_trade` is called on two `AVAILABLE` matched items, **then** the exception propagates and both items are still `AVAILABLE` (the whole block rolled back).

### Accept, reject, cancel — service

- **Given** a `PROPOSED` trade (A proposed X for B's Y), **when** B calls `accept_trade(B, trade)`, **then** the trade is `ACCEPTED`, `updated_at` is later than `created_at`, and X and Y are both `TRADED`.
- **Given** an `ACCEPTED` trade, **when** anyone calls `accept_trade`, `reject_trade`, or `cancel_trade` on it with the otherwise-allowed actor, **then** `TradeConflict` with `This trade has already been resolved.` and the trade and both items are unchanged.
- **Given** a `PROPOSED` trade, **when** B calls `reject_trade(B, trade)`, **then** the trade is `REJECTED`, X and Y are both `AVAILABLE`, and a subsequent `propose_trade(A, X, Y)` succeeds, creating a second `Trade` row while the first stays `REJECTED`.
- **Given** a `PROPOSED` trade, **when** A calls `cancel_trade(A, trade)`, **then** the trade is `CANCELLED`, X and Y are both `AVAILABLE`, and a subsequent `propose_trade(B, Y, X)` succeeds.
- **Given** a `PROPOSED` trade, **when** the proposer A calls `accept_trade` or `reject_trade`, **then** `TradeNotAllowed` with `Only the counterparty can accept or reject this trade.` and nothing changes.
- **Given** a `PROPOSED` trade, **when** the counterparty B calls `cancel_trade`, **then** `TradeNotAllowed` with `Only the proposer can cancel this trade.` and nothing changes.
- **Given** a `PROPOSED` trade and a third user C, **when** C calls any of the three functions, **then** `TradeNotAllowed` (with the matching message) and nothing changes; **when** C calls them on an already-resolved trade, **then** still `TradeNotAllowed`, not `TradeConflict` (authorization is checked first).
- **Given** a `PROPOSED` trade, **when** B accepts and then A cancels, **then** the cancel raises `TradeConflict` and both items stay `TRADED`; **when** instead A cancels and then B accepts, **then** the accept raises `TradeConflict` and both items stay `AVAILABLE`.
- **Given** a `PROPOSED` trade whose `item_offered` has been set to `AVAILABLE` directly (outside the service), **when** B calls `accept_trade`, **then** `TradeInvariantError` is raised and the trade is still `PROPOSED` (step 1 was rolled back with step 3).

### Routes — access

- **Given** an anonymous visitor, **when** they `POST` any of `/matches/<id>/propose`, `/trades/<id>/accept`, `/trades/<id>/reject`, `/trades/<id>/cancel`, **then** they are redirected to exactly `/login` (no `next`), no `Trade` row is created or changed, and no `Item.status` changes.
- **Given** any user, **when** they `GET` any of the four routes, **then** `405` and nothing changes.
- **Given** a logged-in user, **when** they `POST /matches/999999/propose` or `/trades/999999/accept` (or reject / cancel), **then** `404` and nothing changes.
- **Given** a `POST` to any action route without a valid CSRF token, **then** it is rejected and nothing changes.

### Routes — propose

- **Given** a `Match{X, Y}` with X owned by A and both items `AVAILABLE`, **when** A `POST`s `/matches/<match.id>/propose`, **then** the response is `302` to `/matches`, and one `Trade` exists with `item_offered = X`, `item_requested = Y`, `proposer = A`, `counterparty = B`, `status = PROPOSED`; both items are `IN_TRADE`.
- **Given** the same match, **when** B `POST`s the same route, **then** the trade has `item_offered = Y` and `proposer = B` (the view picks the actor's own item).
- **Given** a third user C who owns neither item, **when** C `POST`s `/matches/<match.id>/propose`, **then** `403` containing `You are not part of this match.` and nothing changes.
- **Given** a match whose items are already `IN_TRADE` (or one is `TRADED`), **when** either owner `POST`s the propose route (stale page), **then** `409` containing `One of these listings is no longer available.` and nothing changes.

### Routes — accept, reject, cancel

- **Given** a `PROPOSED` trade, **when** the counterparty `POST`s `/trades/<id>/accept`, **then** `302` to `/matches`, the trade is `ACCEPTED`, both items `TRADED`.
- **Given** a `PROPOSED` trade, **when** the counterparty `POST`s `/trades/<id>/reject`, **then** `302` to `/matches`, the trade is `REJECTED`, both items `AVAILABLE`.
- **Given** a `PROPOSED` trade, **when** the proposer `POST`s `/trades/<id>/cancel`, **then** `302` to `/matches`, the trade is `CANCELLED`, both items `AVAILABLE`.
- **Given** a `PROPOSED` trade, **when** the proposer `POST`s accept or reject, **then** `403` containing `Only the counterparty can accept or reject this trade.`; **when** the counterparty `POST`s cancel, **then** `403` containing `Only the proposer can cancel this trade.`; **when** a third user `POST`s any of the three, **then** `403`. Nothing changes in any case.
- **Given** a trade that is already `ACCEPTED`, `REJECTED`, or `CANCELLED`, **when** the otherwise-allowed actor `POST`s accept, reject, or cancel, **then** `409` containing `This trade has already been resolved.` and nothing changes.

### Matches page — `match_actions`

- **Given** a `Match` whose two items are both `AVAILABLE`, **when** either owner opens `/matches`, **then** that row's `match_actions` region contains a `<form>` with `method="post"`, `action="/matches/<match.id>/propose"`, a CSRF token, and a submit button with the text `Propose trade`.
- **Given** a `Match` with at least one item `IN_TRADE` or `TRADED`, **when** either owner opens `/matches`, **then** that row contains no `<form>` whose action is a propose route and no `Propose trade` text.
- **Given** a user with two matches, one proposable and one not, **when** `/matches` renders, **then** exactly one `Propose trade` form is present and its action names the proposable match's id.

### Matches page — `matches_trades`

- **Given** any logged-in user, **when** `/matches` renders, **then** the headings `Incoming proposals`, `Outgoing proposals`, and `Finished trades` are present in that order, after the pair list or its empty state.
- **Given** a user with no trades, **when** `/matches` renders, **then** the texts `No incoming proposals.`, `No outgoing proposals.`, and `No finished trades.` are present and no `/trades/` action form exists.
- **Given** A proposed X for B's Y, **when** B opens `/matches`, **then** the trade is under `Incoming proposals` with Y as "Your item", X as "Their item", A's `display_name` as other party, `Proposed by` A's `display_name`, status text `PROPOSED`, both badges `IN_TRADE`, and two forms: `action="/trades/<id>/accept"` with button `Accept` and `action="/trades/<id>/reject"` with button `Reject`; no cancel form. The trade does not appear under `Outgoing proposals` or `Finished trades`.
- **Given** the same trade, **when** A opens `/matches`, **then** it is under `Outgoing proposals` with X as "Your item", Y as "Their item", B's `display_name`, `Proposed by` `You`, and exactly one form: `action="/trades/<id>/cancel"` with button `Cancel`; no accept or reject form.
- **Given** the same trade, **when** a third user C opens `/matches`, **then** the trade appears in none of the three sections.
- **Given** the trade has been accepted (or rejected, or cancelled), **when** A or B opens `/matches`, **then** it is under `Finished trades` with status text `ACCEPTED` (or `REJECTED` / `CANCELLED`), the item badges `TRADED` (or `AVAILABLE`), and no `<form>` in the row; it no longer appears under incoming or outgoing.
- **Given** two incoming proposals created in sequence, **when** `/matches` renders, **then** the older one is listed first; **given** two finished trades resolved in sequence, **then** the more recently resolved one is listed first.
- **Given** any trade row, **when** `/matches` renders, **then** the other party's email appears nowhere in the body.

### Listing detail page

- **Given** a logged-in user viewing any listing in any status, **when** `/listings/<id>` renders, **then** the body contains no `<form>` whose action is a propose, accept, reject, or cancel route (this spec adds nothing to `listing_actions`).

### Demo flow (00-overview *Core flows* 7)

- **Given** the seeded `Match` between demo user A's item and demo user B's item, **when** A signs in, opens `/matches`, submits `Propose trade`, and `/` is rendered, **then** both listings show the badge `IN_TRADE`; **when** B then signs in, opens `/matches`, submits `Accept`, and `/` is rendered, **then** both listings show `TRADED`, and both users' Matches pages list the trade under `Finished trades` with status `ACCEPTED`.

## Data and business rules

- **Models** (from [00-architecture.md](00-architecture.md); no new models or fields): `Trade` (`item_offered` FK → `Item`, `item_requested` FK → `Item`, `proposer` FK → `User`, `counterparty` FK → `User`, `status` choices `PROPOSED` | `ACCEPTED` | `REJECTED` | `CANCELLED` default `PROPOSED`, `created_at`, `updated_at`). `Match`, `Item`, and `User` are read; `Item.status` is written only by the service functions below. `Trade` rows are never deleted or edited apart from the `status` / `updated_at` transition.
- **Service boundary.** `propose_trade`, `accept_trade`, `reject_trade`, `cancel_trade` in `trades/services.py` are the only code that writes `Trade` rows or changes `Item.status` or `Trade.status`. Views, templates, the `seed` command, and tests never call `Trade.objects.create`, `Trade.objects.update`, or set `Item.status` for these transitions. (Tests that need an `IN_TRADE` / `TRADED` fixture **without** a trade may set `Item.status` directly, as 03/04/05 already do; that is fixture setup, not a transition.)
- **Service exceptions.** Three classes in `trades/services.py`:

  | Exception | Meaning | View response |
  | --- | --- | --- |
  | `TradeNotAllowed` | The actor may never do this (wrong owner, self-trade, no match, wrong party). Carries one of the fixed messages. | `403` |
  | `TradeConflict` | The actor may do this, but the state has changed (lock refused, trade already resolved). Carries one of the fixed messages. | `409` |
  | `TradeInvariantError` | Items of a `PROPOSED` trade were not both `IN_TRADE`. A bug or an out-of-band write, never a user error. | not caught (`500`) |

  `TradeNotAllowed` mirrors `LikeNotAllowed` from 05-likes-matches. All three are raised before commit, so a caught exception always means "nothing was written".
- **State machine** (architecture *State machine*, reproduced here as the contract this spec implements):

  | Trigger | Who | `Trade.status` | `Item.status` (both items, same transaction) |
  | --- | --- | --- | --- |
  | Propose | Either matched owner | — → `PROPOSED` | `AVAILABLE → IN_TRADE` |
  | Accept | `counterparty` | `PROPOSED → ACCEPTED` | `IN_TRADE → TRADED` |
  | Reject | `counterparty` | `PROPOSED → REJECTED` | `IN_TRADE → AVAILABLE` |
  | Cancel | `proposer` | `PROPOSED → CANCELLED` | `IN_TRADE → AVAILABLE` |

  `ACCEPTED`, `REJECTED`, `CANCELLED` are terminal for the trade. `TRADED` is terminal for the item. There is no "edit a proposal", no counter-offer, no re-open.
- **Preconditions for propose**, in the order checked: (a) `user == item_offered.owner`; (b) `item_offered != item_requested` and their owners differ; (c) a `Match` exists for `(min(id), max(id))`; (d) both items `AVAILABLE` and neither in a `PROPOSED` trade — enforced **only** by the conditional update's row count, never by a prior read (requirement 11). `counterparty` is derived as `item_requested.owner`, never supplied by the caller. "The actor is logged in" (architecture) is enforced by `login_required` on the views; the service additionally treats an unauthenticated or `None` user as failing check (a).
- **The lock** (plan section 3; architecture *Double-booking prevention*). One `UPDATE ... WHERE id IN (offered, requested) AND status = 'AVAILABLE'` inside `transaction.atomic()`; row count must be exactly 2, otherwise raise so the transaction (including any one row that did flip) rolls back; only then insert the `Trade`. Because both the update and the insert are in the same transaction, two overlapping proposes sharing an item cannot both see a count of 2, and no committed state ever has an `IN_TRADE` item without a `PROPOSED` trade. SQLite serializes writers at the database level, which is sufficient for this pattern; `select_for_update()` is not used (PostgreSQL note in the architecture spec).
- **Resolve pattern.** Accept / reject / cancel use the same conditional-update-plus-row-count shape on the `Trade` row (`WHERE status = 'PROPOSED'`, count 1) and then on both items (`WHERE status = 'IN_TRADE'`, count 2), all in one `transaction.atomic()`. Checking the trade row first means concurrent accept-vs-cancel has exactly one winner; the loser gets `TradeConflict`.
- **`updated_at`** is written in the same `update()` call that changes `Trade.status`, so the two are never out of step. `created_at` is never changed. On create, `created_at == updated_at`.
- **Authorization order.** Existence (`404`) → actor permission (`403`) → state (`409`). A third user can never learn from the status code whether a trade is still open.
- **Routes** use the `Match` id for propose (the pair is fixed by the match; the actor's side is derived server-side) and the `Trade` id for accept / reject / cancel. All four are `POST`-only protected actions in the sense of 02-login-session requirement 20: anonymous → `/login` without `next`; `GET` → `405`. They are never used as a `next` value.
- **Redirect target** after every successful action is `/matches`, the single page that shows the result (the pair row's badges change, the trade moves between sections).
- **Matches page queries.** One query for the viewer's trades: `Trade.objects.filter(Q(proposer=user) | Q(counterparty=user)).select_related("item_offered__owner", "item_requested__owner", "proposer", "counterparty")`, split in Python into the three sections and sorted per requirement 23; plus the match query already defined in 05-likes-matches. The page stays a bounded number of queries regardless of trade count. The `Propose trade` decision uses the item statuses already loaded for the match row (no extra query).
- **Render-time status reads are advisory.** The `match_actions` "both `AVAILABLE`" check and the section membership are computed from loaded rows for display only; the service re-decides everything with conditional updates when a form is submitted. A stale page can never produce a double booking — only a `409`.
- **Privacy.** As in 04-browse and 05-likes-matches, the other party and the proposer are identified by `display_name` only; no `User` email, id, or other field appears anywhere in the trade sections.
- **CSRF** on every action form (`CsrfViewMiddleware`, `{% csrf_token %}`).
- **Templates** live in `trades/templates/trades/`: the `matches.html` page from 05-likes-matches is extended by filling its two blocks; proposed include names `_match_actions.html` (the propose form) and `_trade_sections.html` (the three sections). They extend the shared base layout.
- **Seed.** `07-seed-data.md` creates no `Trade` rows and leaves all six items `AVAILABLE`; the seeded `Match` is therefore proposable on first load, which is the demo's live hook.

## Out of scope

- Counter-offers, editing a proposal, re-opening a finished trade, or any trade status other than the four in the plan
- Multi-item, many-to-many, or three-way trades; a `Trade` is always one `item_offered` for one `item_requested` (00-overview *Out of scope*)
- A propose control on the listing detail page (decided here: Matches page only; see Open question 2)
- A separate "My trades" page, a trade detail page (`/trades/<id>`), or trade history on the listing detail page
- Notifications, emails, or flash messages when a trade is proposed or resolved (Phase 5 polish; the Matches page sections are the only communication)
- Messaging or contact exchange between the parties after acceptance (brief: real-time chat is out of scope; the plan defines no message or contact field)
- Expiry or timeouts on `PROPOSED` trades
- Pagination, filtering, or sorting controls for the trade sections
- Deleting `Trade` rows, or deleting / archiving `TRADED` items (items are never deleted)
- Any new model, field, or database constraint — including a uniqueness constraint for "one `PROPOSED` trade per item" (architecture: guaranteed by the `IN_TRADE` lock, not by a constraint)
- `select_for_update()` / PostgreSQL row locks (documented upgrade path only)
- Any JSON / API endpoint; server-rendered HTML only
- Brief-level exclusions: payments, shipping, chat, image upload, OAuth, email verification, sports category, Neo4j, message brokers, native mobile

## Test cases

Tests live in `trades/tests/`. Cases 1–15 call the service functions directly (plan section 5: "Focus tests on the trade service, not the templates"; architecture *Testing approach* 1–10). Cases 16–30 use Django's test client. Fixtures: users A, B, C (and D where noted), one `AVAILABLE` item each (X, Y, Z, W), and `Match` rows created through `like_item` from 05-likes-matches (reciprocal likes), not by inserting `Match` rows directly. Where a fixture needs an `IN_TRADE` / `TRADED` item without a trade, the test sets `Item.status` directly. **Must-have** cases are required before Phase 4 is considered done (plan section 7: "tests for transitions and double-booking" must not be cut); **nice-to-have** cases are added if time allows.

**Service — state machine (must-have; plan section 5 "State machine", architecture 1–6)**

1. **Propose happy path**: `Match{X, Y}`, both `AVAILABLE`; `propose_trade(A, X, Y)`. Assert X and Y are `IN_TRADE`; exactly one `Trade` with `item_offered = X`, `item_requested = Y`, `proposer = A`, `counterparty = B`, `status = PROPOSED`; `created_at == updated_at`; the function returned that trade.
2. **Either owner may propose**: same match, `propose_trade(B, Y, X)`. Assert `item_offered = Y`, `proposer = B`, `counterparty = A`.
3. **Accept**: after case 1, `accept_trade(B, trade)`. Assert trade `ACCEPTED`, `updated_at > created_at`, X and Y `TRADED`. Then call `accept_trade(B, trade)`, `reject_trade(B, trade)`, `cancel_trade(A, trade)` in turn: each raises `TradeConflict` with `This trade has already been resolved.`, and trade and item statuses are unchanged after each.
4. **Reject, then re-propose allowed**: after case 1, `reject_trade(B, trade)`. Assert trade `REJECTED`, X and Y `AVAILABLE`. Then `propose_trade(A, X, Y)` succeeds: two `Trade` rows exist, the first still `REJECTED`, the second `PROPOSED`, items `IN_TRADE`.
5. **Cancel, then re-propose allowed**: after case 1, `cancel_trade(A, trade)`. Assert trade `CANCELLED`, X and Y `AVAILABLE`. Then `propose_trade(B, Y, X)` succeeds with `proposer = B`.
6. **Authorization**: on a `PROPOSED` trade, `accept_trade(A, …)` and `reject_trade(A, …)` raise `TradeNotAllowed` with `Only the counterparty can accept or reject this trade.`; `cancel_trade(B, …)` raises `TradeNotAllowed` with `Only the proposer can cancel this trade.`; `accept_trade(C, …)`, `reject_trade(C, …)`, `cancel_trade(C, …)` all raise `TradeNotAllowed`. Assert the trade is still `PROPOSED` and both items `IN_TRADE` after every call. Also: resolve the trade, then call the three functions as C and assert `TradeNotAllowed` (not `TradeConflict`).
7. **Propose preconditions**: (a) `propose_trade(B, X, Y)` where B does not own X → `TradeNotAllowed` `You can only offer your own listing.`; (b) A owns X and X2: `propose_trade(A, X, X2)` and `propose_trade(A, X, X)` → `You cannot trade with yourself.`; (c) no `Match{X, Z}`: `propose_trade(A, X, Z)` → `These listings are not matched.`. Assert no `Trade` exists and every item is still `AVAILABLE` after each.
8. **Race by sequence**: `PROPOSED` trade; `accept_trade(B, …)` then `cancel_trade(A, …)` → cancel raises `TradeConflict`, items `TRADED`. Fresh trade; `cancel_trade(A, …)` then `accept_trade(B, …)` → accept raises `TradeConflict`, items `AVAILABLE`.
9. **Timestamps**: after propose, `created_at == updated_at`; after each resolve, `updated_at` changed and `created_at` did not.

**Service — double-booking (must-have; plan section 5 "Double-booking", architecture 7–9)**

10. **Second propose on a locked item is refused (the demo test)**: `Match{X, Y}` and `Match{X, Z}` (C owns Z). `propose_trade(A, X, Y)` succeeds. Then `propose_trade(C, Z, X)` raises `TradeConflict` with `One of these listings is no longer available.`. Assert Z is `AVAILABLE` (rolled back), X and Y `IN_TRADE`, the first trade still `PROPOSED`, exactly one `Trade` row. Repeat the second call as `propose_trade(A, X, Z)` with the same assertions. Name the test method so it reads as `second propose on a locked item is refused` in the test output.
11. **Locked `item_requested` is also refused**: same as 10 but the third match is `Match{Y, W}` (D owns W) and the second call is `propose_trade(D, W, Y)`. Assert W `AVAILABLE`, one `Trade` row, first trade `PROPOSED`.
12. **One item `TRADED`, the other rolled back**: set X to `TRADED` directly; `Match{X, Z}`; `propose_trade(C, Z, X)` → `TradeConflict`. Assert Z is still `AVAILABLE` (the single updated row was reverted), X still `TRADED`, no `Trade`.
13. **Propose is atomic**: patch the `Trade` creation inside `propose_trade` to raise after the item update. Assert the exception propagates and X and Y are both `AVAILABLE`, no `Trade`.
14. **Resolve is atomic / invariant guard**: `PROPOSED` trade; set X to `AVAILABLE` directly; `accept_trade(B, trade)` raises `TradeInvariantError`. Assert the trade is still `PROPOSED` (step 1 rolled back) and Y still `IN_TRADE`.

**Service — nice-to-have**

15. **True parallel race**: `TransactionTestCase`; two threads call `propose_trade` on `Match{X, Y}` and `Match{X, Z}` simultaneously. Assert exactly one `Trade` exists, exactly one call raised `TradeConflict`, and the loser's own item is `AVAILABLE`. (Architecture 10: optional; the contract is already covered by 10–12.)

**Views — access (must-have; completes 02-login-session case 12 for the trade routes)**

16. **Anonymous redirect, no-op**: anonymous `POST` to each of the four routes with valid ids → `302` to exactly `/login` (no `next`); `Trade` count and every `Item.status` unchanged.
17. **GET refused**: `GET` on each of the four routes → `405`, logged in and anonymous.
18. **Not found**: logged-in `POST /matches/999999/propose`, `/trades/999999/accept`, `/reject`, `/cancel` → `404`, nothing changes.
19. **CSRF**: `POST` to each route without a token (CSRF checks enabled) → `403`, nothing changes.

**Views — propose (must-have)**

20. **Propose via view**: A `POST`s `/matches/<id>/propose` → `302` to `/matches`; one `Trade` with `item_offered = X`, `proposer = A`, `counterparty = B`, `PROPOSED`; X, Y `IN_TRADE`. Repeat as B on a fresh fixture and assert `item_offered = Y`.
21. **Non-member**: C `POST`s the propose route → `403` containing `You are not part of this match.`; nothing changes.
22. **Locked pair via view**: items `IN_TRADE` (or one `TRADED`); owner `POST`s propose → `409` containing `One of these listings is no longer available.`; nothing changes.

**Views — accept, reject, cancel (must-have)**

23. **Counterparty accepts / rejects**: B `POST`s accept → `302` to `/matches`, trade `ACCEPTED`, items `TRADED`. Fresh trade; B `POST`s reject → `302`, `REJECTED`, items `AVAILABLE`.
24. **Proposer cancels**: A `POST`s cancel → `302`, `CANCELLED`, items `AVAILABLE`.
25. **Wrong party**: A `POST`s accept and reject → `403` containing `Only the counterparty can accept or reject this trade.`; B `POST`s cancel → `403` containing `Only the proposer can cancel this trade.`; C `POST`s all three → `403`. Nothing changes.
26. **Already resolved via view**: after accept, B `POST`s accept and reject, A `POST`s cancel → each `409` containing `This trade has already been resolved.`; nothing changes.

**Matches page — `match_actions` and `matches_trades` (must-have; completes 05-likes-matches case 36)**

27. **Propose button matrix**: `Match{X, Y}`; render `/matches` as A with (both `AVAILABLE`), (X `IN_TRADE`), (Y `TRADED`). Assert the `Propose trade` form with `action="/matches/<id>/propose"` and a CSRF input is present only in the first case; in the other two no propose form and no `Propose trade` text. With two matches, one proposable, assert exactly one propose form naming the right match id.
28. **Incoming / outgoing rendering**: A proposed X for Y. As B: trade under `Incoming proposals` with accept and reject forms (`action="/trades/<id>/accept"` / `/reject`, buttons `Accept` / `Reject`), no cancel form, Y shown as "Your item", `Proposed by` A's `display_name`, status text `PROPOSED`, badges `IN_TRADE`. As A: under `Outgoing proposals` with only a cancel form, `Proposed by` `You`. As C: the trade appears nowhere. Assert the three headings appear in order after the pair list.
29. **Finished rendering**: after accept, reject, and cancel respectively, render as A and B. Assert the trade is under `Finished trades` with status text `ACCEPTED` / `REJECTED` / `CANCELLED`, badges `TRADED` / `AVAILABLE` / `AVAILABLE`, no `<form>` in the row, and absent from incoming / outgoing.
30. **Demo flow end to end**: A `POST`s propose on the match, `GET /` shows both badges `IN_TRADE`; B `POST`s accept, `GET /` shows both `TRADED`; both users' `/matches` list the trade under `Finished trades` as `ACCEPTED`.

**Matches page — nice-to-have**

31. **Empty states**: user with no trades → `No incoming proposals.`, `No outgoing proposals.`, `No finished trades.` present; no `/trades/` form.
32. **Ordering**: two incoming proposals created in sequence → older first; two finished trades resolved in sequence → most recently resolved first.
33. **No email leak**: render `/matches` with trades present; assert no `User` email appears in the body.
34. **Query count**: with several trades, rendering `/matches` performs a bounded number of queries (`assertNumQueries` with the number the implementation settles on).
35. **No propose control on detail page**: logged-in owner and non-owner `GET /listings/<id>`; assert no `<form>` whose action is a propose / accept / reject / cancel route.

## Open questions

All decided; recorded here for traceability. None of these are settled by `docs/plan.md`.

1. **HTTP status for state refusals.** The plan fixes the behaviour (roll back and refuse) but not the status code. **Decided:** `409 Conflict` for both "lock refused" (`One of these listings is no longer available.`) and "already resolved" (`This trade has already been resolved.`), keeping `403` for "you may never do this" (requirement 17). Alternative considered: `403` for everything, matching 03-listings' stale-edit refusal.
2. **Propose from the listing detail page?** 04-browse Open question 4 left this to this spec. **Decided: no** — Matches page only (00-overview *Core flows* 5); `listing_actions` gets nothing from this spec (requirement 19). Alternative considered: also render `Propose trade` on the detail page when a proposable `Match` exists.
3. **Ordering of the trade sections.** **Decided:** incoming and outgoing oldest first (`created_at`, `id`); finished most recently resolved first (`updated_at` desc, `id` desc) (requirement 23).
4. **Route shape.** **Decided:** `POST /matches/<match_id>/propose` (pair fixed by the match, actor's side derived server-side, no item inputs in the body) and `POST /trades/<trade_id>/{accept,reject,cancel}` (requirements 3, 8).
5. **Button, heading, and message texts.** **Decided:** `Propose trade`, `Accept`, `Reject`, `Cancel`; headings `Incoming proposals`, `Outgoing proposals`, `Finished trades`; empty-state lines `No incoming proposals.` / `No outgoing proposals.` / `No finished trades.`; `Proposed by` `You` / `<display_name>`; the eight fixed error messages in requirement 17.
6. **Trade status display.** **Decided:** raw enum text (`PROPOSED`, `ACCEPTED`, …) in a `<span class="trade-status trade-status-<lowercased>">`, mirroring 04-browse's raw-enum item badges (requirement 21).
7. **`TradeInvariantError` handling.** **Decided:** not caught by the views (surfaces as a `500` in development), because it can only mean an out-of-band write or a bug (requirement 15, Data and business rules).
8. **Redirect after an action.** **Decided:** always `/matches` (requirement 3).
9. **Must-have vs nice-to-have tests.** **Decided:** service cases 1–14, view cases 16–26, and template cases 27–30 are must-have; the parallel race (15) and cases 31–35 are nice-to-have.
