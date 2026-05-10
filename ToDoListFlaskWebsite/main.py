"""
main.py
-------
Entry point for the Listly Flask web application.

Responsibilities:
  - Creates and configures the Flask app instance.
  - Registers all URL routes (Home, Auth, Lists, Tasks, Diagnostics).
  - Wires up Flask-Login for session-based authentication.

How routes are organised:
  ──────────────────────────────────────────────────────
  Section       URL pattern                  Auth?
  ──────────────────────────────────────────────────────
  Home          /                            no
  Auth          /register, /login, /logout   no (except logout)
  Lists         /lists, /lists/new, ...      yes
  Tasks         /tasks/<id>/...              yes
  Diagnostics   /db-status                   no
  ──────────────────────────────────────────────────────

Configuration is read from environment variables so the same code works in
both development and production without any code changes:

  SECRET_KEY    – signs the session cookie (keep this secret in production!)
  DATABASE_URL  – SQLAlchemy DB connection string; falls back to a local
                  PostgreSQL database named 'todolist'

Running locally:
  python main.py
  → starts a development server at http://127.0.0.1:5000
"""

import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, List, Task
from dotenv import load_dotenv

load_dotenv()  

# GLOBAL CONFIGURATION
PWD_LENGTH_MIN = 8 # minimum password length requirement for registration

app = Flask(__name__)

# ── App configuration ─────────────────────────────────────────────────────────

# SECRET_KEY is used to cryptographically sign the session cookie.
# The default value is fine for local development, but must be changed to a
# long random string in production (e.g. `python -c "import secrets; print(secrets.token_hex())"`)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')

# Full SQLAlchemy connection string. Examples:
#   postgresql://user:password@localhost/todolist   ← PostgreSQL (production)
#   sqlite:///todolist.db                           ← SQLite (quick local test)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://localhost/todolist'
)

# Disable SQLAlchemy's event system for object modifications — we don't use it
# and keeping it on wastes memory
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Attach the SQLAlchemy `db` instance (defined in models.py) to this Flask app
db.init_app(app)

# ── Flask-Login setup ─────────────────────────────────────────────────────────

login_manager = LoginManager(app)

# Name of the route to redirect to when a @login_required page is accessed
# without being logged in (e.g. a guest tries to open /lists directly)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login callback — called automatically on every incoming request.

    Flask-Login reads the user ID from the session cookie and passes it here.
    This function must return the matching User object, or None if not found.
    Returning None effectively logs the user out.
    """
    return User.query.get(int(user_id))


# ── Home ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """
    Landing page (route: '/').

    Behaviour:
      - Logged-in users → redirected straight to their lists dashboard.
      - Guests          → shown the public marketing page (templates/index.html).
    """
    if current_user.is_authenticated:
        return redirect(url_for('lists'))
    return render_template('index.html')


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Registration page (route: '/register').

    GET  → renders the sign-up form (templates/register.html).
    POST → reads the submitted form, validates the data, creates the user,
           logs them in, and redirects to their lists dashboard.

    Validation rules checked in order:
      1. All four fields must be non-empty.
      2. Password must be at least 6 characters long.
      3. Email must not already exist in the database.

    If any validation fails, the form is re-rendered with a flash error message
    so the user can correct their input without losing the page.

    Already-logged-in users are redirected away immediately (they don't need
    to register again).
    """
    if current_user.is_authenticated:
        return redirect(url_for('lists'))

    if request.method == 'POST':
        # .strip() removes accidental leading/trailing whitespace
        # .lower() normalises the email so "User@Example.com" == "user@example.com"
        first_name = request.form.get('first_name', '').strip()
        last_name  = request.form.get('last_name',  '').strip()
        email      = request.form.get('email',      '').strip().lower()
        password   = request.form.get('password',   '')

        # Validate: all fields must be filled in
        if not all([first_name, last_name, email, password]):
            flash('All fields are required.', 'error')
            return render_template('register.html', pwd_min=PWD_LENGTH_MIN)

        # Validate: minimum password length
        if len(password) < PWD_LENGTH_MIN:
            flash(f'Password must be at least {PWD_LENGTH_MIN} characters.', 'error')
            return render_template('register.html', pwd_min=PWD_LENGTH_MIN)

        # Validate: no duplicate accounts for the same email
        if User.query.filter_by(EmailAddress=email).first():
            flash('An account with this email already exists.', 'error')
            return render_template('register.html', pwd_min=PWD_LENGTH_MIN)

        # Create the new user.
        # generate_password_hash() stores the password as a secure hash
        # (e.g. "pbkdf2:sha256:...") so plain-text passwords are never saved.
        user = User(
            FirstName=first_name,
            LastName=last_name,
            EmailAddress=email,
            Password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        # Log in immediately after registration so the user doesn't have to
        # fill in the login form right after signing up
        login_user(user)
        flash(f'Welcome, {first_name}!', 'success')
        return redirect(url_for('lists'))

    return render_template('register.html', pwd_min=PWD_LENGTH_MIN)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page (route: '/login').

    GET  → renders the login form (templates/login.html).
    POST → looks up the user by email, verifies the password hash, and logs
           them in on success; shows a generic error message on failure.

    On success, the user is redirected to:
      - the 'next' query-string parameter if present (Flask-Login adds this
        automatically when redirecting a guest away from a protected page), OR
      - the lists dashboard.

    The error message intentionally does not say whether the email or the
    password was wrong — revealing which field failed helps attackers enumerate
    valid accounts (a security best practice).

    Already-logged-in users are redirected away immediately.
    """
    if current_user.is_authenticated:
        return redirect(url_for('lists'))

    if request.method == 'POST':
        email    = request.form.get('email',    '').strip().lower()
        password = request.form.get('password', '')
        user     = User.query.filter_by(EmailAddress=email).first()

        # check_password_hash() safely compares the submitted password against
        # the stored hash without exposing the original password
        if user and check_password_hash(user.Password, password):
            login_user(user)
            # `next` is set by Flask-Login when it redirects a guest to /login
            next_page = request.args.get('next')
            return redirect(next_page or url_for('lists'))

        flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """
    Logs the current user out (route: '/logout').

    Clears the session and redirects to the home/landing page.
    The @login_required decorator ensures only authenticated users can call
    this route (guests are redirected to /login instead).
    """
    logout_user()
    return redirect(url_for('index'))


# ── Lists ─────────────────────────────────────────────────────────────────────

@app.route('/lists')
@login_required
def lists():
    """
    Lists dashboard (route: '/lists').

    Shows all to-do lists that belong to the currently logged-in user,
    ordered newest-first so the most recently created list is at the top.

    Template context passed to lists.html:
      lists – list of List objects owned by current_user
    """
    user_lists = (
        List.query
        .filter_by(UserId=current_user.UserId)
        .order_by(List.CreatedAt.desc())
        .all()
    )
    return render_template('lists.html', lists=user_lists)


@app.route('/lists/new', methods=['POST'])
@login_required
def new_list():
    """
    Creates a new to-do list (route: POST '/lists/new').

    Only accepts POST requests. The title comes from the inline form on
    the lists dashboard. If the user submits a blank title, it falls back to
    'Untitled list' rather than rejecting the request.

    After creating the list, the user is redirected to its detail page so they
    can start adding tasks immediately.
    """
    title = request.form.get('title', '').strip() or 'Untitled list'
    todo_list = List(UserId=current_user.UserId, Title=title)
    db.session.add(todo_list)
    db.session.commit()
    return redirect(url_for('list_detail', list_id=todo_list.ListId))


@app.route('/lists/<int:list_id>')
@login_required
def list_detail(list_id):
    """
    Detail page for a single to-do list (route: '/lists/<list_id>').

    URL parameter:
      list_id (int) – primary key of the list to display

    Security: the query filters on BOTH ListId AND UserId. This means a user
    cannot view another user's list by guessing a different list_id in the URL
    — they will get a 404 instead of someone else's data.

    Template context passed to list_detail.html:
      todo_list – the List object (tasks are loaded automatically via the
                  SQLAlchemy relationship defined in models.py)
    """
    todo_list = List.query.filter_by(
        ListId=list_id, UserId=current_user.UserId
    ).first_or_404()
    return render_template('list_detail.html', todo_list=todo_list)


@app.route('/lists/<int:list_id>/delete', methods=['POST'])
@login_required
def delete_list(list_id):
    """
    Deletes a to-do list and all of its tasks (route: POST '/lists/<list_id>/delete').

    URL parameter:
      list_id (int) – primary key of the list to delete

    Only accepts POST to prevent accidental deletion if someone opens the URL
    in a browser (GET requests should never have side effects).

    The cascade delete defined on the List model in models.py automatically
    removes all child Tasks when the List is deleted, so no extra queries are
    needed here.

    Returns 404 if the list does not exist or belongs to a different user.
    """
    todo_list = List.query.filter_by(
        ListId=list_id, UserId=current_user.UserId
    ).first_or_404()
    db.session.delete(todo_list)
    db.session.commit()
    flash('List deleted.', 'info')
    return redirect(url_for('lists'))


# ── Tasks ─────────────────────────────────────────────────────────────────────

@app.route('/lists/<int:list_id>/tasks/add', methods=['POST'])
@login_required
def add_task(list_id):
    """
    Adds a new task to a list (route: POST '/lists/<list_id>/tasks/add').

    URL parameter:
      list_id (int) – primary key of the list that will own the new task

    The list ownership is verified before inserting the task; returns 404 if
    the list does not belong to the current user.

    Blank task text is silently ignored (no error shown) so accidental empty
    form submissions do not create meaningless tasks.
    """
    # Ownership check: raises 404 if list_id doesn't belong to current_user
    List.query.filter_by(
        ListId=list_id, UserId=current_user.UserId
    ).first_or_404()

    task_text = request.form.get('task_text', '').strip()
    if task_text:
        db.session.add(Task(ListId=list_id, TaskText=task_text))
        db.session.commit()
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    """
    Toggles a task's completion state (route: POST '/tasks/<task_id>/toggle').

    URL parameter:
      task_id (int) – primary key of the task to toggle

    Security: the query JOINs Task → List and checks List.UserId so that a
    user cannot toggle tasks belonging to another user's list.

    The IsDone field is flipped: True → False, False → True.
    """
    task = (
        Task.query.join(List)
        .filter(Task.TaskId == task_id, List.UserId == current_user.UserId)
        .first_or_404()
    )
    task.IsDone = not task.IsDone
    db.session.commit()
    return redirect(url_for('list_detail', list_id=task.ListId))


@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    """
    Deletes a single task (route: POST '/tasks/<task_id>/delete').

    URL parameter:
      task_id (int) – primary key of the task to delete

    Security: the query JOINs Task → List and checks List.UserId so that a
    user cannot delete tasks belonging to another user's list.

    The list_id is saved before deletion so the redirect back to the list
    detail page still works after the task object is removed from the session.
    """
    task = (
        Task.query.join(List)
        .filter(Task.TaskId == task_id, List.UserId == current_user.UserId)
        .first_or_404()
    )
    list_id = task.ListId  # save before deleting; task.ListId is unavailable after db.session.delete()
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('list_detail', list_id=list_id))


# ── Diagnostics ───────────────────────────────────────────────────────────────

@app.route('/db-status')
def db_status():
    """
    Database health-check endpoint (route: GET '/db-status').

    Returns a JSON response — no HTML, no login required:
      HTTP 200  →  { "status": "ok",    "message": "Database connection successful" }
      HTTP 500  →  { "status": "error", "message": "<error details>" }

    Flask automatically converts a Python dict return value to a JSON response.

    This route intentionally requires NO login so that:
      - Deployment scripts can poll it before opening the app to users.
      - Monitoring tools (uptime checkers, load balancers) can hit it freely.

    Usage example:
      curl http://localhost:5000/db-status
    """
    try:
        # `SELECT 1` is the lightest possible query — it tests connectivity
        # without reading or writing any application data
        db.session.execute(db.text('SELECT 1'))
        return {'status': 'ok', 'message': 'Database connection successful'}
    except Exception as exc:
        return {'status': 'error', 'message': str(exc)}, 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Create all database tables defined in models.py if they don't exist yet.
    # SQLAlchemy checks each table name and skips ones that are already there,
    # so this is safe to run on every startup.
    with app.app_context():
        db.create_all()
    # debug=True enables the interactive debugger and auto-reloads the server
    # when code changes. NEVER use debug=True in production.
    app.run(debug=True)
