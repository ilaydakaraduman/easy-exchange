# Spec: Header, hero, and theme

**Status:** Draft — awaiting user approval before any application code.

## Purpose

This change request gives every page one header: the brand, the only search form, the account links, and a day/night toggle, plus a home banner that appears only on the unfiltered browse page. It exists so the demo reads as a marketplace and can be read in a dark theme without a flash of the wrong colors.

Stack per [00-architecture.md](00-architecture.md): Django, server-rendered templates, SQLite, no JavaScript framework, no CDN, no web fonts. The one exception is `static/js/theme.js`, defined below. Browse stays public. Create, like, Matches, and trade stay login-gated. `Item.status` and `Trade.status` still change only in `trades/services.py`.

## User stories

- As any visitor, I want the brand, search, account links, and categories in the header on every page so that I can move around without going back to the home page.
- As any visitor, I want one search field that always submits to the browse page so that a search from a listing or from Matches still finds items.
- As an anonymous visitor on the unfiltered home page, I want a banner that explains the swap and offers browse and register actions so that I know this is a trade, not a shop.
- As a logged-in user on that same home page, I want the banner to offer a new listing so that I can add an item without hunting the header.
- As any visitor, I want the page to follow my system's light or dark setting, and a header control that remembers my choice, so that the text stays readable either way.

## Functional requirements

### What stays

1. No new route, model, field, migration, or change to `trades/services.py`. Like, match, trade, login, logout, registration, and permission behavior are not edited. Search matching is not edited: `q` is still trimmed, cut at 100 characters, and applied with `__icontains` on `title` or `description`, together with `category` and `game`, newest first (`order_by("-created_at", "-id")`). Unknown `category` and unknown `game` are still `404`.
2. These strings stay character for character, including punctuation:

   | Surface | Text that must stay |
   | --- | --- |
   | Brand | `Easy Exchange`, `href="/"` , class `brand` |
   | Header, anonymous | `Sign in` to `/login`, `Register` to `/register` |
   | Header, logged in | the user's `display_name` as text, `Logout` on a `POST` form to `/logout` |
   | Header, logged in only | `New listing` to `/listings/new`, `Matches` to `/matches` |
   | Chips | `All`, then each `Category.name`, same hrefs and `aria-current="page"` rules as specs 04 and 08-enhancements |
   | Hero heading | `Swap collectibles, not cash` |
   | Hero sentence | `List what you have and trade it one for one with another collector.` |
   | Tiles | `List an item`, `Match with collectors`, `Swap` |
   | Browse empty | `No listings yet.` |
   | Browse empty, category | `No <category name> listings yet.` |
   | Browse empty, search | `No listings match your search.` |
   | Footer | `Easy Exchange, class project` |
   | Search button | `Search` |
   | Search label | `Search` |

   Chip icons stay siblings immediately before the Funko, Lego, and TCG anchors, outside the `<a>`, with the same three files (`icons/figure.svg`, `icons/brick.svg`, `icons/card.svg`). `All` and `nav.game-filters` still have no icons. Class names `listing-card`, `filters`, `game-filters`, `badge`, `match-row`, `trade-row`, `search-form`, `hero`, `listing-actions`, `match_actions`, and `matches_trades` stay. The files under `static/img/placeholders/` are not renamed, moved, or rewritten. The favicon link and the single viewport meta tag stay. No second stylesheet.

### 1 — Site header

3. `templates/base.html` renders the header on every page that extends it, in two rows inside `<header>`.

   **Row 1** (`div.header-top`), in this order:

   | Piece | Markup |
   | --- | --- |
   | Brand | `<a class="brand" href="/">Easy Exchange</a>` |
   | Search | the one `form.search-form` from requirement 5 |
   | User area | anonymous: `<a href="/login">Sign in</a>` then `<a href="/register">Register</a>`. Logged in: `<span>` of `display_name`, then `<form method="post" action="/logout">` with `{% csrf_token %}` and `<button type="submit">Logout</button>`. No logout `<a>`. |
   | Theme | the button from requirement 16 |

   `New listing` and `Matches` are not in row 1.

   **Row 2** (`div.header-nav`), in this order: the existing category `nav.filters` (`aria-label="Categories"`), then, only when the user is logged in, `<a href="/listings/new">New listing</a>` and `<a href="/matches">Matches</a>`. Those two anchors are siblings after the nav, not inside it, so `nav.filters` still contains exactly the `All` anchor plus one anchor per `Category`. Anonymous visitors do not see `New listing`, `Matches`, or `Logout`.

4. The category anchors are built from `Category.objects.order_by("slug")`, not hard-coded. Href and `aria-current` rules are unchanged from spec 04 requirement 5 and spec 08-enhancements requirement 15: with a blank normalized `q`, `All` is `/` and each category is `/?category=<slug>`; with a non-blank `q`, `All` is `/?q=<encoded>` and each category is `/?category=<slug>&q=<encoded>` (`urlencode`, space as `%20`). Category links do not carry `game`. `aria-current="page"` is rendered only when `request.path == "/"` and that link is the active filter (the same rule as today's browse template). On every other path, no chip has `aria-current`. Chip-icon markup stays as spec 09 requirement 14.

5. There is exactly one search form on every page that extends the base layout, and it is this form, inside `header`, not inside `main`:

   ```html
   <form class="search-form" method="get" action="/">
     <label class="visually-hidden" for="id_q">Search</label>
     <input id="id_q" type="text" name="q" maxlength="100" placeholder="Search listings..." value="...">
     <button type="submit">Search</button>
   </form>
   ```

   The label text is `Search` and it is visually hidden (requirement 8). The placeholder is exactly `Search listings...`. The input value is the normalized `q` on the browse page and empty on every other page. When `active_category` is set, the form still includes `<input type="hidden" name="category" value="<slug>">`. When `active_game` is set, it still includes `<input type="hidden" name="game" value="<choice>">`. When those are inactive or the page is not browse, the matching hidden input is absent. The form is `GET` and has no CSRF token. `main` contains no `form.search-form` and no second `name="q"` input. `catalog/templates/catalog/browse.html` does not contain a search form.

6. **Where the category list comes from.** A context processor `catalog.context_processors.nav_categories` adds `categories` on every render. It stores `list(Category.objects.order_by("slug"))` on `request._nav_categories` and reuses that list if the browse view already set it. `browse` calls this helper for its own category list instead of querying `Category` a second time. `GET /` therefore stays two queries (categories, then items), with or without `q`. `GET /matches` gains that one category query and no other new query.

7. **Phone.** Inside the existing `@media (max-width: 639px)` block, `.header-top .search-form` is on its own row at `width: 100%` (`flex: 1 0 100%`). `.header-nav` is one non-wrapping row (`flex-wrap: nowrap`, `overflow-x: auto`) so the chips, and the logged-in `New listing` and `Matches` links, scroll horizontally. The search input, the search button, and `.theme-toggle` have a 44px minimum tap size (`min-height: 44px` and `min-width: 44px` on the button and the toggle; `min-height: 44px` on the input). The existing ≤ 960px 44px rules for the brand, `Sign in`, `Register`, `New listing`, `Matches`, `Logout`, and the chips stay.

8. `.visually-hidden` clips the search label out of view without removing it from the accessibility tree (`position: absolute`, `width` and `height` `1px`, `overflow: hidden`, `clip`). The label stays associated by `for="id_q"`.

### 2 — Home hero

9. The hero and the tiles render only from the browse view, and only when the home page is unfiltered: `request.path == "/"`, the normalized `q` is empty, `active_category` is `None` (`category` absent, `""`, or `all`), and the `game` value is absent, `""`, or `all`. A known `game` choice hides them even when the category is not `tcg` and the list itself is not game-filtered. An unknown `game` or `category` is still `404` and renders no hero. `/?q=`, `/?q=%20%20`, `/?category=all`, `/?category=`, and `/?game=all` still show the hero, because those values do not filter (specs 04 and 08-enhancements).

10. When requirement 9 is true, `main` starts with `<section class="hero">`, then `<section class="feature-tiles">`, then `<section id="listings">`. When it is false, `main` starts with `<section id="listings">` and contains no `section.hero` and no `section.feature-tiles`. No other template renders the hero or the tiles.

11. `<section class="hero">` contains, in this order, and nothing else that is a form, a heading, or a link: `div.hero-copy` (the `h1` `Swap collectibles, not cash`, one `<p>` with the sentence in requirement 2, and `<p class="hero-actions">` with the two anchors below), then `<img class="hero-scene" src="/static/img/hero.svg" alt="">`. The scene stays two faceless collectors exchanging a card and a figure. `static/img/hero.svg` is redrawn in place: same path, `viewBox="0 0 320 200"`, flat shapes, the palette in requirement 22, no face, no `<script`, no `<image`, no `http` other than the SVG namespace. No carousel.

    The two anchors are not `<button>` elements and are not wrapped in a form. Exact markup, in this order:

    | Visitor | Anchors |
    | --- | --- |
    | Anonymous | `<a href="#listings">Browse listings</a>` then `<a href="/register">Create an account</a>` |
    | Logged in | `<a href="#listings">Browse listings</a>` then `<a href="/listings/new">New listing</a>` |

    The hero contains no `<form>`, no `href="/listings/new"` when anonymous, and no `href="/login"`, no `href="/register"`, and no `Create an account` when logged in. It contains no `href` to `/matches`, `/trades/`, or any propose path. The steps are not inside the hero.

12. `<section class="feature-tiles">` follows the hero and contains three tiles, in order, each with an empty-alt image and the text: `/static/img/steps/list.svg` + `List an item`, `/static/img/steps/match.svg` + `Match with collectors`, `/static/img/steps/swap.svg` + `Swap`. The three files already exist; they are not renamed. A tile is not an `<a>` and not a `<button>`. The section contains no `<form>` and no `href` to `/matches`, `/trades/`, `/listings/new`, `/login`, `/register`, or any propose path.

13. `<section id="listings">` wraps the browse results on every `GET /`, filtered or not. Inside it, in order: `nav.game-filters` only when the category is `tcg` (same links, hrefs, and `aria-current` as spec 08-enhancements requirement 21), then either `ul.listings` or the empty `<img class="empty-art">` immediately followed by the one empty `<p>`. Card contents, badge markup, and the three empty sentences are unchanged. The game nav is not in the header.

14. The hero banner uses a teal gradient from `#0b5552` to `#0f6e6b` in both themes. Text on that banner is `#f6f1e6`. Those two colors are custom properties (`--hero-start`, `--hero-end`, `--on-hero`) and are not overridden to a darker pair in the dark theme.

### 3 — Day and night theme

15. Every color that paints a page, header, card, form, input, table, chip, badge, button, link, or focus outline comes from a custom property in `static/css/base.css`. Light theme is the current look: the existing `:root` values stay, and any hex or `rgb` that is still written on a rule moves into a property whose light value is that same color. `color-scheme: light` is set for the light theme.

    Dark theme tokens, used both under `@media (prefers-color-scheme: dark)` on `:root:not([data-theme])` and under `[data-theme="dark"]`:

    | Property | Dark value |
    | --- | --- |
    | `--bg`, `--page-start`, `--page-end` | `#0e1a1f` |
    | `--page-mid` | `#12343a` |
    | `--surface` | `#15262c` |
    | `--header-bg` | `#102126` |
    | `--input-bg` | `#1b333b` |
    | `--ink` | `#f6f1e6` |
    | `--muted` | `#d7cfc4` |
    | `--border` | `#2c454d` |
    | `--border-strong` | `#3d5c66` |
    | `--accent` (filled buttons) | `#0f6e6b` |
    | `--on-accent` | `#ffffff` |
    | `--accent-strong` (links and the focus outline) | `#8ef6ee` |
    | `--accent-soft` | `#163a3a` |
    | `--danger` | `#ffb4b4` |
    | `--danger-soft` | `#3b1212` |

    `[data-theme="light"]` uses the light values even when the system preference is dark. `[data-theme="dark"]` uses the dark values even when the system preference is light. With no `data-theme`, the system preference wins, including `color-scheme`. No script is required for that default.

    Badge pairs stay the current light-chip values in both themes, because those pairs already meet AA: `AVAILABLE` `--available-bg` `#d9f2e3` / `--available-fg` `#0b4f28`; `IN_TRADE` and `PROPOSED` `--pending-bg` `#fbe7c2` / `--pending-fg` `#6a3d00`; `TRADED` and `CANCELLED` `--neutral-bg` `#eceae6` / `--neutral-fg` `#3f3a36`; `ACCEPTED` uses the available pair; `REJECTED` `--rejected-bg` `#fadcd9` / `--rejected-fg` `#8a1a1a`. Text on `--bg`, `--surface`, `--header-bg`, `--input-bg`, and `--hero-end`, and white text on `--accent`, meet WCAG AA (4.5:1 for text, 3:1 for the focus outline) in both themes.

16. The header toggle is:

    ```html
    <button type="button" class="theme-toggle" aria-label="Switch to dark theme" aria-pressed="false">
    ```

    with two inline SVGs inside it, `class="icon-sun"` and `class="icon-moon"`, each `aria-hidden="true"`, a `viewBox`, no `<script`, no `<image`, and no `http` other than the SVG namespace. The server always renders the label `Switch to dark theme` and `aria-pressed="false"` (the test client does not run script). CSS shows the sun in the light theme and the moon in the dark theme, including the no-`data-theme` system-dark case. `.theme-toggle` is not inside the search form and does not submit it.

17. The choice is stored in `localStorage` under the key `easy-exchange-theme`. The only stored values that count are `light` and `dark`. Any other value, or a storage error, is treated as no override. The applied value is the attribute `data-theme` on `<html>` (`light` or `dark`). When there is no stored override, the script does not set `data-theme`, so requirement 15's media query stands.

18. The behavior lives in one file, `static/js/theme.js`, and nowhere else. `templates/base.html` loads it from `<head>` as `<script src="/static/js/theme.js"></script>` (the `{% static %}` result), with no `defer`, no `async`, and no `type="module"`. The tag is empty. It is the only `<script` element on the page. There is no inline script, no `onclick`, and no other JavaScript file. The script runs while the parser is still in `<head>`, reads `localStorage`, and sets `data-theme` before the body is parsed when a stored `light` or `dark` value exists, so a stored theme does not flash. On `DOMContentLoaded` it points the button's `aria-label` at `Switch to dark theme` or `Switch to light theme`, sets `aria-pressed` to `false` for light and `true` for dark, and on click stores the opposite value and sets `data-theme`. About 20 lines. No libraries.

19. Illustration tiles keep a light background in the dark theme so the dark strokes stay legible. `--illustration-bg` is `#f6f1e6` in both themes and is not overridden. It is the background of `.feature-tile`, `.hero-scene`, `.chip-icon`, `.empty-art`, and `.listing-photo`. User-uploaded photos are not recolored.

20. `color-scheme` follows the active theme (requirement 15). `@media (prefers-reduced-motion: reduce)` already sets `transition: none` and `transform: none` on the existing hovers. Theme changes are not animated. Do not add a color transition.

### Artwork and script file

21. `static/js/theme.js` is the only new static file required. `static/img/hero.svg` is replaced in place. The step SVGs, chip icons, `empty.svg`, `favicon.svg`, and the four placeholder files stay. New or replaced SVG art is drawn for this app: flat shapes, no downloaded or copied art, no brand logo, no licensed character, no face, no wordmark, no web font, no `<script`, no `<image`. Fills and strokes use only `#f6f1e6`, `#fffdf9`, `#e5f3f2`, `#f2faf6`, `#0f6e6b`, `#0b5552`, `#1c1917`, `#e8a23a`, and `#fbe7c2`.

22. Templates and files this spec may edit: `templates/base.html`, `catalog/templates/catalog/browse.html`, `static/css/base.css`, `static/img/hero.svg`, `catalog/views.py` (browse calls the shared category helper; filter logic unchanged), `catalog/context_processors.py` (new), `config/settings.py` (register that processor only). Tests named under *Existing assertions this spec supersedes* may be edited as that section says. Nothing else.

## Acceptance criteria

- **Given** an anonymous visitor, **when** they open `/`, `/?category=funko`, a listing detail page, or `/login`, **then** each page contains exactly one `form.search-form`, it is inside `header`, its action is `/`, its method is `get`, it has `name="q"`, the placeholder `Search listings...`, a visually hidden label `Search`, and a `Search` button, and `main` has no second search form.
- **Given** a logged-in user, **when** they open `/matches`, **then** that same one search form is in the header, and the page has no second `name="q"` input.
- **Given** an anonymous visitor, **when** any base page renders, **then** the header shows `Easy Exchange` to `/`, `Sign in` to `/login`, and `Register` to `/register`, the four category links with the spec 04 hrefs, and no `New listing`, no `Matches`, and no `Logout`.
- **Given** a logged-in user, **when** any base page renders, **then** the header shows the `display_name`, a `POST` `Logout` button, `New listing` to `/listings/new`, and `Matches` to `/matches` outside `nav.filters`, and it shows no `Sign in` and no `Register`.
- **Given** `GET /` with no filtering `q`, `category`, or `game`, **when** an anonymous visitor renders it, **then** `section.hero` is in `main` and contains the heading, the sentence, `/static/img/hero.svg`, `Browse listings` to `#listings`, and `Create an account` to `/register`, and the hero contains no `<form>`, no `/listings/new`, and no `/login`.
- **Given** the same unfiltered `GET /` for a logged-in user, **when** it renders, **then** the hero contains `Browse listings` to `#listings` and `New listing` to `/listings/new`, and the hero contains no `<form>`, no `/login`, no `/register`, and no `Create an account`.
- **Given** `/?q=ada`, `/?category=funko`, or `/?category=tcg&game=Other`, **when** the page renders, **then** it contains no `section.hero` and no `section.feature-tiles`, and it still contains `id="listings"` and the one header search form.
- **Given** the unfiltered home page, **when** it renders, **then** `section.feature-tiles` follows the hero and contains `List an item`, `Match with collectors`, and `Swap` in that order, with the three step image URLs, and that section contains no `<form>` and no trade, match, login, or register href.
- **Given** any of `/`, `/?category=funko`, a detail page, `/login`, and `/matches`, **when** it renders, **then** the header contains `<button type="button" class="theme-toggle" aria-label="Switch to dark theme" aria-pressed="false">` and an inline sun or moon SVG.
- **Given** any base page, **when** the head is read, **then** it contains exactly one script tag, `src="/static/js/theme.js"`, with no `defer` and no inline body, and the document has no other `<script`.
- **Given** `static/js/theme.js`, **when** the staticfiles finder resolves `js/theme.js`, **then** the file exists and contains `easy-exchange-theme`, `localStorage`, and `data-theme`.
- **Given** `GET /`, **when** the response is read, **then** a description or title of `<script>alert(1)</script>` is escaped, and the only raw `<script` is the theme file tag.
- **Given** six listings, **when** `GET /` is rendered inside `assertNumQueries`, **then** the count is still 2. **Given** six matches, **when** `GET /matches` is rendered, **then** the count is 5.

## Data and business rules

### Statements superseded

This spec supersedes only the claims below. The pointer line in those files is `Superseded by specs/10-header-hero-theme.md`. It does not replace the surrounding requirement. Link text, hrefs, badge text, empty sentences, search matching, and form actions listed in requirement 2 stay in force.

| Spec | Statement | What changes |
| --- | --- | --- |
| `00-architecture.md` | Rendering sentence: server-side only, no JavaScript framework | One file, `static/js/theme.js`, may load. No framework, no client-side validation, and no REST API stay. |
| `09-visual-polish.md` | Stack line "no JavaScript"; requirement 17 "does not add a `<script>`"; out of scope "JavaScript" | The head loads `theme.js`. No second stylesheet, no CDN, no web font. |
| `09-visual-polish.md` | Requirements 9 and 10, the two hero acceptance bullets, and test cases 1 and 2 | Hero buttons become `Browse listings` plus `Create an account` or `New listing`. The three steps move out of the hero into `section.feature-tiles`. The hero is only the unfiltered home page. Heading, sentence, and `hero.svg` stay. |
| `09-visual-polish.md` | Requirement 11, and requirement 2's "the search form stay as they are" | The search form moves into the header. Hidden `category` and `game` inputs, `name="q"`, `id="id_q"`, `maxlength="100"`, class `search-form`, and the `Search` button stay. The label becomes visually hidden and gains the placeholder. |
| `09-visual-polish.md` | "Do not edit an existing test" | Only the tests named under *Existing assertions* are edited, and only as that section says. |
| `08-enhancements.md` | Requirement 2 "no `<script>`"; the acceptance bullet "the body contains no `<script`"; test case 3 "`GET /` contains no `<script`"; out of scope "JavaScript" | The one external script tag is allowed. CDN assets and the Pillow-only dependency rule stay. |
| `08-enhancements.md` | Requirement 14, the form sits above the cards after the category nav; requirement 9, the empty `<p>` sits after the search form; requirement 21, the game nav is before the search form; requirement 31, browse body order | Category nav and the search form leave the browse body. The game nav, the list, and the empty state stay, inside `#listings`. |
| `08-visual-design-and-photos.md` | Requirement 14 "No `<script>` is added"; out of scope "JavaScript" | The one theme script is allowed. The viewport, breakpoints, and "no remote `url(http`" stay. Broken images still use the CSS background, not script. |
| `04-browse.md` | Requirement 5, the filter row is the first browse content (the pointer already notes spec 09) | `nav.filters` moves into header row 2. Href text, order, and `aria-current` stay. |

Not superseded, and left unchanged on purpose:

- Spec 01 and spec 03 bans on client-side validation. `theme.js` does not validate forms.
- Spec 04 filter hrefs, card contents, badge classes, empty sentences, and the two-query browse bound.
- Spec 08-enhancements search matching, the 100-character cut, hidden inputs, and game-link hrefs.
- Spec 02 header strings for `Sign in`, `Register`, `display_name`, and `Logout`, and the `POST`-only logout rule.
- Spec 03 and spec 05: `New listing` and `Matches` stay logged-in-only. They move to row 2 and stay outside `nav.filters`.
- Spec 09 detail columns, match thumbnails, empty-art, footer, favicon, and chip icons.
- Every service, model, migration, and permission rule.

No new model or field. The header reads `Category` rows and `request.GET` values the browse view already resolves (`q`, `active_category`, `active_game`).

## Out of scope

- Changing `trades/services.py`, models, migrations, authentication, or permission checks
- A second search form, search of metadata or owner, or search on a route other than `GET /`
- Putting `New listing` or `Matches` inside `nav.filters`
- A hero on filtered browse, detail, login, Matches, or any page that is not the unfiltered home
- A carousel, a form inside the hero, or a tile that links to a trade or match route
- More than `static/js/theme.js`, inline scripts, libraries, CDN assets, or web fonts
- Renaming or rewriting `static/img/placeholders/`
- Copying a third-party logo, wordmark, character, or layout text
- Payments, shipping, chat, OAuth, email verification, sports, Neo4j, brokers, native mobile
- Rewriting specs 00–09 beyond the pointer line, or editing `docs/plan.md`

## Test cases

Tests use Django's built-in runner and `django.test.TestCase` only. No pytest. One behavior per test. Plain helper functions, no factory_boy. New docstrings start with `Spec 10 case N:`. New tests live in `catalog/tests/test_header_hero_theme.py`. The test client does not execute JavaScript, so aria-label checks read the server HTML. "Served" means `django.contrib.staticfiles.finders.find("js/theme.js")` returns a file, and the rendered href is `/static/js/theme.js`. Do not use a live server and do not use pytest.

**Must-have**

1. **One search form, home.** Anonymous `GET /` has exactly one `form.search-form`. It is inside `<header>`, `method="get"`, `action="/"`, with `name="q"`, `id="id_q"`, `placeholder="Search listings..."`, a label `Search` that has class `visually-hidden`, and `>Search</button>`. `<main>` contains no `search-form`.
2. **One search form, filtered browse.** `GET /?category=funko` has exactly one `form.search-form`, in the header, and its hidden category value is `funko`.
3. **One search form, detail.** Anonymous `GET /listings/<id>` has exactly one `form.search-form`, in the header, and no hidden `category` input.
4. **One search form, login.** `GET /login` has exactly one `form.search-form`. The login `POST` form is still present and is not that search form.
5. **One search form, matches.** A logged-in `GET /matches` has exactly one `name="q"` input, inside the header search form.
6. **Anonymous header links.** `GET /` contains `<a class="brand" href="/">Easy Exchange</a>`, `<a href="/login">Sign in</a>`, `<a href="/register">Register</a>`, and the four `nav.filters` hrefs `/`, `/?category=funko`, `/?category=lego`, `/?category=tcg`. It does not contain `New listing`, `href="/listings/new"`, `href="/matches"`, or `>Logout</button>`.
7. **Logged-in header links.** A logged-in `GET /` contains the `display_name`, `<form method="post" action="/logout">`, `>Logout</button>`, `<a href="/listings/new">New listing</a>`, and `<a href="/matches">Matches</a>`. Those two anchors are outside `nav.filters`. The page does not contain `>Sign in</a>` or `>Register</a>`.
8. **Anonymous hero, unfiltered only.** `GET /` has `section.hero` inside `main`, the heading, the sentence, `hero.svg`, `<a href="#listings">Browse listings</a>`, and `<a href="/register">Create an account</a>`. The hero substring contains no `<form`, no `href="/listings/new"`, and no `href="/login"`.
9. **Logged-in hero buttons.** The hero contains `<a href="#listings">Browse listings</a>` and `<a href="/listings/new">New listing</a>`, and does not contain `href="/login"`, `href="/register"`, or `Create an account`.
10. **Hero hidden when a filter is on.** `GET /?q=ada`, `GET /?category=funko`, and `GET /?category=tcg&game=Other` each contain no `section class="hero"` and no `section class="feature-tiles"`, and each contains `id="listings"`.
11. **No form in the hero.** For anonymous and logged-in `GET /`, the hero substring contains no `<form` and no `href` containing `/matches`, `/trades/`, or `/propose`.
12. **Feature tiles.** On unfiltered `GET /`, `section.feature-tiles` follows the hero and contains, in order, `List an item`, `Match with collectors`, `Swap`, and the three step image URLs. That section contains no `<a ` and no `<form`.
13. **Theme toggle on every page type.** `/`, `/?category=funko`, a detail URL, `/login`, and a logged-in `/matches` each contain `class="theme-toggle"`, `aria-label="Switch to dark theme"`, and `aria-pressed="false"`.
14. **theme.js linked and found.** The head contains one `<script src="/static/js/theme.js"></script>` with no `defer`. `finders.find("js/theme.js")` returns a path. That file contains `easy-exchange-theme`, `localStorage`, and `data-theme`.
15. **No inline script.** Across the five pages in case 13, each document contains exactly one `<script`, and that tag's body is empty.
16. **Static files.** `static/js/theme.js` and `static/img/hero.svg` exist. `hero.svg` contains `<svg`, `viewBox="0 0 320 200"`, and does not contain `<script`, `<image`, or `http` after the SVG namespace is stripped. `static/img/placeholders/funko.svg`, `lego.svg`, `tcg.svg`, and `generic.svg` still exist.

**Nice-to-have**

17. In a browser, with no stored key, the colors follow `prefers-color-scheme`, and choosing the toggle writes `easy-exchange-theme` and sets `data-theme` with no flash on the next load.
18. At 320px the search form is on its own row, the category row scrolls, and the tap targets are at least 44px. Contrast of body text and the seven badge labels meets AA in both themes.

### Existing assertions this spec supersedes

Edit only these tests, and only in the way written here. Do not delete an assertion that this list does not replace. Do not change `catalog/tests/test_search.py`, `test_browse.py`, `test_tcg_game.py`, `accounts/tests/test_login.py`, or `catalog/tests/test_create_listing.py`.

| Test | Why it changes | What the edited assertion must still prove |
| --- | --- | --- |
| `catalog/tests/test_visual_polish.py` `test_anonymous_hero_texts_and_links` | Hero links and the step list move; `nav.filters` moves into the header, so the hero is no longer before that nav | Heading, sentence, and `hero.svg` stay inside the hero. The hero contains `Browse listings` to `#listings` and `Create an account` to `/register`, and still contains no `href="/listings/new"`. The three step texts and three step image URLs move to `section.feature-tiles`, still in that order. `nav.filters` is inside `<header>` and the hero is inside `<main>`. |
| `catalog/tests/test_visual_polish.py` `test_logged_in_hero_offers_new_listing` | The steps leave the hero; `Browse listings` is added | The hero still contains `<a href="/listings/new">New listing</a>` and still contains no `href="/login"` and no `href="/register"`. Step texts are asserted on `section.feature-tiles`, not on the hero substring. |
| `catalog/tests/test_responsive.py` `test_stylesheet_defines_breakpoints_without_a_remote_url` | `GET /` now contains one external script tag, so `assertNotIn("<script"` fails | Keep every CSS assertion in that test. Replace only the script assertion: exactly one `<script`, `src="/static/js/theme.js"`, empty body, no `defer`. |
| `catalog/tests/test_detail.py` `test_description_script_is_escaped` | The same external tag contains the substring `<script>`, so `assertNotIn("<script>", html)` fails | Keep `assertIn("&lt;script&gt;", html)`. Replace the raw-tag assertion: no `<script>alert`, and the only `<script` is `src="/static/js/theme.js"`. |
| `trades/tests/test_matches.py` `test_matches_page_query_count_is_bounded` | The header category list adds one `Category` query | Change `assertNumQueries(4)` to `assertNumQueries(5)`. Keep the assertion that six match rows render. Do not raise the browse or TCG query bounds; those stay 2. |

`test_hero_has_no_form_or_trade_link` is not edited. The hero still has no form and no trade href. `test_category_chip_links_stay_and_gain_icons` is not edited. `nav.filters` still has the four anchors and the three icons outside them.

## Open questions

All decided. Each choice is the smallest one that meets the change request and keeps the assertions this spec does not name.

1. **Hero sentence.** Decided: keep `List what you have and trade it one for one with another collector.` (requirement 2).
2. **Hero actions.** Decided: `Browse listings` (`#listings`) then, for anonymous visitors, `Create an account` (`/register`), and for logged-in users, `New listing` (`/listings/new`). Anchors, not buttons, so the hero has no form and no script (requirement 11).
3. **Where the hero appears.** Decided: only the unfiltered home page. `category` or `game` of `""` or `all`, and a blank `q`, still count as unfiltered (requirement 9).
4. **Tiles.** Decided: the three existing step SVGs, outside the hero, not links (requirement 12).
5. **Search form.** Decided: move the existing form into the header. One per page. Label stays `Search` and is visually hidden. Placeholder `Search listings...` (requirement 5).
6. **Category nav.** Decided: move `nav.filters` into header row 2 without putting `New listing` or `Matches` inside it (requirement 3).
7. **Game nav.** Decided: it stays in the browse body, inside `#listings` (requirement 13).
8. **Category query.** Decided: one shared request cache so `GET /` stays at 2 queries and `GET /matches` becomes 5 (requirement 6).
9. **`aria-current` off the home page.** Decided: only when `request.path == "/"` (requirement 4). The request context processor is already enabled.
10. **Theme storage.** Decided: `localStorage` key `easy-exchange-theme`, attribute `data-theme` on `<html>`, values `light` and `dark` only (requirement 17).
11. **Default theme.** Decided: CSS `prefers-color-scheme` when `data-theme` is absent. The script sets `data-theme` only for a stored value (requirements 15 and 17).
12. **Server-rendered toggle.** Decided: `aria-label="Switch to dark theme"` and `aria-pressed="false"`, because the test client does not run script (requirement 16).
13. **Script loading.** Decided: one empty `<script src>` in `<head>`, no `defer`, so a stored theme is applied before the body is parsed (requirement 18).
14. **Dark palette.** Decided: the token table in requirement 15. Badge chip pairs stay as they are in both themes. Hero gradient stays `#0b5552` to `#0f6e6b` with cream text in both themes.
15. **Illustration tiles.** Decided: `--illustration-bg` `#f6f1e6` in both themes on the feature tiles, the hero scene, chip icons, empty art, and listing photos (requirement 19).
16. **Light header fill.** Decided: solid `var(--header-bg)` `#fffdf9`, the current header tint without the 0.94 alpha, so the color is a custom property.
17. **Phone breakpoint.** Decided: the existing `639px` breakpoint for the full-width search row and 44px search and toggle targets (requirement 7).
18. **Existing tests.** Decided: only the five rows in *Existing assertions* are edited (that section).

## Assumptions to confirm

1. The hero sentence stays `List what you have and trade it one for one with another collector.`
2. Hero actions are anchors: `Browse listings` to `#listings`, then `Create an account` or `New listing`.
3. The hero and the three tiles show only on unfiltered `/`. Blank `q` and `category` or `game` of `all` still count as unfiltered.
4. The only search form is in the header. The label `Search` is visually hidden. The placeholder is `Search listings...`.
5. `New listing` and `Matches` sit in header row 2, outside `nav.filters`. The game chips stay in the listings section.
6. `GET /` stays at 2 queries. `GET /matches` becomes exactly 5.
7. The server-rendered toggle always says `Switch to dark theme` until `theme.js` runs.
8. Light mode keeps today's colors. Dark mode uses the slate and teal tokens in requirement 15. Illustration tiles stay on `#f6f1e6`.
9. Only the five existing tests named in this spec are edited, and `static/img/placeholders/` is not touched.
