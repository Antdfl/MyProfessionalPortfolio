# ANALYSIS AND DESIGN DOCUMENT

## 1. REQUIREMENTS

Today, you are going to build a todo list website. This is a right of passage for any developer.

You can choose the type of todo list you want to build. It could be as simple as a website where you can list some items and cross them out. Or as complex as a Kanban-style task list like Trello.

Here is a website for inspiration:

https://flask.io/new

 ## 2. FUNCTIONAL ANALYSIS

1. Design and prototype the structure(pages to create) of the website at layout level
2. Specify what are the main website functionalities.
3. Design the database structure.

Other details. We need to use the SQLAlchemy python library so to call a PostreSQL Database to store our data. The table needed will be 3.  

### Database Design 

The table "users" that contains all the data necessary for each user with the fields
(one to many relationship towards the table lists): 
| Column Name  | Data type     |Nullable  |Key          |Notes                    |
| ------------ | ------------- | -------- | ----------- | ----------------------- |
| UserId       | integer       | No       | Primary key |                         | 
| FirstName    | string(100)   | False    |             |                         | 
| LastName     | string(100)   | False    |             |                         | 
| EmailAddress | string(255)   | False    |             |                         | 
| Password     | string(255)   | False    |             |                         | 
| CreatedAt    | DateTime      |          |             | User's Creation date    |


The table "lists" that contains all the lists associated to a user.
(many to 1 relatiosnhip towards the table users):   
| Column Name  | Data type     | Nullable  | Key          | Notes                   |
| ------------ | ------------- | --------- | ------------ | ----------------------- |         
| ListId       | Integer       |  No       |  Primary Key |                         |
| UserId       | Integer       |  False    |  Foreign Key |                         |
| Title        | string(200)   |  False    |              |                         | 
| CreatedAt    | Datetime      |  False    |              | Date of list creation   |


The table "Task" that contains all the task contained in a list
(many to one relationship towards the list table):
| Column Name  | Data type     | Nullable  | Key          | Notes                   |
| ------------ | ------------- | --------- | ------------ | ----------------------- |                   
| TaskId       | Integer       |           | Primary Key  |                         |
| ListId       | Integer       | False     | Foreign Key  |                         |
| TaskText     | string(500)   | False     |              |                         |  
| Isdone       | boolean       | False     |              | Default=False           | 
| CreatedAt    | False         |           |              | Date of task creation   |


### Claude Code Prompt
I have created a website layout with Claude Design to use coupled with Claude. 

**Here's the prompt.**
Create a Flask website keeping into consideration the README.md file present in this folder with the exlusion of test and production parts. These are the istruction at layout level --> Fetch this design file, read its readme, and implement the relevant aspects of the design. https://api.anthropic.com/....


## 3. DESIGN AND IMPLEMENTATION DETAILS

### 3.1 At Code level 
I divided the project into smaller parts:

-  Connect the Flask application with the SQLite database.
-  Create routes to display lists information.
-  Design HTML templates using Bootstrap for a clean UI.
-  Display tasks dynamically using Jinja templating.
-  Add forms for adding new tasks.
-  Implement delete functionality for lists and single tasks.
-  Improve navigation and overall styling.

### 3.2 ADDED UI INTERNATIONALISATION
- All UI labels in the three supported languages.
. Keys prefixed by page (nav_, idx_, reg_, login_, lists_, detail_, flash_).
- {n} and {name} are runtime placeholders replaced by get_label().

Created a new table SiteLabel
| Column Name  | Data type     | Nullable  | Key          | Notes                   |
| ------------ | ------------- | --------- | ------------ | ----------------------- |  
| LabelId      | Integer       | No        | Primary Key  |                         |
| LabelKey     | String(100)   | No        |              |                         |
| Lang         | String(5)     | No        |              |                         |
| LabelValue   | String(1000)  | No        |              |                         |

2. Affected Files
File	Type of change
ToDoListFlaskWebsite/main.py	Backend — new route + i18n labels
ToDoListFlaskWebsite/templates/list_detail.html	Frontend — inline edit UI

3. Backend Changes (main.py)
3.1 New Route
POST /lists/<list_id>/rename
Auth: @login_required — rejects unauthenticated requests.
Ownership check: the list is fetched with both ListId and UserId constraints (first_or_404), preventing one user from renaming another user's list.
Validation: empty or whitespace-only titles are silently discarded; the existing title is preserved.
Response: flashes a localised success message and redirects back to the detail page.
3.2 New i18n Labels
Five new entries added to SEED_LABELS (EN / IT / ES):
flash_list_renamed	Success flash message after rename
detail_rename_btn	Tooltip on the pencil button
detail_save_btn	Submit button label
detail_cancel_btn	Cancel button label
Labels are inserted into the database at startup by seed_labels(), which skips rows that already exist — no migration required.

4. Frontend Changes (list_detail.html)
4.1 Interaction Design
The rename feature follows an inline edit pattern:
The list title is displayed normally inside a .title-wrap container.
A pencil icon button (.rename-btn) is hidden by default and revealed on hover via CSS.
Clicking the pencil hides .title-wrap and shows the .rename-form (a standard <form> with method="POST").
The text input is pre-filled with the current title and immediately focused and selected.
The user either submits (Save) or cancels (Cancel), which restores the title display.
No JavaScript framework is required — the toggle is handled by two plain functions (startRename / cancelRename) that set display styles.
4.2 CSS Added
Class	Purpose
.title-wrap	Flex container for title + pencil
.rename-btn	Pencil trigger; opacity 0 → 1 on hover
.rename-form	Hidden by default; shown inline on activation
.rename-input	Styled to match the < h1 > typographic weight underline-only border to signal editability

5. Security Considerations
The rename endpoint verifies list ownership server-side; the client-side UI is convenience only.
Input is sanitised with .strip() before writing to the database.
The form uses POST (not GET), preventing the new title from appearing in server logs or browser history.
No raw SQL is used; the update goes through SQLAlchemy's ORM, which parameterises all queries.

6. No-Migration Deployment
The schema is unchanged — only the Title column of an existing row is updated. The new SEED_LABELS entries are inserted automatically at startup by seed_labels(). No manual database intervention is needed.

### 3.3 LIST RENAME
1. Objective
Add the ability for authenticated users to rename an existing to-do list directly from the list detail page, without navigating to a separate form.

## 3.4 CACHING LANGUAGE LABELS

To avoid invoking each time the user change the langiage in the drop down list, implemented a cache mechanism, so that all the data-related data is loaded only once. 

- Add a module-level _label_cache dict (keyed by language code)
- Add a _load_labels_for_lang() helper that queries the DB and stores into the cache
- Update seed_labels() to prime the cache for all 3 languages after seeding
- Update get_label() and inject_labels() to read from cache, querying DB only on a cache miss

1. _label_cache: dict = {} (new, after seed_labels) — module-level dict keyed by language code ('en', 'it', 'es'). Lives for the lifetime of the process, so it survives across all requests.

2. _load_labels_for_lang(lang) (new) — the single place that actually queries the DB. It runs SiteLabel.query.filter_by(Lang=lang).all(), builds the {LabelKey: LabelValue} dict, stores it in _label_cache[lang], and returns it. Called at most once per language per process lifetime.

3. seed_labels() — after the existing DB seeding logic, now calls _load_labels_for_lang for all three languages. This pre-warms the cache at startup so the very first request is already served from memory.

4. get_label() — replaced two SiteLabel.query calls with cache lookups. Pattern: _label_cache[lang] if lang in _label_cache else _load_labels_for_lang(lang). Fallback to English uses the same cache-first pattern.

5. inject_labels() — replaced SiteLabel.query.filter_by(Lang=lang).all() with the same cache-first lookup. This context processor runs on every request, so this is where the savings are largest.

Net result: after the first request per language (or after startup if seed_labels() runs), all label lookups are pure Python dict reads with zero DB round-trips.

### 3.5 Test environment
1. Prepare a local Postgres sql Container for local test. Done
2. Test it locally in a development environment. Done

### 3.6 Production release
- After the positive test locally, prepare the folder /vendor to deploy into the Production Linux environment.
- Install the source code into production, make all the settings (.htaccess, environmental variables, flask setup)

### 3.7 EMAIL CONFIRMATION ON REGISTRATION

#### Objective
Require new users to verify their email address before they can log in, preventing fake account creation and ensuring the stored email is reachable.

#### User Flow
1. User fills in the registration form and submits.
2. Account is created with `EmailConfirmed=False` — login is blocked until confirmation.
3. A confirmation email is sent with a tokenised link valid for **30 minutes**.
4. User is redirected to a "Check your inbox" page (`/confirm-pending`).
5. User clicks the link → account is activated → redirected to login with a success message.
6. If the email didn't arrive, a **Resend** button appears after a **60-second cooldown**; resending invalidates the previous link immediately.
7. If a returning (unconfirmed) user tries to log in, they are redirected to the same `/confirm-pending` page.

#### Database Changes (models.py — both dev and prod)
Three new columns added to the `User` model via a safe `ALTER TABLE … ADD COLUMN IF NOT EXISTS` migration that runs at startup:

| Column            | Type         | Default | Notes                                      |
|-------------------|--------------|---------|--------------------------------------------|
| `EmailConfirmed`  | Boolean      | FALSE   | Pre-existing rows defaulted to TRUE so they are not locked out |
| `ConfirmationToken` | String(128) | NULL  | 43-char URL-safe random token; overwritten on each resend |
| `TokenExpiresAt`  | DateTime     | NULL    | now + 30 min; checked server-side at confirmation |

#### New Routes (main.py)
| Route | Method | Description |
|---|---|---|
| `/confirm-pending` | GET | "Check your inbox" page; reads `session['pending_email']` |
| `/confirm/<token>` | GET | Validates token, marks account confirmed, redirects to login |
| `/resend-confirmation` | POST | Issues new token (invalidates old), sends new email, enforces 60s cooldown |

#### Email Delivery
- **SMTP relay:** Brevo (formerly Sendinblue) — 300 emails/day free tier, IP-restricted to the server's outgoing address.
- **Protocol:** STARTTLS on port 587.
- **Sender:** configured via `MAIL_SENDER` environment variable.
- **Credentials:** `MAIL_LOGIN` and `MAIL_PASSWORD` environment variables (set in `flask.wsgi` for production, `.env` for development).

#### Dev vs Production Differences
| Aspect | Development (`main.py`) | Production (`Prod/main.py`) |
|---|---|---|
| Env vars | Loaded from `.env` via `python-dotenv` | Set in `flask.wsgi` before app import |
| DB table | `users` | `tl_users` |
| Template reload | Not forced | `TEMPLATES_AUTO_RELOAD = True` |
| SQLAlchemy C ext | Enabled | Disabled via `DISABLE_SQLALCHEMY_CEXT_RUNTIME=1` |



