# Spec: Seed data

**Status:** Approved

## Purpose

`python manage.py seed` fills a migrated local database with the demo data from plan section 4: the three MVP categories, two users with known credentials, six `AVAILABLE` listings, and one reciprocal like pair so a `Match` exists on first load. Re-running it creates no duplicates and changes nothing. This is the seed half of plan Phase 2 and the data the demo flow in [00-overview.md](00-overview.md) starts from. The command lives in the `catalog` app ([00-architecture.md](00-architecture.md)).

## User stories

- As an anonymous visitor, I want Funko, Lego, and TCG listings to exist after seed so that I can browse the demo without registering.
- As a logged-in user, I want two demo accounts with known emails and passwords so that I can sign in and run the live demo.
- As a proposer, I want one reciprocal match already stored so that I can propose a trade without clicking through likes.
- As a counterparty, I want that same match and no pre-made trade so that accepting or rejecting is something I do during the demo, not something seed already did.

## Functional requirements

### Command

1. The command name is `seed`, invoked as `python manage.py seed` with no arguments. It lives at `catalog/management/commands/seed.py` (architecture folder layout). It is not a view and creates no session.
2. It is run after `migrate`. The demo line is `python manage.py migrate && python manage.py seed && python manage.py runserver`. If the tables do not exist yet, the command fails with Django's database error; this spec defines no custom message for that case.
3. **Idempotent.** Running `seed` again on a database that already contains the rows below creates no duplicate `Category`, `User`, `Item`, `Like`, or `Match` rows and writes nothing: existing rows are not updated. In particular, a second run does not call `set_password` (a new hash would change the stored password) and does not change any `Item.status`. Lookup rules are in Data and business rules.
4. The whole command body runs inside one `transaction.atomic()`. If `validate_metadata_schema`, `validate_metadata`, or `like_item` raises, the exception propagates, the process exits non-zero, and nothing from that run is committed.
5. On success the command writes exactly one line to stdout and nothing else (no per-row logs, no emails, no passwords):

   `Seed complete: 3 categories, 2 users, 6 items, 1 match, 0 trades.`

   The line is the same on a re-run. Exit code is 0.

### Categories

6. Seed ensures exactly these three `Category` rows, and no others (no `sports`, no nostalgia, no fourth slug):

   | `slug` | `name` |
   | --- | --- |
   | `funko` | Funko Pop & Figures |
   | `lego` | Lego Sets & Minifigures |
   | `tcg` | Trading Card Games |

7. Each row's `metadata_schema` is the list from [03-listings.md](03-listings.md) requirement 2, which is the architecture schema plus the labels and the optional `min` / `max` / `choices`. Entry order is the table order. Keys inside an entry are `key`, `label`, `type`, `required`, then `min` and `max` or `choices` when present. `required` is a JSON boolean. No other entries and no other keys (no character, line, vaulted, set number).

   `funko`:

   ```json
   [
     {"key": "box_condition", "label": "Box condition (1–10)", "type": "int", "required": true, "min": 1, "max": 10},
     {"key": "original_box_included", "label": "Original box included", "type": "bool", "required": true},
     {"key": "serial_number", "label": "Serial number", "type": "str", "required": true}
   ]
   ```

   `lego`:

   ```json
   [
     {"key": "sealed_misb", "label": "Factory sealed (MISB)", "type": "bool", "required": true},
     {"key": "missing_parts", "label": "Missing parts", "type": "bool", "required": true},
     {"key": "year", "label": "Year", "type": "int", "required": true}
   ]
   ```

   `tcg`:

   ```json
   [
     {"key": "grading", "label": "Grading (company and score)", "type": "str", "required": false},
     {"key": "card_condition", "label": "Card condition", "type": "str", "required": true, "choices": ["Mint", "Near Mint", "Played"]}
   ]
   ```

8. For each of the three schemas, seed calls `validate_metadata_schema(schema)` from `catalog/validators.py` **before** saving that `Category`. If it raises, the command fails (requirement 4) and that row is not saved. A schema error is a developer error, not a form error (architecture *Schema configuration check*; 03-listings requirement 3).
9. Categories are matched by `slug`. If that slug already exists, seed does not save it again and does not change `name` or `metadata_schema`. If it does not exist, seed inserts it with the `name` and the validated `metadata_schema`.

### Demo users

10. Seed ensures two `User` rows. Emails are stored normalized (trimmed, lowercased) as in [01-user-registration.md](01-user-registration.md). Passwords are hashed with Django's default hasher via the user manager (`create_user` or equivalent); plaintext is never stored. Seed does not `POST` to `/register` and does not sign anyone in.

    | | `email` | `display_name` | Password (plaintext only in this spec and the command source) |
    | --- | --- | --- | --- |
    | Demo user A | `ada@example.com` | `Ada` | `ExchangeDemo1!` |
    | Demo user B | `ben@example.com` | `Ben` | `ExchangeDemo2!` |

    These passwords are chosen to pass Django's default `AUTH_PASSWORD_VALIDATORS` (01-user-registration). `display_name` is within 2–40 characters. Seed sets no other user fields (`is_staff` and `is_superuser` stay the model defaults, `False`).
11. Users are matched by normalized `email`. If that email already exists, seed does not change `display_name`, `email`, or `password`. If it does not exist, seed creates the user.

### Listings

12. Seed ensures one `Item` per demo user per MVP category: six items. It creates an item for a `(owner, category)` pair only when that user currently owns **zero** items in that category. If the user already owns one or more, seed skips that pair (no insert, no update).
13. On create, seed sets these fields directly on the model (not through `POST /listings/new` and not through the listing form): `owner`, `category`, `title`, `description`, `metadata`. `status` is `AVAILABLE` (the model default; seed may set it on the new row only). `created_at` is set by the model. Seed does not set any field the `Item` model does not have.
14. `title` and `description`:

    | Owner | Category | `title` | `description` |
    | --- | --- | --- | --- |
    | Ada | `funko` | Ada Funko Demo | Demo Funko listing for Ada. |
    | Ada | `lego` | Ada Lego Demo | Demo Lego listing for Ada. |
    | Ada | `tcg` | Ada TCG Demo | Demo TCG listing for Ada. |
    | Ben | `funko` | Ben Funko Demo | Demo Funko listing for Ben. |
    | Ben | `lego` | Ben Lego Demo | Demo Lego listing for Ben. |
    | Ben | `tcg` | Ben TCG Demo | Demo TCG listing for Ben. |

15. `metadata` uses only keys declared for that category. Before each item is saved, seed calls `validate_metadata(category, metadata)` and saves only if it returns without error. The objects:

    | Owner | Category | `metadata` |
    | --- | --- | --- |
    | Ada | `funko` | `{"box_condition": 8, "original_box_included": true, "serial_number": "ADA-FUNKO-1"}` |
    | Ada | `lego` | `{"sealed_misb": true, "missing_parts": false, "year": 2021}` |
    | Ada | `tcg` | `{"grading": "PSA 10", "card_condition": "Mint"}` |
    | Ben | `funko` | `{"box_condition": 4, "original_box_included": false, "serial_number": "BEN-FUNKO-1"}` |
    | Ben | `lego` | `{"sealed_misb": false, "missing_parts": true, "year": 2016}` |
    | Ben | `tcg` | `{"card_condition": "Played"}` |

    Ben's TCG object omits optional `grading`. That is valid (03-listings: a blank optional `str` is omitted). Every value matches the schema type: `int` is a Python `int`, `bool` is a Python `bool` (`false` counts as present), `str` is a Python `str`.
16. Creation order on a fresh database: users Ada then Ben; for each user, categories in slug order `funko`, `lego`, `tcg`. All six `status` values are `AVAILABLE`.

### Reciprocal like

17. After categories, users, and items are ensured, seed creates the one reciprocal pair by calling `like_item` from `trades/services.py` exactly twice, in this order (05-likes-matches requirement 9 and the *Seed* paragraph): `like_item(Ada, Ben's funko item)` then `like_item(Ben, Ada's funko item)`. It never calls `Like.objects.create`, `Match.objects.create`, or any other direct insert of `Like` or `Match`.
18. The item passed to `like_item` is that owner's item in category `funko`. On a fresh seed there is exactly one. If a skip (requirement 12) left more than one, seed likes the one with the smallest `id`.
19. Those two calls produce exactly one `Match` for that pair, with `item_a_id < item_b_id`, through the reciprocal check in 05-likes-matches. They produce exactly two `Like` rows. A re-run calls `like_item` the same way; `like_item` is idempotent, so the `Like` and `Match` counts stay the same and no error is raised.

### Trades and other categories

20. Seed creates no `Trade` rows. It does not call `propose_trade`, `accept_trade`, `reject_trade`, or `cancel_trade`. It does not write `Item.status` except the `AVAILABLE` value on an item it itself inserts (requirement 13). After seed, on a fresh database, all six items are `AVAILABLE` and `Trade` count is 0.
21. Seed does not insert a `sports` category or any slug other than `funko`, `lego`, and `tcg`. It is not a reset command: it does not delete extra users, items, categories, likes, matches, or trades that something else created.

## Acceptance criteria

- **Given** an empty migrated database, **when** `python manage.py seed` runs, **then** it exits 0 and stdout is exactly `Seed complete: 3 categories, 2 users, 6 items, 1 match, 0 trades.` plus a trailing newline.
- **Given** that run, **when** categories are read, **then** there are exactly three, with slugs `funko`, `lego`, `tcg`, names from requirement 6, and `metadata_schema` equal to the JSON in requirement 7, and `validate_metadata_schema` raises nothing for each.
- **Given** that run, **when** users are read, **then** `ada@example.com` (`Ada`) and `ben@example.com` (`Ben`) exist, `check_password` succeeds for `ExchangeDemo1!` and `ExchangeDemo2!`, and the stored password fields are not those plaintext strings.
- **Given** that run, **when** items are read, **then** there are exactly six, one per user per category, each `status` is `AVAILABLE`, each `title` / `description` / `metadata` equals requirements 14–15, and `validate_metadata` raises nothing for each.
- **Given** that run, **when** likes and matches are read, **then** there are exactly two `Like` rows (Ada liked Ben's funko item, Ben liked Ada's funko item), exactly one `Match` whose items are those two, `item_a_id < item_b_id`, and zero `Trade` rows.
- **Given** `like_item` is replaced with a no-op for the duration of the command, **when** seed runs, **then** `Match` count stays 0 (seed does not insert a `Match` itself).
- **Given** a successful seed, **when** seed runs a second time, **then** the counts stay 3 categories, 2 users, 6 items, 2 likes, 1 match, 0 trades; the primary keys are unchanged; `name`, `metadata_schema`, `display_name`, the password hash, and each item's `title`, `description`, `metadata`, and `status` are unchanged; stdout is the same success line.
- **Given** a successful seed and one seed item's `title` changed and its `status` set to `IN_TRADE`, **when** seed runs again, **then** that `title` and `status` stay as changed, no seventh item is created, and the `Trade` count stays 0.
- **Given** a database with no `Category` row whose `slug` is `sports`, **when** seed runs, **then** there is still no `sports` row.

## Data and business rules

- **Models** (no new models or fields): `Category` (`slug`, `name`, `metadata_schema`), `User` (`email`, `display_name`, `password` hash), `Item` (`owner`, `category`, `title`, `description`, `status`, `metadata`, `created_at`), `Like`, `Match`. `Trade` is never written.
- **Natural keys and the no-update rule.** `Category` by `slug`. `User` by normalized `email`. `Item` by the pair `(owner, category)`: the slot is filled if that user owns any item in that category. A filled slot or an existing category or user is left byte-for-byte as stored, even when the stored values differ from the constants in this spec (seed does not repair drift and does not reset a demo trade's `IN_TRADE` / `TRADED` back to `AVAILABLE`). An empty slot is filled by an insert.
- **Fields seed sets on insert.**

  | Model | Set by seed on insert | Not set by seed |
  | --- | --- | --- |
  | `Category` | `slug`, `name`, `metadata_schema` | — |
  | `User` | `email`, `display_name`, `password` (hash only) | `is_staff`, `is_superuser` (defaults), any session |
  | `Item` | `owner`, `category`, `title`, `description`, `metadata`, `status=AVAILABLE` | `created_at` (model default). No status other than `AVAILABLE`, and only on the inserted row |

  `title`, `description`, and `metadata` are assigned in the command after `validate_metadata` succeeds. They are not submitted through the listing form.
- **Validation calls.** `validate_metadata_schema` once per category schema, before that category's insert. `validate_metadata` once per item, before that item's insert. Skipped slots and already-existing rows are not re-saved, so those calls are what guards the insert path. Both functions are the ones in `catalog/validators.py`; seed does not reimplement the checks.
- **Likes.** Only `like_item(user, item)`. The pair is Ada's `funko` item and Ben's `funko` item. Two calls, Ada first. That is the one pre-made reciprocal pair from plan section 4. No other likes.
- **Statuses.** Item status values are only `AVAILABLE` on the six inserted rows. Trade statuses are not used. Seed never moves `AVAILABLE → IN_TRADE`.
- **Counts on a fresh database after one seed:** `Category` 3, `User` 2, `Item` 6, `Like` 2, `Match` 1, `Trade` 0.
- **Stdout** is the single line in requirement 5. Passwords stay in the command source so the demo can sign in; they are not written to the database as plaintext and not printed.

## Out of scope

- Wiping the database, a `--reset` flag, or overwriting rows that already exist
- Repairing a `metadata_schema` or item that was edited after the first seed
- Creating `Trade` rows or calling the trade service
- Inserting `Like` or `Match` except by calling `like_item`
- Any category other than `funko`, `lego`, `tcg` (sports and nostalgia stay unseeded)
- Registration, login, browse, listing forms, the Matches page, and propose / accept (other specs). Seed only supplies the rows those features read
- Image upload, wishlist text, payments, shipping, chat, OAuth, email verification, Neo4j, message brokers, native mobile
- PostgreSQL, cloud deployment, or running `migrate` itself

## Test cases

Tests live in `catalog/tests/` and call `call_command("seed")` against the test database. **Must-have** cases are the ones this spec treats as the contract. **Nice-to-have** cases lock wording or edge behavior that the demo does not depend on.

**Must-have**

1. **Three categories, exact schema.** Empty database; run seed. Assert exactly three `Category` rows, slugs `funko`, `lego`, `tcg`, names from requirement 6, and `metadata_schema` deep-equal to the JSON in requirement 7 (including `min` / `max` on `box_condition` and `choices` on `card_condition`). Assert `validate_metadata_schema` raises nothing for each. Assert no row with `slug="sports"` and that the category count is 3.
2. **Two users, hashed passwords.** Assert exactly two users, emails `ada@example.com` and `ben@example.com`, display names `Ada` and `Ben`. Assert `check_password("ExchangeDemo1!")` / `check_password("ExchangeDemo2!")` and that the stored `password` string is not the plaintext.
3. **Six valid items, all `AVAILABLE`.** Assert exactly six items, one per user per category, `status == AVAILABLE`, `title` / `description` / `metadata` equal to requirements 14–15 (Ben's TCG metadata has no `grading` key; Ada's has `"grading": "PSA 10"`). Assert `validate_metadata(category, item.metadata)` raises nothing for each, and that every metadata key is one of that category's schema keys.
4. **One match, zero trades.** Assert exactly two `Like` rows and exactly one `Match`, the match's two items are Ada's funko item and Ben's funko item, `item_a_id < item_b_id`, and `Trade` count is 0. Assert no item has status other than `AVAILABLE`.
5. **No direct `Match` insert.** Patch `like_item` to a no-op that records its arguments. Run seed. Assert `Match` count is 0 and `Like` count is 0, and that `like_item` was called twice: `(Ada, Ben's funko item)` then `(Ben, Ada's funko item)`.
6. **Idempotency.** Run seed twice on an empty database. After the second run, counts are still 3 / 2 / 6 / 2 / 1 / 0 (`Category` / `User` / `Item` / `Like` / `Match` / `Trade`). Primary keys of the categories, users, items, likes, and the match are unchanged. `metadata_schema`, `display_name`, the password hash string, and each item's `title`, `description`, `metadata`, and `status` are unchanged. Stdout of the second run is the same success line.

**Nice-to-have**

7. **Stdout wording.** Capture stdout of a first run. Assert it equals `Seed complete: 3 categories, 2 users, 6 items, 1 match, 0 trades.\n` and contains neither email nor either password.
8. **Does not clobber edits.** After a successful seed, change one item's `title` and set its `status` to `IN_TRADE` in the test. Run seed again. Assert that `title` and `status` are still the edited values, item count is still 6, and `Trade` count is still 0.
9. **Filled slot is not duplicated.** Create Ben's user and one funko item with a different title before seed. Run seed. Assert Ben still has exactly one funko item (the pre-created one, unchanged) and that the other five seed items exist.
10. **Rollback.** Patch `validate_metadata` to raise on the fourth item. Assert the command raises and that `Category`, `User`, and `Item` counts are unchanged from before the call.
11. **Demo login.** Using Django's test client, `POST /login` as `ada@example.com` / `ExchangeDemo1!` and as `ben@example.com` / `ExchangeDemo2!`. Assert each login succeeds. (Crosses [02-login-session.md](02-login-session.md); the password check in case 2 is the must-have.)

## Open questions

All decided; recorded here for traceability. None of these was settled by `docs/plan.md`.

1. **Demo credentials.** Decided: `ada@example.com` / `Ada` / `ExchangeDemo1!` and `ben@example.com` / `Ben` / `ExchangeDemo2!`.
2. **Listing text and metadata.** Decided: the titles, descriptions, and six metadata objects in requirements 14–15, including omitting `grading` on Ben's TCG item and using `PSA 10` on Ada's.
3. **Which items are liked.** Decided: Ada's funko item and Ben's funko item, `like_item(Ada, Ben's funko)` then `like_item(Ben, Ada's funko)`.
4. **Success line.** Decided: stdout is exactly `Seed complete: 3 categories, 2 users, 6 items, 1 match, 0 trades.` Passwords stay off stdout.
5. **Re-run does not repair drift.** Decided: an existing category, user, or filled `(owner, category)` item slot is left unchanged.
6. **Item identity is `(owner, category)`, not title.** Decided: a renamed seed item is not duplicated on re-run.
7. **One transaction.** Decided: the command body is a single `transaction.atomic()` so a validator failure commits nothing.
