"""Protection CSRF : jeton par session, exigé sur toute requête qui modifie l'état."""
import hmac
import secrets

from flask import request, session

from .errors import CsrfError

SESSION_KEY = "_csrf_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def get_token() -> str:
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token


def rotate_token() -> str:
    session[SESSION_KEY] = secrets.token_urlsafe(32)
    return session[SESSION_KEY]


def _check():
    if request.method in SAFE_METHODS:
        return
    expected = session.get(SESSION_KEY)
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    if not expected or not sent or not hmac.compare_digest(str(expected), str(sent)):
        raise CsrfError()


def init_app(app):
    app.before_request(_check)
    app.jinja_env.globals["csrf_token"] = get_token
