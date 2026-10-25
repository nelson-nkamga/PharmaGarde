"""Authentification par session Flask + contrôle d'accès par rôle.

Règle R1 : l'identité (et donc la pharmacie) vient TOUJOURS de la session, relue en base
à chaque requête. Aucune route n'accepte un identifiant de pharmacie venant d'un formulaire.
"""
from functools import wraps
from urllib.parse import urlparse

from flask import g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import csrf
from .errors import ForbiddenError, NotAuthenticated

_DUMMY_HASH = None


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(hash_: str | None, password: str) -> bool:
    """Temps constant même si l'utilisateur n'existe pas (hash factice)."""
    global _DUMMY_HASH
    if hash_ is None:
        if _DUMMY_HASH is None:
            _DUMMY_HASH = generate_password_hash("dummy-password-not-used")
        check_password_hash(_DUMMY_HASH, password)
        return False
    return check_password_hash(hash_, password)


def current_user():
    from ..repositories import utilisateur_repo
    if "user" not in g:
        user = None
        uid = session.get("user_id")
        if uid:
            user = utilisateur_repo.get(uid)
            if user is None or not user.peut_se_connecter:
                session.clear()  # compte supprimé, suspendu ou pharmacie désactivée
                user = None
        g.user = user
    return g.user


def login_user(user):
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    csrf.rotate_token()
    g.user = user


def logout_user():
    session.clear()
    g.user = None


def current_pharmacie_id() -> int:
    """Pharmacie du pharmacien connecté (source unique : la session)."""
    user = current_user()
    if not user or user.role != "pharmacien" or user.pharmacie_id is None:
        raise ForbiddenError()
    return user.pharmacie_id


def safe_next(target: str | None) -> str | None:
    """N'accepte que des chemins relatifs du site (évite les redirections ouvertes)."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            if _wants_json():
                raise NotAuthenticated()
            return redirect(url_for("auth.connexion", next=request.full_path.rstrip("?")))
        return fn(*args, **kwargs)
    return wrapper


def role_required(role: str):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user().role != role:
                raise ForbiddenError()
            return fn(*args, **kwargs)
        return wrapper
    return decorator
