"""Filtres et variables globales Jinja (formats français)."""
from flask import current_app, request

from . import dates
from .text import pluriel as _pluriel


def _nombre(n) -> str:
    return f"{int(n):,}".replace(",", "\u00a0")


def init_app(app):
    env = app.jinja_env
    env.filters.update({
        "date_fr": lambda d, annee=True: dates.date_fr(d, annee),
        "jour_fr": dates.jour_fr,
        "heure_fr": dates.heure_fr,
        "heure_courte": dates.heure_courte,
        "jj_mm": dates.jj_mm,
        "mois_annee": dates.mois_annee,
        "plage_semaine": dates.plage_semaine,
        "anciennete": lambda d, now=None: dates.anciennete(d, now),
        "pluriel": _pluriel,
        "nombre": _nombre,
        "fcfa": lambda n: f"{_nombre(n)} FCFA",
        "plus_un_jour": lambda d, fin: dates.lendemain(d, fin),
    })
    env.tests["lendemain"] = lambda fin, debut: dates.lendemain(debut, fin)

    @app.context_processor
    def _globals():
        from .security import current_user
        from ..services import stock_service
        from ..repositories import pharmacie_repo
        now = dates.now_utc()
        u = current_user()
        reseau = pharmacie_repo.compter_total() if u and u.role == "admin" else None
        return {
            "reseau_total": reseau,
            "now": now,
            "demo_mode": current_app.config["DEMO_MODE"],
            "user": current_user(),
            "statut_stock": stock_service.statut_stock,
            "endpoint": request.endpoint or "",
        }
