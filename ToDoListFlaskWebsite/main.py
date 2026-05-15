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
  SQLALCHEMY_DATABASE_URI – SQLAlchemy DB connection string; falls back to a local
                  PostgreSQL database named 'todolist'

Running locally:
  python main.py
  → starts a development server at http://127.0.0.1:5000
"""

import os
import smtplib
import ssl
import secrets
import certifi
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, List, Task, SiteLabel
from dotenv import load_dotenv  # dev only — not used in production (Prod/main.py)

load_dotenv()  # loads .env in development; no-op in production

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

# ── Email / SMTP configuration ────────────────────────────────────────────────
# In development these are read from .env via load_dotenv() above.
# In production (Prod/main.py) they come from os.environ set in flask.wsgi.
SMTP_HOST            = os.environ.get('SMTP_HOST', '')
SMTP_PORT            = os.environ.get('SMTP_PORT', 587)
MAIL_SENDER          = os.environ.get('MAIL_SENDER','')
MAIL_LOGIN           = os.environ.get('MAIL_LOGIN', '')
MAIL_PASSWORD        = os.environ.get('MAIL_PASSWORD', '')
# Set SMTP_VERIFY_SSL=false in .env when a local SSL inspector (antivirus/proxy)
# intercepts TLS and presents a self-signed cert. Never disable in production.
SMTP_VERIFY_SSL      = os.environ.get('SMTP_VERIFY_SSL', 'true').lower() != 'false'
TOKEN_TTL_MINUTES    = 30
RESEND_COOLDOWN_SECS = 60

# ── Flask-Login setup ─────────────────────────────────────────────────────────

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login user-loader callback.

    Called automatically by Flask-Login on every authenticated request to
    reload the User object from the database using the ID that was serialised
    into the signed session cookie at login time.

    Args:
        user_id (str): The user's primary key as a string (Flask-Login always
            passes it as a string regardless of the column type).

    Returns:
        User | None: The matching User model instance, or None if the ID is
        not found — Flask-Login will then treat the session as expired and
        redirect the visitor to the login page.
    """
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

    # ── Email confirmation ─────────────────────────────────────────────────────
    'flash_email_not_confirmed': {
        'en': 'Please confirm your email address before logging in.',
        'it': 'Conferma il tuo indirizzo email prima di accedere.',
        'es': 'Confirma tu dirección de correo antes de iniciar sesión.',
    },
    'flash_confirm_invalid': {
        'en': 'This confirmation link has expired or is invalid. Request a new one below.',
        'it': 'Questo link di conferma è scaduto o non è valido. Richiedi un nuovo link.',
        'es': 'Este enlace de confirmación ha expirado o no es válido. Solicita uno nuevo.',
    },
    'flash_confirm_success': {
        'en': 'Email confirmed — you can now log in.',
        'it': 'Email confermata — ora puoi accedere.',
        'es': 'Correo confirmado — ya puedes iniciar sesión.',
    },
    'flash_already_confirmed': {
        'en': 'Your email is already confirmed. Please log in.',
        'it': 'La tua email è già confermata. Accedi.',
        'es': 'Tu correo ya está confirmado. Inicia sesión.',
    },
    'flash_resend_sent': {
        'en': 'Confirmation email sent — check your inbox.',
        'it': 'Email di conferma inviata — controlla la tua casella.',
        'es': 'Correo de confirmación enviado — revisa tu bandeja.',
    },
    'flash_resend_failed': {
        'en': 'Could not send the confirmation email. Please try again.',
        'it': "Impossibile inviare l'email di conferma. Riprova.",
        'es': 'No se pudo enviar el correo de confirmación. Inténtalo de nuevo.',
    },
    'flash_send_failed': {
        'en': 'Account created but the confirmation email could not be sent. Use the button below to resend it.',
        'it': "Account creato ma l'email di conferma non è stata inviata. Usa il pulsante per reinviarla.",
        'es': 'Cuenta creada pero no se pudo enviar el correo. Usa el botón para reenviarlo.',
    },
    'pending_heading':    {'en': 'Check your inbox',  'it': 'Controlla la tua casella', 'es': 'Revisa tu correo'},
    'pending_resend_btn': {'en': 'Resend email',      'it': 'Reinvia email',            'es': 'Reenviar correo'},
    'pending_back_login': {'en': 'back to log in',    'it': 'torna al login',           'es': 'volver al inicio de sesión'},

    'detail_rename_btn':  {'en': 'Rename',  'it': 'Rinomina', 'es': 'Renombrar'},
    'detail_save_btn':    {'en': 'Save',    'it': 'Salva',    'es': 'Guardar'},
    'detail_cancel_btn':  {'en': 'Cancel',  'it': 'Annulla',  'es': 'Cancelar'},
}


def seed_labels():
    """
    Populate the site_labels table with the default translations defined in SEED_LABELS.

    Iterates over every (key, language, value) triple in SEED_LABELS and inserts
    a new SiteLabel row only when no matching (LabelKey, Lang) pair already exists
    in the database.  Rows that are already present are left untouched, so this
    function is safe to call on every startup without overwriting user-edited labels.

    A single db.session.commit() is issued at the end only when at least one new
    row was added, avoiding an unnecessary round-trip on subsequent starts.

    After the DB write (or if nothing changed), all supported languages are loaded
    into _label_cache so that every subsequent request is served from memory.

    Called once inside the ``if __name__ == '__main__'`` block after db.create_all().
    """
    changed = False
    for key, translations in SEED_LABELS.items():
        for lang, value in translations.items():
            if not SiteLabel.query.filter_by(LabelKey=key, Lang=lang).first():
                db.session.add(SiteLabel(LabelKey=key, Lang=lang, LabelValue=value))
                changed = True
    if changed:
        db.session.commit()
    for lang in ('en', 'it', 'es'):
        _load_labels_for_lang(lang)


# Module-level label cache: {lang_code: {LabelKey: LabelValue}}.
# Populated lazily on first use per language (or eagerly by seed_labels at startup).
# Labels are static after seeding, so no invalidation is needed.
_label_cache: dict = {}


def _load_labels_for_lang(lang: str) -> dict:
    """Query the DB for every label of *lang*, store the result in _label_cache, and return it."""
    rows = SiteLabel.query.filter_by(Lang=lang).all()
    _label_cache[lang] = {row.LabelKey: row.LabelValue for row in rows}
    return _label_cache[lang]


def get_label(key, **kwargs):
    """
    Return the label string for the current session language.

    Reads from the in-memory _label_cache (populated once per language).
    Falls back to English if the requested language has no entry for the key.
    Placeholders like {n} or {name} in the value are replaced with kwargs.
    """
    lang = session.get('lang', 'en')
    cache = _label_cache[lang] if lang in _label_cache else _load_labels_for_lang(lang)
    value = cache.get(key)
    if value is None and lang != 'en':
        en_cache = _label_cache['en'] if 'en' in _label_cache else _load_labels_for_lang('en')
        value = en_cache.get(key)
    if value is None:
        value = key
    for k, v in kwargs.items():
        value = value.replace(f'{{{k}}}', str(v))
    return value


@app.context_processor
def inject_labels():
    """
    Inject L (label dict) and current_lang into every template context.

    Reads from the in-memory _label_cache — no database query after the first
    request for each language.  Falls back to an empty dict on unexpected errors.
    Templates access labels via {{ L.some_key }}.
    current_lang is used by the language switcher to mark the active option.
    """
    try:
        lang = session.get('lang', 'en')
        L = _label_cache[lang] if lang in _label_cache else _load_labels_for_lang(lang)
    except Exception:
        lang = 'en'
        L = _label_cache.get('en', {})
    return dict(L=L, current_lang=lang)


# ── Email confirmation helpers ────────────────────────────────────────────────

def _issue_confirmation_token(user) -> str:
    """Generate a fresh token, store it on the user object (caller must commit)."""
    token = secrets.token_urlsafe(32)
    user.ConfirmationToken = token
    user.TokenExpiresAt    = datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)
    return token


def _send_confirmation_email(to_email: str, first_name: str, confirm_url: str) -> None:
    """Send an HTML + plain-text confirmation email via Brevo SMTP relay (STARTTLS port 587)."""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Confirm your Listly account'
    msg['From']    = MAIL_SENDER
    msg['To']      = to_email

    text_body = (
        f"Hi {first_name},\n\n"
        f"Click the link below to confirm your Listly account:\n"
        f"{confirm_url}\n\n"
        f"This link expires in {TOKEN_TTL_MINUTES} minutes.\n\n"
        f"If you did not sign up for Listly, you can ignore this email.\n\n"
        f"— The Listly Team"
    )
    html_body = f"""\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#f9f9f9;margin:0;padding:40px 20px">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
              padding:40px;box-shadow:0 2px 12px rgba(0,0,0,.06)">
    <h2 style="margin:0 0 8px;font-size:22px;color:#1a1a2e">Confirm your email</h2>
    <p style="color:#666;margin:0 0 28px;font-size:15px">Hi {first_name}, welcome to Listly!</p>
    <a href="{confirm_url}"
       style="display:inline-block;padding:13px 28px;background:#6b46ff;color:#fff;
              border-radius:999px;text-decoration:none;font-weight:600;font-size:15px">
      Confirm my email
    </a>
    <p style="color:#999;margin:24px 0 0;font-size:13px">
      This link expires in {TOKEN_TTL_MINUTES} minutes.<br>
      If you did not create a Listly account, ignore this email.
    </p>
  </div>
</body>
</html>"""

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    print(f"[DIAG] SMTP config → HOST={SMTP_HOST!r}  PORT={SMTP_PORT!r}  "
          f"LOGIN={MAIL_LOGIN!r}  SENDER={MAIL_SENDER!r}  TO={to_email!r}  "
          f"VERIFY_SSL={SMTP_VERIFY_SSL!r}")
    ctx = ssl.create_default_context(cafile=certifi.where())
    if not SMTP_VERIFY_SSL:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        print("[DIAG] SSL verification DISABLED (SMTP_VERIFY_SSL=false)")
    print("[DIAG] Connecting to SMTP server…")
    with smtplib.SMTP(SMTP_HOST, int(SMTP_PORT), timeout=15) as smtp:
        print("[DIAG] Connected. Sending EHLO…")
        smtp.ehlo()
        print("[DIAG] Starting TLS…")
        smtp.starttls(context=ctx)
        smtp.ehlo()
        print("[DIAG] Logging in…")
        smtp.login(MAIL_LOGIN, MAIL_PASSWORD)
        print("[DIAG] Sending message…")
        smtp.sendmail(MAIL_SENDER, [to_email], msg.as_string())
        print(f"[DIAG] Message sent successfully to {to_email}")


def _run_email_migration() -> None:
    """Add email-confirmation columns to the users table if they don't exist.

    Dev uses the 'users' table (no prefix); production uses 'tl_users'.
    DEFAULT TRUE so pre-existing rows are not locked out.
    The DO block renames any lowercase columns created by an earlier broken
    migration before attempting the quoted PascalCase ADD COLUMN.
    """
    try:
        db.session.execute(db.text("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='users'
                           AND column_name='email_confirmed') THEN
                    ALTER TABLE users RENAME COLUMN email_confirmed TO "EmailConfirmed";
                END IF;
                IF EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='users'
                           AND column_name='confirmation_token') THEN
                    ALTER TABLE users RENAME COLUMN confirmation_token TO "ConfirmationToken";
                END IF;
                IF EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='users'
                           AND column_name='token_expires_at') THEN
                    ALTER TABLE users RENAME COLUMN token_expires_at TO "TokenExpiresAt";
                END IF;
            END $$;
        """))
        db.session.execute(db.text(
            'ALTER TABLE users '
            'ADD COLUMN IF NOT EXISTS "EmailConfirmed" BOOLEAN NOT NULL DEFAULT TRUE'
        ))
        db.session.execute(db.text(
            'ALTER TABLE users ADD COLUMN IF NOT EXISTS "ConfirmationToken" VARCHAR(128)'
        ))
        db.session.execute(db.text(
            'ALTER TABLE users ADD COLUMN IF NOT EXISTS "TokenExpiresAt" TIMESTAMP'
        ))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        import logging
        logging.error("Email confirmation migration failed: %s", exc)


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
    """
    Marketing / landing page — GET /

    Authenticated users are redirected immediately to their list dashboard so
    they never land on the marketing page again after signing in.
    Unauthenticated visitors receive the index.html landing page.

    Returns:
        Response: Redirect to /lists for authenticated users, or the rendered
        index.html template for guests.
    """
    if current_user.is_authenticated:
        return redirect(url_for('lists'))
    return render_template('index.html')


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User registration — GET / POST /register

    GET:  Renders the registration form.  Already-authenticated users are
          redirected to /lists so they cannot accidentally create a second account.

    POST: Validates the submitted form data in this order:
          1. All four fields (first_name, last_name, email, password) must be
             non-empty after stripping whitespace → flashes 'flash_all_fields'
             and re-renders the form on failure.
          2. Password length must be >= PWD_LENGTH_MIN characters →
             flashes 'flash_pwd_length' (with the limit interpolated) and
             re-renders on failure.
          3. Email must not already exist in the users table →
             flashes 'flash_email_exists' and re-renders on failure.
          On success: hashes the password with Werkzeug's PBKDF2-SHA256, saves
          the new User row, logs the user in immediately via Flask-Login, and
          redirects to /lists with a personalised welcome flash message.

    Returns:
        Response: Redirect to /lists on success or when already authenticated;
        rendered register.html (with pwd_min context variable) on GET or any
        validation failure.
    """
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
            EmailConfirmed=False,
        )
        db.session.add(user)
        db.session.flush()

        token = _issue_confirmation_token(user)
        db.session.commit()

        confirm_url = url_for('confirm_email', token=token, _external=True)
        try:
            _send_confirmation_email(email, first_name, confirm_url)
        except Exception:
            import traceback
            print("[DIAG] *** Email send FAILED ***")
            traceback.print_exc()
            flash(get_label('flash_send_failed'), 'error')

        session['pending_email'] = email
        session['pending_name']  = first_name
        session.pop('last_resend_at', None)
        return redirect(url_for('confirm_pending'))

    return render_template('register.html', pwd_min=PWD_LENGTH_MIN)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login — GET / POST /login

    GET:  Renders the login form.  Already-authenticated users are redirected
          to /lists.

    POST: Looks up the user by email (lowercased for case-insensitive matching)
          and verifies the submitted password against the stored Werkzeug hash
          using check_password_hash().
          On success: logs the user in via Flask-Login and honours the optional
          ``next`` query-string parameter so users land on the page they were
          trying to reach before being redirected to login.  Flask-Login
          validates the next URL to prevent open-redirect attacks.
          On failure: flashes 'flash_invalid_login' — a deliberately vague
          message that does not reveal whether the email or the password was
          wrong (avoids user enumeration).

    Returns:
        Response: Redirect to ``next`` or /lists on success; rendered login.html
        on GET or when credentials are invalid.
    """
    if current_user.is_authenticated:
        return redirect(url_for('lists'))

    if request.method == 'POST':
        email    = request.form.get('email',    '').strip().lower()
        password = request.form.get('password', '')
        user     = User.query.filter_by(EmailAddress=email).first()

        if user and check_password_hash(user.Password, password):
            if not user.EmailConfirmed:
                session['pending_email'] = user.EmailAddress
                session['pending_name']  = user.FirstName
                session.pop('last_resend_at', None)
                flash(get_label('flash_email_not_confirmed'), 'info')
                return redirect(url_for('confirm_pending'))
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('lists'))

        flash(get_label('flash_invalid_login'), 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """
    User logout — GET /logout  (login required)

    Ends the current session by calling Flask-Login's logout_user(), which
    removes the user ID from the signed session cookie.  The @login_required
    decorator ensures unauthenticated requests are redirected to /login before
    this view is ever invoked.

    Returns:
        Response: Redirect to the home page (/).
    """
    logout_user()
    return redirect(url_for('index'))


@app.route('/confirm-pending')
def confirm_pending():
    email = session.get('pending_email')
    if not email:
        return redirect(url_for('register'))
    last_resend_ts = session.get('last_resend_at')
    cooldown_remaining = 0
    if last_resend_ts:
        elapsed = datetime.utcnow().timestamp() - last_resend_ts
        cooldown_remaining = max(0, int(RESEND_COOLDOWN_SECS - elapsed))
    return render_template('confirm_pending.html', email=email, cooldown_remaining=cooldown_remaining)


@app.route('/confirm/<token>')
def confirm_email(token):
    user = User.query.filter_by(ConfirmationToken=token).first()
    if not user or user.TokenExpiresAt is None or user.TokenExpiresAt < datetime.utcnow():
        flash(get_label('flash_confirm_invalid'), 'error')
        return redirect(url_for('login'))
    if user.EmailConfirmed:
        flash(get_label('flash_already_confirmed'), 'info')
        return redirect(url_for('login'))
    user.EmailConfirmed    = True
    user.ConfirmationToken = None
    user.TokenExpiresAt    = None
    db.session.commit()
    session.pop('pending_email',  None)
    session.pop('pending_name',   None)
    session.pop('last_resend_at', None)
    flash(get_label('flash_confirm_success'), 'success')
    return redirect(url_for('login'))


@app.route('/resend-confirmation', methods=['POST'])
def resend_confirmation():
    email = session.get('pending_email')
    if not email:
        return redirect(url_for('register'))
    last_resend_ts = session.get('last_resend_at')
    if last_resend_ts:
        elapsed = datetime.utcnow().timestamp() - last_resend_ts
        if elapsed < RESEND_COOLDOWN_SECS:
            return redirect(url_for('confirm_pending'))
    user = User.query.filter_by(EmailAddress=email).first()
    if not user or user.EmailConfirmed:
        session.pop('pending_email', None)
        return redirect(url_for('login'))
    token = _issue_confirmation_token(user)
    db.session.commit()
    session['last_resend_at'] = datetime.utcnow().timestamp()
    confirm_url = url_for('confirm_email', token=token, _external=True)
    try:
        _send_confirmation_email(email, user.FirstName, confirm_url)
        flash(get_label('flash_resend_sent'), 'success')
    except Exception as _mail_err:
        import logging
        logging.error("Resend confirmation email failed: %s", _mail_err)
        flash(get_label('flash_resend_failed'), 'error')
    return redirect(url_for('confirm_pending'))


# ── Lists ─────────────────────────────────────────────────────────────────────

@app.route('/lists')
@login_required
def lists():
    """
    List dashboard — GET /lists  (login required)

    Fetches every List row owned by the current user, ordered newest-first by
    CreatedAt, and passes them to the lists.html template.  Only the current
    user's lists are ever returned; ownership is enforced by the UserId filter.

    Returns:
        Response: Rendered lists.html with a ``lists`` template variable
        containing the user's List objects in descending CreatedAt order.
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
    Create a new list — POST /lists/new  (login required)

    Reads the ``title`` form field, strips surrounding whitespace, and falls
    back to 'Untitled list' if the result is empty.  Inserts a new List row
    owned by the current user, commits, and redirects straight to the new
    list's detail page so the user can start adding tasks immediately.

    Returns:
        Response: Redirect to /lists/<new_list_id>.
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
    List detail page — GET /lists/<list_id>  (login required)

    Loads the requested List, enforcing ownership so that users cannot view
    each other's lists even if they guess a valid list_id.  Uses
    first_or_404() which returns a 404 response when the list does not exist
    *or* when it belongs to a different user — preventing information
    disclosure across accounts.

    Args:
        list_id (int): Primary key of the List to display, taken from the URL.

    Returns:
        Response: Rendered list_detail.html with ``todo_list`` in the template
        context.  404 if the list is not found or is owned by another user.
    """
    todo_list = List.query.filter_by(
        ListId=list_id, UserId=current_user.UserId
    ).first_or_404()
    return render_template('list_detail.html', todo_list=todo_list)


@app.route('/lists/<int:list_id>/rename', methods=['POST'])
@login_required
def rename_list(list_id):
    """
    Rename a list — POST /lists/<list_id>/rename  (login required)

    Reads the ``title`` form field and, if non-empty after stripping whitespace,
    updates the list's Title and commits.  A blank title is silently ignored so
    the existing title is preserved without any error message.  Ownership is
    enforced via first_or_404 (same pattern as list_detail).

    Args:
        list_id (int): Primary key of the List to rename, taken from the URL.

    Returns:
        Response: Redirect to /lists/<list_id> after the rename (or no-op).
        404 if the list is not found or is owned by another user.
    """
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
    """
    Delete a list — POST /lists/<list_id>/delete  (login required)

    Removes the List row after verifying ownership with first_or_404.  All
    associated Task rows are deleted automatically via the cascade rule defined
    in models.py, so no separate Task deletion is needed here.  Flashes a
    localised confirmation message and redirects back to the dashboard.

    Args:
        list_id (int): Primary key of the List to delete, taken from the URL.

    Returns:
        Response: Redirect to /lists after deletion.
        404 if the list is not found or is owned by another user.
    """
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
    """
    Add a task to a list — POST /lists/<list_id>/tasks/add  (login required)

    First verifies that the target list exists and belongs to the current user
    (first_or_404) so no task can be injected into another user's list.  Then
    reads the ``task_text`` form field; if non-empty after stripping whitespace
    a new Task row is inserted.  Blank submissions are silently ignored — the
    page reloads without adding anything.

    Args:
        list_id (int): Primary key of the parent List, taken from the URL.

    Returns:
        Response: Redirect to /lists/<list_id>.
        404 if the list is not found or is owned by another user.
    """
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
    Toggle a task's completion state — POST /tasks/<task_id>/toggle  (login required)

    Loads the Task by joining through its parent List so ownership can be
    verified in a single query (List.UserId == current_user.UserId).  This
    join-based check prevents a user from toggling tasks that belong to lists
    they do not own, even if they know the task's primary key directly.
    Flips the boolean IsDone column and commits.

    Args:
        task_id (int): Primary key of the Task to toggle, taken from the URL.

    Returns:
        Response: Redirect to /lists/<parent_list_id> after the toggle.
        404 if the task is not found or the owning list belongs to another user.
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
    Delete a task — POST /tasks/<task_id>/delete  (login required)

    Uses the same join-based ownership check as toggle_task to prevent
    cross-account deletions.  The parent list_id is captured before the row
    is deleted so the redirect target URL can still be built after the Task
    object is gone from the session.

    Args:
        task_id (int): Primary key of the Task to delete, taken from the URL.

    Returns:
        Response: Redirect to /lists/<parent_list_id> after deletion.
        404 if the task is not found or the owning list belongs to another user.
    """
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
    """
    Database health check — GET /db-status  (public, no auth required)

    Executes a trivial ``SELECT 1`` via SQLAlchemy to verify that the
    application can reach the configured PostgreSQL database.  Intended for
    uptime monitors, load-balancer health probes, and deployment smoke tests;
    no login is required so external tools can call it without credentials.

    Returns:
        dict: ``{'status': 'ok', 'message': 'Database connection successful'}``
        with HTTP 200 on success.
        dict: ``{'status': 'error', 'message': <exception text>}`` with HTTP
        500 if the database is unreachable or the query fails.
    """
    try:
        db.session.execute(db.text('SELECT 1'))
        return {'status': 'ok', 'message': 'Database connection successful'}
    except Exception as exc:
        return {'status': 'error', 'message': str(exc)}, 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_labels()
        _run_email_migration()
    app.run(debug=True)
