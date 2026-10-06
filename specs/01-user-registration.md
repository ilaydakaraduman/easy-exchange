# Spec: User registration page

**Status:** Draft — awaiting user approval before any application code.

## Purpose

A visitor can create an account so they can later sign in and use Easy Exchange (listings, likes, trades). Registration is the first step of the demo flow and the only way a `User` row is created outside of seed data.

Stack per [../docs/plan.md](../docs/plan.md): Django, server-rendered templates, SQLite. Validation is server-side; errors are shown when the form is re-rendered.

## User stories

- As an anonymous visitor, I want to register with an email, display name, and password so that I can sign in and use the marketplace.
- As an anonymous visitor who already has an account, I want a link to the sign-in page from the registration page so that I do not create a duplicate account.

## Functional requirements

1. Route `GET /register` renders the registration page with an empty form. Public; no login required.
2. The form has exactly four fields, all required:

   | Field | Rules |
   | --- | --- |
   | Display name | 2–40 characters after trimming |
   | Email | Valid email format; unique (case-insensitive) |
   | Password | Passes Django's default password validators (see Data and business rules) |
   | Confirm password | Must match password |

   No extra profile fields on this page.
3. Route `POST /register` validates all fields server-side. If any field is invalid, the page is re-rendered with the submitted values (passwords cleared) and an error message next to each invalid field. No account is created.
4. If the normalized email is already registered, the form is re-rendered with the error `An account with this email already exists.` on the email field. No account is created.
5. If the form is valid and the email is new, a `User` is created with a hashed password. Plaintext is never stored.
6. After success, the user is redirected to `/login` (or the login route defined in the login/session spec). The user is **not** logged in automatically.
7. The page shows a link `Already have an account? Sign in` pointing to the login route.
8. Both password inputs use `type="password"`.
9. The form includes Django's CSRF token; a `POST` without a valid token is rejected.
10. UI: a simple, readable form. No design system for MVP.

## Acceptance criteria

- **Given** an anonymous visitor, **when** they open `/register`, **then** a form with Display name, Email, Password, and Confirm password is shown, with a link to sign in.
- **Given** a valid, unused email and matching passwords that pass the validators, **when** the visitor submits the form, **then** a `User` is created with a hashed password and the visitor is redirected to the login page without being logged in.
- **Given** an email that differs from an existing user's email only by letter case or surrounding whitespace, **when** the visitor submits the form, **then** the form is re-rendered with `An account with this email already exists.` and no user is created.
- **Given** a password and confirm password that do not match, **when** the visitor submits the form, **then** the form is re-rendered with an error on the confirm password field and no user is created.
- **Given** a password that fails Django's default validators (for example shorter than 8 characters), **when** the visitor submits the form, **then** the form is re-rendered with the validator's message on the password field and no user is created.
- **Given** an email that is not in a valid format, **when** the visitor submits the form, **then** the form is re-rendered with an error on the email field and no user is created.
- **Given** one or more required fields left empty, **when** the visitor submits the form, **then** the form is re-rendered with an error on each empty field and no user is created.
- **Given** any invalid submission, **when** the form is re-rendered, **then** the display name and email keep the submitted values and both password fields are empty.
- **Given** a `POST /register` without a valid CSRF token, **when** it reaches the server, **then** it is rejected and no user is created.

## Data and business rules

- Model: `User` (plan: Django's `AbstractUser` or a thin profile on `auth.User`). Fields used here: email (unique, case-insensitive), display name, password hash.
- Email normalization: trim surrounding whitespace and lowercase the full address **before** validation and the uniqueness check. The normalized value is what gets stored.
- Email uniqueness is enforced case-insensitively at the database level (unique constraint on the normalized value), not only in the form.
- Display name is trimmed before the 2–40 character check. Display names do not need to be unique.
- Passwords are validated with Django's default `AUTH_PASSWORD_VALIDATORS` (minimum length 8, not too similar to user attributes, not a common password, not entirely numeric). Stored with Django's default password hasher; no plaintext storage anywhere (database, logs, or session).
- Confirm password is compared in the form only; it is never stored.
- CSRF protection is required on the registration form (Django's `CsrfViewMiddleware` and `{% csrf_token %}`).
- Successful registration does not create a session. Login is a separate spec.

## Out of scope

- OAuth / social login
- Email verification
- Password reset
- Admin approval of accounts
- Profile photos or collector bios
- Captcha
- Client-side (JavaScript) validation; all validation is server-side
- Login, logout, and session handling (separate spec; only the link/route target is reserved here)
- Brief-level exclusions: payments, shipping, chat, image upload, sports category, Neo4j, message brokers, native mobile

## Test cases

1. **Valid registration**: `POST /register` with a new email, a 2–40 character display name, and a matching valid password. Assert a `User` exists with the normalized email, `check_password` succeeds, the stored password field is not the plaintext, the response redirects to the login route, and the client is not authenticated.
2. **Duplicate email with different letter case**: create a user with `alice@example.com`; `POST /register` with `  Alice@Example.COM `. Assert the form re-renders with `An account with this email already exists.` and the user count is unchanged.
3. **Mismatched passwords**: password and confirm password differ. Assert an error on the confirm password field and no user is created.
4. **Short password**: password shorter than 8 characters. Assert the validator message on the password field and no user is created.
5. **Invalid email**: for example `not-an-email`. Assert an error on the email field and no user is created.
6. **Missing fields**: submit with each field empty in turn, and with all fields empty. Assert an error on every empty field and no user is created.
7. **Re-render keeps safe values**: after any invalid submission, assert display name and email are prefilled and both password inputs are empty.
8. **CSRF**: `POST /register` without a CSRF token (CSRF checks enabled in the test client). Assert the request is rejected and no user is created.

## Open questions

- Already logged-in users: what should `GET /register` do for an authenticated user — redirect to the home/browse page, or show the form anyway? Proposed default: redirect to the home page.
- Account enumeration: the message `An account with this email already exists.` reveals whether an email is registered. **Accepted for the demo**; a production version would use a neutral message plus an email flow, which is out of scope.
