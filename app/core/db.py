"""Accès SQLite : connexion par requête, transactions explicites, schéma."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

from .text import norm


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)  # autocommit, BEGIN explicites
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.create_function("norm", 1, norm, deterministic=True)
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@contextmanager
def transaction(db=None):
    """Transaction d'écriture (BEGIN IMMEDIATE : verrou posé dès le début)."""
    db = db or get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
    except BaseException:
        db.execute("ROLLBACK")
        raise
    else:
        db.execute("COMMIT")


def init_db(path: str | None = None):
    """Crée les tables (idempotent)."""
    path = path or current_app.config["DATABASE"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    schema = (Path(current_app.root_path).parent / "schema.sql").read_text(encoding="utf-8")
    conn = _connect(path)
    try:
        conn.executescript(schema)
    finally:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)
