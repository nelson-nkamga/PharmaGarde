"""Endpoints JSON publics (lecture seule)."""
from flask import Blueprint, jsonify, request

from ..core import dates
from ..core.errors import NotFoundError
from ..repositories import garde_repo, pharmacie_repo, quartier_repo
from ..services import public_service
from .helpers import int_arg

bp = Blueprint("api", __name__, url_prefix="/api")


def _pharmacie_dict(p):
    return {"id": p.id, "nom": p.nom, "adresse": p.adresse, "telephone": p.telephone,
            "quartier": {"id": p.quartier_id, "nom": p.quartier_nom}}


@bp.get("/quartiers")
def quartiers():
    return jsonify({"data": [{"id": q.id, "nom": q.nom} for q in quartier_repo.lister()]})


@bp.get("/gardes/en-cours")
def gardes_en_cours():
    quartier_id = int_arg("quartier_id")
    if quartier_id and quartier_repo.get(quartier_id) is None:
        raise NotFoundError("Quartier introuvable.")
    now = dates.now_utc()
    gardes = garde_repo.en_cours(dates.to_iso(now), quartier_id)
    data = [{"pharmacie": {"id": g.pharmacie_id, "nom": g.pharmacie_nom, "adresse": g.adresse,
                           "telephone": g.telephone, "quartier": g.quartier_nom},
             "garde": {"debut": dates.to_iso(g.debut), "fin": dates.to_iso(g.fin)}} for g in gardes]
    return jsonify({"data": data, "meta": {"genere_le": dates.to_iso(now), "total": len(data)}})


@bp.get("/pharmacies/<int:pharmacie_id>")
def pharmacie(pharmacie_id: int):
    p = pharmacie_repo.get(pharmacie_id)
    if p is None or not p.actif:
        raise NotFoundError("Pharmacie introuvable.")
    now = dates.now_utc()
    gardes = [g for g in garde_repo.pour_pharmacie(pharmacie_id) if g.fin > now][:5]
    data = _pharmacie_dict(p)
    data["de_garde_maintenant"] = any(g.debut <= now < g.fin for g in gardes)
    data["prochaines_gardes"] = [{"debut": dates.to_iso(g.debut), "fin": dates.to_iso(g.fin)} for g in gardes]
    return jsonify({"data": data})


@bp.get("/medicaments/suggestions")
def suggestions():
    items = public_service.suggestions(request.args.get("q", ""), limit=8)
    return jsonify({"data": [{"id": m.id, "nom": m.nom, "dosage": m.dosage, "forme": m.forme,
                              "conditionnement": m.conditionnement, "libelle": m.libelle,
                              "principe_actif": m.principe_actif} for m in items]})
