# Spec: Enhancements

**Status:** Approved

## Purpose

This change request adds four features the approved MVP left out: a phone-usable layout with a photo area on listing cards, text search on the public browse page, two optional TCG metadata fields that ride the existing schema, and one optional uploaded photo per listing. It exists so the demo can be used on a phone, found by title or description, and shown to extend a category by editing schema data rather than adding tables.

Stack per [00-architecture.md](00-architecture.md): Django, server-rendered templates, SQLite, no JavaScript framework, no CDN. Browse stays public. Create and edit stay login-gated and `AVAILABLE`-only, per [03-listings.md](03-listings.md). `Item.status` and `Trade.status` still change only in `trades/services.py`.

Where this spec and specs 00–07 disagree on the statements listed under *Statements superseded*, this spec wins. Every other requirement in specs 00–07 stays in force. `docs/plan.md` is not edited by this spec; plan section 2 ("No image upload in MVP"), plan section 7 cut 1 (image URLs and search beyond the category filter), and the fixed TCG key list are the plan statements this spec supersedes once it is approved.

## User stories

- As an anonymous visitor on a phone, I want the browse page, forms, and Matches page to fit the screen so that I can read listings without a shrunken desktop page.
- As an anonymous visitor, I want each listing card to show a photo or a clear placeholder so that I can scan the board quickly.
- As an anonymous visitor, I want to search listings by words in the title or description, together with the category filter, so that I can find one item in the list.
- As a logged-in user, I want optional Game and Set name fields on a TCG listing so that the category schema can grow without a new table.
- As an anonymous visitor browsing TCG, I want to filter by game so that I only see Pokémon, Magic, Yu-Gi-Oh!, or Other.
- As a listing owner, I want to attach one optional photo when I create or edit an `AVAILABLE` listing so that the card and the detail page show the item.
- As a listing owner, I want a clear error when the file is the wrong type or too large so that I know what to upload instead.

## Functional requirements

### A — Mobile and visual polish

1. `templates/base.html` includes exactly one viewport tag: `<meta name="viewport" content="width=device-width, initial-scale=1">`. If that tag is already present, do not add a second one.
2. Styling stays in `static/css/base.css`, loaded by the existing `{% static 'css/base.css' %}` link. No new stylesheet, no `@import` of a remote URL, no `url(http...)` or `url(https...)`, no CDN font, and no `<script>` added to any template this spec touches.
3. **Columns** for `ul.listings`, from a 320px-wide viewport up:
   - width ≤ 639px: one column
   - 640px through 960px inclusive: two columns
   - width ≥ 961px: three columns

   Use `repeat(3, minmax(0, 1fr))` as the wide default, `repeat(2, minmax(0, 1fr))` inside `@media (max-width: 960px)`, and `minmax(0, 1fr)` inside `@media (max-width: 639px)`. The `li` class stays `listing-card`.
4. **Header.** At widths ≤ 960px, the header nav wraps onto extra lines instead of forcing page scroll. The brand link, each header link (`New listing`, `Matches`, `Sign in`, `Register`), and the `Logout` button have a minimum tap size of 44px by 44px (`min-height: 44px` and `min-width: 44px`). Link text and the `Logout` button text stay the strings from specs 02, 03, and 05.
5. **Filter chips.** `.filters` and `.game-filters` lay out in one non-wrapping row (`flex-wrap: nowrap`) that scrolls horizontally (`overflow-x: auto`). At widths ≤ 960px each chip link has a minimum block size of 44px by 44px. Chip text stays on one line.
6. **Forms and Matches.** At widths ≤ 639px, login, register, the category switch, the create form, and the edit form stack as a single column with controls at `width: 100%` and `max-width: 100%`. `.match-row`, `.trade-row`, and `.details` become one column. Images, inputs, textareas, and selects use `max-width: 100%`. The page does not require horizontal scrolling at 320px. The existing `overflow-x: clip` on `html` may stay; do not rely on clipping as a substitute for the column and `max-width` rules.
7. **Card photo area.** Every browse card starts with a photo area, before the title link, so the title `<a href="/listings/<id>">` remains the first anchor in the card. The `li` class stays exactly `listing-card`. Until an `Item.photo` field exists (feature D), every card renders this placeholder and does not read a photo attribute:

   `<div class="listing-photo listing-photo-placeholder"></div>`

   The placeholder has no text. It is a block that fills the card width, uses `aspect-ratio: 4 / 3`, and uses the existing `--neutral-bg` token as its background. No external image.
8. The card still shows, after the photo area and in this order, the title link, the category name, the status badge, and the owner `display_name`. It still omits `description`, metadata values, `Edit`, and every `<form>` (spec 04 requirement 6, plus the photo area).
9. Empty-state copy stays in a `<p>` after the search form (feature B). Extend the existing empty-state CSS so that paragraph keeps its current styling when `.game-filters` or `.search-form` sits between `nav.filters` and the paragraph.

### B — Search

10. `GET /` accepts a query parameter `q`. Browse stays public and `GET`-only (spec 04 requirements 1 and 18).
11. **Normalization.** Trim leading and trailing whitespace. A missing `q`, an empty `q`, or a `q` that is empty after trimming means no search: the listing set is exactly the set spec 04 would return for the same `category` (and, once feature C exists, the same `game`). A value longer than 100 characters is cut to the first 100 characters after trimming. There is no error page and no field error for length. The value shown in the search input is the normalized value (trimmed, then cut).
12. **Match.** A non-blank normalized `q` keeps items whose `title` or `description` contains that string, case-insensitively, using Django `__icontains` (logical OR). Metadata, owner, status, and category name are not searched. The category filter and the game filter (feature C) still apply. Ordering stays `order_by("-created_at", "-id")`. There is still no pagination.
13. **Unknown category** is still `404` before search runs (spec 04 requirement 4). A search does not turn an unknown category into an empty list.
14. **Form.** Above the cards, after the category nav and after the game nav when that nav is present:

    ```html
    <form class="search-form" method="get" action="/">
      <label for="id_q">Search</label>
      <input id="id_q" type="text" name="q" maxlength="100" value="...">
      <button type="submit">Search</button>
    </form>
    ```

    The button text is exactly `Search`. When a category is selected, the form includes `<input type="hidden" name="category" value="<slug>">`. When a game filter is active (feature C), it also includes `<input type="hidden" name="game" value="<choice>">`. When those filters are inactive, the matching hidden input is absent. The form is `GET` and has no CSRF token.
15. **Category links and `q`.** When the normalized `q` is empty, category-link hrefs and `aria-current` stay exactly as spec 04 requirement 5 (`All` → `/`, each category → `/?category=<slug>`). When `q` is non-blank, `All` is `/?q=<encoded>` and each category is `/?category=<slug>&q=<encoded>`. Encoding uses Django's `urlencode` filter (space as `%20`). Category links do not carry `game`.
16. **Empty results.** When the normalized `q` is non-blank and the filtered list is empty, the page shows exactly `No listings match your search.` and does not show `No listings yet.` or `No <category name> listings yet.` When `q` is blank, those two spec 04 strings stay as they are, including a TCG game filter that matches nothing.
17. **Escaping.** `q`, titles, and descriptions are written with Django auto-escaping. No `|safe` on them. A `q` or title containing `<script>` is escaped in the HTML and does not create a script element.

### C — TCG schema fields and game filter

18. The `tcg` `metadata_schema` gains two entries, appended after `card_condition`, in this order. `funko` and `lego` schemas are unchanged. The generic validator and the dynamic form builder are not modified and gain no `slug` branch.

    | `key` | `label` | `type` | `required` | Optional entry keys |
    | --- | --- | --- | --- | --- |
    | `game` | Game | `str` | `false` | `choices: ["Pokémon", "Magic: The Gathering", "Yu-Gi-Oh!", "Other"]` |
    | `set_name` | Set name | `str` | `false` | |

    Entry key order is `key`, `label`, `type`, `required`, then `choices` when present. `required` is a JSON boolean. The full seeded `tcg` list is:

    ```json
    [
      {"key": "grading", "label": "Grading (company and score)", "type": "str", "required": false},
      {"key": "card_condition", "label": "Card condition", "type": "str", "required": true, "choices": ["Mint", "Near Mint", "Played"]},
      {"key": "game", "label": "Game", "type": "str", "required": false, "choices": ["Pokémon", "Magic: The Gathering", "Yu-Gi-Oh!", "Other"]},
      {"key": "set_name", "label": "Set name", "type": "str", "required": false}
    ]
    ```

    The choice strings use the character `é` in `Pokémon` (U+00E9) and the exclamation mark in `Yu-Gi-Oh!`. No other TCG keys are added. `character`, `line`, `vaulted`, and set number stay forbidden.
19. Blank optional `game` and `set_name` are omitted from `metadata`, the same rule as blank `grading` (spec 03). A create or edit `POST` that omits them stores the same metadata as it did before this spec. An unknown `game` value on the form is a field error `Select a valid choice. <value> is not one of the available choices.` A present `set_name` is stored trimmed.
20. Create (`/listings/new?category=tcg`) and edit render the new inputs from `metadata_schema` with no hand-written TCG fields: `game` is a `<select>` with a leading blank option plus the four choices, and is not required; `set_name` is a text input and is not required. They appear after `grading` and `card_condition`. Funko and Lego forms do not render `game` or `set_name`. The detail page already iterates the schema; it shows `Game` and `Set name` in that order after card condition, with the stored string or `—` when the key is absent (spec 04 requirement 14).
21. **Game filter row.** When the resolved category slug is `tcg`, the browse page renders a second nav after `nav.filters` and before the search form:

    `<nav class="game-filters" aria-label="Games">`

    It is not inside `nav.filters`, and its class is not `filters`, so the category nav remains the first `<nav class="filters" ...>`. The links, in order, are `All games`, then each string in the `choices` list of the `tcg` schema entry whose `key` is `game`. The view reads those choices from the category row already loaded for the category nav. It does not hard-code the four names and does not add a query.

    | Link text | Href when `q` is blank |
    | --- | --- |
    | All games | `/?category=tcg` |
    | Pokémon | `/?category=tcg&game=Pok%C3%A9mon` |
    | Magic: The Gathering | `/?category=tcg&game=Magic%3A+The+Gathering` |
    | Yu-Gi-Oh! | `/?category=tcg&game=Yu-Gi-Oh%21` |
    | Other | `/?category=tcg&game=Other` |

    Hrefs are built with `urllib.parse.urlencode` in the order `category`, then `game` when present, then `q` when the normalized search is non-blank. `All games` omits `game`. The active link has `aria-current="page"` and is the only one in that nav that does. `All games` is active when `game` is absent, empty, or `all`.
22. **Applying `game`.** Allowed values are absent, `""`, `all`, and the choice strings exactly (case-sensitive, not trimmed). Any other value is `404`, on `/` and on every category, including a non-TCG category. A known choice filters only when the category is `tcg`: keep items whose `metadata["game"]` equals that string (`metadata__game`). Items with no `game` key appear under `All games` and under no specific game. When the category is not `tcg`, a known `game` value is ignored, the game nav is not rendered, and the category listing is unchanged. `game=all` and a blank `game` do not filter.
23. **Seed.** On insert of the `tcg` category, `python manage.py seed` writes the schema in requirement 18. `validate_metadata_schema` still runs before the insert. The six seed items are unchanged: they do not gain `game`, `set_name`, or a photo, and they stay valid because the new keys are optional. Seed still does not update an existing category row (spec 07 requirement 9), including a `tcg` row seeded before this spec. Funko and Lego schema JSON from spec 07 stay byte-for-byte the insert values. The success line is unchanged: `Seed complete: 3 categories, 2 users, 6 items, 1 match, 0 trades.`

### D — Listing photo

24. `Item` gains one optional field, not stored in `metadata`:

    | Field | Type | Constraints |
    | --- | --- | --- |
    | `photo` | `ImageField` | `upload_to="listings/"`, `blank=True`, not `null`. Empty value is `""`. |

    No new model and no new table. `trades/services.py` is not modified. Create still sets `status` only by the model default `AVAILABLE`. Edit still does not write `status`, `owner`, `category`, or `created_at`.
25. **Settings and files.** `requirements.txt` gains one line, `Pillow>=10`, and no other dependency. Settings gain `MEDIA_URL = "/media/"` and `MEDIA_ROOT = BASE_DIR / "media"`. The leading slash on `MEDIA_URL` is required so the detail URL `/listings/<id>` does not resolve a relative `media/` path under `/listings/`. `.gitignore` gains `media/`. Uploaded files are never committed. `config/urls.py` appends Django's media serving only inside `if settings.DEBUG`. When `DEBUG` is false, no media route is registered.
26. **Forms.** `ListingForm` gains an optional file field `photo` (`ImageField`, `required=False`) placed after `description` and before the metadata fields. The label is `Photo`. The widget is a file input with `accept="image/jpeg,image/png,image/webp"`. Create and edit `<form>` tags gain `enctype="multipart/form-data"` after the existing `action` attribute. The create tag stays `method="post" action="/listings/new"` and keeps `novalidate`. The edit tag stays `method="post" action="/listings/<id>/edit"` and keeps `novalidate`. A `POST` that includes no `photo` part is valid.
27. **Accepted files.** The server checks the upload; the `accept` attribute is only a hint. Size is the file's `size` in bytes. The limit is 5 × 1024 × 1024 bytes, inclusive. A larger file is rejected with the field error `Image must be 5 MB or smaller.` and is not opened for format. Otherwise Pillow's reported format must be `JPEG`, `PNG`, or `WEBP`. Anything else, including GIF, SVG, a non-image, and a corrupt file, is rejected with the field error `Upload a JPEG, PNG, or WebP image.` The filename extension is not the authority. These are field errors on `photo`. On any error the form re-renders with status `200`, no `Item` is created, an edit writes nothing, and no file is left under `MEDIA_ROOT`.
28. **Create.** A valid `POST` with a file stores it on the new `Item` and redirects to `/listings/<id>` as today. A valid `POST` without a file leaves `photo` blank.
29. **Edit.** Authorization is unchanged (spec 03 requirements 18–19 and 23): non-owner `403` `You can only edit your own listings.`; owner of an `IN_TRADE` or `TRADED` item `403` `This listing is in a trade and cannot be edited.`; anonymous redirects unchanged. A valid edit still runs the conditional update `WHERE id = <id> AND owner = <user> AND status = 'AVAILABLE'`. If the row count is 0, nothing is written, the response is that `403`, and the uploaded file is not stored. If the row count is 1, `title`, `description`, and `metadata` are updated. A new file in that same success path replaces `photo`. An empty file input leaves the stored photo as it was. There is no clear checkbox and no separate delete control. The edit page shows the current photo, when one exists, above the form using the same markup as requirement 30; the file input itself stays empty.
30. **Display.** On a browse card and as the first element of the detail content (before the `<h1>`):

    - photo set: `<img class="listing-photo" src="<item.photo.url>" alt="<item.title>">` with the title escaped
    - photo blank: the placeholder div from requirement 7

    `src` is the field's `.url` (under `/media/`). The detail page's other elements, badge, `Edit` link rule, and action area are unchanged. Seed sets no photo, so seeded cards and detail pages show the placeholder.

### Page order on `GET /`

31. The browse body order is: category `nav.filters`, then `nav.game-filters` only when category is `tcg`, then `form.search-form`, then `ul.listings` or the empty `<p>`. Superseded by specs/09-visual-polish.md.

### What this spec does not change

32. Like, match, and trade behavior, including every function in `trades/services.py` and the `Item.status` state machine.
33. Routes, button text, badge text, badge classes, empty-state strings in spec 04 (except the additional search empty string), `403` edit messages, and the class names `listing-card`, `filters`, `badge`, `match-row`, and `trade-row`.
34. The rule that a second seed does not rewrite an existing `metadata_schema`.

## Acceptance criteria

### A — Layout and photo area

- **Given** any page that extends the base layout, **when** it renders, **then** the head contains one viewport meta tag with `name="viewport"` and `content="width=device-width, initial-scale=1"`, the stylesheet href is the local `base.css` static file, and the body contains no `<script`.
- **Given** a browse card for an item with no photo, **when** `/` renders, **then** the card's first element is the placeholder div, the title link is still the first `<a>`, and the card still shows category name, badge, and owner display name, in that order, with no description and no metadata value.
- **Given** the stylesheet, **when** it is read, **then** it defines the one-, two-, and three-column breakpoints in requirement 3, horizontal scrolling for `.filters`, and no remote `url(http` or `url(https`.

### B — Search

- **Given** items titled `Amber Vase` and `Bronze Bowl`, **when** `GET /?q=amber`, **then** only `Amber Vase` is listed.
- **Given** an item whose title does not contain `demo` and whose description does, **when** `GET /?q=DEMO`, **then** that item is listed.
- **Given** a Funko item and a Lego item that both match `q`, **when** `GET /?q=demo&category=funko`, **then** only the Funko item is listed and the search form's hidden category value is `funko`.
- **Given** `GET /`, `GET /?q=`, and `GET /?q=%20%20`, **when** compared, **then** they list the same items.
- **Given** two matches with different `created_at`, **when** a `q` that matches both is submitted, **then** the newer item is first.
- **Given** a `q` of 101 characters whose first 100 match a title and the 101st would not, **when** the page renders, **then** the item is listed and the input value is those 100 characters.
- **Given** a non-blank `q` that matches nothing, **when** `/` renders, **then** the body contains `No listings match your search.` and does not contain `No listings yet.`
- **Given** `q=<script>alert(1)</script>`, **when** `/` renders, **then** the response body contains no `<script>alert` and the input value is escaped.
- **Given** no `q`, **when** `/` and `/?category=lego` render, **then** the category hrefs are `/`, `/?category=funko`, `/?category=lego`, and `/?category=tcg`, as in spec 04.

### C — TCG fields and game filter

- **Given** a fresh database, **when** seed runs, **then** the `tcg` `metadata_schema` deep-equals requirement 18, `funko` and `lego` deep-equal spec 07, and each of the six items still has the metadata in spec 07 requirements 14–15 with a blank photo.
- **Given** `GET /listings/new?category=tcg`, **when** the form renders, **then** it includes optional `game` (blank option plus the four choices) and optional `set_name` after `card_condition`, and a Funko form does not include either name.
- **Given** a TCG create with `card_condition=Mint` and blank `game` and `set_name`, **when** it is saved, **then** `metadata` is `{"card_condition": "Mint"}`.
- **Given** a TCG item with `game` `Pokémon` and `set_name` `Base`, **when** its detail page renders, **then** the Details rows include `Game` → `Pokémon` and `Set name` → `Base` after card condition.
- **Given** a TCG item with neither key, **when** its detail page renders, **then** `Game` and `Set name` are `—`.
- **Given** `GET /?category=tcg`, **when** the page renders, **then** the game nav shows the five links in requirement 21, only `All games` has `aria-current="page"`, and the category nav is still the four spec 04 links.
- **Given** two TCG items, one with `metadata.game` `Pokémon` and one with no `game` key, **when** `GET /?category=tcg&game=Pokémon`, **then** only the Pokémon item is listed and only that game link is current.
- **Given** `GET /?category=tcg&game=Pokemon` (no accent) or `GET /?game=Nope`, **then** the response is `404`.
- **Given** `GET /?category=funko&game=Pokémon`, **then** the response is `200`, the Funko listings are unfiltered by game, and the game nav is absent.

### D — Photo

- **Given** a logged-in user, **when** they create a listing with a small JPEG, PNG, or WebP, **then** the item's `photo` is set, `metadata` does not contain a photo key, the card and the detail page show an `img.listing-photo` whose `src` is that file's `/media/` URL, and `GET` of that URL returns the bytes while `DEBUG` is true.
- **Given** a create with no file, **when** it succeeds, **then** `photo` is blank and both pages show the placeholder div.
- **Given** a GIF or a text file renamed `.png`, **when** it is submitted, **then** the form shows `Upload a JPEG, PNG, or WebP image.` and no item is created.
- **Given** a JPEG larger than 5 × 1024 × 1024 bytes, **when** it is submitted, **then** the form shows `Image must be 5 MB or smaller.` and no item is created.
- **Given** the owner of an `AVAILABLE` item that already has a photo, **when** they save an edit without a new file, **then** the stored photo is unchanged; **when** they save with a new PNG, **then** `photo` points at the new file.
- **Given** the owner of an `IN_TRADE` item, **when** they `POST` an edit that includes a photo, **then** the response is `403` with `This listing is in a trade and cannot be edited.` and the stored photo is unchanged.
- **Given** seed has just run, **when** the six items are read, **then** every `photo` is blank.
- **Given** `config/urls.py`, **when** it is read, **then** media serving is inside `if settings.DEBUG`.

## Data and business rules

### Statements superseded

This spec supersedes only the following. Pointers in specs 00–07 read `Superseded by specs/08-enhancements.md` and do not rewrite those specs.

| Spec | Statement | What changes |
| --- | --- | --- |
| `00-overview.md` | MVP catalog sentence "Text only, no image upload." | A listing may have one optional uploaded photo. |
| `00-overview.md` | "These are the only metadata keys in the MVP." and the TCG rows of the metadata table | `tcg` also has optional `game` and `set_name`. |
| `00-overview.md` | Out of scope "Image upload …" | Listing photo upload is in scope. An image URL field is not. |
| `00-overview.md` | Out of scope "Search beyond filtering by category" | `q` search on `/` is in scope. Metadata search, owner filter, and other sorts stay out. |
| `00-overview.md` | Glossary **Item** field list | `photo` is added. |
| `00-architecture.md` | `Item` field table | `photo` is added. Status rules in that section stay. |
| `00-architecture.md` | "These are the only metadata keys in the MVP; do not add … any other key." and the TCG rows of the schema table | The two TCG entries in requirement 18 are allowed. Other new keys stay forbidden. |
| `00-architecture.md` | Seed bullet "metadata using only the keys above" | Seed metadata stays the spec 07 objects. The stored TCG schema also lists the two optional keys. |
| `03-listings.md` | Requirement 2 "No other entries and no other keys." and its TCG rows | The two entries in requirement 18. |
| `03-listings.md` | "There is no … image input" | The optional `photo` file input exists. There is still no status, owner, or wishlist input. |
| `03-listings.md` | "no new models or fields" and the `Item` field list in *Data and business rules* | `Item.photo` is added. No new model. |
| `03-listings.md` | Out of scope "Image upload or image URL" | Upload of one listing photo is in scope. An image URL field stays out. |
| `03-listings.md` | Acceptance criterion that TCG inputs are exactly `grading` and `card_condition`, and test case 15's exact field-name lists | See *Existing assertions this spec supersedes*. |
| `04-browse.md` | Requirement 9 "No search." | Requirement 10–17 of this spec. |
| `04-browse.md` | Requirement 6's card contents | The photo area is added in front. Description, metadata, `Edit`, and forms stay off the card. |
| `04-browse.md` | Requirement 21 "No new model, field, migration, or setting" | `Item.photo`, its migration, `MEDIA_URL`, and `MEDIA_ROOT`. |
| `04-browse.md` | Out of scope text search, and "Listing images or image URLs … thumbnails, placeholders" | `q` search, one photo, and the CSS placeholder. |
| `04-browse.md` | Out-of-scope brief bullet's "image upload" | Listing photos only. |
| `04-browse.md` | Test case 14's exact TCG detail rows when the category uses the seeded schema | Rows gain `Game` and `Set name`. |
| `07-seed-data.md` | Requirement 7's "No other entries and no other keys" and the `tcg` JSON block | Insert path uses requirement 18. |
| `07-seed-data.md` | "no new models or fields" and the `Item` field list | `photo` exists. Seed does not set it. |
| `07-seed-data.md` | Out of scope "Image upload" | The product accepts uploads. Seed still creates none. |
| `07-seed-data.md` | Must-have case 1 deep-equal of the `tcg` schema | The expected schema is requirement 18. |
| `01-user-registration.md`, `02-login-session.md`, `05-likes-matches.md`, `06-trades.md` | The words "image upload" inside the brief-level exclusion bullet | Listing photos only. |

Not superseded, and left unchanged on purpose:

- Spec 01 "Profile photos or collector bios".
- Specs 05 and 06 "no new models or fields" for `Like`, `Match`, and `Trade`.
- Spec 07 requirement 9: an existing category row is not updated on re-seed.
- Spec 04 category `404`, badge markup, owner email privacy, and "no description on the card".
- Every trade, like, and match rule.

### Other rules

- **Search** is a bound ORM filter on the existing browse queryset. `GET /` stays two queries (categories, then items) when `q` is present or absent. The game choices are taken from that category list in Python.
- **`game` 404** uses the same `Http404` style as an unknown category. No custom body is required.
- **Photo storage** uses Django's default file storage under `MEDIA_ROOT`. Replacing a photo does not delete the previous file from disk.
- **Tests** that upload set `MEDIA_ROOT` to a temporary directory and remove it afterwards. They do not write the repository `media/` directory. Image bytes are built in memory with Pillow. No image fixture is committed.
- **Validator** behavior for the new keys is the existing optional-`str` and `choices` behavior. Spec 03 validator cases that construct their own schema literals stay valid without edits.

## Out of scope

- Profile photos, galleries, more than one photo per listing, cropping, drag-and-drop, client-side compression, and a control that clears `photo`
- Deleting a replaced file from disk
- An image URL field (plan Phase 5) instead of upload
- Serving media when `DEBUG` is false, cloud storage, and a production web server
- Search of metadata, owner, or status; search on any route other than `GET /`; pagination; radius or map search
- A game filter on Funko or Lego, a new category, or any metadata key other than `game` and `set_name`
- Rewriting a category schema that seed already stored
- JavaScript, CDN assets, and any dependency other than Pillow
- Changes to `trades/services.py`, likes, matches, trade routes, or `Item.status` transitions
- Wishlist, payments, shipping, chat, OAuth, email verification, sports, Neo4j, brokers, native mobile
- Admin customization for the new field

## Test cases

Tests use Django's test runner and `django.test.TestCase` only. No pytest. One behavior per test. Each docstring starts with `Spec 08 case N:`. Image tests use a temporary `MEDIA_ROOT`. Helpers are plain functions.

**Must-have — A** (`catalog/tests/test_responsive.py`)

1. **Viewport.** `GET /` HTML contains exactly one `name="viewport"` meta tag with `content="width=device-width, initial-scale=1"`.
2. **Placeholder and card order.** A card with no photo starts with `listing-photo listing-photo-placeholder`, contains no `<img`, and still orders the title link, category name, badge, and display name as spec 04 case 5. Description and metadata stay absent.
3. **CSS contract.** `static/css/base.css` contains the three breakpoints from requirement 3, `overflow-x: auto` on the filter chips, and `min-height: 44px`. The file contains no `url(http` and no `url(https`. `GET /` contains no `<script`.

**Must-have — B** (`catalog/tests/test_search.py`)

4. **Title match is case-insensitive.** `q=amber` lists `Amber Vase` and not an unrelated title.
5. **Description match.** `q` matches a description when the title does not contain it.
6. **Combined with category.** `q` plus `category=funko` returns only matching Funko items. The form includes `name="q"`, a submit button whose text is `Search`, and `name="category" value="funko"`.
7. **Blank `q`.** Missing, empty, and whitespace-only `q` return the same titles as `GET /`.
8. **Newest first.** Two matches are ordered by `created_at` descending, then larger `id`.
9. **Max 100.** A 101-character `q` is applied and redisplayed as the first 100 characters.
10. **Empty copy.** A non-blank `q` with no matches renders `No listings match your search.` and not `No listings yet.` With a blank `q` and no items, `No listings yet.` is still the text.
11. **Escaping.** `q` value `<script>alert(1)</script>` produces no raw `<script>alert` in the body. A matching title of `<script>alert(1)</script>` is escaped in the card.
12. **Substring, not a wider match.** `q` equal to `' OR 1=1 --` does not list an item whose title and description lack that substring.
13. **Stable category hrefs.** With no `q`, category hrefs equal spec 04. With `q=ada`, the Funko href contains `category=funko` and `q=ada`.

**Must-have — C** (`catalog/tests/test_tcg_game.py`, plus the seed assertion named below)

14. **Seeded schema.** After seed, `tcg.metadata_schema` deep-equals requirement 18, including choice order. Funko and Lego schemas are unchanged from spec 07. `validate_metadata_schema` raises nothing. Seed item metadata is unchanged and contains neither `game` nor `set_name`.
15. **Create and edit render the fields.** TCG step 2 shows optional `game` and `set_name` after `card_condition`, with the four game options in order after a blank option. The edit form of a TCG item that lacks both keys shows them empty. A Funko form's HTML does not contain `name="game"` or `name="set_name"`.
16. **Blank omitted, choice enforced.** A TCG create with blank `game` and `set_name` omits both keys. `game=Good` re-renders with `Select a valid choice. Good is not one of the available choices.` and creates no item. `game=Pokémon` and `set_name=Base` are stored.
17. **Detail rows.** Absent keys render `Game` / `—` and `Set name` / `—` after card condition. Present values render the stored strings.
18. **Game nav.** `GET /?category=tcg` shows the five links and hrefs from requirement 21. Only `All games` is current. The first `nav.filters` still has four links.
19. **Game filter.** `game=Pokémon` lists only TCG items whose `metadata["game"]` is `Pokémon`. An item with no `game` key is absent there and present for `All games`. `GET /` query count for six items stays the two queries asserted by spec 04 case 11.
20. **Unknown game.** `game=Pokemon`, `game=Nope`, and `/?category=funko&game=Nope` return `404`.
21. **Known game off TCG.** `/?category=funko&game=Pokémon` returns `200`, shows the Funko items, and has no `game-filters` nav.

**Must-have — D** (`catalog/tests/test_photo.py`)

22. **JPEG, PNG, and WebP.** Each format creates an item, sets `photo`, leaves `metadata` without a photo key, and renders `img.listing-photo` with that `src` on `/` and on the detail page. `GET` of the `src` returns `200` and the same bytes.
23. **No file.** Create without `photo` leaves the field blank and renders the placeholder div on the card and the detail page, with no `img.listing-photo`.
24. **Rejected files.** A GIF, and a text payload whose name ends in `.png`, each show `Upload a JPEG, PNG, or WebP image.` and create no item. A JPEG of `5 * 1024 * 1024 + 1` bytes shows `Image must be 5 MB or smaller.` and creates no item. `MEDIA_ROOT` has no leftover file after the rejected post.
25. **Edit while `AVAILABLE`.** Saving with no new file keeps the previous photo name. Saving with a new PNG changes `photo` and does not change `status`, `owner`, `category`, or `created_at`.
26. **Edit refused.** Owner `POST` of an `IN_TRADE` item with a photo returns `403` and `This listing is in a trade and cannot be edited.`, and the stored photo is unchanged. A non-owner's `POST` with a photo returns `403` and `You can only edit your own listings.`
27. **Invalid edit stores nothing.** A valid file plus `box_condition=11` leaves the item, including `photo`, unchanged.
28. **Seed photos.** After seed, all six items have a blank `photo`.
29. **DEBUG guard.** The source of `config/urls.py` places the `static(` media call inside `if settings.DEBUG`.

**Nice-to-have**

30. A JPEG of exactly 5 × 1024 × 1024 bytes is accepted.
31. Replacing a photo leaves the previous file on disk.
32. At 320px, 640px, and 961px the column counts are 1, 2, and 3 and the document does not scroll horizontally. Header controls are at least 44px. This is a browser check; the test client cannot measure layout.
33. `game=all` and `game=` on `category=tcg` match `All games` and list every TCG item.
34. Search form preserves an active `game` hidden input.

### Existing assertions this spec supersedes

Update these existing tests when the feature that supersedes them lands, and nowhere else. Do not weaken the assertions that remain. If any other existing test fails, fix the implementation so the old assertion and this spec both hold.

- **Feature C, `catalog/tests/test_seed.py`.** The local `TCG_SCHEMA` used by spec 07 case 1 (and the idempotency compare that reuses it) gains `game` then `set_name` as in requirement 18. Expected item metadata, counts, passwords, and the "no `grading` on Ben's TCG item" assertion stay.
- **Feature C, `catalog/tests/test_create_listing.py`.** `test_tcg_step_two_renders_optional_grading_and_condition_choices` field names become `category`, `title`, `description`, `grading`, `card_condition`, `game`, `set_name`. Widget checks for `grading` and `card_condition` stay. Funko and Lego field-name lists are not given `game` or `set_name`.
- **Feature C, `catalog/tests/test_detail.py`.** `test_absent_grading_renders_as_an_em_dash` expected rows become grading `—`, card condition `Mint`, `Game` `—`, `Set name` `—`. `test_present_grading_renders_the_grade` checks only the first row and stays as written while `grading` remains the first TCG entry.
- **Feature D, `catalog/tests/test_create_listing.py`.** The Funko, Lego, and TCG step-2 field-name lists each gain `photo` immediately after `description`. The create form tag keeps `method="post" action="/listings/new"` so the existing form regex still matches; `enctype` is added after `action`.

`catalog/tests/test_validators.py` keeps its private schema literals. Do not edit it to match the seeded TCG schema.

## Open questions

All decided; recorded here for traceability. Each choice is the smallest one that meets the change request.

1. **Column edges.** Decided: ≤639px one column, 640–960px two, ≥961px three (requirement 3).
2. **Photo markup before the field exists.** Decided: feature A renders only the placeholder div and does not read `item.photo`. Feature D adds the `img` branch (requirements 7 and 30).
3. **Placeholder contents.** Decided: no text, `--neutral-bg`, aspect ratio 4/3.
4. **Image `alt`.** Decided: the item title.
5. **Tap targets.** Decided: 44px minimum at widths ≤960px for the brand, header links, `Logout`, and filter chips (requirements 4–5).
6. **Search overflow.** Decided: trim, then keep the first 100 characters. No error (requirement 11).
7. **Empty-copy priority.** Decided: a non-blank `q` with no rows always shows `No listings match your search.`, including when a category or game is selected (requirement 16).
8. **Where the new TCG keys sit.** Decided: after `card_condition` (requirement 18).
9. **Where game names come from.** Decided: the `tcg` schema `choices`, not a hard-coded view list (requirement 21).
10. **Unknown versus inapplicable `game`.** Decided: a value outside the choices is `404` everywhere. A known choice is applied only when `category=tcg`; otherwise it is ignored (requirement 22).
11. **Game nav markup.** Decided: a following `nav.game-filters`, not extra links inside `nav.filters` (requirement 21).
12. **Seed on a database that already has `tcg`.** Decided: do not update the stored schema (requirement 23, spec 07 requirement 9).
13. **`photo` null.** Decided: `blank=True` and not `null` (requirement 24).
14. **File rules.** Decided: Pillow format `JPEG` / `PNG` / `WEBP`; size checked first; limit 5 × 1024 × 1024 inclusive; the two messages in requirement 27.
15. **Form placement.** Decided: `photo` after `description` and before metadata fields. Label `Photo`. No help text (requirement 26).
16. **Clearing a photo.** Decided: an empty file input keeps the current file. No clear control. Replaced files stay on disk (requirement 29).
17. **`MEDIA_URL`.** Decided: `"/media/"` with a leading slash, `MEDIA_ROOT = BASE_DIR / "media"` (requirement 25).
18. **Category links while searching.** Decided: they gain `q` only when `q` is non-blank, and they never carry `game` (requirement 15).

## Assumptions to confirm

1. Column breakpoints are ≤639px / 640–960px / ≥961px. Yes if that matches "below 640, two up to 960, three above".
2. The placeholder is an empty div with no "No photo" text.
3. A `q` longer than 100 characters is truncated, not rejected.
4. `No listings match your search.` replaces the category empty sentence whenever `q` is non-blank and nothing matches.
5. `game` and `set_name` are appended after `card_condition`, and both are optional.
6. An unknown `game` is `404` on every category. A known `game` is ignored unless `category=tcg`.
7. Re-running seed does not rewrite a `tcg` schema that is already stored.
8. Edit with no new file keeps the photo. There is no clear control.
9. The file input sits after Description and before the metadata fields. Its label is `Photo`.
10. The size limit is 5 × 1024 × 1024 bytes, and an oversize file gets the size message even if it is also the wrong format.
11. `MEDIA_URL` is `/media/` (leading slash), not the relative string `media/`.
12. The game links live in a separate `nav.game-filters`, and category hrefs are unchanged when `q` is blank.
