"""Pages publiques (aucune connexion requise)."""
from flask import Blueprint, render_template, request

from ..services import public_service
from .helpers import int_arg

bp = Blueprint("public", __name__)


@bp.get("/")
def accueil():
    data = public_service.accueil(int_arg("quartier"))
    return render_template("public/accueil.html", **data)


@bp.get("/medicaments")
def medicaments():
    q = request.args.get("q", "").strip()
    quartier_id = int_arg("quartier")
    medicament_id = int_arg("m")
    en_stock = request.args.get("stock") == "1"
    if not q and not medicament_id:
        from ..repositories import quartier_repo
        quartiers = quartier_repo.lister()
        return render_template("public/recherche.html", quartiers=quartiers, quartier_id=quartier_id,
                               frequents=public_service.frequents(6))
    data = public_service.rechercher(q, quartier_id, en_stock, medicament_id)
    return render_template("public/resultats.html", **data)
