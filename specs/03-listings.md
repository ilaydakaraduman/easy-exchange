# Spec: Categories and listings (create / edit)

**Status:** Approved

## Purpose

A logged-in user creates a listing (`Item`) in one of the three MVP categories and later edits it while it is still `AVAILABLE`. The form shows exactly the metadata fields of the chosen category, read from `Category.metadata_schema`, and the server validates the submitted metadata against that schema before saving. This is the first half of plan Phase 2 ("Category table + schemas; create/edit listing form that shows fields from `metadata_schema`") and the demo's proof that adding a category is data, not code.

Stack per [00-architecture.md](00-architecture.md): Django, server-rendered templates, SQLite `JSONField`, the `catalog` app (`Category`, `Item`, `catalog/validators.py`, `catalog/forms.py`). Login gating per [02-login-session.md](02-login-session.md). Public listing detail and browse pages belong to `04-browse.md`; the seed command that inserts the `Category` rows belongs to `07-seed-data.md`. This spec defines the category data, the create and edit routes, the dynamic form, the validation messages, and the owner / `AVAILABLE` edit rule.

## User stories

- As a logged-in user, I want to pick a category and fill in only that category's fields so that my listing carries the right collector details (box condition, sealed state, card grade) without irrelevant inputs.
- As a logged-in user, I want clear errors next to each wrong field when I submit so that I can fix the listing without guessing.
- As a listing owner, I want to edit my listing's title, description, and metadata while it is still `AVAILABLE` so that I can correct mistakes before anyone trades for it.
- As a listing owner, I want the edit action to disappear once my item is `IN_TRADE` or `TRADED` so that I cannot change what the other party agreed to.
- As a counterparty or any other user, I want other people's listings to be read-only to me so that nobody can alter an item I liked or am trading for.
- As an anonymous visitor, I want to be sent to `/login` when I try to create a listing so that I know listing requires an account.

## Functional requirements

### Category data

1. Exactly three `Category` rows exist in the MVP, inserted by the `seed` command (`07-seed-data.md`) and never created through the UI:

   | `slug` | `name` |
   | --- | --- |
   | `funko` | Funko Pop & Figures |
   | `lego` | Lego Sets & Minifigures |
   | `tcg` | Trading Card Games |

2. Each row's `metadata_schema` is the list below, in this order. Entries use only the keys `key`, `label`, `type`, `required` and, where shown, the optional `min`, `max`, `choices` from [00-architecture.md](00-architecture.md). No other entries and no other keys.

   | `slug` | `key` | `label` | `type` | `required` | Optional entry keys |
   | --- | --- | --- | --- | --- | --- |
   | `funko` | `box_condition` | Box condition (1–10) | `int` | `true` | `min: 1`, `max: 10` |
   | `funko` | `original_box_included` | Original box included | `bool` | `true` | |
   | `funko` | `serial_number` | Serial number | `str` | `true` | |
   | `lego` | `sealed_misb` | Factory sealed (MISB) | `bool` | `true` | |
   | `lego` | `missing_parts` | Missing parts | `bool` | `true` | |
   | `lego` | `year` | Year | `int` | `true` | |
   | `tcg` | `grading` | Grading (company and score) | `str` | `false` | |
   | `tcg` | `card_condition` | Card condition | `str` | `true` | `choices: ["Mint", "Near Mint", "Played"]` |

3. Every schema passes `validate_metadata_schema` (architecture *Schema configuration check*) before the row is saved; a failing schema is a developer error that stops the seed command, not a user-facing form error.
4. Categories are listed in the UI ordered by `slug` (`funko`, `lego`, `tcg`), showing `name`.

### Create a listing

5. Route `GET /listings/new`. Requires login; an anonymous visitor is redirected to `/login?next=/listings/new` (02-login-session requirement 19).
6. **Step 1 — choose a category.** `GET /listings/new` with no `category` query parameter renders a page with a single `GET` form: a `<select name="category">` listing the three categories (requirement 4) and a `Continue` submit button. Submitting it reloads the page as `GET /listings/new?category=<slug>`. No JavaScript; this is the "page reload per category" switch. (Decided: Option A, Open question 1.)
7. **Step 2 — the listing form.** `GET /listings/new?category=<slug>` renders the same category `<select>` (pre-selected to `<slug>`) with its `Continue` button, followed by the listing form for that category. Changing the select and pressing `Continue` reloads step 2 for the new category; anything typed into the listing form is discarded by the reload (accepted; Open question 1).
8. `GET /listings/new?category=<slug>` with a `slug` that is not a `Category` row returns `404`.
9. The listing form is a `POST` form to `/listings/new` with Django's CSRF token and these inputs, in this order:

   | Input | Rendered as | Rules |
   | --- | --- | --- |
   | `category` | hidden input holding the `slug`; the category `name` is shown as read-only text above the form | Must be an existing `slug`; otherwise `404` |
   | `title` | text input | Required after trimming; see Data and business rules for length |
   | `description` | textarea | Required after trimming |
   | one input per `metadata_schema` entry | see requirement 10 | Validated per requirement 12 |

   There is no status input, no owner input, no image input, and no wishlist input.
10. **Dynamic metadata inputs**, built in `catalog/forms.py` from the category's `metadata_schema` (architecture *Dynamic form*). Field name = entry `key`; label = entry `label`:

    | Entry `type` | Rendered as | Form-level behaviour |
    | --- | --- | --- |
    | `int` | `<input type="number">` with `min` / `max` attributes when the entry has them | Coerced to an integer; non-integer text is a field error |
    | `bool` | checkbox | Unchecked submits as `false`; `false` satisfies `required` (a required `bool` is **not** "must be checked") |
    | `str` without `choices` | text input | Trimmed; required entries reject blank after trimming |
    | `str` with `choices` | `<select>` with one `<option>` per choice plus a leading blank option | Value must be one of `choices` |

    Metadata inputs appear in schema order after `description`.
11. Route `POST /listings/new`. Requires login; an anonymous `POST` is redirected to `/login` with no `next` and nothing is saved (02-login-session requirement 20).
12. **Server-side validation** (always; there is no client-side validation). `title` and `description` are checked by the form. The metadata inputs are coerced by the form (requirement 10), assembled into one object keyed by `key`, and passed to `validate_metadata(category, metadata)` from `catalog/validators.py`, which applies the architecture's five checks (object, required present, type, `min` / `max` / `choices`, no undeclared keys). Each failing check becomes a field-level error on the input with the same `key`; errors that cannot be attributed to a field (not an object, undeclared key) are non-field errors. Messages are fixed in Data and business rules.
13. On any validation error the page is re-rendered with status `200`, the submitted values kept in every input (including checkbox state and select choice), and the error text next to each failing input. No `Item` is created.
14. On success an `Item` is created with `owner = request.user`, the chosen `category`, trimmed `title` and `description`, `metadata` containing exactly the declared keys (optional blank `str` keys omitted; see Data and business rules), `status = AVAILABLE`, and `created_at` set. The user is redirected to the listing's public detail page `/listings/<id>` (owned by `04-browse.md`; path decided, Open question 2).
15. The shared base layout shows a `New listing` link to `/listings/new` for logged-in users only. It is the only navigation this spec adds (extends 02-login-session requirement 17).

### Edit a listing

16. Route `GET /listings/<id>/edit`. Requires login; an anonymous visitor is redirected to `/login?next=/listings/<id>/edit`.
17. If no `Item` with that `id` exists, return `404`.
18. If the logged-in user is not `item.owner`, return `403` with the message `You can only edit your own listings.` The form is not rendered.
19. If the user is the owner but `item.status` is not `AVAILABLE`, return `403` with the message `This listing is in a trade and cannot be edited.` (same message for `IN_TRADE` and `TRADED`). The form is not rendered.
20. Otherwise render the edit form: the category `name` as read-only text (no category select, no hidden `category` input — the category is fixed for the life of the `Item`), the `title`, `description`, and the dynamic metadata inputs of `item.category`, all pre-filled from the `Item` (`item.metadata` values into the matching inputs; an optional key absent from `metadata` renders blank). The form `POST`s to `/listings/<id>/edit` with a CSRF token. There is no status input and no "change category" control on the edit page.
21. Route `POST /listings/<id>/edit`. Requires login (anonymous → `/login`, no `next`, nothing saved). Requirements 17–19 apply to the `POST` exactly as to the `GET`.
22. Validation is identical to create (requirements 12–13) against `item.category.metadata_schema`. On error the form re-renders with the submitted values and errors; the `Item` is unchanged.
23. On success, `title`, `description`, and `metadata` are written **only if the item is still `AVAILABLE` at write time**: the save is a single conditional update `WHERE id = <id> AND owner = <user> AND status = 'AVAILABLE'`. If the affected row count is 0 (a trade was proposed between the `GET` and the `POST`), nothing is written and the response is the `403` from requirement 19. `status`, `owner`, `category`, and `created_at` are never changed by this route. On success the user is redirected to the listing's detail page.
24. The `Edit` link to `/listings/<id>/edit` is rendered on the listing detail page (`04-browse.md`) **only** when the viewer is the owner **and** `status = AVAILABLE`. Other viewers and other statuses see no edit control. (The link placement is owned by `04-browse.md`; the visibility rule is fixed here.)

### What this spec does not change

25. `Item.status` is never read-modified-written or set by these views; the only status this spec touches is the default `AVAILABLE` on create and the `status = 'AVAILABLE'` condition on the edit update (architecture business rule: status changes go through `trades/services.py`).
26. There is no delete route and no way to change an `Item`'s owner or category after creation.

## Acceptance criteria

### Category data

- **Given** a freshly seeded database, **when** `Category` rows are read, **then** there are exactly three with `slug` values `funko`, `lego`, `tcg` and `metadata_schema` lists matching requirement 2 key-for-key, label-for-label, including `min: 1, max: 10` on `box_condition` and `choices: ["Mint", "Near Mint", "Played"]` on `card_condition`.
- **Given** any of the three seeded schemas, **when** `validate_metadata_schema` runs, **then** it raises nothing.

### Create — access and category choice

- **Given** an anonymous visitor, **when** they `GET /listings/new`, **then** they are redirected to `/login?next=/listings/new` and no form is rendered.
- **Given** an anonymous visitor, **when** they `POST /listings/new` with a valid payload, **then** they are redirected to `/login` (no `next`) and the `Item` count is unchanged.
- **Given** a logged-in user, **when** they `GET /listings/new`, **then** a category select with the three categories (ordered `funko`, `lego`, `tcg`, showing names) and a `Continue` button are shown, and no `title` / `description` / metadata inputs are present.
- **Given** a logged-in user, **when** they `GET /listings/new?category=funko`, **then** the page shows the select pre-set to Funko, the read-only name "Funko Pop & Figures", a hidden `category=funko`, `title`, `description`, and exactly the inputs `box_condition` (number, `min=1`, `max=10`), `original_box_included` (checkbox), `serial_number` (text), in that order, and no `lego` or `tcg` inputs.
- **Given** `GET /listings/new?category=lego`, **then** the metadata inputs are exactly `sealed_misb` (checkbox), `missing_parts` (checkbox), `year` (number, no `min` / `max`).
- **Given** `GET /listings/new?category=tcg`, **then** the metadata inputs are exactly `grading` (text, not required) and `card_condition` (select with a blank option plus `Mint`, `Near Mint`, `Played`).
- **Given** a logged-in user on the Funko form, **when** they change the select to Lego and press `Continue`, **then** the page reloads as `/listings/new?category=lego` with the Lego inputs and empty `title` / `description`.
- **Given** `GET /listings/new?category=sports` (or any unknown slug), **then** the response is `404`.

### Create — validation and save

- **Given** a logged-in user, **when** they `POST /listings/new` with `category=funko`, a title, a description, `box_condition=7`, `original_box_included` checked, `serial_number=FP-0001`, **then** an `Item` is created with `owner` = that user, `category` = funko, `status = AVAILABLE`, `metadata == {"box_condition": 7, "original_box_included": true, "serial_number": "FP-0001"}`, and the response redirects to the item's detail page.
- **Given** the same post with `original_box_included` unchecked, **then** the item is created with `"original_box_included": false` (unchecked is a valid present value).
- **Given** `box_condition=0` or `box_condition=11`, **when** submitted, **then** the form re-renders with `Ensure this value is between 1 and 10.` next to `box_condition` and no `Item` is created.
- **Given** `box_condition=abc` or `box_condition=7.5`, **when** submitted, **then** the form re-renders with `Enter a whole number.` next to `box_condition` and no `Item` is created.
- **Given** `serial_number` blank or whitespace only, **when** submitted, **then** the form re-renders with `This field is required.` next to `serial_number` and no `Item` is created.
- **Given** `category=lego` with `year` missing, **when** submitted, **then** `This field is required.` appears next to `year` and no `Item` is created.
- **Given** `category=tcg`, `card_condition=Mint`, `grading` blank, **when** submitted, **then** the item is created with `metadata == {"card_condition": "Mint"}` (blank optional `grading` is omitted).
- **Given** `category=tcg`, `card_condition=Mint`, `grading=PSA 10`, **then** `metadata == {"grading": "PSA 10", "card_condition": "Mint"}`.
- **Given** `category=tcg` with `card_condition` blank or `card_condition=Good`, **when** submitted, **then** the form re-renders with `Select a valid choice. Good is not one of the available choices.` (or `This field is required.` when blank) next to `card_condition` and no `Item` is created.
- **Given** a `POST` whose body contains an input not declared in the category's schema (for example `character=Batman` for funko), **when** submitted, **then** the undeclared input is ignored by the form (it is not a form field) and is never written to `metadata`; the saved `metadata` contains only declared keys.
- **Given** `title` or `description` blank or whitespace only, **when** submitted, **then** `This field is required.` appears next to that input and no `Item` is created.
- **Given** a `POST /listings/new` with `category=sports`, **then** the response is `404` and no `Item` is created.
- **Given** any invalid submission, **when** the form re-renders, **then** every input keeps its submitted value (text, number, checkbox state, selected choice) and the response status is `200`.
- **Given** a `POST /listings/new` without a valid CSRF token, **then** it is rejected and no `Item` is created.

### Edit — access

- **Given** an anonymous visitor, **when** they `GET /listings/<id>/edit`, **then** they are redirected to `/login?next=/listings/<id>/edit`.
- **Given** a logged-in user who is not the owner of an `AVAILABLE` item, **when** they `GET` or `POST /listings/<id>/edit`, **then** the response is `403` containing `You can only edit your own listings.` and the item is unchanged.
- **Given** the owner of an item whose status is `IN_TRADE` or `TRADED`, **when** they `GET` or `POST /listings/<id>/edit`, **then** the response is `403` containing `This listing is in a trade and cannot be edited.` and the item is unchanged.
- **Given** `GET /listings/999999/edit` for a non-existent id, **then** `404`.
- **Given** the owner of an `AVAILABLE` Funko item, **when** they `GET /listings/<id>/edit`, **then** the form shows "Funko Pop & Figures" as read-only text, no category select or hidden `category` input, and `title`, `description`, `box_condition`, `original_box_included`, `serial_number` pre-filled from the item.
- **Given** the owner of an `AVAILABLE` TCG item whose `metadata` has no `grading` key, **when** they open the edit form, **then** the `grading` input is empty and `card_condition` is pre-selected.

### Edit — validation and save

- **Given** the owner of an `AVAILABLE` item, **when** they `POST` a valid edit, **then** `title`, `description`, and `metadata` are updated, `status` is still `AVAILABLE`, `owner`, `category`, and `created_at` are unchanged, and the response redirects to the detail page.
- **Given** the owner of an `AVAILABLE` item, **when** they `POST` an invalid edit (for example `box_condition=11`), **then** the form re-renders with the error and the stored `Item` is byte-for-byte unchanged.
- **Given** the owner opened the edit form while the item was `AVAILABLE` and the item then became `IN_TRADE` (a trade was proposed), **when** they `POST` the edit, **then** the conditional update affects 0 rows, the response is the `403` from requirement 19, and the item's `title`, `description`, and `metadata` are unchanged.
- **Given** a `POST /listings/<id>/edit` that includes a `category` or `status` input, **when** submitted, **then** those inputs are ignored and `category` and `status` are unchanged.
- **Given** a `POST /listings/<id>/edit` without a valid CSRF token, **then** it is rejected and the item is unchanged.

### Edit control visibility (rule only; rendering in 04-browse)

- **Given** the owner viewing their own `AVAILABLE` listing's detail page, **then** an `Edit` link to `/listings/<id>/edit` is present.
- **Given** the owner viewing their own `IN_TRADE` or `TRADED` listing, or any non-owner (logged in or anonymous) viewing any listing, **then** no `Edit` link is present.

## Data and business rules

- **Models** (from [00-architecture.md](00-architecture.md); no new models or fields): `Category` (`slug`, `name`, `metadata_schema`) and `Item` (`owner`, `category`, `title`, `description`, `status`, `metadata`, `created_at`). This spec reads `User` only as `item.owner` / `request.user`.
- **`title`**: trimmed; required; maximum 120 characters (decided, Open question 3; the plan sets no length). **`description`**: trimmed; required; no maximum beyond the database text type.
- **`Item.status`** defaults to `AVAILABLE` on create and is never set by the create or edit views. The edit `POST` only *conditions* on `status = 'AVAILABLE'`; it does not write `status`.
- **`Item.category`** is set once on create and is immutable. The edit form has no category input; any `category` value in an edit `POST` body is ignored.
- **`Item.owner`** is always `request.user` on create and is never changed.
- **Edit authorization**: owner only (`item.owner == request.user`), and only while `status = AVAILABLE`. Checked on `GET` (to decide whether to render) and on `POST` (before validation), and enforced again at write time by the conditional update in requirement 23 so a status change between `GET` and `POST` cannot be overwritten. Non-owner → `403`; owner but not `AVAILABLE` → `403`. Anonymous → login redirect per 02-login-session.
- **`metadata` contents**: exactly the declared `key`s of `item.category.metadata_schema`, with values of the declared `type` (`int` → Python `int`, never `bool` or `float`; `bool` → Python `bool`; `str` → Python `str`, trimmed). Optional `str` entries whose trimmed input is blank are **omitted** from `metadata` rather than stored as `""` (decided, Open question 4). No undeclared keys are ever stored.
- **Validation order on `POST`**: (1) category / item resolution (`404`), (2) edit authorization (`403`), (3) form field validation (required, coercion, `min` / `max`, `choices`), (4) `validate_metadata(category, metadata)` on the coerced object as the authoritative check. Step 3 is Django's standard form fields configured from the schema entry (`IntegerField(min_value, max_value)`, `BooleanField(required=False)`, `CharField(required=…)`, `ChoiceField`), so steps 3 and 4 enforce the same rules; step 4 exists so the rule also holds for non-form callers (seed, tests) and so the validator, not the form, is the contract. A key that already has a step-3 error does not receive a duplicate step-4 message.
- **Error messages** (field-level, next to the input named by `key`, or `title` / `description`):

  | Condition | Message |
  | --- | --- |
  | Required `str` / `int` missing or blank; `title` / `description` blank | `This field is required.` |
  | `int` value not an integer (text, decimal) | `Enter a whole number.` |
  | `int` value outside `min` / `max` (both present) | `Ensure this value is between <min> and <max>.` |
  | `int` value below `min` (only `min` present) | `Ensure this value is greater than or equal to <min>.` |
  | `int` value above `max` (only `max` present) | `Ensure this value is less than or equal to <max>.` |
  | `str` value not in `choices` | `Select a valid choice. <value> is not one of the available choices.` |
  | `bool` field receives a non-boolean value (direct validator callers only; the form cannot produce this) | `Enter a yes or no value.` |

  **Message sources.** `This field is required.`, `Enter a whole number.`, `Ensure this value is greater than or equal to <min>.`, `Ensure this value is less than or equal to <max>.`, and `Select a valid choice. <value> is not one of the available choices.` are Django's default form-field messages, used unchanged. **`Ensure this value is between <min> and <max>.` is a custom message, not a Django default**: Django's `IntegerField(min_value, max_value)` has no combined range message and would emit the two separate `greater than or equal to` / `less than or equal to` messages. The custom message is produced in the dynamic form builder in `catalog/forms.py`: when a schema entry has **both** `min` and `max`, the builder passes `error_messages={"min_value": "Ensure this value is between <min> and <max>.", "max_value": "Ensure this value is between <min> and <max>."}` to that entry's `IntegerField`, so either bound violation shows the single range message. When only one of `min` / `max` is present, no override is applied and Django's default single-bound message is shown. The validator's own range message (`"<key>" must be between <min> and <max>.`, below) is separate and is only seen by direct callers.

  Validator-only messages, raised by `validate_metadata` when called outside the form (seed, tests) and surfaced as non-field errors if they ever reach a form: `Metadata must be an object.`; `Unknown metadata field "<key>".`; `Missing required field "<key>".`; `"<key>" must be a whole number.`; `"<key>" must be yes or no.`; `"<key>" must be text.`; `"<key>" must be between <min> and <max>.`; `"<key>" must be one of: <choices joined by ", ">.`

- **Checkbox semantics**: HTML omits unchecked checkboxes from the `POST` body. The form therefore uses `required=False` on every `bool` input and maps absence to `false`. `validate_metadata` treats `false` as present and valid for a `required = true` `bool` entry (architecture check 2).
- **Category switching** is a page reload (`GET /listings/new?category=<slug>`) driven by a plain `GET` form; no JavaScript, no partial rendering. Switching discards unsaved `title` / `description` (decided, Open question 1).
- **No deletion.** Items are never deleted (overview *Out of scope*). No route, no admin shortcut documented for the product.
- **CSRF** on every `POST` form (`CsrfViewMiddleware`, `{% csrf_token %}`), as in 01 and 02.
- **Generic validator**: `validate_metadata` and the form builder contain no `if slug == "funko"` logic. A `Category` created in a test with a new `metadata_schema` (using `min` / `max` / `choices`) produces a working form and is enforced without code changes (architecture test 19).

## Out of scope

- Public listing detail page, browse page, category filter, status badges, and the placement / markup of the `Edit` link — `04-browse.md` (only the visibility rule is fixed here)
- Inserting the `Category` rows and the six demo `Item` rows — `07-seed-data.md` (this spec fixes their `metadata_schema` content)
- Deleting a listing, archiving, or hiding it
- Changing a listing's category or owner after creation
- Any change to `Item.status` from these views; status moves only via `trades/services.py`
- Image upload or image URL (optional Phase 5 polish, cut first)
- A "what I want in return" wishlist field; the plan's data model has no such field, and matching is by likes
- Creating, editing, or deleting categories through the UI; the sports / nostalgia stretch categories
- JavaScript-driven category switching, client-side validation, or AJAX
- Rich text, markdown, or length-limited descriptions beyond "required"
- Draft / unpublished listings; a created `Item` is immediately `AVAILABLE` and public
- A "My listings" page (not in the plan; the owner reaches edit from the public detail page)
- Brief-level exclusions: payments, shipping, chat, OAuth, email verification, sports category, Neo4j, message brokers, native mobile

## Test cases

Tests live in `catalog/tests/`. Cases 1–12 call `validate_metadata` / `validate_metadata_schema` directly and mirror architecture tests 13–20 and plan section 5 "Metadata (lightweight)". Cases 13–30 use Django's test client.

**Validator (`catalog/validators.py`)**

1. **Valid metadata passes per category**: funko `{"box_condition": 7, "original_box_included": true, "serial_number": "FP-0001"}`; lego `{"sealed_misb": false, "missing_parts": false, "year": 2019}`; tcg `{"card_condition": "Near Mint"}` and `{"grading": "PSA 10", "card_condition": "Mint"}`. Assert no error.
2. **Missing required keys rejected**: for each category, drop each required key in turn. Assert `Missing required field "<key>".` on that key. Dropping tcg `grading` is accepted.
3. **Blank required string rejected**: funko `serial_number: ""` and `"   "`. Assert rejected; tcg `grading: ""` accepted.
4. **`box_condition` bounds**: 0 and 11 rejected with `"box_condition" must be between 1 and 10.`; 1 and 10 accepted.
5. **`box_condition` type**: `"7"`, `7.5`, `true` rejected with `"box_condition" must be a whole number.`
6. **`card_condition` choices**: `"Good"`, `"mint"` (case differs) rejected with `"card_condition" must be one of: Mint, Near Mint, Played.`; each of the three allowed values accepted.
7. **Wrong types**: lego `year: "2019"`; lego `sealed_misb: "yes"`; funko `serial_number: 123`. Assert the matching type message.
8. **Undeclared key rejected**: funko metadata with an extra `character` key. Assert `Unknown metadata field "character".`
9. **Not an object**: `[]`, `"x"`, `None`. Assert `Metadata must be an object.`
10. **Required bool `false` is valid**: funko with `original_box_included: false`; lego with both bools `false`. Assert accepted.
11. **Generic validator**: create a `Category` in the test with `slug="test"` and a schema containing an `int` with `min: 0, max: 5`, a `str` with `choices: ["a", "b"]`, and an optional `str`. Assert bounds and choices are enforced and the optional key may be absent, with no code change.
12. **Schema configuration check**: `validate_metadata_schema` raises for `min` on a `str` entry, `choices` on an `int` entry, `min > max`, empty `choices`, unknown `type`, missing `label`, unknown entry key `default`, and duplicate `key`. The three seeded schemas pass.

**Create view**

13. **Anonymous redirects**: `GET /listings/new` → `302` to `/login?next=/listings/new`; `POST /listings/new` with a valid body → `302` to `/login` (no `next`), `Item` count unchanged.
14. **Step 1 renders chooser only**: logged in, `GET /listings/new`. Assert the three options in order `funko`, `lego`, `tcg` with their names, a `Continue` button, and no `title` input.
15. **Step 2 renders the right fields**: for each slug, `GET /listings/new?category=<slug>`. Assert exactly the inputs from requirement 2 in order, correct widget types, `min="1" max="10"` on `box_condition`, no `min` / `max` on `year`, a blank-plus-three-options select for `card_condition`, `grading` not required, and no inputs from the other categories.
16. **Unknown slug**: `GET /listings/new?category=sports` → `404`; `POST` with `category=sports` → `404` and no `Item`.
17. **Valid create per category**: post one valid payload per category. Assert the `Item` exists with `owner`, `category`, `status = AVAILABLE`, trimmed `title` / `description`, exact `metadata` (including `false` for an unchecked checkbox and omission of blank `grading`), and a redirect to the detail path.
18. **Out-of-range and non-integer `box_condition`**: `0`, `11`, `abc`, `7.5`. Assert `200`, the message from the table next to `box_condition`, no `Item`. For `0` and `11` assert the custom combined message `Ensure this value is between 1 and 10.` and that neither Django default single-bound message appears.
19. **Invalid `card_condition`**: blank and `Good`. Assert the respective message, no `Item`.
20. **Missing required**: blank `serial_number`, missing `year`, blank `title`, blank `description`. Assert `This field is required.` on each, no `Item`.
21. **Undeclared input ignored**: funko `POST` with an extra `character=Batman`. Assert the `Item` is created and `"character"` is not in `metadata`.
22. **Re-render keeps values**: an invalid funko `POST` with `box_condition=11`, checkbox checked, `serial_number=X`. Assert all three are reflected in the re-rendered form and `title` / `description` are prefilled.
23. **CSRF**: `POST /listings/new` without a token (CSRF checks enabled) → `403`, no `Item`.
24. **Nav link**: render `/` logged in and anonymous. Assert the `New listing` link to `/listings/new` appears only when logged in.

**Edit view**

25. **Anonymous redirects**: `GET /listings/<id>/edit` → `/login?next=/listings/<id>/edit`; `POST` → `/login`, item unchanged.
26. **Non-owner forbidden**: another logged-in user `GET` and `POST`. Assert `403`, `You can only edit your own listings.`, item unchanged.
27. **Non-`AVAILABLE` forbidden**: set the owner's item to `IN_TRADE` and then `TRADED` directly in the test. Assert `GET` and `POST` return `403` with `This listing is in a trade and cannot be edited.` and the item is unchanged.
28. **Pre-filled form, no category control**: owner `GET` on an `AVAILABLE` item. Assert values prefilled, category shown as text, no `<select name="category">` and no hidden `category` input; for a tcg item without `grading`, the `grading` input is empty.
29. **Valid edit**: owner posts new `title`, `description`, `metadata`. Assert the three are updated, `status` still `AVAILABLE`, `owner` / `category` / `created_at` unchanged, redirect to the detail path. Also assert that a `category` or `status` value in the body is ignored.
30. **Invalid edit leaves item unchanged**: owner posts `box_condition=11`. Assert `200`, the error, and the stored item equals its pre-request snapshot.
31. **Stale edit refused**: owner `GET`s the edit form; the test then sets the item to `IN_TRADE`; owner `POST`s a valid edit. Assert `403` and `title` / `description` / `metadata` unchanged (conditional update affected 0 rows).
32. **Edit link visibility** (asserted against the detail page once `04-browse.md` lands; rule fixed here): present for owner + `AVAILABLE`; absent for owner + `IN_TRADE` / `TRADED`, for a non-owner, and for anonymous.

## Open questions

All decided; recorded here for traceability.

1. **How is the category chosen on the create page?** The plan says only "User picks a `Category`; the form shows the fields from that category's `metadata_schema`". Options considered, all without JavaScript: **A** — `/listings/new` shows a `GET` form with a category `<select>` and a `Continue` button; picking a category reloads the page as `/listings/new?category=<slug>` with the full listing form below the select; switching discards unsaved `title` / `description`. **B** — three links, one per category, with a "Change category" link back. **C** — the `<select>` inside the `POST` form with a second `Change category` submit that re-renders without saving and preserves typed values. **Decided: A** (requirements 6–7).
2. **Routes.** Decided: `GET/POST /listings/new`, `GET/POST /listings/<id>/edit`; the detail page is `/listings/<id>` (owned by `04-browse.md`).
3. **`title` maximum length.** The plan and architecture say only "string, required". Decided: 120 characters.
4. **Blank optional `str` (tcg `grading`).** Decided: omit the key (so `metadata == {"card_condition": "Mint"}`), which makes "absent" and "blank" the same case for `04-browse.md` display.
5. **Refusal style for a non-`AVAILABLE` or non-owned edit.** Decided: HTTP `403` with the fixed messages in requirements 18–19 (not a silent redirect; there is no flash-message mechanism until Phase 5).
6. **Stale edit.** Decided: the edit `POST` saves via a conditional update on `status = 'AVAILABLE'` and returns the requirement-19 `403` when 0 rows are affected (requirement 23).
7. **Where the `New listing` link lives.** Decided: the shared base layout header, logged-in users only (requirement 15).
8. **Error message wording.** Decided: Django default messages, except the combined range message `Ensure this value is between <min> and <max>.`, which is a custom `error_messages` override set in `catalog/forms.py` when an entry has both `min` and `max` (see *Message sources* under Data and business rules).
9. **Category order.** Decided: by `slug` (`funko`, `lego`, `tcg`).
10. **Category names.** Decided: "Funko Pop & Figures", "Lego Sets & Minifigures", "Trading Card Games".
