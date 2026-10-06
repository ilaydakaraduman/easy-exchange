# Spec: Likes and matches

**Status:** Approved

## Purpose

A logged-in user likes another user's listing (`Item`) from its detail page. When the owner of item X has liked item Y **and** the owner of item Y has liked item X, a `Match` for that pair exists, and both owners see it on their Matches page as a pair they can propose a trade on. This is plan Phase 3 ("Likes and matches") and the step that turns public browsing into a tradeable pair; it is the only way a `Match` — the sole starting point for a `Trade` — comes into existence.

Stack per [00-architecture.md](00-architecture.md): Django, server-rendered templates, SQLite, the `trades` app (`Like`, `Match`, `trades/services.py`). Login gating per [02-login-session.md](02-login-session.md). The detail page and its `listing_actions` block per [04-browse.md](04-browse.md) requirement 17. This spec defines the like action and its service function, the reciprocal-like check that creates a `Match`, the like control on the detail page, and the Matches page route and pair list. `06-trades.md` adds the trade sections (incoming, outgoing, finished) and the propose control to the same page; this spec reserves their places. `07-seed-data.md` creates the one pre-made reciprocal pair through the service defined here.

## User stories

- As a logged-in user, I want to like another collector's listing so that they know I am interested and we can be matched if they like one of mine.
- As a logged-in user, I want the like button to turn into a `Liked` state after I click it so that I know it registered and do not click again.
- As a listing owner, I want no like button on my own listing so that I cannot accidentally like my own item.
- As a logged-in user, I want a Matches page that lists every pair where the other owner and I have liked each other's items so that I can see exactly what I could trade for what.
- As a logged-in user with no matches yet, I want the Matches page to tell me clearly that there is nothing yet and what to do so that an empty page is not confusing.
- As a counterparty whose like came first, I want the match to appear on my Matches page the moment the other owner likes my item back so that neither of us has to do anything extra.
- As an anonymous visitor, I want to be sent to `/login` when I try to like or open the Matches page so that I know these need an account.

## Functional requirements

### Like action

1. Route `POST /listings/<id>/like`. Requires login. An anonymous `POST` is redirected to `/login` with **no** `next` parameter and nothing is saved (02-login-session requirement 20). `GET /listings/<id>/like` returns `405 Method Not Allowed`; the like route is `POST`-only. The view lives in the `trades` app (the path is under `/listings/` for readability only).
2. If no `Item` with that `id` exists, return `404`.
3. If `request.user == item.owner`, return `403` with the message `You cannot like your own listing.` No `Like` is created.
4. Otherwise the view calls `like_item(request.user, item)` from `trades/services.py` (requirements 9–14) and redirects to the listing's detail page `/listings/<id>`. The response is the same whether the like was new or already existed (requirement 11); there is no error for liking twice. If `like_item` raises `LikeNotAllowed` (own item or `TRADED` item, requirement 10), the view returns `403` with the exception's message — `You cannot like your own listing.` or `This listing has already been traded.` — and nothing is saved.
5. The `POST` form includes Django's CSRF token; a `POST` without a valid token is rejected and no `Like` is created.
6. The view never writes `Like` or `Match` rows itself; all creation goes through `like_item`.

### Like control on the listing detail page

7. The like control fills the `listing_actions` block that `04-browse.md` requirement 17 reserves on `/listings/<id>`. It is rendered only for logged-in users (anonymous visitors see the `Sign in to like or trade` link from 04-browse requirement 16 and nothing from this spec). The block's content depends on the viewer:

   | Viewer | Rendered in `listing_actions` |
   | --- | --- |
   | Owner of the item | Nothing from this spec (no like button, no `Liked` text, no explanatory text). `06-trades.md` may still render into the same block. |
   | Logged-in non-owner who has **not** liked this item, item `AVAILABLE` or `IN_TRADE` | A `<form method="post" action="/listings/<id>/like">` with `{% csrf_token %}` and a single submit button with the text `Like`. |
   | Logged-in non-owner who has **not** liked this item, item `TRADED` | Nothing from this spec: no `Like` form and no explanatory text (the public `TRADED` badge from 04-browse already says why). |
   | Logged-in non-owner who **has** liked this item (any status) | The text `Liked` in a non-interactive element (a `<span>`; no form, no button, no link to the like route). If a `Match` exists whose two items are this item and one of the viewer's items, the text is followed by a link `See match` pointing to `/matches` (requirement 15). A like placed earlier stays visible as `Liked` after the item becomes `TRADED`. |

   The `Like` button and the `Liked` text are never shown together.
8. **Non-`AVAILABLE` items (decided, Open question 1).** A new like on an `IN_TRADE` item is **allowed**, exactly as on an `AVAILABLE` item: the item can return to `AVAILABLE` when its trade is rejected or cancelled, so the like and any match it completes stay useful. A new like on a `TRADED` item is **refused**: `TRADED` is terminal, so the like could never lead to a trade. The refusal is enforced in `like_item` (requirement 10) with the message `This listing has already been traded.`, returned by the view as `403` (requirement 4), and the `Like` form is not rendered for `TRADED` items (requirement 7) so the normal UI never reaches the refusal; it exists for stale pages and non-view callers.

### Service: `like_item`

9. `like_item(user, item)` in `trades/services.py` is the **only** code path that creates `Like` and `Match` rows — the like view, the `seed` command (`07-seed-data.md`), and tests all call it. Everything it does runs inside one `transaction.atomic()` block, so a like is never committed without its reciprocal check having run, and a failure anywhere rolls back everything.
10. **Preconditions.** Checked in this order before anything is written; each failure raises the service exception `LikeNotAllowed` carrying a fixed message, and nothing is written:

    | Condition | Message |
    | --- | --- |
    | `user == item.owner` | `You cannot like your own listing.` |
    | `item.status == TRADED` | `This listing has already been traded.` |

    `AVAILABLE` and `IN_TRADE` items pass. The own-item rule is the same one the view enforces in requirement 3; the service checks both rules again so non-view callers (seed, tests) cannot bypass them. The status read here is a plain read of `item.status`, not a lock: a like is not a state change, and the propose lock in `06-trades.md` remains the only thing that decides whether a pair can become a trade.
11. **Idempotent like.** Obtain the `Like` row for `(user, item)` with a get-or-create. If it already exists, no error is raised and no second row is written (the unique constraint on `(user, item)` would refuse it anyway). The call then continues to the reciprocal check (requirement 12) exactly as for a new like, so calling `like_item` twice is harmless and a re-run `seed` is safe.
12. **Reciprocal check.** Let `Y = item` and `V = item.owner`. Find every item `X` such that `X.owner == user` **and** a `Like(user=V, item=X)` exists — that is, every one of the caller's items that the other owner has already liked. Each such `X` together with `Y` is a **completed pair**. The query does not filter on `X.status` (`Y` has already passed requirement 10): a pair whose `X` is `IN_TRADE` or `TRADED` is still recorded, shown on the Matches page with its badges, and left to the propose lock.
13. **One `Match` per completed pair.** For each completed pair, order the two items by `id` so that `item_a_id < item_b_id`, then get-or-create `Match(item_a, item_b)`. One new like can complete several pairs at once (the other owner may have liked several of the caller's items, or the caller may be liking the last of several of the other owner's items); **one `Match` row is created for every completed pair that does not already have one**, all inside the same transaction. A pair that already has a `Match` is left untouched. Creating a `Match` twice for the same pair is impossible: the database has a unique constraint on `(item_a, item_b)` plus the check constraint `item_a_id < item_b_id`, and the service uses get-or-create, so a repeated call — or two concurrent calls that both find the same completed pair — ends with exactly one row. If the insert nevertheless raises an integrity error (the concurrent case), the service treats it as "already exists" and continues; it does not surface an error to the user.
14. **Return value.** `like_item` returns the `Like` row and the list of `Match` rows created by this call (empty when nothing new was completed). Callers that do not care (the view) ignore it; tests assert on it.

### Matches page

15. Route `GET /matches`. Requires login; an anonymous visitor is redirected to `/login?next=/matches` (02-login-session requirement 19) and the page body is not rendered. `POST /matches` returns `405`.
16. The page heading is `Matches`. It lists every `Match` in which the logged-in user owns `item_a` or `item_b`, ordered by `Match.id` ascending (architecture: "lists of likes and matches are ordered by `id`"; `Match` has no `created_at`). Each match is one row showing, in this order:

    | Element | Source / rule |
    | --- | --- |
    | **Your item**: title as a link to `/listings/<id>`, category name, status badge | whichever of `item_a` / `item_b` the viewer owns; badge per 04-browse requirement 13 |
    | **Their item**: title as a link to `/listings/<id>`, category name, status badge | the other item |
    | **Other owner** | the other item's `owner.display_name` (text only, never the email) |
    | Pair actions | a reserved per-row region (template block name `match_actions`) that this spec leaves empty; `06-trades.md` decides whether the propose control is rendered here |

    The row shows both status badges because a pair is only proposable while both items are `AVAILABLE`; this spec displays the status and does not interpret it (no "proposable" / "locked" label of its own). All matches are listed regardless of either item's status (decided here; see Open question 2 for the alternative of hiding dead pairs).
17. **Empty state.** When the user has no `Match` rows, the list is replaced by the text `No matches yet. Like other collectors' listings — when they like one of yours back, the pair appears here.` followed by a link `Browse listings` to `/`. The heading and the reserved trades block (requirement 18) are still rendered.
18. **Reserved block for trades.** The template contains a named block `matches_trades`, rendered **after** the pair list (or its empty state), that this spec leaves empty. `06-trades.md` fills it with the three trade sections — incoming proposals, outgoing proposals, finished trades — on this same page; there is no separate "My trades" page (00-overview). Nothing in `matches_trades` is defined or asserted here.
19. The page is read-only: it never creates, changes, or deletes `Like`, `Match`, `Trade`, or `Item` rows.

### Navigation

20. The shared base layout shows a `Matches` link to `/matches` for logged-in users only, next to the `New listing` link from 03-listings requirement 15. Anonymous visitors see no `Matches` link. This is the only navigation this spec adds.

### What this spec does not change

21. Nothing here reads or writes `Item.status` or `Trade.status` other than displaying status badges (architecture business rule: status changes go through the trade functions in `trades/services.py`, defined in `06-trades.md`).
22. No unlike route, no match deletion, no like count, no notification. Likes are append-only and a `Match` is never removed.

## Acceptance criteria

### Like action — access

- **Given** an anonymous visitor, **when** they `POST /listings/<id>/like`, **then** they are redirected to exactly `/login` (no `next`) and the `Like` and `Match` counts are unchanged.
- **Given** any user, **when** they `GET /listings/<id>/like`, **then** the response is `405` and nothing changes.
- **Given** a logged-in user, **when** they `POST /listings/999999/like` for a non-existent id, **then** `404` and no `Like` is created.
- **Given** a logged-in user viewing their own listing, **when** they `POST /listings/<id>/like`, **then** the response is `403` containing `You cannot like your own listing.` and no `Like` is created.
- **Given** a logged-in non-owner and a `TRADED` item, **when** they `POST /listings/<id>/like` (for example from a stale tab), **then** the response is `403` containing `This listing has already been traded.` and no `Like` or `Match` is created.
- **Given** a `POST /listings/<id>/like` without a valid CSRF token, **then** it is rejected and no `Like` is created.

### Like action — behaviour

- **Given** a logged-in user A and an item Y owned by user B that A has not liked, **when** A `POST`s `/listings/<Y.id>/like`, **then** exactly one `Like(user=A, item=Y)` exists and A is redirected to `/listings/<Y.id>`.
- **Given** A has already liked Y, **when** A `POST`s `/listings/<Y.id>/like` again, **then** the response is the same redirect to `/listings/<Y.id>`, no error is shown, and there is still exactly one `Like(user=A, item=Y)`.
- **Given** A likes B's item Y and B has **not** liked any of A's items, **when** the like is saved, **then** no `Match` exists.
- **Given** B has liked A's item X, **when** A likes B's item Y, **then** exactly one `Match` exists, its `item_a` is whichever of X / Y has the smaller `id`, its `item_b` is the other, and both A's and B's Matches pages show the pair.
- **Given** B has liked **two** of A's items X1 and X2, **when** A likes B's item Y, **then** exactly two `Match` rows exist — one for `{X1, Y}` and one for `{X2, Y}` — created in the same request, and A's Matches page lists both.
- **Given** a `Match` already exists for `{X, Y}`, **when** either owner likes the other item again (duplicate like), **then** there is still exactly one `Match` for that pair and no error.
- **Given** B has liked A's item X and A's item X2, and A has liked B's item Y so that `Match{X, Y}` and `Match{X2, Y}` already exist, **when** A likes B's second item Y2, **then** exactly two new `Match` rows are created (`{X, Y2}` and `{X2, Y2}`) and the two existing rows are unchanged.
- **Given** B's item Y is `IN_TRADE` and B has liked A's item X, **when** A likes Y, **then** the `Like` is created exactly as for an `AVAILABLE` item and `Match{X, Y}` is created.
- **Given** B's item Y is `TRADED`, **when** `like_item(A, Y)` is called, **then** `LikeNotAllowed` is raised with the message `This listing has already been traded.`, and no `Like` or `Match` is created even if B has liked one of A's items.
- **Given** A's item X is `TRADED` and B has liked X earlier, **when** A likes B's `AVAILABLE` item Y, **then** the `Like` is created and `Match{X, Y}` is created (the liked item's status is checked; the caller's own items are not filtered), and the pair shows on the Matches page with X's `TRADED` badge.

### Like control on the detail page

- **Given** a logged-in non-owner who has not liked the item and the item is `AVAILABLE` or `IN_TRADE`, **when** `/listings/<id>` renders, **then** the `listing_actions` region contains a `<form>` with `method="post"`, `action="/listings/<id>/like"`, a CSRF token, and a submit button whose text is `Like`, and does not contain the text `Liked`.
- **Given** a logged-in non-owner who has not liked the item and the item is `TRADED`, **when** `/listings/<id>` renders, **then** the region contains no `<form>` whose action is the like route, no `Like` button, and no `Liked` text.
- **Given** a logged-in non-owner who has liked the item (in any status, including an item that became `TRADED` after the like), **when** `/listings/<id>` renders, **then** the region contains the text `Liked`, no `<form>` whose action is the like route, and no `Like` button.
- **Given** a logged-in non-owner who has liked the item and a `Match` exists between this item and one of the viewer's items, **when** the page renders, **then** the `Liked` text is followed by a `See match` link to `/matches`.
- **Given** a logged-in non-owner who has liked the item and **no** `Match` involves this item and one of the viewer's items, **then** no `See match` link is present.
- **Given** the owner viewing their own listing (any status), **when** the page renders, **then** no `Like` form, no `Liked` text, and no `See match` link is present.
- **Given** an anonymous visitor, **when** the page renders, **then** nothing from this spec is present (only the `Sign in to like or trade` link from 04-browse).

### Matches page

- **Given** an anonymous visitor, **when** they `GET /matches`, **then** they are redirected to `/login?next=/matches` and the page body is not rendered.
- **Given** a logged-in user with no `Match` rows, **when** they `GET /matches`, **then** the response is `200`, the heading `Matches` is present, the text `No matches yet.` is present with a `Browse listings` link to `/`, and no pair rows are rendered.
- **Given** a logged-in user A with `Match{X, Y}` where A owns X and B owns Y, **when** A opens `/matches`, **then** one row shows X's title (linking to `/listings/<X.id>`), X's category name and status badge as "Your item", Y's title (linking to `/listings/<Y.id>`), Y's category name and status badge as "Their item", and B's `display_name`; B's email appears nowhere in the body.
- **Given** the same `Match`, **when** B opens `/matches`, **then** the same pair is shown with Y as "Your item" and X as "Their item", and A's `display_name`.
- **Given** a third user C with no item in the pair, **when** C opens `/matches`, **then** the pair is not shown.
- **Given** a user with three matches created in sequence, **when** `/matches` renders, **then** the rows appear in ascending `Match.id` order.
- **Given** a match whose items are `IN_TRADE` (or one is `TRADED`), **when** `/matches` renders, **then** the pair is still listed and each badge text equals the item's stored status.
- **Given** any logged-in user, **when** `/matches` renders, **then** the template block `matches_trades` is rendered after the pair list or empty state, and each pair row renders a `match_actions` region (their content is asserted by `06-trades.md`, not here).
- **Given** any user, **when** they `POST /matches`, **then** `405` and nothing changes.

### Navigation

- **Given** a logged-in user, **when** any page using the base layout renders, **then** a `Matches` link to `/matches` is present.
- **Given** an anonymous visitor, **when** any page using the base layout renders, **then** no `/matches` href is present.

## Data and business rules

- **Models** (from [00-architecture.md](00-architecture.md); no new models or fields): `Like` (`user` FK → `User`, `item` FK → `Item`; unique `(user, item)`; no `created_at`) and `Match` (`item_a` FK → `Item`, `item_b` FK → `Item`; unique `(item_a, item_b)`; database check constraint `item_a_id < item_b_id`; no `created_at`). Both live in the `trades` app. `Item`, `Category`, and `User` are read only.
- **Service boundary.** `like_item(user, item)` in `trades/services.py` is the single creation path for both `Like` and `Match`. Views, the `seed` command, and tests never call `Like.objects.create` or `Match.objects.create` directly. The whole function body is inside `transaction.atomic()`.
- **Own-item rule.** `user != item.owner`, enforced in the view (`403`, requirement 3) and in the service (`LikeNotAllowed`, requirement 10). Because every `Like` crosses owners, the two items of a completed pair always have different owners, which is the architecture's `Match` service rule `item_a.owner != item_b.owner`; no separate check is needed.
- **Status rule for new likes (decided, Open question 1).** New likes are allowed on `AVAILABLE` and `IN_TRADE` items and refused on `TRADED` items (`LikeNotAllowed`, message `This listing has already been traded.`). Rationale: `IN_TRADE` is reversible (reject / cancel returns the item to `AVAILABLE`, and the match then becomes proposable), `TRADED` is terminal. Only the **liked** item's status is checked; the caller's own items that complete pairs are not filtered, so a `Match` may involve a `TRADED` item on the caller's side and is simply dead. Existing likes are never removed when an item changes status.
- **Append-only.** There is no unlike. A `Like` row is never deleted or updated, so a `Match` is never removed; the only way a pair stops being tradeable is through `Item.status` (`06-trades.md`). This is the plan's "likes can be append-only" simplification and the overview's out-of-scope entry "Unlike and match removal".
- **Idempotency.** `like_item` uses get-or-create for the `Like` and for every `Match`, and always runs the reciprocal check. Calling it any number of times with the same arguments leaves the database in the same state as calling it once: one `Like`, one `Match` per completed pair, no errors. The unique constraints are the hard guarantee; get-or-create is the normal path that avoids ever hitting them; catching the integrity error is the fallback for two concurrent callers racing on the same pair (SQLite serializes writers, so in practice the second caller simply sees the first's row).
- **Pair ordering.** The canonical form of a pair is `(min(id), max(id))`. The service orders the two ids before every lookup and insert; templates never assume that `item_a` is "mine" — they decide "your item" / "their item" by comparing each item's `owner` to `request.user`.
- **Reciprocal check scope.** The check runs only for pairs involving the item just liked (`Y`) and the caller's own items that `Y`'s owner has liked. It does not rescan the whole `Like` table and it does not create matches between other users' items; a `Match` only ever appears as a direct consequence of a like placed by one of its two owners.
- **Status is read, never changed, here.** Apart from the `TRADED` refusal above, `like_item` and the like control do not interpret `item.status`. The propose lock in `06-trades.md` (conditional update requiring two `AVAILABLE` rows) is what stops a match on a locked item from becoming a trade (architecture: "Likes on locked or traded items are kept for history but cannot start a trade"). The Matches page shows status badges so the user can see which pairs are currently inert or dead.
- **Matches page query.** `Match.objects.filter(Q(item_a__owner=user) | Q(item_b__owner=user)).select_related("item_a__owner", "item_a__category", "item_b__owner", "item_b__category").order_by("id")`, so the page is a bounded number of queries regardless of match count. The viewer's own `Like` on the detail page is one `exists()` query; the `See match` check is one `exists()` on `Match` for the pair set.
- **Privacy.** As in 04-browse, the other owner is identified by `display_name` only; no `User` email, id, or other field appears anywhere in the Matches page or the like control output.
- **Protected routes** (02-login-session requirement 18 table): the like action is a `POST`-only protected action (anonymous → `/login`, no `next`); the Matches page is a protected `GET` page (anonymous → `/login?next=/matches`). `LOGIN_URL = "/login"`.
- **CSRF** on the like form (`CsrfViewMiddleware`, `{% csrf_token %}`), as in every other `POST` in this product.
- **Templates** live in `trades/templates/trades/` (proposed names `matches.html` for the page and `_like_control.html` for the include rendered into `listing_actions`) and extend the shared base layout.
- **Seed.** `07-seed-data.md` creates its one reciprocal pair by calling `like_item` twice (A on one of B's items, then B on one of A's items), which produces exactly one `Match` through this spec's logic rather than inserting rows directly. Re-running `seed` calls `like_item` again and, by idempotency, changes nothing.

## Out of scope

- Unlike / removing a like, and removing or hiding a `Match` (append-only by decision; overview *Out of scope*)
- "Pass" / dislike on a listing (the brief mentions "like or pass"; the plan's data model has no pass record, and not liking is the pass)
- Like counts, "who liked my item" lists, popularity signals, or any view of other users' likes beyond the matches they complete
- Notifications, emails, or flash messages when a match is created (the `See match` link and the Matches page are the only communication; flash messages are Phase 5 polish)
- Any trade behaviour: the propose control, the incoming / outgoing / finished sections, and everything about `Trade` and `Item.status` transitions — `06-trades.md` (this spec only reserves `match_actions` and `matches_trades`)
- A separate "My trades" page (trades live on the Matches page, per 00-overview)
- Person-level matching ("match the user, then pick items"); matching is pairwise by listing (plan decision)
- Match suggestions, recommendations, or ranking of pairs
- Filtering or sorting the Matches page; pagination of matches
- Liking from the browse page (cards have no controls, 04-browse requirement 6); likes happen on the detail page only
- Any JSON / API endpoint; server-rendered HTML only
- Brief-level exclusions: payments, shipping, chat, image upload, OAuth, email verification, sports category, Neo4j, message brokers, native mobile

## Test cases

Tests live in `trades/tests/`. Cases 1–13 call `like_item` directly (the service is the contract; architecture *Testing approach* 11–12, adjusted for the idempotent duplicate like and the status rule decided here — see Open question 3). Cases 14–39 use Django's test client. Where an `IN_TRADE` / `TRADED` status is needed the test sets `Item.status` directly, since the trade service belongs to `06-trades.md`.

**Service (`trades/services.py::like_item`)**

1. **Own item refused**: `like_item(A, X)` where `X.owner == A`. Assert `LikeNotAllowed` is raised with the message `You cannot like your own listing.` and `Like` / `Match` counts are unchanged.
2. **Single like, no match**: `like_item(A, Y)` with no prior likes. Assert one `Like(A, Y)`, zero `Match`, and the returned match list is empty.
3. **Duplicate like is idempotent**: call `like_item(A, Y)` twice. Assert no exception, exactly one `Like(A, Y)`, returned match list empty both times.
4. **Reciprocal like creates one match, ordered by id**: `like_item(B, X)` then `like_item(A, Y)` where A owns X, B owns Y. Assert exactly one `Match`, `item_a_id == min(X.id, Y.id)`, `item_b_id == max(X.id, Y.id)`, and the second call returned that one `Match`. Repeat with the item ids swapped (create Y before X) and assert ordering still holds.
5. **Order of likes does not matter**: same as 4 but `like_item(A, Y)` first, then `like_item(B, X)`. Assert the same single `Match`.
6. **Repeated reciprocal pair creates no second match**: after case 4, call `like_item(A, Y)` and `like_item(B, X)` again. Assert still exactly one `Match`, both calls return empty lists.
7. **One like completes several pairs**: B likes A's X1 and X2; then `like_item(A, Y)`. Assert exactly two `Match` rows (`{X1, Y}`, `{X2, Y}`), both returned by the single call, both correctly ordered.
8. **Existing matches untouched when more complete**: from case 7, B also owns Y2 and `like_item(A, Y2)` is called after B liked X1 and X2. Assert four `Match` rows total, the two original rows have the same ids as before, and the call returned exactly the two new ones.
9. **No cross-user matches**: A likes B's Y; C likes B's Y; B likes A's X. Assert exactly one `Match` (`{X, Y}`) and none involving any of C's items.
10. **Unique constraint is the backstop**: attempt `Match.objects.create` for a pair that already has a row, and attempt a row with `item_a_id > item_b_id`. Assert both raise an integrity error (the constraints exist independently of the service).
11. **Atomicity**: patch the `Match` creation to raise after the `Like` row is written inside `like_item`. Assert the exception propagates and **no** `Like` row remains (the whole call rolled back).
12. **`IN_TRADE` item may be liked**: B has liked A's X; set Y (B's) to `IN_TRADE`; `like_item(A, Y)`. Assert no exception, one `Like(A, Y)`, and `Match{X, Y}` created and returned.
13. **`TRADED` item refused**: B has liked A's X; set Y to `TRADED`; `like_item(A, Y)`. Assert `LikeNotAllowed` with the message `This listing has already been traded.`, no `Like(A, Y)`, no `Match`. Also: A's own X is `TRADED`, B liked X earlier, Y is `AVAILABLE`; `like_item(A, Y)` succeeds and creates `Match{X, Y}` (only the liked item's status is checked).

**Like view**

14. **Anonymous redirect, no-op**: anonymous `POST /listings/<id>/like` → `302` to exactly `/login` (no `next`); `Like` / `Match` counts unchanged. (Completes 02-login-session case 12 for the like route.)
15. **GET refused**: `GET /listings/<id>/like` → `405`, logged in and anonymous.
16. **Not found**: logged-in `POST /listings/999999/like` → `404`, no `Like`.
17. **Own item**: owner `POST`s their own item's like route. Assert `403`, body contains `You cannot like your own listing.`, no `Like`.
18. **`TRADED` item via view**: non-owner `POST`s the like route of a `TRADED` item. Assert `403`, body contains `This listing has already been traded.`, no `Like`, no `Match`.
19. **`IN_TRADE` item via view**: non-owner `POST`s the like route of an `IN_TRADE` item. Assert `302` to `/listings/<id>` and one `Like`.
20. **Valid like redirects**: non-owner `POST` on an `AVAILABLE` item. Assert `302` to `/listings/<id>`, one `Like`.
21. **Duplicate like via view**: `POST` twice. Assert the second response is the same `302`, still one `Like`, no error text.
22. **Match through the view**: B likes X via `POST`; A likes Y via `POST`. Assert one `Match`, correctly ordered.
23. **CSRF**: `POST` without a token (CSRF checks enabled) → `403`, no `Like`.

**Like control on the detail page (completes 04-browse case 21)**

24. **Not yet liked, `AVAILABLE` and `IN_TRADE`**: logged-in non-owner `GET /listings/<id>` for an item in each of the two statuses. Assert a form with `action="/listings/<id>/like"`, `method="post"`, a CSRF input, and a submit button with text `Like`; assert `Liked` is absent.
25. **Not yet liked, `TRADED`**: logged-in non-owner `GET` of a `TRADED` item they have not liked. Assert no form whose action is the like route, no `Like` button, no `Liked` text, and no `This listing has already been traded.` text (the badge is the only indicator).
26. **Already liked**: after liking, `GET` the detail page. Assert `Liked` is present, no form whose action is the like route, no `Like` button. Repeat after setting the item to `TRADED`: `Liked` is still present and there is still no form.
27. **Liked and matched**: with `Match{X, Y}` present, A `GET`s `/listings/<Y.id>`. Assert `Liked` and a `See match` link to `/matches`. Without the match (B has not liked back), assert no `/matches` href inside `listing_actions`.
28. **Owner sees nothing**: owner `GET`s their own listing in each status. Assert no like form, no `Liked`, no `See match`.
29. **Anonymous sees nothing from this spec**: anonymous `GET`. Assert no like form and no `Liked` (the `Sign in to like or trade` link is asserted by 04-browse).

**Matches page**

30. **Anonymous redirect**: `GET /matches` → `302` to `/login?next=/matches`; the `matches.html` template is not rendered. (Completes 02-login-session case 11 for this page.)
31. **Empty state**: logged-in user with no matches. Assert `200`, heading `Matches`, the text `No matches yet.`, a `Browse listings` link to `/`, and no pair row.
32. **Pair rendered from both sides**: `Match{X, Y}`, A owns X, B owns Y. As A: assert X under "Your item" and Y under "Their item", both titles linking to their detail pages, both category names, both badges, B's `display_name`, and B's email absent from the body. As B: the sides are swapped and A's `display_name` is shown.
33. **Third user excluded**: user C `GET /matches`. Assert the pair is absent and the empty state is shown.
34. **Ordering**: three matches for A created in sequence. Assert their rows appear in ascending `Match.id` order.
35. **Dead / inert pairs still listed**: set X to `IN_TRADE` and in a second run to `TRADED`. Assert the pair row is present and the badge text equals the status.
36. **Reserved blocks**: assert the rendered page contains the `matches_trades` block region after the list and a `match_actions` region in each row (presence only; content is 06-trades').
37. **POST refused**: `POST /matches` → `405`.
38. **Query count**: with six matches, rendering `/matches` performs a bounded number of queries (no per-row item / owner / category query), asserted with `assertNumQueries` using the number the implementation settles on. Once `06-trades.md` is implemented, the page also renders three trade sections, adding exactly three queries to the count asserted here.

**Navigation**

39. **`Matches` link**: render `/` logged in and anonymous. Assert the `/matches` href appears only when logged in.

## Open questions

All decided; recorded here for traceability.

1. **May a new `Like` be placed on an `IN_TRADE` or `TRADED` item?** `docs/plan.md` says likes on locked / traded items "may remain for history but cannot start a new trade", which covers *existing* likes but does not say whether *new* ones are blocked. Options considered: **A** — allowed in any status (the architecture's current wording); **B** — refused on both `IN_TRADE` and `TRADED`. **Decided: a hybrid.** New likes on `IN_TRADE` items are **allowed**, because the item can return to `AVAILABLE`; new likes on `TRADED` items are **refused** by `like_item` with `LikeNotAllowed` and the message `This listing has already been traded.`, and the `Like` form is not rendered for `TRADED` items (requirements 7, 8, 10; tests 12, 13, 18, 19, 24, 25). Existing likes are never removed on a status change.
2. **Should the Matches page hide pairs that can never be traded?** A pair with a `TRADED` item is dead forever; a pair with an `IN_TRADE` item is inert until the trade is rejected or cancelled. **Decided** (requirement 16): show every match with status badges, because the demo flow shows the seeded pair moving `AVAILABLE → IN_TRADE → TRADED` and hiding it mid-demo would be confusing, and because `06-trades.md` places the finished trade for that pair on the same page.
3. **Duplicate like: idempotent vs refused; follow-up edits to `00-architecture.md`.** **Decided:** liking the same item twice is a no-op with no error (requirements 4 and 11). Under the architecture document's own rule the numbered spec wins, and `00-architecture.md` is revised **separately** (not by this spec) with exactly these two changes once this spec is approved:
   1. *Testing approach*, case 11 — "A duplicate `(user, item)` like is refused." becomes "A duplicate `(user, item)` like is idempotent: no error, no second row."
   2. The `Like` status rule, which appears in two places — the `Like` model section ("Likes on `IN_TRADE` or `TRADED` items are allowed and kept for history but cannot start a new trade") and the *Item status* side rules ("Likes are accepted in any status but only `AVAILABLE` items can enter a trade") — becomes: "New likes are accepted on `AVAILABLE` and `IN_TRADE` items and refused on `TRADED` items (`This listing has already been traded.`); existing likes are kept for history in any status but only `AVAILABLE` items can enter a trade."
4. **Match communication.** **Decided:** the brief's planning question "How matches are communicated between users" is answered by the Matches page plus the `See match` link in the `Liked` state. No notification or message.
5. **Route, messages, names, and layout** (confirmed): like route `POST /listings/<id>/like`; `403` with fixed messages for refused likes; `LikeNotAllowed` exception; `like_item` returns `(like, created_matches)`; reciprocal check runs on every call; `Liked` as a `<span>` plus the `See match` link; owner sees nothing in `listing_actions` from this spec; `GET /matches` with heading `Matches` and `405` on `POST`; empty-state text and `Browse listings` link as in requirement 17; blocks `match_actions` and `matches_trades`; `Matches` header link for logged-in users.
6. **`TRADED` edge cases** (confirmed): a non-owner viewing a `TRADED` item they have not liked sees nothing from this spec in `listing_actions` (no refusal text; the public badge is the indicator); an earlier like keeps showing `Liked` after the item becomes `TRADED`; only the liked item's status is checked in `like_item`, so a caller's own `TRADED` item can still complete a dead `Match` that is listed with its badge.
