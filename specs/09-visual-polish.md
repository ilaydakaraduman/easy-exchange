# Spec: Visual polish

**Status:** Approved

## Purpose

This change request makes the existing pages easier to scan: a home intro, small item pictures on match and trade rows, a two-column listing detail, category icons, empty-state drawings, and a few shared finishing touches. It does not change routes, copy that specs 04–06 already fix, or any trade, like, match, or account behavior.

Stack per [00-architecture.md](00-architecture.md): Django, server-rendered templates, SQLite, no JavaScript, no CDN, no web fonts.

Superseded by specs/10-header-hero-theme.md. [08-visual-design-and-photos.md](08-visual-design-and-photos.md) stays approved. Where the two disagree on the layout statements named under *Statements superseded*, this spec wins once approved. Photo storage, search, the TCG schema, the four placeholder files, and the breakpoint rules stay in force.

## User stories

- As an anonymous visitor, I want the home page to explain the swap in one glance so that I know this is a trade, not a shop.
- As an anonymous visitor, I want Register and Sign in in that intro so that I can start an account without hunting the header.
- As a logged-in user, I want New listing in that intro so that I can add an item from the home page.
- As a logged-in user, I want each match and each trade row to show both items as small pictures so that I can tell the two sides apart.
- As any visitor, I want the listing page to put the picture beside the facts on a wide screen, and to stack them on a phone, so that the photo does not push the title off the screen.
- As any visitor, I want a small icon on each category chip, and a drawing when a list is empty, so that the page is not only text.
- As any visitor, I want a footer, a favicon, and a visible keyboard focus so that the demo feels finished.

## Functional requirements

### What stays

1. No new route, model, field, migration, form, or view. `trades/services.py` is not edited. Like, match, trade, login, logout, and permission behavior are not edited. `Item.status` and `Trade.status` still change only in `trades/services.py`.
2. Templates that change are only `templates/base.html`, `catalog/templates/catalog/browse.html`, `catalog/templates/catalog/item_detail.html`, `trades/templates/trades/matches.html`, `trades/templates/trades/_trade_sections.html`, and `static/css/base.css`. `catalog/templates/catalog/_listing_photo.html` is included and is not edited. Badge markup, `Edit`, like controls, propose / accept / reject / cancel forms, and the search form stay as they are.

Superseded by specs/10-header-hero-theme.md.
3. These strings stay character for character, including punctuation:

   | Surface | Text that must stay |
   | --- | --- |
   | Browse empty | `No listings yet.` |
   | Browse empty, category selected | `No <category name> listings yet.` |
   | Browse empty, search | `No listings match your search.` |
   | Matches heading | `Matches` |
   | Matches empty | `No matches yet. Like other collectors' listings — when they like one of yours back, the pair appears here.` |
   | Matches empty link | `Browse listings` to `/` |
   | Match row labels | `Your item`, `Their item`, `Other owner <display_name>` |
   | Trade headings | `Incoming proposals`, `Outgoing proposals`, `Finished trades` |
   | Trade empty | `No incoming proposals.`, `No outgoing proposals.`, `No finished trades.` |
   | Trade row labels | `Your item`, `Their item`, `Other party <display_name>`, `Proposed by You` or `Proposed by <display_name>` |
   | Trade buttons | `Propose trade`, `Accept`, `Reject`, `Cancel` |
   | Detail | title, category name, raw status, `display_name`, `Listed on <date>`, description, `Details`, `Edit`, `Sign in to like or trade`, `Like`, `Liked`, `See match` |
   | Header | `Easy Exchange`, `Sign in`, `Register`, `New listing`, `Matches`, `Logout` |
   | Chips | `All`, each `Category.name`, and the game-filter labels |

   Chip `href`s and `aria-current="page"` stay as specs 04 and 08-enhancements define them. Class names `listing-card`, `filters`, `game-filters`, `badge`, `match-row`, `trade-row`, `listing-actions`, `match_actions`, and `matches_trades` stay. The files under `static/img/placeholders/` are not renamed, moved, or rewritten.

### 1 — Matches and trade rows

4. On `/matches`, each `li.match-row` shows the two items side by side on a wide screen. Each side is the existing block (`Your item` or `Their item`, the title link to `/listings/<id>`, the category name, the status badge) plus a thumbnail as the first element inside that block. The thumbnail is `{% include "catalog/_listing_photo.html" %}` with `item` set to that side's item. A photo uses `item.photo`; a blank photo uses the category illustration from spec 08-visual-design-and-photos requirements 8–10. The include is not modified, so the `img` classes and the alt text `<title> (<category name>)` stay.
5. Between the two sides, one inline SVG, not a static file. It has `class="swap-arrow"` and `aria-hidden="true"`, a `viewBox`, no `<title>`, no `<script`, no `<image`, and no `http`. It draws a simple two-way arrow in `#0f6e6b`. It is not a link and not a button.
6. After the two sides, the row still shows `Other owner <display_name>` and the `match_actions` region, in that order. Propose-button rules from spec 06 are unchanged.
7. Each incoming, outgoing, and finished `li.trade-row` shows the same thumbnail immediately before each title link (`Your item`'s link and `Their item`'s link). Finished rows get the thumbnails too. Trade rows do not get the swap arrow. The existing labels, links, badges, `Other party`, `Proposed by`, `trade-status` span, date, and forms stay in the spec 06 order, with the same `action`s and button texts. A finished row still has no `<form>`.
8. Wide layout places the two match sides and the arrow on one row. Inside the existing `@media (max-width: 639px)` block, the match row stacks in the same order: your side, arrow, their side, other owner, actions. Thumbnail width on match and trade rows is at most `4.5rem`. The browse card's `.listing-photo` rules (4:3, `object-fit: cover`) are not changed for `.listing-card` or the detail page. CSS that positions `.match-row` or `.trade-row` children with `nth-child` is updated so the new arrow and thumbnails do not take those styles.

### 2 — Home intro

9. `GET /` renders `<section class="hero">` as the first content, before `nav.filters`. It is not rendered on any other page. It contains, in this order: the heading `Swap collectibles, not cash` (the only `h1` in the hero), the sentence `List what you have and trade it one for one with another collector.`, an `<img>` whose `src` is `/static/img/hero.svg` and whose `alt` is empty, and an ordered list of three steps. The steps are, in order, `List an item`, `Match with collectors`, and `Swap`. Each step shows one image: `/static/img/steps/list.svg`, `/static/img/steps/match.svg`, and `/static/img/steps/swap.svg`. Step `alt` text is empty. The scene is two faceless collectors exchanging a card and a figure.

Superseded by specs/10-header-hero-theme.md.
10. The hero's action line depends on the visitor:

    | Visitor | Links, in this order |
    | --- | --- |
    | Anonymous | `<a href="/register">Register</a>` then `<a href="/login">Sign in</a>` |
    | Logged in | `<a href="/listings/new">New listing</a>` only |

    The hero contains no `<form>`, no `href="/listings/new"` when anonymous, and no `href="/login"` or `href="/register"` when logged in. It contains no `href` to `/matches`, `/trades/`, or any propose path. The header links are unchanged, so a logged-in home page still has the header `New listing` and `Matches` links outside the hero.

Superseded by specs/10-header-hero-theme.md.
11. Below the hero, the browse body stays in the spec 08-enhancements order: `nav.filters`, then `nav.game-filters` only when the category is `tcg`, then `form.search-form`, then `ul.listings` or the empty state. Search, category, and game behavior are unchanged.

Superseded by specs/10-header-hero-theme.md.

### 3 — Detail page, two columns

12. On `/listings/<id>`, the content block's first element is `<div class="detail-layout">`. Inside it, `<div class="detail-media">` comes first and contains only the existing photo include. `<div class="detail-main">` comes second and contains the existing detail elements in their current order: `h1` title, status badge, category name, owner `display_name`, `Listed on`, description, the `Details` section, the `Edit` link when spec 04 shows it, and either `div.listing-actions` or the `Sign in to like or trade` link. Nothing in that list is removed, renamed, or reordered.
13. `.detail-layout` is a two-column grid at widths above 639px (picture left, facts right). Inside the existing `@media (max-width: 639px)` block it is one column, media then main. Do not add a second viewport meta tag or a new breakpoint.

### 4 — Category chip icons

14. Each category link in `nav.filters` is immediately preceded by `<img class="chip-icon" alt="" src="/static/img/icons/<file>.svg">`. The image is a sibling of the `<a>`, not a child, so the anchor's text stays exactly the category `name`.

    | Slug | File | Drawing |
    | --- | --- | --- |
    | `funko` | `static/img/icons/figure.svg` | A small figure |
    | `lego` | `static/img/icons/brick.svg` | A small brick |
    | `tcg` | `static/img/icons/card.svg` | A small card |

    `All` has no icon. `nav.game-filters` has no icons. Href, `aria-current`, and link text are unchanged.

### 5 — Empty states

15. When a list is empty, `<img class="empty-art" alt="" src="/static/img/empty.svg">` is rendered immediately before the existing empty paragraph. The paragraph text is not wrapped or changed. The image is omitted when that list has rows.

    | Page | Paragraphs that get the image |
    | --- | --- |
    | `/` | Whichever one empty string requirement 3 is showing |
    | `/matches` pair list | The `No matches yet.` paragraph |
    | Incoming, outgoing, finished | That section's `No …` paragraph |

    An empty Matches page therefore shows the image four times (pair list plus three trade sections). A browse page with items shows it zero times. The `Browse listings` link stays after the matches paragraph.

### 6 — Footer, favicon, motion

16. `templates/base.html` ends the body with `<footer class="site-footer">Easy Exchange, class project</footer>` after `</main>`. The text is not a link. Every page that extends the base layout shows it, including `/login` and `/register`.
17. The same template's `<head>` contains one `<link rel="icon" href="/static/img/favicon.svg" type="image/svg+xml">` (the `{% static %}` result). It does not add a `<script>` or a second stylesheet. The viewport meta tag stays the single existing tag.

Superseded by specs/10-header-hero-theme.md.
18. Cards (`.listing-card`, `.match-row`, `.trade-row`) keep the existing hover lift (`translateY(-2px)`). `button:hover` uses the same lift. `@media (prefers-reduced-motion: reduce)` sets `transition: none` and `transform: none` on those hovers, including `button:hover`. The existing `:focus-visible` outline (`2px solid` on links, buttons, and fields) stays and is not removed.

### Artwork

19. Every new SVG is drawn for this app. Flat shapes only. No downloaded or copied art, no brand logo, no licensed character, no face, no wordmark, no web font, no `<script`, no `<image`, and no `http` URL. Fills and strokes use only `#f6f1e6`, `#fffdf9`, `#e5f3f2`, `#f2faf6`, `#0f6e6b`, `#0b5552`, `#1c1917`, `#e8a23a`, and `#fbe7c2`.

    | File | Use |
    | --- | --- |
    | `static/img/hero.svg` | Home scene, `viewBox="0 0 320 200"` |
    | `static/img/steps/list.svg` | Step 1, `viewBox="0 0 24 24"` |
    | `static/img/steps/match.svg` | Step 2, `viewBox="0 0 24 24"` |
    | `static/img/steps/swap.svg` | Step 3, `viewBox="0 0 24 24"` |
    | `static/img/icons/card.svg` | TCG chip, `viewBox="0 0 24 24"` |
    | `static/img/icons/brick.svg` | Lego chip, `viewBox="0 0 24 24"` |
    | `static/img/icons/figure.svg` | Funko chip, `viewBox="0 0 24 24"` |
    | `static/img/empty.svg` | Empty states, `viewBox="0 0 160 120"` |
    | `static/img/favicon.svg` | Favicon, `viewBox="0 0 32 32"` |

    `empty.svg` is a new drawing. It is not a copy of `static/img/placeholders/generic.svg`. The four placeholder files are not modified.

## Acceptance criteria

- **Given** an anonymous visitor, **when** they `GET /`, **then** the hero is the first content and contains `Swap collectibles, not cash`, `List what you have and trade it one for one with another collector.`, `/static/img/hero.svg`, the three step texts in that order, `Register` to `/register`, and `Sign in` to `/login`, and the hero contains no `<form>`, no `/listings/new`, and no `/matches` or `/trades/` href.

Superseded by specs/10-header-hero-theme.md.
- **Given** a logged-in user, **when** they `GET /`, **then** the hero contains the same heading, sentence, scene, and steps, and `New listing` to `/listings/new`, and the hero contains no `<form>`, no `href="/login"`, and no `href="/register"`.

Superseded by specs/10-header-hero-theme.md.
- **Given** `/` with the three categories, **when** the category nav renders, **then** the four link texts and hrefs are unchanged (`All` to `/`, then the three category names to `/?category=<slug>`), `figure.svg` precedes the Funko link, `brick.svg` precedes the Lego link, `card.svg` precedes the Trading Card Games link, and none of those images is inside an `<a>`.
- **Given** a match of two photo-less items, **when** either owner opens `/matches`, **then** the row contains two `img.listing-photo` thumbnails (the category illustrations) and one `svg.swap-arrow` with `aria-hidden="true"` between the two titles, and `Your item`, `Their item`, both title links, both badges, and the other `display_name` are still present.
- **Given** a match where only one item has a photo, **when** the row renders, **then** that side's thumbnail `src` is the photo URL and the other side's `src` is that category's placeholder.
- **Given** an incoming proposal, an outgoing proposal, and a finished trade, **when** `/matches` renders, **then** each of those rows contains two thumbnails, the finished row contains no `<form>`, and the accept, reject, and cancel actions are unchanged.
- **Given** a listing detail page, **when** it renders, **then** `detail-media` precedes `detail-main` inside `detail-layout`, the photo is in `detail-media`, and the title, badge, owner, `Details`, and the action area are in `detail-main`.
- **Given** `static/css/base.css`, **when** the `max-width: 639px` block is read, **then** `.detail-layout` is a single column there.
- **Given** an empty browse page, a category with no rows, and a search with no rows, **when** each page renders, **then** the matching empty sentence is present, the other two browse empty sentences are absent, and `/static/img/empty.svg` appears immediately before the sentence that is shown.
- **Given** a logged-in user with no matches and no trades, **when** they `GET /matches`, **then** the four empty sentences from requirement 3 are present and `empty.svg` appears four times.
- **Given** any page that extends the base layout, **when** it renders, **then** the head has one favicon link to `/static/img/favicon.svg` and the body contains `Easy Exchange, class project`.
- **Given** the nine new SVG paths, **when** each file is read, **then** it contains `<svg` and does not contain `<script`, `<image`, or `http`, and the four placeholder paths still exist.

## Data and business rules

### Statements superseded

This spec supersedes only the layout claims below. The pointer line in those files is `Superseded by specs/09-visual-polish.md`. It does not replace the surrounding requirement. Link text, hrefs, badge text, empty sentences, and form actions listed in requirement 3 stay in force.

| Spec | Statement | What changes |
| --- | --- | --- |
| `04-browse.md` | Home / browse: the filter row is the first content (requirement 5, the pointer after that paragraph) | A hero is rendered above `nav.filters`. The filter row and everything below it stay. |
| `04-browse.md` | Requirement 12, detail content as one sequence after the picture | The picture sits in a left column and the existing sequence sits in a right column. The sequence itself is not reordered. |
| `05-likes-matches.md` | Requirement 16, each match is a plain row in that element order | Each side gains a thumbnail and a swap arrow sits between the sides. The listed texts stay in that order. |
| `08-enhancements.md` | Requirement 31, browse body starts at `nav.filters` | The hero is inserted before that sequence. The rest of the sequence stays. |
| `08-visual-design-and-photos.md` | Requirement 10, the detail picture is the first content element before the `h1`, and "The Matches page does not gain images." | The picture is the first child of `detail-media`. Match rows and trade rows gain thumbnails. |
| `08-visual-design-and-photos.md` | Out of scope "Images on the Matches page … or trade rows" and open question 9 | Those thumbnails are in scope. Like controls still gain no image. |

Not superseded, and left unchanged on purpose:

- Spec 04 filter hrefs, `aria-current`, card contents after the picture, badge classes, and the `Edit` / anonymous action rules.
- Spec 05 like rules, the empty sentence, and `Browse listings`.
- Spec 06 trade sections, button labels, form actions, and the relative order of the existing trade-row elements.
- Spec 08-visual placeholder file names, alt text, `STATIC_URL`, photo validation, and the gradient.
- Every service, model, and permission rule.

No new model, field, or query. Thumbnails read `item.photo` and `item.category` from rows the page already loads.

## Out of scope

- Changing `trades/services.py`, models, migrations, authentication, or permission checks
- New routes, including any hero link to `/matches` or a trade route
- Editing `_listing_photo.html` or any file under `static/img/placeholders/`
- Icons on `All` or on the game-filter chips
- A swap arrow on trade rows
- Reordering detail fields, or removing `Listed on`, the description, or `Edit`
- JavaScript, CDN assets, downloaded images, brand logos, faces, and web fonts

Superseded by specs/10-header-hero-theme.md.
- Payments, shipping, chat, OAuth, email verification, sports, Neo4j, brokers, native mobile
- Rewriting specs 00–08 beyond the pointer line, or editing `docs/plan.md`

## Test cases

Tests use Django's built-in runner and `django.test.TestCase` only. No pytest. One behavior per test. New docstrings start with `Spec 09 case N:`. Home, detail, favicon, footer, chips, browse empty states, and static files live in `catalog/tests/test_visual_polish.py`. Match and trade rows and the Matches empty states live in `trades/tests/test_visual_polish.py`. Image uploads use a temporary `MEDIA_ROOT`. Do not edit an existing test: this spec supersedes no current assertion.

Superseded by specs/10-header-hero-theme.md.

**Must-have**

1. **Anonymous hero.** `GET /` contains `section.hero` before `nav.filters`, the heading, the sentence, `hero.svg`, the three step texts in order, the three step image URLs, `Register` to `/register`, and `Sign in` to `/login`. The hero HTML contains no `href="/listings/new"`.

Superseded by specs/10-header-hero-theme.md.
2. **Logged-in hero.** The same heading, sentence, scene, and steps. The hero contains `New listing` to `/listings/new` and does not contain `href="/login"` or `href="/register"`.

Superseded by specs/10-header-hero-theme.md.
3. **No form and no trade link in the hero.** For both an anonymous and a logged-in `GET /`, the hero substring contains no `<form` and no `href` containing `/matches`, `/trades/`, or `/propose`.
4. **Chip links unchanged.** The four `nav.filters` anchors still match spec 04 (text, href, `aria-current` on `All` only at `/`). `icons/figure.svg`, `icons/brick.svg`, and `icons/card.svg` each appear in that nav, outside the anchors, before the matching category name. `nav.game-filters` on `/?category=tcg` contains no `icons/`.
5. **Match thumbnails and arrow.** A photo-less pair renders two `img.listing-photo` elements whose `src` values are the category placeholders, and one `svg` with `class="swap-arrow"` and `aria-hidden="true"` between the two title links. `Your item`, `Their item`, both category names, both badges, and the other display name remain.
6. **Photo versus placeholder on a match row.** One item has a stored photo and the other does not. The photo side's `src` is that file's URL. The blank side's `src` is its placeholder. Both alts stay `<title> (<category name>)`.
7. **Trade-row thumbnails.** After propose, the incoming row (as the counterparty) and the outgoing row (as the proposer) each contain two thumbnails, and the accept, reject, and cancel forms are unchanged. After accept, the finished row contains two thumbnails and no `<form>`.
8. **Detail structure.** The detail HTML has `detail-media` before `detail-main` inside `detail-layout`. The photo `img` is inside `detail-media`. The `h1`, the badge, the owner display name, `Details`, and the action region (`listing-actions` when logged in, the sign-in link when anonymous) are inside `detail-main`.
9. **Detail stacks in CSS.** `base.css` sets `.detail-layout` to one column inside `@media (max-width: 639px)`.
10. **Browse empty texts.** No items → `No listings yet.` and not the other two sentences, with `empty.svg` immediately before it. A category with no items → `No <category name> listings yet.` A non-blank `q` with no hits → `No listings match your search.` and not `No listings yet.` Each shown sentence is immediately preceded by `empty.svg`. A page with items does not include `empty.svg`.
11. **Matches empty texts.** A logged-in user with no matches sees the `No matches yet.` sentence, `Browse listings`, and the three trade empty sentences, and `empty.svg` four times.
12. **Favicon.** The head contains one `rel="icon"` link whose `href` is `/static/img/favicon.svg`.
13. **Static files.** The nine paths in requirement 19 exist. Each contains `<svg` and does not contain `<script`, `<image`, or `http`. `static/img/placeholders/funko.svg`, `lego.svg`, `tcg.svg`, and `generic.svg` still exist.
14. **Footer.** `GET /` and `GET /login` both contain `Easy Exchange, class project`.

**Nice-to-have**

15. `button:hover` lifts, and `prefers-reduced-motion: reduce` sets `transform: none` on that hover as well as on `.listing-card:hover`.
16. At 320px and at 1000px the detail columns are 1 and 2, the match row stacks only at 320px, and focus outlines are visible. This is a browser check.

### Existing assertions this spec supersedes

None. Do not change `catalog/tests/test_browse.py`, `test_detail.py`, `test_search.py`, `test_responsive.py`, `test_photo.py`, `trades/tests/test_matches.py`, or `trades/tests/test_matches_trades.py`. Chip icons stay outside the anchors so the link-text parser still reads `All` and the category names. The hero must not add `New listing` for an anonymous visitor or `Sign in` / `Register` for a logged-in visitor, because those absences are already asserted on `GET /`.

## Open questions

All decided. Each choice is the smallest one that meets the change request.

1. **Hero sentence.** Decided: `List what you have and trade it one for one with another collector.` (requirement 9).
2. **Hero links.** Decided: anonymous `Register` then `Sign in`; logged-in `New listing` only (requirement 10).
3. **Where the hero appears.** Decided: `GET /` only (requirement 9).
4. **Step and icon file names.** Decided: `list.svg`, `match.svg`, `swap.svg`, and `figure.svg` / `brick.svg` / `card.svg` (requirements 9 and 14).
5. **Which chips get icons.** Decided: the three category links only. `All` and the game chips do not (requirement 14).
6. **Icon placement.** Decided: a sibling immediately before the `<a>`, so the anchor text stays exact (requirement 14).
7. **One empty drawing.** Decided: `empty.svg` on every empty paragraph in requirement 15, including all three trade sections.
8. **Detail order.** Decided: wrap the current sequence. Do not move the badge, category, `Listed on`, description, or `Edit` (requirement 12).
9. **Phone width.** Decided: the existing 639px breakpoint. No new breakpoint (requirement 13).
10. **Arrow.** Decided: inline SVG on match rows only, `aria-hidden="true"`, class `swap-arrow` (requirements 5 and 7).
11. **Thumbnails.** Decided: reuse `_listing_photo.html` unchanged. Shrink them with CSS on match and trade rows only (requirements 4 and 8).
12. **Footer.** Decided: the exact text `Easy Exchange, class project`, not a link, in `base.html` (requirement 16).
13. **Favicon.** Decided: one `rel="icon"` link to `favicon.svg` (requirement 17).
14. **People in the scene.** Decided: faceless silhouettes. No licensed character and no face (requirement 19).
15. **Amber.** Decided: `#e8a23a` and `#fbe7c2` added to the existing cream / teal / mint / ink palette (requirement 19).
16. **Views.** Decided: no view or query change. Templates read objects the pages already have (Data and business rules).
17. **Existing tests.** Decided: none are updated (Test cases, *Existing assertions*).
18. **Hover and focus.** Decided: keep the current card lift and focus outline; add the same lift to `button:hover`; reduced motion disables it (requirement 18).

## Assumptions to confirm

1. The hero sentence is `List what you have and trade it one for one with another collector.`
2. Anonymous hero links are `Register` then `Sign in`. Logged-in visitors see only `New listing` in the hero.
3. The hero is only on `/`. The footer and favicon are on every base page.
4. Category icons sit outside the chip links. `All` and the game chips have no icon.
5. Detail fields stay in today's order, split into two columns that stack below 640px.
6. Match rows gain thumbnails and one inline swap arrow. Trade rows gain thumbnails and no arrow.
7. One `empty.svg` is reused for the browse empty lines and all four Matches empty lines.
8. No existing test is edited, and no view, model, migration, or service file is edited.
