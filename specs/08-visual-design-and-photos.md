# Spec: Visual design and photos

**Status:** Approved

## Purpose

This change request makes listings easier to scan: one optional photo per listing, an original category illustration when that photo is absent, and a lighter visual design (page gradient, equal-height cards, wrapping text) that does not change routes, copy, or trade behavior. It exists so the demo shows the item, not only its title, including on the six seeded listings, which stay photo-less.

Stack per [00-architecture.md](00-architecture.md): Django, server-rendered templates, SQLite, no JavaScript framework, no CDN, no web fonts. Browse stays public. Create and edit stay login-gated and `AVAILABLE`-only, per [03-listings.md](03-listings.md). `Item.status` and `Trade.status` still change only in `trades/services.py`.

[08-enhancements.md](08-enhancements.md) is already approved. It added `Item.photo`, media settings, search, TCG `game` / `set_name`, and the phone layout. This spec does not replace that file. Where the two disagree on the display rules named under *Statements superseded*, this spec wins once approved. Search, the TCG schema, the photo storage contract, and the breakpoint rules in 08-enhancements stay in force. `docs/plan.md` is not edited. Plan section 2 ("No image upload in MVP") and plan section 7 (text listings, cut 1 image URLs) were already set aside by 08-enhancements; this spec does not widen that exception past one listing photo and four static SVG illustrations.

## User stories

- As an anonymous visitor, I want each card and detail page to show the listing photo, or a clear picture for its category, so that I can tell a card, a brick, and a figure apart without reading every title.
- As an anonymous visitor, I want a broken or missing image to leave a visible placeholder, so that the page still has a picture when a file fails to load.
- As a listing owner, I want to attach one optional photo when I create or edit an `AVAILABLE` listing, and a clear error when the file is the wrong type or too large, so that I know what to upload instead.
- As an anonymous visitor on a phone, I want the same pages to stay on one screen width, with readable text on a soft background, so that the livelier layout does not hide the words.

## Functional requirements

### A — Listing photo (keep the approved contract)

1. `Item.photo` is the one optional image. It is not a key in `metadata`.

   | Field | Type | Constraints |
   | --- | --- | --- |
   | `photo` | `ImageField` | `upload_to="listings/"`, `blank=True`, not `null`. Empty value is `""`. |

   No new model. Create still sets `status` only by the model default `AVAILABLE`. Edit still does not write `status`, `owner`, `category`, or `created_at`. The migration that adds this field is `catalog/migrations/0002_item_photo.py`. Do not add a second migration, and do not edit or delete that file or any earlier migration. Do not rewrite existing rows.

2. **Settings and files.** `requirements.txt` lists `Pillow>=10` and no other image library. If that line is already present, do not add a second copy. Settings keep `MEDIA_URL = "/media/"` (leading slash required) and `MEDIA_ROOT = BASE_DIR / "media"`. `.gitignore` keeps `media/`. Uploaded files are never committed. `config/urls.py` registers Django media serving only inside `if settings.DEBUG`. When `DEBUG` is false, that route is absent.

3. **`STATIC_URL`.** Set `STATIC_URL = "/static/"` (leading slash). `{% static %}` must render a root-relative URL so an illustration on `/listings/<id>` is not requested under `/listings/static/`. Do not add a CDN or a second stylesheet.

4. **Forms.** `ListingForm` keeps an optional file field `photo` (`required=False`) after `description` and before the metadata fields. Label `Photo`. The widget is a file input with `accept="image/jpeg,image/png,image/webp"`. Create and edit forms keep `enctype="multipart/form-data"`. The create tag stays `method="post" action="/listings/new"` and keeps `novalidate`. The edit tag stays `method="post" action="/listings/<id>/edit"` and keeps `novalidate`. A `POST` with no `photo` part is valid.

5. **Accepted files.** The server checks the upload. `accept` is only a hint. Size is the file's `size` in bytes. The limit is 5 × 1024 × 1024 bytes, inclusive. A larger file is rejected with the field error `Image must be 5 MB or smaller.` and is not opened for format. Otherwise Pillow's reported format must be `JPEG`, `PNG`, or `WEBP`. Anything else, including GIF, an uploaded SVG, a non-image, and a corrupt file, is rejected with the field error `Upload a JPEG, PNG, or WebP image.` The filename extension is not the authority. These are field errors on `photo`. On any error the form re-renders with status `200`, no `Item` is created, an edit writes nothing, and no file is left under `MEDIA_ROOT`.

6. **Create.** A valid `POST` with a file stores it on the new `Item` and redirects to `/listings/<id>`. A valid `POST` without a file leaves `photo` blank.

7. **Edit.** Authorization is unchanged (spec 03 requirements 18–19 and 23): non-owner `403` `You can only edit your own listings.`; owner of an `IN_TRADE` or `TRADED` item `403` `This listing is in a trade and cannot be edited.`; anonymous redirects unchanged. A valid edit still runs the conditional update `WHERE id = <id> AND owner = <user> AND status = 'AVAILABLE'`. If the row count is 0, nothing is written, the response is that `403`, and the uploaded file is not stored. If the row count is 1, `title`, `description`, and `metadata` are updated. A new file on that success path replaces `photo`. An empty file input leaves the stored photo as it was. There is no clear checkbox and no separate delete control. The previous file stays on disk. The edit page shows the current picture above the form using requirement 10. The file input itself stays empty.

### B — Category illustrations

8. **Static files.** Four original SVGs, drawn for this app, flat, no brand logos, no characters, no downloaded or copied artwork. Each file is XML SVG with `viewBox="0 0 160 120"`, contains no `<script`, no `<image`, and no `http` URL.

   | File | Shown for slug | Drawing |
   | --- | --- | --- |
   | `static/img/placeholders/tcg.svg` | `tcg` | A trading card: a rounded rectangle, a smaller inner rectangle, and two plain bars. |
   | `static/img/placeholders/lego.svg` | `lego` | A brick with round studs. No wordmark. |
   | `static/img/placeholders/funko.svg` | `funko` | A figure silhouette: round head, rectangular body, two legs. No face and no character. |
   | `static/img/placeholders/generic.svg` | any other slug, and the CSS fallback | A simple framed picture: a rectangle, a circle, and a triangle. |

   Fills use only `#f6f1e6`, `#fffdf9`, `#e5f3f2`, `#0f6e6b`, `#0b5552`, and `#1c1917`.

9. **Which file.** The template chooses by `item.category.slug`, compared exactly (case-sensitive) to `funko`, `lego`, or `tcg`. Any other slug, including a slug that does not exist in seed data, uses `generic.svg`. Seed is not changed. Spec 07 still forbids updating existing rows, so every current and seeded listing has a blank `photo` and therefore shows its category illustration with no data migration.

10. **Markup.** One include, `catalog/templates/catalog/_listing_photo.html`, is used by the browse card, the detail page (first element inside the content block, before the `<h1>`), and the edit page (the preview above the form). It loads `static`.

    Photo set:

    ```html
    <img class="listing-photo" src="<item.photo.url>" alt="<item.title> (<category name>)">
    ```

    Photo blank:

    ```html
    <img class="listing-photo listing-photo-placeholder" src="/static/img/placeholders/<file>.svg" alt="<item.title> (<category name>)">
    ```

    `<file>` is the name from requirement 8. `src` for a blank photo is the `{% static %}` URL of that file, which requirement 3 makes `/static/img/placeholders/<file>.svg`. Alt text is exactly the title, then a space, then the category `name` in parentheses. Example: `Visible Title (Funko Pop & Figures)`. Django auto-escaping applies to the title, the category name, and the URL. No `|safe`. The image is not wrapped in a link, so on a card the title `<a href="/listings/<id>">` stays the first anchor.

    The browse card's `li` class stays `listing-card`. After the image, the card still shows, in this order, the title link, the category name, the status badge, and the owner `display_name`. It still omits `description`, metadata, `Edit`, and every `<form>`. The detail page's other elements, badge, `Edit` link rule, and action area are unchanged. The Matches page does not gain images.

11. **CSS fallback without JavaScript.** `.listing-photo` keeps a fixed box: `width: 100%`, `aspect-ratio: 4 / 3`, `object-fit: cover`, `object-position: center`, and the existing rounded corners (`border-radius`). It also sets `background-color: #e5f3f2` and `background-image: url("../img/placeholders/generic.svg")` with `background-size: cover` and `background-position: center`. That URL is relative to `static/css/base.css`. It is not `url(http...)` or `url(https...)`. A loaded photo or illustration covers this background. A broken or missing `src` still shows the generic illustration behind the image box. No script handles the error.

### C — Visual design

12. **Page background.** `body` uses a gradient and no remote image:

    `linear-gradient(160deg, #f6f1e6 0%, #e5f3f2 52%, #f2faf6 100%)`

    Warm cream, then pale teal, then very light mint. Text color stays `#1c1917` (`--ink`). Cards stay on `--surface` (`#fffdf9`). The header keeps its current surface fill so the brand and links stay on a solid light bar. Do not change brand text `Easy Exchange`, nav labels, or button labels.

13. **Cards.** `.listings` stays a grid with `align-items: stretch`. `.listing-card` has `height: 100%` so cards in one row share a height. The card keeps a border, a soft shadow, and a hover transition on border, shadow, and a small lift. Long titles and category names wrap (`overflow-wrap: anywhere` on the card). Status badge markup stays `<span class="badge badge-available">AVAILABLE</span>`, `badge badge-in_trade` / `IN_TRADE`, and `badge badge-traded` / `TRADED`. Colors stay distinguishable: AVAILABLE green (`--available-bg` / `--available-fg`), IN_TRADE amber (`--pending-bg` / `--pending-fg`), TRADED gray (`--neutral-bg` / `--neutral-fg`).

14. **Responsive rules already in 08-enhancements stay.** Do not add a second viewport tag. The one tag remains `<meta name="viewport" content="width=device-width, initial-scale=1">`. Columns stay: `repeat(3, minmax(0, 1fr))` by default, `repeat(2, minmax(0, 1fr))` inside `@media (max-width: 960px)`, and `minmax(0, 1fr)` inside `@media (max-width: 639px)`. That is one column below 640px, two through 960px, and three above 960px. Header links and the `Logout` button keep a 44px minimum tap size at widths ≤ 960px. `.filters` and `.game-filters` stay one non-wrapping row with `overflow-x: auto`. At widths ≤ 639px, login, register, create, edit, and the search form stay a single column at `max-width: 100%`, and `.match-row`, `.trade-row`, and `.details` stay one column. The page does not require horizontal scrolling at 320px. No `<script>` is added. The stylesheet contains no `url(http` and no `url(https`.

15. **Motion.** `@media (prefers-reduced-motion: reduce)` sets `transition: none` on `.listing-card` and `transform: none` on `.listing-card:hover`. Do not add a new animation.

## Acceptance criteria

- **Given** a logged-in user, **when** they create a listing with a small JPEG, PNG, or WebP, **then** `photo` is set, `metadata` has no photo key, the card and the detail page each show `<img class="listing-photo" src="<photo url>" alt="<title> (<category name>)">`, and `GET` of that `src` returns the bytes while `DEBUG` is true.
- **Given** a create with no file in category `funko`, **when** it succeeds, **then** `photo` is blank and both the card and the detail page show `<img class="listing-photo listing-photo-placeholder" ... src="/static/img/placeholders/funko.svg" alt="<title> (Funko Pop & Figures)">`, and the title link is still the first `<a>` in the card.
- **Given** a listing whose category slug is not `funko`, `lego`, or `tcg` and whose `photo` is blank, **when** the card renders, **then** the image `src` is `/static/img/placeholders/generic.svg`.
- **Given** a GIF, an uploaded SVG, or a text file renamed `.png`, **when** it is submitted, **then** the form shows `Upload a JPEG, PNG, or WebP image.` and no item is created.
- **Given** a JPEG larger than 5 × 1024 × 1024 bytes, **when** it is submitted, **then** the form shows `Image must be 5 MB or smaller.` and no item is created.
- **Given** the owner of an `AVAILABLE` item that already has a photo, **when** they save an edit without a new file, **then** the stored photo is unchanged; **when** they save with a new PNG, **then** `photo` points at the new file and the card alt is `<new title> (<category name>)`.
- **Given** the owner of an `IN_TRADE` item, **when** they `POST` an edit that includes a photo, **then** the response is `403` with `This listing is in a trade and cannot be edited.` and the stored photo is unchanged.
- **Given** seed has just run, **when** the six items are read, **then** every `photo` is blank, and `/` shows `funko.svg` for the Funko listings, `lego.svg` for the Lego listings, and `tcg.svg` for the Trading Card Games listings.
- **Given** `static/css/base.css`, **when** it is read, **then** it contains the gradient colors `#f6f1e6`, `#e5f3f2`, and `#f2faf6`, `url("../img/placeholders/generic.svg")`, `aspect-ratio: 4 / 3`, `object-fit: cover`, the three column breakpoints from requirement 14, and `@media (prefers-reduced-motion: reduce)`, and it contains no `url(http` and no `url(https`.
- **Given** `config/urls.py`, **when** it is read, **then** media serving is inside `if settings.DEBUG`.
- **Given** any page that extends the base layout, **when** it renders, **then** the head contains exactly one viewport meta tag with that content, and the body contains no `<script`.

## Data and business rules

### Statements superseded

This spec supersedes only the following. Pointers added in specs 00–07 read `Superseded by specs/08-visual-design-and-photos.md` and do not rewrite those specs. Pointers that already say `Superseded by specs/08-enhancements.md` stay.

| Spec | Statement | What changes |
| --- | --- | --- |
| `00-overview.md` | MVP catalog sentence "Text only, no image upload." | A listing may have one optional uploaded photo. A blank photo shows a category illustration. |
| `00-overview.md` | Out of scope "Image upload …" | That one listing photo, plus the four static SVGs. An image URL field is not added. |
| `00-overview.md` | Glossary **Item** field list | `photo` is the only added field. |
| `00-architecture.md` | `Item` field list | `photo` is the only added field. Status rules in that section stay. |
| `03-listings.md` | "There is no … image input" | The optional `photo` file input exists. There is still no status, owner, or wishlist input. |
| `03-listings.md` | "no new models or fields" and the `Item` field list | `Item.photo` exists. No new model and no further field. |
| `03-listings.md` | Out of scope "Image upload or image URL" | Upload of one listing photo is in scope. An image URL field stays out. |
| `04-browse.md` | Requirement 6 card order (title first) | The picture is first. Title, category, badge, and owner follow. Description, metadata, `Edit`, and forms stay off the card. |
| `04-browse.md` | Requirement 12 detail order (title first) | The picture is the first content element, before the title. The rest of the order stays. |
| `04-browse.md` | Out of scope "Listing images or image URLs … thumbnails, placeholders." | One photo and the category SVG placeholders. |
| `04-browse.md` | Out-of-scope brief bullet's "image upload" | Listing photos only. |
| `07-seed-data.md` | "no new models or fields" and the `Item` field list | `photo` exists. Seed does not set it and does not update existing rows. |
| `07-seed-data.md` | Out of scope "Image upload" | The product accepts uploads. Seed still creates none. |
| `01-user-registration.md`, `02-login-session.md`, `05-likes-matches.md`, `06-trades.md` | The words "image upload" inside the brief-level exclusion bullet | Listing photos only. |
| `08-enhancements.md` | Requirement 7 (empty placeholder div, no photo attribute) and requirement 30 (alt is the title only; a blank photo is that div) | Requirements 8–11 of this spec. |
| `08-enhancements.md` | Acceptance bullets that a blank photo renders the placeholder div, and test cases 2 and 23 (`assertNotIn("<img"`) | The illustration `<img>` in requirement 10. |
| `08-enhancements.md` | Open questions 3 and 4 (empty div, alt is the title) | Alt is `<title> (<category name>)`. The blank-photo element is the illustration image. |
| `08-enhancements.md` | Test case 22's exact `alt="<title>"` | Alt gains ` (<category name>)`. The `src`, the bytes, and the metadata assertion stay. |

Not superseded, and left unchanged on purpose:

- Spec 01 "Profile photos or collector bios".
- Specs 05 and 06 "no new models or fields" for `Like`, `Match`, and `Trade`.
- Spec 04 requirement 9 and the search behavior in 08-enhancements.
- Spec 04 badge class names and badge text.
- Spec 07 requirement 9: an existing category or item row is not updated on re-seed.
- The TCG `game` and `set_name` schema in 08-enhancements.
- 08-enhancements requirements 1–6 and 24–29 (viewport, breakpoints, tap targets, photo field, validation messages, media settings), except the display markup those requirements point at requirement 30 for.
- Every trade, like, and match rule.

### Other rules

- **Photo storage** uses Django's default file storage under `MEDIA_ROOT`. Replacing a photo does not delete the previous file from disk.
- **Tests** that upload set `MEDIA_ROOT` to a temporary directory and remove it afterwards. They do not write the repository `media/` directory. Image bytes are built in memory with Pillow. No image fixture is committed. The four SVGs are the only image files added to the repo.
- **Illustrations** are static files. They are not `ImageField` values and they are not valid uploads (requirement 5 still rejects an uploaded SVG).

## Out of scope

- Profile photos, galleries, more than one photo per listing, cropping, drag-and-drop, client-side compression, and a control that clears `photo`
- Deleting a replaced file from disk
- An image URL field instead of upload
- Serving media when `DEBUG` is false, cloud storage, and a production web server
- Images on the Matches page, like controls, or trade rows
- Changing seed rows, seed copy, or `catalog/management/commands/seed.py`
- A second `photo` migration or any edit to an existing migration
- Search, TCG `game` / `set_name`, or any new metadata key
- JavaScript, CDN assets, downloaded images, brand logos, character art, and any dependency other than Pillow
- Changes to `trades/services.py`, likes, matches, trade routes, authentication, or `Item.status` transitions
- Wishlist, payments, shipping, chat, OAuth, email verification, sports, Neo4j, brokers, native mobile
- Rewriting specs 00–07 beyond the pointer phrase, or editing `docs/plan.md`

## Test cases

Tests use Django's built-in runner and `django.test.TestCase` only. No pytest. One behavior per test. New docstrings start with `Visual spec case N:`. Image uploads use a temporary `MEDIA_ROOT`. Helpers stay plain functions. Do not weaken an assertion that this spec does not name below.

**Must-have** (`catalog/tests/test_photo.py` unless noted)

1. **JPEG, PNG, and WebP.** Each format creates an item, sets `photo`, leaves `metadata` without a photo key, and renders `img.listing-photo` on `/` and on the detail page with that file's `src` and alt `<title> (<category name>)`. `GET` of the `src` returns `200` and the same bytes. This is the existing `test_jpeg_png_and_webp_are_stored_and_shown`, updated only for alt text.
2. **No file, category illustration.** Create without `photo` leaves the field blank. The card and the detail page contain `img.listing-photo.listing-photo-placeholder` whose `src` is `/static/img/placeholders/funko.svg` and whose alt is `Photo Funko (Funko Pop & Figures)`. The card's first `<a>` is still the title link. This updates `test_create_without_a_file_shows_the_placeholder`: the `assertNotIn("<img"` line is replaced by these image assertions.
3. **Rejected files.** A GIF, an SVG upload, and a text payload whose name ends in `.png` each show `Upload a JPEG, PNG, or WebP image.` and create no item. A JPEG of `5 * 1024 * 1024 + 1` bytes shows `Image must be 5 MB or smaller.` and creates no item. `MEDIA_ROOT` has no leftover file after the rejected post. The existing GIF and fake-PNG assertions stay; add the SVG upload to that test.
4. **Edit while `AVAILABLE`.** Saving with no new file keeps the previous photo name. Saving with a new PNG changes `photo` and does not change `status`, `owner`, `category`, or `created_at`. Existing test stays.
5. **Edit refused when not `AVAILABLE`.** Owner `POST` of an `IN_TRADE` item with a photo returns `403` and `This listing is in a trade and cannot be edited.`, and the stored photo is unchanged. A non-owner's `POST` with a photo returns `403` and `You can only edit your own listings.` Existing test stays.
6. **Unknown slug.** A blank-photo item whose category slug is `other` renders `src="/static/img/placeholders/generic.svg"` on `/` and on the detail page.
7. **Seed photos.** After seed, all six items have a blank `photo`, and the browse HTML contains `/static/img/placeholders/funko.svg`, `lego.svg`, and `tcg.svg`. The existing blank-photo assertion stays.
8. **Alt text on a seeded card.** A seeded Funko card's illustration alt is `<that item's title> (Funko Pop & Figures)`.
9. **DEBUG guard.** The source of `config/urls.py` places media serving inside `if settings.DEBUG`. Existing test stays.
10. **Illustration files and CSS** (`catalog/tests/test_responsive.py`). The four SVG paths exist, each file contains `<svg` and does not contain `<script` or `http`. `base.css` contains the three gradient hex colors, `url("../img/placeholders/generic.svg")`, `aspect-ratio: 4 / 3`, `object-fit: cover`, and `prefers-reduced-motion`. It still contains no `url(http` and no `url(https`. The existing breakpoint assertions stay.
11. **Card order** (`catalog/tests/test_responsive.py`, `test_card_without_a_photo_starts_with_the_placeholder`). The card's first element is the Funko illustration `img`, not the empty div. Alt is `Visible Title (Funko Pop & Figures)`. The title link still precedes the category name, the badge, and `Ada`. Description and the serial stay absent. Remove `startswith` of the empty div and `assertNotIn("<img"`.

**Nice-to-have**

12. A JPEG of exactly 5 × 1024 × 1024 bytes is accepted.
13. Replacing a photo leaves the previous file on disk.
14. At 320px, 640px, and 961px the column counts are 1, 2, and 3, text contrast on the gradient meets WCAG AA, and the document does not scroll horizontally. This is a browser check. The test client cannot measure layout.
15. The edit page of a photo-less Funko listing shows the same `funko.svg` image as the detail page.

### Existing assertions this spec supersedes

Update only these. Do not edit `catalog/tests/test_browse.py` or `catalog/tests/test_detail.py` for the new image: their order and badge assertions still hold with the image placed in front.

- `catalog/tests/test_photo.py` `test_jpeg_png_and_webp_are_stored_and_shown`: alt `"{fmt} Funko"` becomes `"{fmt} Funko (Funko Pop & Figures)"`.
- `catalog/tests/test_photo.py` `test_create_without_a_file_shows_the_placeholder`: drop `assertNotIn("<img"`. Assert the Funko illustration `img`, its `src`, and its alt, as in must-have case 2.
- `catalog/tests/test_photo.py` `test_rejected_files_are_not_stored`: also reject an SVG upload with `Upload a JPEG, PNG, or WebP image.` The GIF, fake PNG, and oversize JPEG assertions stay.
- `catalog/tests/test_photo.py` `test_seed_creates_no_photos`: keep the blank-photo assertion and also assert the three illustration URLs on `/`.
- `catalog/tests/test_responsive.py` `test_card_without_a_photo_starts_with_the_placeholder`: replace the empty-div start and the ban on `<img` with must-have case 11. Keep the order and the hidden-text assertions.

`test_stylesheet_defines_breakpoints_without_a_remote_url` is not weakened. A relative `url("../img/placeholders/generic.svg")` still satisfies its `url(http` / `url(https` bans.

## Open questions

All decided. Each choice is the smallest one that meets the change request.

1. **Relationship to 08-enhancements.** Decided: this file does not replace it. Display rules in the table above change. Storage, search, and TCG stay (Purpose, *Statements superseded*).
2. **Task numbers.** Decided: `docs/tasks.md` already ends at Task 19. The later task pass appends Tasks 20–22 and does not renumber 16–19.
3. **Alt text.** Decided: `<title> (<category name>)` using `Category.name`, with one space before the parenthesis (requirement 10).
4. **Blank photo element.** Decided: an `img` with classes `listing-photo listing-photo-placeholder`, not an empty div (requirement 10).
5. **Unknown slug.** Decided: exact match on `funko`, `lego`, `tcg`; otherwise `generic.svg` (requirement 9).
6. **Broken image.** Decided: CSS `background-image` of `generic.svg` on `.listing-photo`, no JavaScript (requirement 11).
7. **`STATIC_URL`.** Decided: `"/static/"` so detail-page illustration URLs are root-relative (requirement 3).
8. **One include.** Decided: `_listing_photo.html` on the card, the detail page, and the edit preview (requirement 10).
9. **Matches page.** Decided: no images added.
10. **Image is not a link.** Decided: the title anchor stays the first `<a>` in the card (requirement 10).
11. **Migration.** Decided: keep `0002_item_photo.py`. Do not generate another (requirement 1).
12. **Seed.** Decided: do not change the command. A blank `photo` is how illustrations appear (requirement 9).
13. **Upload messages and limit.** Decided: the two strings and the 5 × 1024 × 1024 inclusive limit in requirement 5. Uploaded SVG is rejected. Static SVG is not an upload.
14. **Gradient.** Decided: the three stops in requirement 12, on `body` only. Badge classes and colors stay.
15. **SVG files.** Decided: the four names, the 160×120 viewBox, and the palette in requirement 8. No logos and no downloaded art.
16. **Old file after replace.** Decided: leave it on disk (requirement 7).
17. **Breakpoints and viewport.** Decided: keep the 08-enhancements rules. Do not add a second viewport tag (requirement 14).

## Assumptions to confirm

1. Tasks for this spec will be numbered 20–22, after the existing Tasks 16–19, rather than reusing 16–18.
2. Alt text is the title, a space, and the category name in parentheses (`Visible Title (Funko Pop & Figures)`).
3. A listing with no photo renders an `img.listing-photo.listing-photo-placeholder` of the category SVG, not an empty div.
4. `STATIC_URL` becomes `/static/` so those images resolve on the detail page.
5. The edit page uses the same picture. The Matches page does not gain pictures.
6. The page background is the cream / pale-teal / mint gradient `#f6f1e6`, `#e5f3f2`, `#f2faf6`.
7. No new migration. `Item.photo` and `0002_item_photo` stay as they are.
8. An unknown category slug uses `generic.svg`.
