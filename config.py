"""Configuration de PharmaGarde Douala (variables d'environnement)."""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "oui", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DATABASE = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "pharmagarde.db"))

    # Cookies de session
    SESSION_COOKIE_NAME = "pharmagarde_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Uploads (CSV de stock : 2 Mo maximum)
    MAX_CONTENT_LENGTH = 3 * 1024 * 1024
    CSV_MAX_BYTES = 2 * 1024 * 1024

    # Règles d'affichage
    PER_PAGE = 10
    SEUIL_STOCK_FAIBLE = 10      # quantité <= seuil => « Stock faible »
    SEUIL_ANCIEN_JOURS = 7       # plus de 7 jours => stock ancien (rouge)
    SEUIL_RECENT_JOURS = 2       # moins de 2 jours => récent (vert)

    # Connexion : 5 échecs / 5 minutes
    LOGIN_MAX_ECHECS = 5
    LOGIN_FENETRE_MIN = 5

    # Mode démonstration : affiche les mentions « données illustratives ».
    DEMO_MODE = _bool("PHARMA_DEMO_MODE", True)
    # Instant figé (heure de Douala, ex. 2026-10-15T20:30) pour reproduire les maquettes.
    DEMO_NOW = os.environ.get("PHARMA_DEMO_NOW") or None

    PLANNING_SEMAINES = 8


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    DEMO_NOW = None

    @classmethod
    def check(cls):
        if cls.SECRET_KEY == "dev-only-change-me":
            raise RuntimeError("SECRET_KEY doit être définie en production.")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    DEMO_NOW = None
    LOGIN_MAX_ECHECS = 5
