# Spec: Login, logout, and session

**Status:** Approved

## Purpose

A registered user signs in at `/login` with email and password, receives a session cookie, and can later sign out at `/logout`. Pages and actions that require login (create / edit listing, like, Matches page, trade actions) send anonymous visitors to `/login` instead of serving the page. This is the second half of plan Phase 1 ("Login / logout (session cookie)") and the gate that makes "browse is public; list / like / trade require login" true.

Stack per [00-architecture.md](00-architecture.md): Django, server-rendered templates, SQLite, the custom `accounts.User` with `email` as `USERNAME_FIELD`. This spec lives in the `accounts` app alongside [01-user-registration.md](01-user-registration.md) and reuses its email normalization and CSRF rules.

## User stories

- As an anonymous visitor with an account, I want to sign in with my email and password so that I can create listings, like items, and trade.
- As an anonymous visitor who opens a page that requires login, I want to be sent to the sign-in page so that I understand why I cannot see it and can sign in.
- As a logged-in user, I want to stay signed in across page loads so that I do not re-enter my password on every request.
- As a logged-in user, I want to sign out so that nobody else at this browser can act as me.
- As an anonymous visitor without an account, I want a link to the registration page from the sign-in page so that I can create an account first.

## Functional requirements

### Login

1. Route `GET /login` renders the sign-in page with an empty form. Public; no login required.
2. The form has exactly two fields, both required:

   | Field | Rules |
   | --- | --- |
   | Email | Trimmed and lowercased before lookup (same normalization as registration) |
   | Password | Checked against the stored Django password hash; `type="password"` |

   No "remember me" checkbox, no captcha, no extra fields.
3. Route `POST /login` validates server-side. Authentication uses the custom `accounts.User` with `email` as the login identifier (`USERNAME_FIELD`), via Django's `authenticate()` / `login()`.
4. If either field is empty, the page is re-rendered with an error next to each empty field. No session is created.
5. If the email is unknown **or** the password is wrong (or the account cannot log in for any other reason, for example `is_active = False`), the page is re-rendered with the single non-field error `Invalid email or password.` No session is created. The response must be the same in both cases (see Data and business rules).
6. On any invalid submission the email field keeps the submitted value; the password field is empty.
7. If the credentials are valid, the user is logged in: a session is created, the session key is rotated (Django's `login()` does this), and the session cookie is set. The user is then redirected to the post-login destination:
   - If the request carries a `next` parameter (query string on `GET /login`, carried into the form and posted back) **and** it is a safe relative path on this site (Django's `url_has_allowed_host_and_scheme`), redirect there.
   - Otherwise redirect to the home / browse page `/` (public browse, defined in `04-browse.md`).

   This is the proposed landing rule; see Open question 1.
8. `GET /login` for a user who is already logged in redirects to `/` without rendering the form (proposed; see Open question 2). `POST /login` while already logged in behaves the same as a fresh login (the new credentials replace the current session).
9. The page shows a link `Don't have an account? Register` pointing to `/register`.
10. The form includes Django's CSRF token; a `POST /login` without a valid token is rejected and no session is created.
11. UI: a simple, readable form matching the registration page. No design system for MVP.

### Logout

12. Route `POST /logout` logs the user out: the session is flushed on the server (Django's `logout()`), the session cookie is invalidated, and the user is redirected to `/`.
13. `GET /logout` is not allowed: it returns `405 Method Not Allowed` and does not change the session. Logout is only ever a `POST`.
14. `POST /logout` includes Django's CSRF token; a `POST` without a valid token is rejected and the session is unchanged.
15. `POST /logout` by an anonymous visitor (no session) simply redirects to `/`; it is not an error.
16. The logout control is a small form with a `Logout` submit button (and `{% csrf_token %}`) in the shared base layout header, shown only when the user is logged in. There is no logout link (`<a href>`).

### Navigation state

17. The shared base layout shows, for anonymous visitors, links `Sign in` (`/login`) and `Register` (`/register`); for logged-in users, the user's `display_name` and the `Logout` button from requirement 16. Nothing else in the header is required by this spec (further nav is plan Phase 5 polish).

### Pages and actions that require login

18. The following require a logged-in user. The exact routes are defined in the specs that own them; this spec defines the rule, not the URLs.

   | Protected | Spec |
   | --- | --- |
   | Create listing, edit listing | `03-listings.md` |
   | Like action | `05-likes-matches.md` |
   | Matches page | `05-likes-matches.md` |
   | Propose, accept, reject, cancel trade: `POST /matches/<id>/propose`, `POST /trades/<id>/accept`, `POST /trades/<id>/reject`, `POST /trades/<id>/cancel`. Anonymous `POST` redirects to exactly `/login` with no `next` parameter; any non-`POST` method returns `405`. | `06-trades.md` |

   Public (never redirect): `/`, browse and category filter, listing detail (read-only, status badges visible), `/register`, `/login`.
19. When an anonymous visitor requests a protected **page** (`GET`), the server responds with a redirect to `/login?next=<requested path>` and does not render the page. Implemented with Django's `login_required` and `LOGIN_URL = "/login"` (so the setting name and the route agree; `redirect_field_name` stays the default `next`).
20. Protected **actions** (like, propose, accept, reject, cancel) are `POST`-only routes. Templates never render their forms or buttons for anonymous visitors; instead the listing detail page shows a `Sign in to like or trade` link to `/login?next=<the current page path>`. If an anonymous `POST` reaches a protected action route anyway (for example a stale tab), the server redirects to `/login` **without** a `next` parameter and the action is not performed. `next` is for `GET` pages only: a post-login `GET` on a `POST`-only URL would return `405`, so the action path must never be used as `next`. After signing in, the user lands on `/` per requirement 7.
21. `next` is only honoured when Django's `url_has_allowed_host_and_scheme` accepts it for the current host (a relative path on this site). An absolute URL, a different host, or a non-`http(s)` scheme is ignored and the user lands on `/`.

## Acceptance criteria

### Login

- **Given** an anonymous visitor, **when** they open `/login`, **then** a form with Email and Password is shown, with a link to `/register`.
- **Given** a registered user with email `alice@example.com` and a correct password, **when** they submit the form, **then** a session cookie is set, `request.user` is authenticated on the next request, and they are redirected to `/`.
- **Given** the same user, **when** they submit `  Alice@Example.COM ` and the correct password, **then** login succeeds exactly as with the normalized email.
- **Given** a registered email and a wrong password, **when** the form is submitted, **then** the page re-renders with `Invalid email or password.`, the email field keeps its value, the password field is empty, and no session is created.
- **Given** an email that is not registered, **when** the form is submitted, **then** the response is indistinguishable from the wrong-password case (same status code, same message, same form state).
- **Given** a user whose account has `is_active = False`, **when** they submit correct credentials, **then** the response is the same generic `Invalid email or password.` and no session is created.
- **Given** an empty email or empty password, **when** the form is submitted, **then** an error is shown on each empty field, no lookup is attempted, and no session is created.
- **Given** an anonymous visitor who arrived at `/login?next=/listings/new`, **when** they sign in successfully, **then** they are redirected to `/listings/new` (path shown as an example; the real path comes from `03-listings.md`).
- **Given** `next=https://evil.example/` or `next=//evil.example/`, **when** the visitor signs in successfully, **then** `next` is ignored and they are redirected to `/`.
- **Given** an already logged-in user, **when** they open `GET /login`, **then** they are redirected to `/` and the form is not shown.
- **Given** a `POST /login` without a valid CSRF token, **when** it reaches the server, **then** it is rejected and no session is created.
- **Given** a successful login, **when** the session key before and after login are compared, **then** they differ (session fixation protection).

### Logout

- **Given** a logged-in user, **when** they submit the `Logout` form (`POST /logout`), **then** the server-side session is flushed, the next request is anonymous, and they are redirected to `/`.
- **Given** a logged-in user, **when** a `GET /logout` is made, **then** the response is `405` and the user is still logged in.
- **Given** a logged-in user, **when** a `POST /logout` is made without a valid CSRF token, **then** it is rejected and the user is still logged in.
- **Given** an anonymous visitor, **when** they `POST /logout`, **then** they are redirected to `/` with no error.
- **Given** a logged-in user, **when** any page using the base layout is rendered, **then** it shows their `display_name` and a `Logout` button, and no `Sign in` / `Register` links.
- **Given** an anonymous visitor, **when** any page using the base layout is rendered, **then** it shows `Sign in` and `Register` links and no `Logout` button.

### Redirecting anonymous visitors

- **Given** an anonymous visitor, **when** they `GET` the create-listing page, the edit page of any listing, or the Matches page, **then** they are redirected to `/login?next=<that path>` and the page body is not rendered.
- **Given** an anonymous visitor, **when** they `POST` to the like route or any trade action route, **then** they are redirected to `/login` with no `next` parameter, and no `Like`, `Match`, or `Trade` row is created or changed and no `Item.status` changes.
- **Given** an anonymous visitor, **when** they open `/`, a category-filtered browse page, a listing detail page, `/register`, or `/login`, **then** the page is served normally with no redirect.
- **Given** an anonymous visitor viewing a listing detail page, **when** the page renders, **then** no like or trade form is present and a `Sign in to like or trade` link to `/login?next=<detail path>` is shown instead.

## Data and business rules

- **Model:** `User` from [00-architecture.md](00-architecture.md): custom `User(AbstractUser)` in `accounts`, `USERNAME_FIELD = "email"`, `AUTH_USER_MODEL = "accounts.User"` set before the first migration. No new model or field is added by this spec. The only `User` fields read here are `email`, `password` (hash), `display_name` (header), and Django's `is_active`.
- **Email normalization on login** is identical to registration: trim surrounding whitespace, lowercase the full address, then look up by the stored (already normalized) value. Login never creates or modifies a `User` row.
- **Generic failure message.** Unknown email, wrong password, and inactive account all produce the same `Invalid email or password.` non-field error with the same response status and form state. The login form must not reveal whether an email is registered. (This is deliberately stricter than registration's `An account with this email already exists.`, which the registration spec accepts for the demo; login is where guessing accounts would otherwise be cheapest.)
- **Passwords** are verified with Django's password hasher via `authenticate()`; plaintext is never stored, logged, or written to the session. Only the user id and auth hash that Django's session auth needs are stored in the session.
- **Session cookie** is Django's `django.contrib.sessions` cookie (`sessionid`) with the database session backend. Settings: `HttpOnly` on (Django default), `SameSite=Lax` (Django default), `SESSION_COOKIE_SECURE = False` because the demo runs on `http://localhost` with no TLS. Session lifetime is Django's default (`SESSION_COOKIE_AGE`, two weeks; not browser-close); see Open question 3.
- **Session fixation.** Django's `login()` rotates the session key on every successful login; this spec relies on that and does not add anything.
- **Logout** uses Django's `logout()`, which flushes the session on the server and expires the cookie. It is `POST` only with CSRF so a cross-site `<img>` or link cannot sign a user out.
- **CSRF** is required on both forms (`CsrfViewMiddleware` and `{% csrf_token %}`), as in registration.
- **Access rule** (product-wide, from [00-overview.md](00-overview.md)): browse is public; list, like, and trade require login. Enforcement is in the view layer (`login_required`) with `LOGIN_URL = "/login"`. Being logged in is a precondition the trade service also checks (architecture: "the actor is logged in"), but the redirect behaviour is a view concern defined here.
- **`next` safety.** The safe-`next` check is Django's `url_has_allowed_host_and_scheme(next, allowed_hosts={request.get_host()}, require_https=request.is_secure())`. Only values it accepts (relative same-host paths) are honoured; anything else falls back to `/`. `next` is passed through the login form as a hidden field so it survives a failed attempt.
- **`next` is for `GET` pages only.** Anonymous `GET` of a protected page redirects to `/login?next=<path>`. Anonymous `POST` to a protected action route (like, propose, accept, reject, cancel) redirects to `/login` **without** `next`, because a post-login `GET` on a `POST`-only URL would return `405`. The action is never performed and no row changes. After login the user lands on `/`.
- **No authorization beyond "logged in" is defined here.** Owner-only edit, counterparty-only accept / reject, proposer-only cancel, and "no likes on own items" are enforced in `03-listings.md`, `05-likes-matches.md`, and `06-trades.md`. This spec only answers "is there a user at all?".

## Out of scope

- "Remember me" / configurable session length per user
- Password reset, change password, email verification
- OAuth / social login
- Account lockout, rate limiting, captcha, or login attempt logging
- Two-factor authentication
- Showing "you have been signed out" or "welcome back" flash messages (plan Phase 5 polish; may be added later without changing this spec)
- Multiple sessions management ("sign out everywhere")
- Any API or token authentication; the product is server-rendered only
- Admin site login (Django admin is available to developers but is not a product feature)
- Brief-level exclusions: payments, shipping, chat, image upload, sports category, Neo4j, message brokers, native mobile

## Test cases

Tests live in `accounts/tests/` and use Django's test client. Cases 11–14 need a protected route to exist and are written when `03-listings.md` / `05-likes-matches.md` land, using whatever route those specs define; the assertions are fixed here.

1. **Valid login**: create a user; `POST /login` with the normalized email and correct password. Assert the response redirects to `/`, the client is authenticated (`_auth_user_id` in session matches the user), and a `sessionid` cookie is set.
2. **Normalized email**: same as 1 but with `  Alice@Example.COM `. Assert login succeeds.
3. **Wrong password**: assert `Invalid email or password.` in the non-field errors, status `200`, email prefilled, password empty, client not authenticated.
4. **Unknown email**: assert the response status, error message, and form state are identical to case 3, and the client is not authenticated.
5. **Inactive user**: user with `is_active = False` and correct credentials. Assert the same generic error and no authentication.
6. **Empty fields**: submit with each field empty in turn, and both empty. Assert a field error on each empty field and no authentication.
7. **Safe `next`**: `POST /login?next=/some/relative/path` (or hidden field). Assert redirect to that path.
8. **Unsafe `next`**: `next=https://evil.example/` and `next=//evil.example/`. Assert redirect to `/`.
9. **Already logged in**: log in, then `GET /login`. Assert redirect to `/`.
10. **Session key rotates**: read the session key before login (after a `GET /login` which creates no auth), log in, assert the key differs.
11. **Protected page redirects**: anonymous `GET` of a protected page. Assert `302` to `/login?next=<path>` and that the page template is not rendered.
12. **Protected action redirects and is a no-op**: anonymous `POST` to the like route and to a trade action route. Assert redirect to exactly `/login` (no `next` query parameter), and that counts of `Like`, `Match`, `Trade` and every `Item.status` are unchanged.
13. **Public pages stay public**: anonymous `GET /`, listing detail, `/register`, `/login`. Assert `200`, no redirect.
14. **Anonymous detail page hides actions**: anonymous `GET` of a listing detail. Assert no like / trade form in the body and that the `Sign in to like or trade` link points to `/login?next=<detail path>`.
15. **Logout**: log in, `POST /logout`. Assert redirect to `/`, the client is no longer authenticated, and the previous session key no longer exists in the session store.
16. **Logout is POST-only**: log in, `GET /logout`. Assert `405` and the client is still authenticated.
17. **Logout CSRF**: with CSRF checks enabled in the test client, `POST /logout` without a token. Assert rejection (`403`) and the client is still authenticated.
18. **Anonymous logout**: `POST /logout` without a session. Assert redirect to `/` and no error.
19. **Login CSRF**: with CSRF checks enabled, `POST /login` without a token. Assert `403` and no authentication.
20. **Header state**: render `/` as anonymous and as a logged-in user. Assert `Sign in` / `Register` links appear only for anonymous, and the `display_name` plus a `POST /logout` form appear only when logged in.

## Open questions

1. **Where do users land after login?** Decided: a safe `next` (per `url_has_allowed_host_and_scheme`, set only for anonymous `GET` of a protected page), otherwise `/` (requirements 7, 19–21).
2. **Already logged-in user opens `/login` or `/register`.** Decided: redirect to `/` (same default as the registration spec).
3. **Session lifetime.** Decided: Django defaults (`SESSION_COOKIE_AGE` two weeks; cookie persists across browser restarts).
4. **Logout destination.** Decided: `/`.
5. **Anonymous detail page link text.** Proposed `Sign in to like or trade`. `04-browse.md` owns the detail page and may rename it; only the target (`/login?next=<detail path>`) is fixed here.
