"""
models.py
---------
Defines the database models (tables) for the Listly application using
SQLAlchemy ORM (Object-Relational Mapper).

An ORM lets you work with database rows as Python objects instead of writing
raw SQL. Each class below maps to one table in the PostgreSQL database.

Three models are defined here:
  - User  → a registered account              (table: users)
  - List  → a named to-do list owned by a User (table: lists)
  - Task  → a single to-do item inside a List  (table: tasks)

Relationships (one-to-many):
  User (1) ──────< List (many) ──────< Task (many)
  One user can have many lists; one list can have many tasks.

How SQLAlchemy is wired into the app:
  1. `db` is created here (not in main.py) to avoid circular imports.
  2. main.py imports `db` and calls `db.init_app(app)` to attach it.
  3. `db.create_all()` creates the tables the first time the app runs.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Central SQLAlchemy instance. Shared across the whole application.
# All models reference this `db` object to define their columns and relationships.
db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    Represents a registered user account.

    Inherits from `UserMixin` (flask_login), which provides default
    implementations for four properties that Flask-Login requires:
      - is_authenticated  → True when logged in
      - is_active         → True for non-banned accounts
      - is_anonymous      → False for real users
      - get_id()          → returns the user's unique ID as a string

    Table: users
    """

    __tablename__ = 'users'

    UserId       = db.Column(db.Integer, primary_key=True)
    FirstName    = db.Column(db.String(100), nullable=False)
    LastName     = db.Column(db.String(100), nullable=False)
    # unique=True ensures no two accounts can share the same email address
    EmailAddress = db.Column(db.String(255), unique=True, nullable=False)
    # Stored as a Werkzeug hash (e.g. "pbkdf2:sha256:..."), never plain-text
    Password     = db.Column(db.String(255), nullable=False)
    CreatedAt    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # One-to-many: one User has many Lists.
    # backref='owner' adds a shortcut: given a List object, list.owner returns its User.
    # cascade='all, delete-orphan' means: if a User is deleted, all their Lists
    # (and via the List→Task cascade, all their Tasks) are deleted automatically.
    lists = db.relationship('List', backref='owner', lazy=True, cascade='all, delete-orphan')

    def get_id(self):
        """
        Required by Flask-Login.

        Returns the user's primary key as a string. Flask-Login stores this
        value in the session cookie, then calls `load_user()` in main.py on
        every request to fetch the matching User from the database.
        """
        return str(self.UserId)


class List(db.Model):
    """
    Represents a named to-do list owned by a User.

    Table: lists
    Belongs to one User (many-to-one via UserId foreign key).
    Contains many Tasks (one-to-many via the `tasks` relationship).
    """

    __tablename__ = 'lists'

    ListId    = db.Column(db.Integer, primary_key=True)
    # Foreign key: links this list to a row in the users table
    UserId    = db.Column(db.Integer, db.ForeignKey('users.UserId'), nullable=False)
    Title     = db.Column(db.String(200), nullable=False, default='Untitled list')
    CreatedAt = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # One-to-many: one List has many Tasks.
    # order_by='Task.CreatedAt' keeps tasks in insertion order on every query.
    # cascade='all, delete-orphan' means deleting a List also deletes all its Tasks.
    tasks = db.relationship(
        'Task', backref='parent_list', lazy=True,
        cascade='all, delete-orphan', order_by='Task.CreatedAt'
    )

    @property
    def done_count(self):
        """
        Returns the number of tasks in this list that are marked as done.

        Used by the templates to display progress (e.g. "3/5 done").
        The `@property` decorator means you call it like an attribute:
          list.done_count   ← no parentheses needed
        """
        return sum(1 for t in self.tasks if t.IsDone)

    @property
    def total_count(self):
        """
        Returns the total number of tasks in this list (done + not done).

        Used together with done_count to calculate completion percentage.
        """
        return len(self.tasks)


class Task(db.Model):
    """
    Represents a single to-do item inside a List.

    Table: tasks
    Belongs to one List (many-to-one via ListId foreign key).
    Can be toggled between done (IsDone=True) and not-done (IsDone=False).
    """

    __tablename__ = 'tasks'

    TaskId   = db.Column(db.Integer, primary_key=True)
    # Foreign key: links this task to its parent list in the lists table
    ListId   = db.Column(db.Integer, db.ForeignKey('lists.ListId'), nullable=False)
    TaskText = db.Column(db.String(500), nullable=False)
    # Defaults to False (not done) on creation; toggled via the toggle_task route
    IsDone   = db.Column(db.Boolean, default=False, nullable=False)
    CreatedAt = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SiteLabel(db.Model):
    """
    Stores translatable UI labels for multi-language support.

    Table: site_labels
    Each row holds one label string for one language. The pair (LabelKey, Lang)
    is unique — enforced by the UniqueConstraint below.

    Supported Lang values: 'en', 'it', 'es'
    """

    __tablename__ = 'site_labels'

    LabelId    = db.Column(db.Integer, primary_key=True)
    LabelKey   = db.Column(db.String(100), nullable=False)
    Lang       = db.Column(db.String(5),   nullable=False)
    LabelValue = db.Column(db.String(1000), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('LabelKey', 'Lang', name='uq_site_label_lang'),
    )
