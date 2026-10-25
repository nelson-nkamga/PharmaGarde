"""Espace administrateur : pharmacies, planning des gardes, statistiques."""
from datetime import timedelta
from urllib.parse import urlencode

from flask import (Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for)

from ..core import dates
from ..core.errors import GardeChevauchement, NotFoundError, ValidationError
from ..core.security import role_required
from ..repositories import garde_repo, pharmacie_repo, quartier_repo
from ..services import garde_service, pharmacie_service, stats_service
from .helpers import int_arg

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@role_required("admin")
def tableau_de_bord():
    return render_template("admin/tableau_de_bord.html", **stats_service.tableau_admin())


# =============================== Pharmacies ===============================================
def _etat_pharmacies():
    return {"q": request.values.get("q", ""), "statut": request.values.get("statut", "toutes"),
            "page": int_arg("page", 1, request.values) or 1}


def _url_pharmacies(**extra):
    e = _etat_pharmacies()
    params = {"q": e["q"], "statut": e["statut"] if e["statut"] != "toutes" else "",
              "page": e["page"] if e["page"] > 1 else ""}
    params.update(extra)
    params = {k: v for k, v in params.items() if v not in (None, "")}
    return url_for("admin.pharmacies") + ("?" + urlencode(params) if params else "")


def _render_pharmacies(status=200, **ctx):
    e = _etat_pharmacies()
    data = pharmacie_service.lister(e["q"], e["statut"], e["page"])
    for cle, defaut in (("modal", None), ("cible", None), ("valeurs", {}), ("erreurs", {})):
        ctx.setdefault(cle, defaut)
    return render_template("admin/pharmacies.html", data=data, quartiers=quartier_repo.lister(),
                           url_pharmacies=_url_pharmacies, **ctx), status


@bp.get("/pharmacies")
@role_required("admin")
def pharmacies():
    return _render_pharmacies()


@bp.get("/pharmacies/nouvelle")
@role_required("admin")
def pharmacie_nouvelle():
    return _render_pharmacies(modal="creer")


@bp.post("/pharmacies")
@role_required("admin")
def pharmacie_creer():
    try:
        pharmacie_service.creer(request.form)
    except ValidationError as e:
        valeurs = {k: request.form.get(k, "") for k in ("nom", "adresse", "quartier_id", "telephone", "email")}
        return _render_pharmacies(422, modal="creer", valeurs=valeurs, erreurs=e.errors)
    flash("Pharmacie ajoutée au réseau", "success")
    return redirect(_url_pharmacies())


@bp.get("/pharmacies/<int:pharmacie_id>/modifier")
@role_required("admin")
def pharmacie_modifier_form(pharmacie_id: int):
    p = pharmacie_service.get(pharmacie_id)
    valeurs = {"nom": p.nom, "adresse": p.adresse, "quartier_id": str(p.quartier_id),
               "telephone": p.telephone, "email": p.email or ""}
    return _render_pharmacies(modal="modifier", cible=p, valeurs=valeurs)


@bp.post("/pharmacies/<int:pharmacie_id>/modifier")
@role_required("admin")
def pharmacie_modifier(pharmacie_id: int):
    p = pharmacie_service.get(pharmacie_id)
    try:
        pharmacie_service.modifier(pharmacie_id, request.form)
    except ValidationError as e:
        valeurs = {k: request.form.get(k, "") for k in ("nom", "adresse", "quartier_id", "telephone", "email")}
        return _render_pharmacies(422, modal="modifier", cible=p, valeurs=valeurs, erreurs=e.errors)
    flash("Pharmacie mise à jour", "success")
    return redirect(_url_pharmacies())


@bp.get("/pharmacies/<int:pharmacie_id>/desactiver")
@role_required("admin")
def pharmacie_desactiver_form(pharmacie_id: int):
    return _render_pharmacies(modal="desactiver", cible=pharmacie_service.get(pharmacie_id))


@bp.post("/pharmacies/<int:pharmacie_id>/desactiver")
@role_required("admin")
def pharmacie_desactiver(pharmacie_id: int):
    pharmacie_service.desactiver(pharmacie_id)
    flash("Pharmacie désactivée", "success")
    return redirect(_url_pharmacies())


@bp.post("/pharmacies/<int:pharmacie_id>/reactiver")
@role_required("admin")
def pharmacie_reactiver(pharmacie_id: int):
    pharmacie_service.reactiver(pharmacie_id)
    flash("Pharmacie réactivée", "success")
    return redirect(_url_pharmacies())


# ================================ Planning des gardes =========================================
def _semaine_arg() -> int:
    return int_arg("semaine", None, request.values) or garde_service.semaine_courante(dates.now_utc())


def _render_planning(status=200, **ctx):
    numero = _semaine_arg()
    data = garde_service.planning_semaine(numero)
    for cle, defaut in (("modal", None), ("garde", None), ("valeurs", {}), ("erreurs", {}),
                        ("conflit_message", None), ("conflit_creneau", None)):
        ctx.setdefault(cle, defaut)
    return render_template("admin/planning.html", data=data, pharmacies=pharmacie_repo.lister_actives(),
                           **ctx), status


def _valeurs_defaut(numero: int) -> dict:
    c = garde_service.cycle()
    jour = c["debut"] + timedelta(days=7 * (numero - 1))
    now = dates.now_utc()
    if dates.jour_local(jour) <= dates.jour_local(now) < dates.jour_local(jour + timedelta(days=7)):
        jour = now
    d = dates.local(jour)
    f = d + timedelta(days=1)
    return {"pharmacie_id": "", "date_debut": d.strftime("%Y-%m-%d"), "heure_debut": "19:00",
            "date_fin": f.strftime("%Y-%m-%d"), "heure_fin": "07:00"}


def _valeurs_formulaire() -> dict:
    return {k: request.form.get(k, "") for k in
            ("pharmacie_id", "date_debut", "heure_debut", "date_fin", "heure_fin")}


def _valeurs_garde(g) -> dict:
    d, f = dates.local(g.debut), dates.local(g.fin)
    return {"pharmacie_id": str(g.pharmacie_id), "date_debut": d.strftime("%Y-%m-%d"),
            "heure_debut": d.strftime("%H:%M"), "date_fin": f.strftime("%Y-%m-%d"),
            "heure_fin": f.strftime("%H:%M")}


def _semaine_de(debut) -> int:
    c = garde_service.cycle()
    return min(max((debut - c["debut"]).days // 7 + 1, 1), c["n"])


def _enregistrer(garde_id: int | None):
    """Valide, applique R2 et enregistre. Retourne (redirect | None, contexte d'erreur)."""
    valeurs = _valeurs_formulaire()
    try:
        d = garde_service.lire_formulaire(request.form)
        if garde_id is None:
            garde_service.creer(d["pharmacie_id"], d["debut"], d["fin"])
            flash("Garde enregistrée", "success")
        else:
            garde_service.modifier(garde_id, d["pharmacie_id"], d["debut"], d["fin"])
            flash("Garde modifiée", "success")
        return redirect(url_for("admin.planning", semaine=_semaine_de(d["debut"]))), None
    except ValidationError as e:
        return None, {"valeurs": valeurs, "erreurs": e.errors}
    except GardeChevauchement as e:
        c = e.conflit
        creneau = (f"Créneau en conflit : du {dates.jj_mm(c.debut)} à {dates.heure_fr(c.debut)} "
                   f"au {dates.jj_mm(c.fin)} à {dates.heure_fr(c.fin)}.") if c else None
        return None, {"valeurs": valeurs, "erreurs": {"date_debut": "", "date_fin": ""},
                      "conflit_message": garde_service.message_conflit(c), "conflit_creneau": creneau}


@bp.get("/gardes")
@role_required("admin")
def planning():
    return _render_planning()


@bp.get("/gardes/nouvelle")
@role_required("admin")
def garde_nouvelle():
    return _render_planning(modal="ajouter", valeurs=_valeurs_defaut(_semaine_arg()))


@bp.post("/gardes/nouvelle")
@role_required("admin")
def garde_creer():
    resp, ctx = _enregistrer(None)
    return resp or _render_planning(422 if "conflit_message" not in ctx else 409, modal="ajouter", **ctx)


@bp.get("/gardes/<int:garde_id>/modifier")
@role_required("admin")
def garde_modifier_form(garde_id: int):
    g = garde_repo.get(garde_id)
    if g is None:
        raise NotFoundError("Garde introuvable.")
    return _render_planning(modal="modifier", garde=g, valeurs=_valeurs_garde(g))


@bp.post("/gardes/<int:garde_id>/modifier")
@role_required("admin")
def garde_modifier(garde_id: int):
    g = garde_repo.get(garde_id)
    if g is None:
        raise NotFoundError("Garde introuvable.")
    resp, ctx = _enregistrer(garde_id)
    return resp or _render_planning(422 if "conflit_message" not in ctx else 409, modal="modifier",
                                    garde=g, **ctx)


@bp.get("/gardes/<int:garde_id>/supprimer")
@role_required("admin")
def garde_supprimer_form(garde_id: int):
    g = garde_repo.get(garde_id)
    if g is None:
        raise NotFoundError("Garde introuvable.")
    return _render_planning(modal="supprimer", garde=g)


@bp.post("/gardes/<int:garde_id>/supprimer")
@role_required("admin")
def garde_supprimer(garde_id: int):
    g = garde_repo.get(garde_id)
    semaine = _semaine_de(g.debut) if g else None
    garde_service.supprimer(garde_id)
    flash("Garde supprimée", "success")
    return redirect(url_for("admin.planning", semaine=semaine))


@bp.post("/gardes/verifier")
@role_required("admin")
def garde_verifier():
    """Contrôle en direct (JSON) d'un créneau, sans l'enregistrer. CSRF exigé (en-tête X-CSRF-Token)."""
    try:
        d = garde_service.lire_formulaire(request.form)
    except ValidationError as e:
        return jsonify({"data": {"valide": False, "erreurs": e.errors}})
    conflit = garde_service.verifier_conflit(d["pharmacie_id"], d["debut"], d["fin"],
                                             int_arg("garde_id", None, request.form))
    if conflit:
        return jsonify({"data": {"valide": False, "message": garde_service.message_conflit(conflit),
                                 "creneau": f"Créneau en conflit : du {dates.jj_mm(conflit.debut)} à "
                                            f"{dates.heure_fr(conflit.debut)} au {dates.jj_mm(conflit.fin)} "
                                            f"à {dates.heure_fr(conflit.fin)}."}})
    return jsonify({"data": {"valide": True}})


# ================================== Statistiques ======================================
@bp.get("/statistiques")
@role_required("admin")
def statistiques():
    return render_template(
        "admin/statistiques.html",
        prix=stats_service.prix(request.args.get("q", ""), 10),
        recherches=stats_service.recherches(request.args.get("periode", "30")),
        gardes=stats_service.gardes(), ruptures=stats_service.ruptures())


def _csv(nom: str, contenu: str):
    return Response(contenu, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nom}.csv"'})


@bp.get("/statistiques/prix.csv")
@role_required("admin")
def export_prix():
    lignes = stats_service.prix(request.args.get("q", ""), 1000)["lignes"]
    return _csv("prix-par-medicament", stats_service.vers_csv(
        ["medicament", "dosage", "forme", "nb_pharmacies", "prix_min", "prix_moyen", "prix_max"],
        [[l["nom"], l["dosage"], l["forme"], l["nb_pharmacies"], l["prix_min"], l["prix_moyen"],
          l["prix_max"]] for l in lignes]))


@bp.get("/statistiques/recherches.csv")
@role_required("admin")
def export_recherches():
    r = stats_service.recherches(request.args.get("periode", "30"))
    return _csv("medicaments-les-plus-recherches", stats_service.vers_csv(
        ["medicament", "nb_recherches", "periode"], [[l["libelle"], l["nb"], r["libelle"]] for l in r["lignes"]]))


@bp.get("/statistiques/gardes.csv")
@role_required("admin")
def export_gardes():
    g = stats_service.gardes()
    return _csv("gardes-par-pharmacie", stats_service.vers_csv(
        ["pharmacie", "nb_gardes"], [[l["nom"], l["nb_gardes"]] for l in g["lignes"]]))


@bp.get("/statistiques/ruptures.csv")
@role_required("admin")
def export_ruptures():
    r = stats_service.ruptures()
    return _csv("ruptures-partout", stats_service.vers_csv(
        ["medicament", "dosage", "forme"], [[l["nom"], l["dosage"], l["forme"]] for l in r["lignes"]]))
