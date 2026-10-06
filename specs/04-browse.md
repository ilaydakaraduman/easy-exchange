# Spec: Public browse and listing detail

**Status:** Approved

## Purpose

Anyone, signed in or not, can open the home page at `/`, see every listing (`Item`) newest first, narrow the list to one category, and open a listing's public detail page at `/listings/<id>`. Both pages show each listing's status badge (`AVAILABLE` | `IN_TRADE` | `TRADED`) to every role. This is the second half of plan Phase 2 ("Public home/browse: filter by category; listing detail (read-only for anonymous)") plus the Phase 4 item "Status badges on listings", and it is the page where the demo shows the trade state machine happening in public.

Stack per [00-architecture.md](00-architecture.md): Django, server-rendered templates, SQLite, the `catalog` app (`Item`, `Category`). Access rule per [02-login-session.md](02-login-session.md): browse is public; like and trade require login. Edit-link visibility rule per [03-listings.md](03-listings.md) requirement 24. The like control is defined in `05-likes-matches.md` and the propose control in `06-trades.md`; this spec only reserves their place on the detail page and fixes what anonymous visitors see instead.

## User stories

- As an anonymous visitor, I want to see all listings on the home page without signing in so that I can decide whether the marketplace is worth an account.
- As an anonymous visitor, I want to filter the home page by category so that I only see Funko, Lego, or TCG items.
- As an anonymous visitor, I want to open a listing and read its description and collector details (box condition, sealed state, card condition) so that I know exactly what is on offer.
- As an anonymous visitor on a listing page, I want a clear "sign in" link where the like and trade actions would be so that I know what an account unlocks.
- As any user, I want every listing to show whether it is `AVAILABLE`, `IN_TRADE`, or `TRADED` so that I do not waste time on an item that is already locked or gone.
- As a logged-in user, I want the newest listings first so that I see what was just added.
- As a listing owner, I want an `Edit` link on my own `AVAILABLE` listing so that I can reach the edit form from the public page.
- As a listing owner, I want the `Edit` link to vanish once my listing is `IN_TRADE` or `TRADED` so that the public page matches what I am allowed to do.

## Functional requirements

### Home / browse page

1. Route `GET /`. Public; never redirects (02-login-session requirement 18). This is also the post-login and post-logout landing page defined in `02-login-session.md`.
2. The page lists `Item` rows of **every** status; `IN_TRADE` and `TRADED` listings are not hidden, because the demo flow (00-overview *Core flows* 7) shows them changing status on this page.
3. **Ordering:** newest first — `created_at` descending, with `id` descending as the tie-breaker so the order is deterministic when two items share a timestamp (seed data).
4. **Category filter** is the query parameter `category`:

   | `?category=` | Result |
   | --- | --- |
   | absent, empty, or `all` | All listings (default) |
   | `funko`, `lego`, `tcg` (an existing `Category.slug`) | Only listings whose `item.category.slug` equals the value |
   | any other value | `404` (same treatment as an unknown slug in 03-listings requirement 8; see Open question 2) |

5. **Filter control:** a row of plain links above the list — `All` (to `/`) followed by one link per `Category` ordered by `slug` (03-listings requirement 4), each showing the category `name` and pointing to `/?category=<slug>`. The link for the active filter is marked as current (`aria-current="page"`); no JavaScript, no `<select>`, no submit button. The category links are built from the `Category` table, not hard-coded, so a new category row appears here without code changes.
6. **Listing card.** Each listing is rendered as one entry showing, in this order:

   | Element | Source |
   | --- | --- |
   | Title, as a link to `/listings/<id>` | `item.title` |
   | Category name | `item.category.name` |
   | Status badge (requirement 13) | `item.status` |
   | Owner | `item.owner.display_name` (text only, not a link) |

   `description` and `metadata` are **not** shown on the browse page; they belong to the detail page. No like, propose, or edit controls appear on the browse page.
7. **Empty state.** If the filtered result is empty the page shows the text `No listings yet.` when the filter is `all`, or `No <category name> listings yet.` when a category is selected. The filter links are still rendered.
8. **No pagination.** All matching listings are rendered on one page (decided, Open question 1).
9. **No search.** There is no text search input, no metadata filter, no sort control, and no owner filter (brief and overview: "Search beyond filtering by category" is out of scope).

### Listing detail page

10. Route `GET /listings/<id>`. Public; never redirects. This is the redirect target after create and edit in `03-listings.md` (requirements 14 and 23).
11. If no `Item` with that `id` exists, return `404`. There is no "listing was removed" state because items are never deleted.
12. The page shows, in this order:

    | Element | Source / rule |
    | --- | --- |
    | Title | `item.title` |
    | Status badge (requirement 13) | `item.status` |
    | Category name | `item.category.name` |
    | Owner | `item.owner.display_name` (text only) |
    | Listed on | `item.created_at`, rendered with Django's default `date` filter |
    | Description | `item.description`, auto-escaped, line breaks preserved (`linebreaks` filter) |
    | Details | one row per entry of `item.category.metadata_schema`, in schema order: the entry `label` and the value from `item.metadata[key]` rendered per requirement 14 |
    | Owner controls | the `Edit` link, per requirement 15 |
    | Action area | per requirements 16–18 |

13. **Status badge.** On both pages the badge is a `<span>` whose text is exactly the stored status value — `AVAILABLE`, `IN_TRADE`, or `TRADED` — with a CSS class derived from it (`badge badge-available`, `badge badge-in_trade`, `badge badge-traded`) so the three states can be styled differently. The badge is rendered for **every** role, including anonymous visitors (00-overview access rule "Status badges are public"). The text is the raw value, not a translated label (decided, Open question 3).
14. **Metadata rendering** (read-only, generic, no per-category code):

    | Entry `type` | Rendered as |
    | --- | --- |
    | `int` | the integer |
    | `bool` | `Yes` for `true`, `No` for `false` |
    | `str` | the string, auto-escaped |
    | key absent from `item.metadata` (optional entry left blank, 03-listings Open question 4) | `—` |

    Only keys declared in `metadata_schema` are rendered; the template iterates the schema, never the raw `metadata` dict, so an undeclared key (which the validator already prevents) could never appear.
15. **`Edit` link** (visibility rule fixed in 03-listings requirement 24; placement fixed here). The link text is `Edit` and it points to `/listings/<id>/edit`. It is rendered **only** when the viewer is logged in, `request.user == item.owner`, **and** `item.status == AVAILABLE`. In every other case — anonymous visitor, non-owner, or owner of an `IN_TRADE` / `TRADED` item — no edit control of any kind is rendered (no disabled link, no explanatory text).
16. **Action area for anonymous visitors.** No like form, no propose form, and no trade button is rendered. In their place the page shows a single link with the text `Sign in to like or trade` pointing to `/login?next=/listings/<id>` (02-login-session requirement 20; the link text is the one proposed in that spec's Open question 5 and is confirmed here).
17. **Action area for logged-in users** is a placeholder region (a template block, proposed name `listing_actions`) that this spec deliberately leaves empty. `05-likes-matches.md` defines the like control rendered there, including the owner / already-liked / non-`AVAILABLE` cases, and `06-trades.md` decides whether any propose control appears on the detail page or only on the Matches page. This spec fixes only that: the region exists on the detail page, it is rendered after the owner controls, and nothing in it is shown to anonymous visitors.
18. The detail page never changes any data. It is `GET` only; a `POST /listings/<id>` returns `405`.

### Navigation

19. The shared base layout's site name / brand in the header links to `/` so every page can reach the browse page (extends 02-login-session requirement 17 and 03-listings requirement 15; the rest of the header is unchanged).

### What this spec does not change

20. These views only read `Item`, `Category`, and `User.display_name`. They never write `Item.status` or any other field (architecture business rule: status changes go through `trades/services.py`).
21. No new model, field, migration, or setting is introduced by this spec.

## Acceptance criteria

### Browse — access and listing

- **Given** an anonymous visitor, **when** they `GET /`, **then** the response is `200` with no redirect, and the page lists every `Item` with its title link, category name, status badge, and owner display name.
- **Given** a logged-in user, **when** they `GET /`, **then** they see exactly the same listings as an anonymous visitor (browse does not depend on the viewer).
- **Given** three items created at increasing times, **when** `/` is rendered, **then** the most recently created item appears first and the oldest last.
- **Given** two items with identical `created_at`, **when** `/` is rendered, **then** the one with the larger `id` appears first.
- **Given** a seeded database with items in `AVAILABLE`, `IN_TRADE`, and `TRADED`, **when** `/` is rendered, **then** all of them appear, each with the badge text matching its status.
- **Given** a browse card, **when** it renders, **then** it contains no `description`, no metadata values, no like / propose form, and no `Edit` link.

### Browse — category filter

- **Given** six seeded items (two per category), **when** `GET /?category=funko`, **then** exactly the two Funko items are listed and no Lego or TCG item appears.
- **Given** `GET /?category=all`, `GET /?category=`, and `GET /`, **when** compared, **then** all three return the same full list.
- **Given** `GET /?category=sports` (or any value that is not a `Category.slug`), **then** the response is `404`.
- **Given** the filter links, **when** `/` is rendered, **then** they are `All`, then "Funko Pop & Figures", "Lego Sets & Minifigures", "Trading Card Games" in that order, pointing to `/`, `/?category=funko`, `/?category=lego`, `/?category=tcg`; and on `/?category=lego` only the Lego link has `aria-current="page"`.
- **Given** a category with no listings, **when** `GET /?category=<slug>`, **then** the page shows `No <category name> listings yet.` and the filter links.
- **Given** an empty `Item` table, **when** `GET /`, **then** the page shows `No listings yet.`.

### Detail — access and content

- **Given** an anonymous visitor, **when** they `GET /listings/<id>` for an existing item, **then** the response is `200` with no redirect.
- **Given** `GET /listings/999999` for a non-existent id, **then** `404`.
- **Given** a Funko item with `metadata == {"box_condition": 7, "original_box_included": true, "serial_number": "FP-0001"}`, **when** its detail page renders, **then** the Details section shows, in order, `Box condition (1–10)` → `7`, `Original box included` → `Yes`, `Serial number` → `FP-0001`.
- **Given** a Lego item with `sealed_misb: false`, `missing_parts: false`, `year: 2019`, **then** the Details show `Factory sealed (MISB)` → `No`, `Missing parts` → `No`, `Year` → `2019`.
- **Given** a TCG item with `metadata == {"card_condition": "Mint"}` (no `grading` key), **then** the Details show `Grading (company and score)` → `—` and `Card condition` → `Mint`.
- **Given** a TCG item with `grading: "PSA 10"`, **then** the `Grading (company and score)` row shows `PSA 10`.
- **Given** a description containing `<script>`, **when** the detail page renders, **then** the text is escaped and no script tag is present in the HTML.
- **Given** any item, **when** its detail page renders, **then** the page shows the title, the status badge, the category name, the owner display name, the listed-on date, and the description.
- **Given** an item whose owner has email `alice@example.com`, **when** `/` and `/listings/<id>` render for an anonymous visitor, a logged-in non-owner, and the owner, **then** the owner's `display_name` appears and the string `alice@example.com` appears nowhere in the response body in any of the six renders.
- **Given** a `POST /listings/<id>`, **then** the response is `405` and nothing changes.

### Status badges

- **Given** an item in each of `AVAILABLE`, `IN_TRADE`, `TRADED`, **when** the detail page renders for an anonymous visitor, for a logged-in non-owner, and for the owner, **then** in all nine cases the badge text equals the item's status.
- **Given** an `IN_TRADE` item, **when** the badge renders, **then** its classes include `badge-in_trade` and exclude `badge-available` and `badge-traded`.

### Edit link

- **Given** the owner, logged in, viewing their own `AVAILABLE` listing, **when** the detail page renders, **then** an `Edit` link to `/listings/<id>/edit` is present.
- **Given** the owner viewing their own `IN_TRADE` or `TRADED` listing, **then** no `Edit` link and no edit-related text is present.
- **Given** a logged-in non-owner or an anonymous visitor viewing any listing in any status, **then** no `Edit` link is present.

### Action area

- **Given** an anonymous visitor viewing `/listings/<id>`, **when** the page renders, **then** no `<form>` targeting a like or trade route exists in the body and a `Sign in to like or trade` link pointing to `/login?next=/listings/<id>` is present.
- **Given** a logged-in user viewing any listing, **when** the page renders, **then** the `Sign in to like or trade` link is **not** present and the `listing_actions` region is rendered (its content is asserted by `05-likes-matches.md` and `06-trades.md`, not here).
- **Given** an anonymous visitor who clicks `Sign in to like or trade` and signs in, **when** login succeeds, **then** they land back on `/listings/<id>` (02-login-session requirement 7, safe relative `next`).

### Navigation

- **Given** any page using the base layout, **when** it renders, **then** the site name in the header links to `/`.

## Data and business rules

- **Models read** (from [00-architecture.md](00-architecture.md); nothing new): `Item` (`owner`, `category`, `title`, `description`, `status`, `metadata`, `created_at`), `Category` (`slug`, `name`, `metadata_schema`), `User.display_name`. Queries use `select_related("owner", "category")` so the browse page is two queries (categories for the filter links, items for the list), not one per card.
- **Ordering** is `order_by("-created_at", "-id")` on every browse query, filtered or not.
- **Filter resolution:** `category` absent, `""`, or `"all"` → no filter. Otherwise look up `Category` by `slug`; not found → `404`. The lookup is exact (case-sensitive) since slugs are stored lowercase and the links are generated by the app.
- **Status badge** text is the stored enum value, unchanged, for all three states; the CSS class is `badge badge-<status lowercased>`. Status is displayed, never interpreted — this page does not know *why* an item is `IN_TRADE` (no trade or counterparty is shown; that is the Matches page in `05-likes-matches.md` / `06-trades.md`).
- **Edit link rule** (owned by 03-listings requirement 24, applied here): `request.user.is_authenticated and request.user == item.owner and item.status == AVAILABLE`. Evaluated at render time only; the edit view re-checks authorization itself and enforces it again with the conditional update, so a stale page cannot grant anything.
- **Anonymous action replacement:** the `Sign in to like or trade` link's `next` is the current detail path `/listings/<id>` — a `GET` page — never a `POST` action route (02-login-session: "`next` is for `GET` pages only").
- **Metadata display is schema-driven:** the template iterates `item.category.metadata_schema` and looks each `key` up in `item.metadata`; `bool` → `Yes` / `No`; missing key → `—`. No `if slug == "funko"` logic anywhere (architecture: adding a category is data, not code).
- **Owner identity on public pages is `display_name` only.** The browse cards and the detail page show `item.owner.display_name` and nothing else about the owner. The owner's `email` must never appear anywhere in the output of `/` or `/listings/<id>` — not as visible text, not in a `title` or `alt` attribute, not in a `mailto:` link, not in an HTML comment, and not in a `data-*` attribute — for any viewer, including the owner themselves and logged-in users. The same holds for every other `User` field (`id`, `password` hash, `is_active`). Templates receive the `Item` (with `owner` pre-fetched) and read `owner.display_name` only; no view passes a `User` object or its email to a public template under its own name.
- **Read-only:** both views are `GET`-only and perform no writes. Detail returns `405` to `POST`.
- **Escaping:** Django template auto-escaping stays on; `description` uses `linebreaks` (which escapes before inserting `<p>` / `<br>`); no `|safe` anywhere on user-supplied values.
- **Templates** live in `catalog/templates/catalog/` (proposed names `browse.html`, `item_detail.html`) and extend the shared base layout from `02-login-session.md`.
- **Public URLs:** `/` and `/listings/<id>` are in the public list of 02-login-session requirement 18 and are never wrapped in `login_required`.

## Out of scope

- Text search, searching by metadata (for example `box_condition >= 8`), owner filter, or any sort control other than the fixed newest-first order (brief / overview: "Search beyond filtering by category")
- Pagination, infinite scroll, or a "load more" control (decided, Open question 1)
- Hiding `IN_TRADE` or `TRADED` listings from browse, or a "show only available" toggle
- The like control's behaviour, labels, and states — `05-likes-matches.md`
- The propose control and any trade or counterparty information on the detail page — `06-trades.md`
- The Matches page — `05-likes-matches.md`
- Edit form, edit authorization messages, and the create flow — `03-listings.md` (this spec only places the `Edit` link)
- A "My listings" page, owner profile page, or clickable owner names (not in the plan)
- Listing images or image URLs (Phase 5 polish, cut first), thumbnails, placeholders
- Like counts, view counts, or any popularity signal on cards
- Showing a listing's trade history
- Nearby / radius search, map view (stretch)
- Breadcrumbs, flash messages, and further nav polish (Phase 5)
- Any JSON / API endpoint for listings; server-rendered HTML only
- Brief-level exclusions: payments, shipping, chat, image upload, OAuth, email verification, sports category, Neo4j, message brokers, native mobile

## Test cases

Tests live in `catalog/tests/` and use Django's test client. Items are created directly in the test (or via the seeded `Category` rows and `validate_metadata`-valid metadata); where a non-`AVAILABLE` status is needed the test sets `Item.status` directly, since the trade service belongs to `06-trades.md`. Cases 20–21 complete 02-login-session cases 13–14 and 03-listings case 32 now that the pages exist.

**Browse**

1. **Public**: anonymous `GET /` → `200`, no redirect; logged-in `GET /` → `200` with the same items.
2. **Newest first**: create three items with distinct `created_at` (set explicitly). Assert the order of titles in the response is newest → oldest.
3. **Tie-break**: two items with identical `created_at`. Assert the larger `id` comes first.
4. **All statuses shown**: items in `AVAILABLE`, `IN_TRADE`, `TRADED`. Assert all three titles appear and each card's badge text equals its status.
5. **Card contents**: assert the card has the title linking to `/listings/<id>`, the category name, the badge, the owner `display_name`; assert `description` text and metadata values are absent; assert no `Edit` link and no form.
6. **Filter by slug**: two items per category; `GET /?category=funko`, `lego`, `tcg`. Assert exactly the matching two titles each time.
7. **Default filter equivalents**: `GET /`, `GET /?category=all`, `GET /?category=`. Assert identical item lists.
8. **Unknown slug**: `GET /?category=sports` → `404`.
9. **Filter links**: assert the four links, their order (`All`, then by `slug`), their hrefs, and that `aria-current="page"` is on `All` for `/` and on the matching category link for `/?category=<slug>` only.
10. **Empty states**: empty table → `No listings yet.`; `GET /?category=tcg` with no TCG items → `No Trading Card Games listings yet.`; filter links still present.
11. **Query count**: with six items, rendering `/` performs a bounded number of queries (no per-item owner / category query), asserted with `assertNumQueries` using the number the implementation settles on.

**Detail**

12. **Public**: anonymous `GET /listings/<id>` → `200`; logged-in non-owner → `200`.
13. **Not found**: `GET /listings/999999` → `404`.
14. **Metadata rendering per category**: a Funko item (`7`, `true`, `FP-0001`) shows `7`, `Yes`, `FP-0001` under the schema labels in schema order; a Lego item with both bools `false` shows `No`, `No`, `2019`; a TCG item without `grading` shows `—` for grading and `Mint` for card condition; a TCG item with `grading = "PSA 10"` shows `PSA 10`.
15. **Core fields present**: title, category name, owner `display_name`, formatted `created_at`, description.
16. **Escaping**: description containing `<script>alert(1)</script>` renders escaped (`&lt;script&gt;`); no raw `<script>` in the body.
17. **POST refused**: `POST /listings/<id>` → `405`; item unchanged.

**Badges**

18. **Badge text for every role and status**: for each status × (anonymous, logged-in non-owner, owner), assert the detail page badge text equals the status and the class `badge-<status lowercased>` is present.

**Edit link (03-listings case 32)**

19. **Visibility matrix**: owner + `AVAILABLE` → `Edit` link to `/listings/<id>/edit` present; owner + `IN_TRADE`, owner + `TRADED`, non-owner (any status), anonymous (any status) → no `/listings/<id>/edit` href anywhere in the body.

**Action area (02-login-session cases 13–14)**

20. **Anonymous**: `GET /listings/<id>` body contains the link text `Sign in to like or trade` with `href="/login?next=/listings/<id>"`, and contains no `<form>` whose action is a like or trade route.
21. **Logged in**: `GET /listings/<id>` body does not contain `Sign in to like or trade`; the `listing_actions` block renders (content asserted in 05 / 06).

**Navigation**

22. **Brand link**: render `/` and a detail page; assert the header site name links to `/`.

**Owner privacy**

23. **Owner email never leaks**: create an owner with email `alice@example.com` and `display_name` `Alice` and one item per category. Render `/`, `/?category=funko`, and each item's `/listings/<id>` as an anonymous visitor, as a logged-in non-owner, and as the owner. In every response assert `Alice` is present and `alice@example.com` is absent from the full body (the assertion is on the raw HTML, so attributes and comments are covered, not just visible text). Since the header (owned by `02-login-session.md`) shows the signed-in user's `display_name` and not their email, also assert that no `@` email address of any `User` appears in the body at all.

## Open questions

All decided; recorded here for traceability.

1. **Pagination.** The plan does not mention it; the demo has six seeded listings and the brief says "keep the demo tiny". **Decided: none** — render all matching listings on one page (requirement 8). If a later phase needs it, Django's `Paginator` with a `page` query parameter is the upgrade path and would not change the filter or ordering rules.
2. **Unknown `category` value.** Options: `404` (consistent with 03-listings requirement 8 for `/listings/new?category=<bad slug>`), or silently fall back to `all`. **Decided: `404`** (requirement 4).
3. **Badge text.** Raw enum (`IN_TRADE`) vs a human label ("In trade"). **Decided: raw enum value** (requirement 13), keeping badges, tests, and the state-machine vocabulary identical across the product. Styling via the `badge-<status>` class.
4. **Does any propose control appear on the detail page?** The overview routes proposing through the Matches page; the plan lists "propose from the listing instead" only as a cut if the Matches page is dropped. **Decided:** this spec reserves the `listing_actions` region and leaves the decision to `06-trades.md` (requirement 17).
5. **Browse card fields.** **Decided:** title, category name, badge, owner display name; no description excerpt and no date on the card (requirement 6). The date appears on the detail page only.
6. **Optional metadata.** **Decided:** shown as `—` rather than omitting the row, so every category's detail page always has the same rows in schema order (requirement 14).
7. **Brand link to `/`.** **Decided:** added to the shared header (requirement 19) — a one-line addition to the base layout owned by `02-login-session.md`; no other header change.
8. **Filter control.** **Decided:** a row of links with `aria-current="page"`, not a `<select>` + submit (requirement 5).
9. **Empty-state text.** **Decided:** `No listings yet.` / `No <category name> listings yet.` (requirement 7).
10. **Tie-break on equal `created_at`.** **Decided:** `id` descending (requirement 3).
11. **`POST /listings/<id>`.** **Decided:** `405` (requirement 18).
12. **Owner identity on public pages.** **Decided:** `display_name` only; the owner's email never appears in any public page output (Data and business rules, test case 23).
