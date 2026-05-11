# Deployment Retrospective — Listly (ToDoList Flask Website)

**Author:** Antonio Di Felice  
**Date:** May 2026  
**Environment:** Heliohost shared hosting (Linux x86_64, Python 3.14.2, Apache mod_wsgi)

---

## Project Overview

Listly is a full-stack to-do list web application built with Python/Flask, PostgreSQL and SQLAlchemy ORM. It supports multi-user authentication, per-user task lists, multi-language UI (EN/IT/ES), and is deployed on shared Linux hosting without SSH access, a constraint that shaped every technical decision in this retrospective.

**Tech stack:** Python · Flask · Flask-SQLAlchemy · psycopg2 · Werkzeug · Flask-Login · Jinja2 · PostgreSQL · Apache mod_wsgi

---

## Part 1 — Local Development Environment

### Challenge: PostgreSQL containerisation

Coming from an Oracle background, setting up PostgreSQL in Docker required learning a new paradigm. The key insight is that PostgreSQL follows the principle of least privilege more strictly than Oracle:
a database user must be granted schema-level permissions separately from database-level permissions, especially from PostgreSQL 15 onwards.

**Repeatable setup commands:**

```bash
# 1. Start the container
docker run -p 5432:5432 --name mypostgres_db \
  -e POSTGRES_PASSWORD=<admin_password> \
  -e POSTGRES_USER=adminuser \
  -d postgres

# 2. Create the app database and user (connect as admin)
CREATE DATABASE todolist_app;
CREATE USER app_user WITH PASSWORD '<secure_password>';
GRANT ALL PRIVILEGES ON DATABASE todolist_app TO app_user;

-- PostgreSQL 15+ requires explicit schema grant
\c todolist_app
GRANT ALL ON SCHEMA public TO app_user;
```

**Lesson:** In PostgreSQL, database-level `GRANT` and schema-level `GRANT` are independent.
Omitting the schema grant causes `permission denied for schema public` errors at runtime — a
non-obvious failure mode for developers migrating from Oracle or MySQL.

---

## Part 2 — Production Deployment

The production environment (Heliohost) provided Apache + mod_wsgi with no SSH access, no ability to run `pip` on the server, and no way to install system libraries. This forced a fully offline, vendored
deployment strategy.

### Challenge 1: Offline dependency installation — the vendor folder pattern

Without SSH or internet access on the server, the standard `pip install -r requirements.txt` workflow is impossible. The solution was to **pre-install all dependencies locally into a `vendor/` subfolder**, then upload that folder alongside the application code.

**Key distinction:** `pip download` produces `.whl` archives that still require `pip install` to unpack, this is the wrong tool here. `pip install --target` extracts the packages directly into a folder that Python can import from with a `sys.path` entry.

```bash
# Cross-compile for the server's platform BEFORE uploading
pip install -r Prod/requirements.txt \
  --target Prod/vendor \
  --platform manylinux2014_x86_64 \
  --python-version 314 \
  --implementation cp \
  --abi cp314 \
  --only-binary=:all:
```

**Critical lesson — always verify the server's Python version first.** The deployment initially
targeted Python 3.12 (as documented by Heliohost). Between sessions, Heliohost silently upgraded to
**Python 3.14.2**. The compiled `.so` extension files (psycopg2, SQLAlchemy, greenlet, MarkupSafe)
are ABI-specific: a wheel built for `cp312` is binary-incompatible with `cp314` and causes a silent
crash with no log output.

A two-line diagnostic `flask.wsgi` that prints `sys.version` before any other import is the fastest
way to confirm the runtime Python version before every vendored deployment.

---

### Challenge 2: Python 3.14 + SQLAlchemy C extension incompatibility

After rebuilding the vendor folder for `cp314`, a new error surfaced during application startup:

```
TypeError: Can't replace canonical symbol for '__firstlineno__' with new int value 646
```

**Root cause analysis (multi-step):**

The error message appeared to come from SQLAlchemy's pure-Python `langhelpers.py` (`symbol` class),
which maintains a singleton registry of named integer constants. Python 3.13 introduced `__firstlineno__`
as a new canonical class attribute (recording the source line where a class is defined). When
`_IntFlagMeta` — SQLAlchemy's custom `IntFlag` metaclass — iterated over class `__dict__` during class
creation, `__firstlineno__` appeared as an integer and conflicted with an existing registry entry.

**What made this hard to debug:**

1. Patching `langhelpers.py` on the server had no effect. Multiple patch attempts, cache invalidations
   (`__pycache__` deletions), and direct server-side edits all failed to resolve the error.
2. The traceback consistently reported the error at line 1635 in `__new__` — but after patching,
   line 1635 in the source was blank (outside `__new__` entirely), proving the bytecode being
   executed did not match the patched source.
3. Incremental diagnostic output (printing `pyc exists: False`, reading lines 1615–1645 of the live
   source) confirmed the patch was on disk and no bytecode cache existed — yet the error persisted.

**True root cause:** SQLAlchemy 2.0.x ships a Cython-compiled extension (`cyextension/util.so`) that
provides an accelerated `symbol` implementation. This `.so` file contained the same canonical-symbol
check compiled into native machine code — completely unaffected by edits to the Python source. All
patch attempts to `langhelpers.py` were irrelevant because Python loaded `symbol` from the `.so` file,
not from the `.py` file.

**Resolution:** SQLAlchemy provides a built-in environment variable to opt out of its C extensions:

```python
# flask.wsgi — must be set before any sqlalchemy import
os.environ['DISABLE_SQLALCHEMY_CEXT_RUNTIME'] = '1'
```

This single line forces SQLAlchemy to use its pure-Python fallback, where our patch to `langhelpers.py`
could take effect. The application started correctly on the next request.

**Broader lesson:** When a Python-level patch has no observable effect despite confirmed source changes
and no bytecode cache, the code path being executed is not in Python. Check for compiled C/Cython
extensions (`.so` / `.pyd` files) in the package that may shadow the module you are editing.

---

### Challenge 3: Shared database — table name collisions

The `production_db` PostgreSQL database was shared with another application that had its own
`users` table. SQLAlchemy's `db.create_all()` found the existing `users` table and skipped creating
its own — then failed when attempting to create the `lists` table, whose foreign key referenced
`users."UserId"`, a column that did not exist in the other application's `users` table.

**Resolution:** Prefix all application table names with `tl_` in `models.py` (`tl_users`, `tl_lists`,
`tl_tasks`, `tl_site_labels`). This is a standard mitigation on shared-database hosting environments
and is transparent to application code — only `__tablename__` strings change, not the ORM classes.

---

### Challenge 4: mod_wsgi — `__main__` guard and table initialisation

Flask's development server is started by `if __name__ == '__main__': app.run()`. Under mod_wsgi, the
module is **imported**, not executed — so the `__main__` block never runs. `db.create_all()` and
`seed_labels()` were inside that guard, which meant the database tables were never created in production,
resulting in empty label queries and a broken UI.

**Resolution:** Move the initialisation calls **outside** the `__main__` guard so they execute at
module import time, and wrap them in `try/except` so a DB error does not crash the entire WSGI startup:

```python
# Runs on every mod_wsgi import — idempotent and safe
try:
    with app.app_context():
        db.create_all()
        seed_labels()
except Exception as e:
    import logging
    logging.error("Startup initialisation failed: %s", e)
```

---

### Challenge 5: Jinja2 template caching and the language switcher

The language-switcher `<select>` used a hardcoded JavaScript path:

```javascript
onchange="window.location='/set-lang/' + this.value"
```

On shared hosting mounted under `/todolistflask/`, this generated `/set-lang/it` (404) instead of
`/todolistflask/set-lang/it`. The fix was to use Flask's `url_for` to generate the correct prefixed
URL at render time:

```html
onchange="window.location='{{ url_for('set_lang', lang='LANG') }}'.replace('LANG', this.value)"
```

A secondary lesson: in production (non-debug) mode, Jinja2 caches compiled templates in memory.
Uploading a corrected template file has no effect until the WSGI process restarts. Adding
`app.config['TEMPLATES_AUTO_RELOAD'] = True` to the production configuration eliminates this friction
by instructing Jinja2 to check file modification times on every request.

---

## Part 3 — Lessons Learned Summary

| Area | Lesson |
|---|---|
| **Dependency management** | Always verify the server's exact Python version (`sys.version`) before cross-compiling a vendor folder. ABI mismatches cause silent crashes, not helpful error messages. |
| **C extensions** | When a Python-level patch has no effect, check for compiled `.so` files that shadow the module. The error may originate in native code entirely outside the Python source tree. |
| **Shared hosting** | Prefix table names to avoid collisions on shared databases. Never assume you are the only tenant. |
| **WSGI lifecycle** | Understand the difference between `python script.py` (executes `__main__`) and WSGI import (never executes `__main__`). Initialisation code must live at module level. |
| **Systematic debugging** | When the usual tools (file edits, cache clears) do not work, add diagnostic layers: verify Python version, print actual file contents from within the running process, check `.pyc` paths with `importlib.util.cache_from_source()`. |
| **Template caching** | Enable `TEMPLATES_AUTO_RELOAD = True` in production to allow hot-reload of templates without a full process restart. |
| **URL generation** | Never hardcode path prefixes in JavaScript. Use server-side `url_for` to generate paths so the application is deployment-location agnostic. |

---

## Part 4 — Skills Demonstrated

This deployment exercised a broad set of engineering competencies under real constraints:

- **Python internals:** bytecode caching (`__pycache__`, `.pyc` validation), C extension loading, ABI compatibility, the import system (`sys.modules`, `sys.path`, `importlib`).
- **WSGI / web server architecture:** mod_wsgi lifecycle, `SCRIPT_NAME` / `PATH_INFO`, Jinja2 template compilation, Flask application factory pattern.
- **PostgreSQL:** schema-level permissions, ORM table creation order, foreign key constraints, shared-database isolation strategies.
- **Systematic debugging in a constrained environment:** no SSH, no interactive shell, all diagnostics expressed as WSGI-served HTTP responses; iterative hypothesis-test cycles to isolate root causes across Python, C extensions, bytecode cache, and web server configuration layers.
- **Cross-platform dependency vendoring:** cross-compiling binary wheels for a target platform different from the development machine.
