"""
main.py
-------
Entry point for the Listly Flask web application.

Responsibilities:
  - Creates and configures the Flask app instance.
  - Registers all URL routes (Home, Auth, Lists, Tasks, Diagnostics, Language).
  - Wires up Flask-Login for session-based authentication.
  - Manages multi-language support via the site_labels table.

How routes are organised:
  ──────────────────────────────────────────────────────
  Section       URL pattern                  Auth?
  ──────────────────────────────────────────────────────
  Home          /                            no
  Auth          /register, /login, /logout   no (except logout)
  Language      /set-lang/<lang>             no
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
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, List, Task, SiteLabel
from dotenv import load_dotenv

load_dotenv()

# GLOBAL CONFIGURATION
PWD_LENGTH_MIN = 8  # minimum password length requirement for registration

app = Flask(__name__)

# ── App configuration ─────────────────────────────────────────────────────────

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://localhost/todolist'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ── Flask-Login setup ─────────────────────────────────────────────────────────

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── Internationalisation ──────────────────────────────────────────────────────
# All UI labels in the three supported languages.
# Keys prefixed by page (nav_, idx_, reg_, login_, lists_, detail_, flash_).
# {n} and {name} are runtime placeholders replaced by get_label().

SEED_LABELS = {
    # ── Navigation ─────────────────────────────────────────────────────────────
    'nav_my_lists': {'en': 'My Lists',  'it': 'Le mie liste', 'es': 'Mis listas'},
    'nav_logout':   {'en': 'Log out',   'it': 'Esci',         'es': 'Cerrar sesión'},
    'nav_login':    {'en': 'Log in',    'it': 'Accedi',       'es': 'Iniciar sesión'},
    'nav_signup':   {'en': 'Sign up',   'it': 'Registrati',   'es': 'Registrarse'},

    # ── index.html ─────────────────────────────────────────────────────────────
    'idx_eyebrow':      {'en': 'Simple. Fast. Yours.', 'it': 'Semplice. Veloce. Tuo.', 'es': 'Simple. Rápido. Tuyo.'},
    'idx_title_1':      {'en': 'Get it',               'it': 'Fallo',                  'es': 'Hazlo'},
    'idx_title_accent': {'en': 'done',                 'it': 'fatto',                  'es': 'hecho'},
    'idx_title_2':      {'en': 'one list at a time',   'it': 'una lista alla volta',   'es': 'una lista a la vez'},
    'idx_sub': {
        'en': 'Listly keeps your tasks organised in clean, shareable lists. No clutter, no noise — just you and your work.',
        'it': 'Listly mantiene le tue attività organizzate in liste ordinate. Nessun disordine — solo tu e il tuo lavoro.',
        'es': 'Listly mantiene tus tareas organizadas en listas limpias. Sin desorden — solo tú y tu trabajo.',
    },
    'idx_cta_start':   {'en': 'Start for free', 'it': 'Inizia gratis',  'es': 'Empieza gratis'},
    'idx_cta_login':   {'en': 'Log in',          'it': 'Accedi',         'es': 'Iniciar sesión'},
    'idx_feat1_title': {'en': 'Multiple Lists',  'it': 'Liste multiple', 'es': 'Múltiples listas'},
    'idx_feat1_desc': {
        'en': 'Create as many lists as you need — work, home, shopping, ideas.',
        'it': 'Crea tutte le liste che vuoi — lavoro, casa, spesa, idee.',
        'es': 'Crea tantas listas como necesites — trabajo, hogar, compras, ideas.',
    },
    'idx_feat2_title': {'en': 'Track Progress',    'it': 'Monitora i progressi', 'es': 'Seguimiento del progreso'},
    'idx_feat2_desc': {
        'en': "Check off tasks as you go. See how much you've accomplished at a glance.",
        'it': "Spunta le attività man mano. Vedi i tuoi progressi in un colpo d'occhio.",
        'es': 'Marca las tareas completadas. Ve cuánto has logrado de un vistazo.',
    },
    'idx_feat3_title': {'en': 'Always in Sync',   'it': 'Sempre sincronizzato', 'es': 'Siempre sincronizado'},
    'idx_feat3_desc': {
        'en': 'Your data lives in a PostgreSQL database — available everywhere, every time.',
        'it': 'I tuoi dati sono in un database PostgreSQL — disponibili ovunque, sempre.',
        'es': 'Tus datos viven en una base de datos PostgreSQL — disponibles en todas partes, siempre.',
    },

    # ── register.html ──────────────────────────────────────────────────────────
    'reg_back':         {'en': 'Back to home',     'it': 'Torna alla home',        'es': 'Volver al inicio'},
    'reg_heading':      {'en': 'Create account',   'it': 'Crea account',           'es': 'Crear cuenta'},
    'reg_sub':          {'en': 'Already have one?','it': 'Hai già un account?',    'es': '¿Ya tienes una cuenta?'},
    'reg_sub_link':     {'en': 'Log in instead',   'it': 'Accedi',                 'es': 'Inicia sesión'},
    'reg_first_name':   {'en': 'First name',        'it': 'Nome',                  'es': 'Nombre'},
    'reg_last_name':    {'en': 'Last name',         'it': 'Cognome',               'es': 'Apellido'},
    'reg_email':        {'en': 'Email address',     'it': 'Indirizzo email',        'es': 'Correo electrónico'},
    'reg_password':     {'en': 'Password',          'it': 'Password',              'es': 'Contraseña'},
    'reg_pwd_hint':     {'en': 'Min. {n} characters', 'it': 'Min. {n} caratteri', 'es': 'Mín. {n} caracteres'},
    'reg_pwd_error': {
        'en': 'Password must be at least {n} characters long.',
        'it': 'La password deve avere almeno {n} caratteri.',
        'es': 'La contraseña debe tener al menos {n} caracteres.',
    },
    'reg_submit':       {'en': 'Create account',   'it': 'Crea account',           'es': 'Crear cuenta'},
    'reg_brand_pre':    {'en': 'Tiny',             'it': 'Piccole',                'es': 'Pequeñas'},
    'reg_brand_accent': {'en': 'lists',            'it': 'liste',                  'es': 'listas'},
    'reg_brand_suf':    {'en': 'big results',      'it': 'grandi risultati',       'es': 'grandes resultados'},
    'reg_brand_sub': {
        'en': 'Create your free account in seconds. No credit card, no spam — just organised, focused work.',
        'it': 'Crea il tuo account gratuito in pochi secondi. Nessuna carta di credito, nessuno spam.',
        'es': 'Crea tu cuenta gratuita en segundos. Sin tarjeta de crédito, sin spam.',
    },
    'reg_pill1': {'en': 'Free forever', 'it': 'Sempre gratis',      'es': 'Gratis para siempre'},
    'reg_pill2': {'en': 'No ads',       'it': 'Nessuna pubblicità', 'es': 'Sin anuncios'},
    'reg_pill3': {'en': 'Secure',       'it': 'Sicuro',             'es': 'Seguro'},

    # ── login.html ─────────────────────────────────────────────────────────────
    'login_back':        {'en': 'Back to home',    'it': 'Torna alla home',           'es': 'Volver al inicio'},
    'login_heading':     {'en': 'Log in',           'it': 'Accedi',                    'es': 'Iniciar sesión'},
    'login_sub':         {'en': 'No account?',      'it': 'Non hai un account?',       'es': '¿No tienes cuenta?'},
    'login_sub_link':    {'en': 'Sign up for free', 'it': 'Registrati gratuitamente',  'es': 'Regístrate gratis'},
    'login_email':       {'en': 'Email address',    'it': 'Indirizzo email',            'es': 'Correo electrónico'},
    'login_password':    {'en': 'Password',         'it': 'Password',                  'es': 'Contraseña'},
    'login_submit':      {'en': 'Log in',           'it': 'Accedi',                    'es': 'Iniciar sesión'},
    'login_brand_line1': {'en': 'Welcome back',     'it': 'Bentornato',                'es': 'Bienvenido'},
    'login_brand_line2': {'en': 'again',            'it': 'di nuovo',                  'es': 'de nuevo'},
    'login_brand_sub': {
        'en': 'Log in to pick up exactly where you left off. Your lists are waiting.',
        'it': 'Accedi per riprendere esattamente da dove hai lasciato. Le tue liste ti aspettano.',
        'es': 'Inicia sesión para retomar exactamente donde lo dejaste. Tus listas están esperando.',
    },
    'login_pill1': {'en': 'Multiple lists', 'it': 'Liste multiple',        'es': 'Múltiples listas'},
    'login_pill2': {'en': 'Task tracking',  'it': 'Tracciamento attività', 'es': 'Seguimiento de tareas'},
    'login_pill3': {'en': 'Always in sync', 'it': 'Sempre sincronizzato',  'es': 'Siempre sincronizado'},

    # ── lists.html ─────────────────────────────────────────────────────────────
    'lists_headline':        {'en': 'My Lists',       'it': 'Le mie liste',      'es': 'Mis listas'},
    'lists_new_placeholder': {'en': 'New list name…', 'it': 'Nome nuova lista…', 'es': 'Nombre de nueva lista…'},
    'lists_create_btn':      {'en': 'Create',         'it': 'Crea',              'es': 'Crear'},
    'lists_badge_empty':     {'en': 'Empty',          'it': 'Vuota',             'es': 'Vacía'},
    'lists_badge_done':      {'en': 'All done',       'it': 'Tutto fatto',       'es': 'Todo hecho'},
    'lists_empty_title':     {'en': 'No lists yet',   'it': 'Nessuna lista',     'es': 'Sin listas'},
    'lists_empty_sub': {
        'en': 'Type a name above and hit Create to get started.',
        'it': 'Digita un nome sopra e premi Crea per iniziare.',
        'es': 'Escribe un nombre arriba y pulsa Crear para empezar.',
    },
    'confirm_delete_pre': {'en': 'Delete list "',        'it': 'Eliminare la lista "', 'es': '¿Eliminar la lista "'},
    'confirm_delete_suf': {'en': '"?',                   'it': '"?',                   'es': '"?'},

    # ── list_detail.html ───────────────────────────────────────────────────────
    'detail_all_lists':     {'en': 'All lists',   'it': 'Tutte le liste',  'es': 'Todas las listas'},
    'detail_task_singular': {'en': 'task',        'it': 'attività',        'es': 'tarea'},
    'detail_task_plural':   {'en': 'tasks',       'it': 'attività',        'es': 'tareas'},
    'detail_progress':      {'en': 'Progress',    'it': 'Progressi',       'es': 'Progreso'},
    'detail_delete_list':   {'en': 'Delete list', 'it': 'Elimina lista',   'es': 'Eliminar lista'},
    'detail_empty': {
        'en': 'No tasks yet — add one below.',
        'it': 'Nessuna attività — aggiungine una sotto.',
        'es': 'Sin tareas — agrega una abajo.',
    },
    'detail_add_placeholder': {'en': 'Add a task…',   'it': "Aggiungi un'attività…", 'es': 'Agrega una tarea…'},
    'detail_mark_done':       {'en': 'Mark done',      'it': 'Segna come fatto',      'es': 'Marcar hecho'},
    'detail_mark_undone':     {'en': 'Mark undone',    'it': 'Segna come non fatto',  'es': 'Marcar sin hacer'},
    'detail_confirm_delete': {
        'en': 'Delete this list and all its tasks?',
        'it': 'Eliminare questa lista e tutte le sue attività?',
        'es': '¿Eliminar esta lista y todas sus tareas?',
    },

    # ── Flash messages ─────────────────────────────────────────────────────────
    'flash_all_fields': {
        'en': 'All fields are required.',
        'it': 'Tutti i campi sono obbligatori.',
        'es': 'Todos los campos son obligatorios.',
    },
    'flash_pwd_length': {
        'en': 'Password must be at least {n} characters.',
        'it': 'La password deve avere almeno {n} caratteri.',
        'es': 'La contraseña debe tener al menos {n} caracteres.',
    },
    'flash_email_exists': {
        'en': 'An account with this email already exists.',
        'it': 'Esiste già un account con questa email.',
        'es': 'Ya existe una cuenta con este correo.',
    },
    'flash_invalid_login': {
        'en': 'Invalid email or password.',
        'it': 'Email o password non validi.',
        'es': 'Correo o contraseña inválidos.',
    },
    'flash_welcome': {
        'en': 'Welcome, {name}!',
        'it': 'Benvenuto, {name}!',
        'es': '¡Bienvenido, {name}!',
    },
    'flash_list_deleted': {
        'en': 'List deleted.',
        'it': 'Lista eliminata.',
        'es': 'Lista eliminada.',
    },
    'flash_list_renamed': {
        'en': 'List renamed.',
        'it': 'Lista rinominata.',
        'es': 'Lista renombrada.',
    },
    'detail_rename_btn':  {'en': 'Rename',  'it': 'Rinomina', 'es': 'Renombrar'},
    'detail_save_btn':    {'en': 'Save',    'it': 'Salva',    'es': 'Guardar'},
    'detail_cancel_btn':  {'en': 'Cancel',  'it': 'Annulla',  'es': 'Cancelar'},
}


def seed_labels():
    """Insert missing rows into site_labels; rows that already exist are skipped."""
    changed = False
    for key, translations in SEED_LABELS.items():
        for lang, value in translations.items():
            if not SiteLabel.query.filter_by(LabelKey=key, Lang=lang).first():
                db.session.add(SiteLabel(LabelKey=key, Lang=lang, LabelValue=value))
                changed = True
    if changed:
        db.session.commit()


def get_label(key, **kwargs):
    """
    Return the label string for the current session language.

    Falls back to English if the requested language has no entry.
    Placeholders like {n} or {name} in the value are replaced with kwargs.
    """
    lang = session.get('lang', 'en')
    lbl = (
        SiteLabel.query.filter_by(LabelKey=key, Lang=lang).first()
        or SiteLabel.query.filter_by(LabelKey=key, Lang='en').first()
    )
    value = lbl.LabelValue if lbl else key
    for k, v in kwargs.items():
        value = value.replace(f'{{{k}}}', str(v))
    return value


@app.context_processor
def inject_labels():
    """
    Inject L (label dict) and current_lang into every template context.

    Templates access labels via {{ L.some_key }}.
    current_lang is used by the language switcher to mark the active option.
    """
    try:
        lang = session.get('lang', 'en')
        rows = SiteLabel.query.filter_by(Lang=lang).all()
        L = {row.LabelKey: row.LabelValue for row in rows}
    except Exception:
        lang = 'en'
        L = {}
    return dict(L=L, current_lang=lang)


# ── Language switcher ─────────────────────────────────────────────────────────

@app.route('/set-lang/<lang>')
def set_lang(lang):
    """
    Store the chosen language in the session and redirect back to the referrer.

    Accepts only the three supported language codes; unknown values are ignored.
    """
    if lang in ('en', 'it', 'es'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))


# ── Home ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('lists'))
    return render_template('index.html')


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('lists'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name  = request.form.get('last_name',  '').strip()
        email      = request.form.get('email',      '').strip().lower()
        password   = request.form.get('password',   '')

        if not all([first_name, last_name, email, password]):
            flash(get_label('flash_all_fields'), 'error')
            return render_template('register.html', pwd_min=PWD_LENGTH_MIN)

        if len(password) < PWD_LENGTH_MIN:
            flash(get_label('flash_pwd_length', n=PWD_LENGTH_MIN), 'error')
            return render_template('register.html', pwd_min=PWD_LENGTH_MIN)

        if User.query.filter_by(EmailAddress=email).first():
            flash(get_label('flash_email_exists'), 'error')
            return render_template('register.html', pwd_min=PWD_LENGTH_MIN)

        user = User(
            FirstName=first_name,
            LastName=last_name,
            EmailAddress=email,
            Password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(get_label('flash_welcome', name=first_name), 'success')
        return redirect(url_for('lists'))

    return render_template('register.html', pwd_min=PWD_LENGTH_MIN)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('lists'))

    if request.method == 'POST':
        email    = request.form.get('email',    '').strip().lower()
        password = request.form.get('password', '')
        user     = User.query.filter_by(EmailAddress=email).first()

        if user and check_password_hash(user.Password, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('lists'))

        flash(get_label('flash_invalid_login'), 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# ── Lists ─────────────────────────────────────────────────────────────────────

@app.route('/lists')
@login_required
def lists():
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
    title = request.form.get('title', '').strip() or 'Untitled list'
    todo_list = List(UserId=current_user.UserId, Title=title)
    db.session.add(todo_list)
    db.session.commit()
    return redirect(url_for('list_detail', list_id=todo_list.ListId))


@app.route('/lists/<int:list_id>')
@login_required
def list_detail(list_id):
    todo_list = List.query.filter_by(
        ListId=list_id, UserId=current_user.UserId
    ).first_or_404()
    return render_template('list_detail.html', todo_list=todo_list)


@app.route('/lists/<int:list_id>/rename', methods=['POST'])
@login_required
def rename_list(list_id):
    todo_list = List.query.filter_by(
        ListId=list_id, UserId=current_user.UserId
    ).first_or_404()
    new_title = request.form.get('title', '').strip()
    if new_title:
        todo_list.Title = new_title
        db.session.commit()
        flash(get_label('flash_list_renamed'), 'success')
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/lists/<int:list_id>/delete', methods=['POST'])
@login_required
def delete_list(list_id):
    todo_list = List.query.filter_by(
        ListId=list_id, UserId=current_user.UserId
    ).first_or_404()
    db.session.delete(todo_list)
    db.session.commit()
    flash(get_label('flash_list_deleted'), 'info')
    return redirect(url_for('lists'))


# ── Tasks ─────────────────────────────────────────────────────────────────────

@app.route('/lists/<int:list_id>/tasks/add', methods=['POST'])
@login_required
def add_task(list_id):
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
    task = (
        Task.query.join(List)
        .filter(Task.TaskId == task_id, List.UserId == current_user.UserId)
        .first_or_404()
    )
    list_id = task.ListId
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('list_detail', list_id=list_id))


# ── Diagnostics ───────────────────────────────────────────────────────────────

@app.route('/db-status')
def db_status():
    try:
        db.session.execute(db.text('SELECT 1'))
        return {'status': 'ok', 'message': 'Database connection successful'}
    except Exception as exc:
        return {'status': 'error', 'message': str(exc)}, 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()   # create tables if they don't exist yet
        seed_labels()     # insert missing i18n labels
    app.run(debug=True)
