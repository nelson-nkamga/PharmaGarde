"""Espace pharmacien. La pharmacie vient TOUJOURS de la session (current_pharmacie_id), jamais d'un champ."""
from urllib.parse import urlencode

from flask import (Blueprint, Response, flash, redirect, render_template, request, session,
                   url_for)

from ..core import dates
from ..core.errors import DoublonError, NotFoundError, ValidationError
from ..core.security import current_pharmacie_id, role_required
from ..repositories import medicament_repo
from ..services import garde_service, import_service, stats_service, stock_service
from .helpers import int_arg

bp = Blueprint("pharmacien", __name__, url_prefix="/pharmacien")

# Champs qu'un formulaire ne doit JAMAIS envoyer (l'identité vient de la session).
CHAMPS_INTERDITS = {"pharmacie_id", "pharmacie", "updated_at", "mis_a_jour_le"}


def _refuser_champs_interdits():
    interdits = CHAMPS_INTERDITS & set(request.form.keys())
    if interdits:
        raise ValidationError({c: "Ce champ ne peut pas être envoyé." for c in sorted(interdits)},
                              "Champ non autorisé.")


def _etat_liste() -> dict:
    return {"q": request.values.get("q", ""), "filtre": request.values.get("filtre", "tous"),
            "page": int_arg("page", 1, request.values) or 1}


def _url_stocks(**extra):
    e = _etat_liste()
    params = {k: v for k, v in {"q": e["q"], "filtre": e["filtre"] if e["filtre"] != "tous" else "",
                                "page": e["page"] if e["page"] > 1 else ""}.items() if v}
    params.update({k: v for k, v in extra.items() if v not in (None, "")})
    return url_for("pharmacien.stocks") + ("?" + urlencode(params) if params else "")


def _render_stocks(status=200, **ctx):
    e = _etat_liste()
    pid = current_pharmacie_id()
    data = stock_service.lister(pid, e["q"], e["filtre"], e["page"])
    surligne = session.pop("stock_surligne", None)
    for cle, defaut in (("modal", None), ("modifier_id", None), ("valeurs", None), ("erreurs", {}),
                        ("apercu", None), ("erreur_fichier", None), ("selection", None),
                        ("existant", None), ("liste", []), ("q_med", ""), ("form_valeurs", {}),
                        ("form_erreurs", {})):
        ctx.setdefault(cle, defaut)
    return render_template("pharmacien/stocks.html", data=data, surligne=surligne,
                           url_stocks=_url_stocks, **ctx), status


@bp.get("/")
@role_required("pharmacien")
def tableau_de_bord():
    data = stats_service.tableau_pharmacien(current_pharmacie_id())
    return render_template("pharmacien/tableau_de_bord.html", **data)


# ---- Liste et modification en ligne ------------------------------------------------
@bp.get("/stocks")
@role_required("pharmacien")
def stocks():
    modifier = int_arg("modifier")
    return _render_stocks(modifier_id=modifier, valeurs=None, erreurs={}, modal=None)


@bp.post("/stocks/<int:medicament_id>/modifier")
@role_required("pharmacien")
def modifier_stock(medicament_id: int):
    _refuser_champs_interdits()
    pid = current_pharmacie_id()  # R1 : session, pas le formulaire
    try:
        ligne, now = stock_service.modifier(pid, medicament_id, request.form.get("quantite"),
                                            request.form.get("prix"))
    except ValidationError as e:
        valeurs = {"quantite": request.form.get("quantite", ""), "prix": request.form.get("prix", "")}
        return _render_stocks(422, modifier_id=medicament_id, valeurs=valeurs, erreurs=e.errors, modal=None)
    session["stock_surligne"] = {"medicament_id": medicament_id, "heure": dates.heure_fr(now)}
    flash("Stock mis à jour", "success")
    return redirect(_url_stocks())


@bp.post("/stocks/<int:medicament_id>/retirer")
@role_required("pharmacien")
def retirer_stock(medicament_id: int):
    _refuser_champs_interdits()
    stock_service.retirer(current_pharmacie_id(), medicament_id)
    flash("Médicament retiré de votre stock", "success")
    return redirect(_url_stocks())


# ---- Ajout d'un médicament (fenêtre modale rendue côté serveur) ------------------------
def _modal_ajout(status=200, selection=None, existant=None, valeurs=None, erreurs=None):
    q_med = request.values.get("q_med", "")
    liste = stock_service.catalogue_pour_ajout(current_pharmacie_id(), q_med)
    if request.args.get("partial") == "1":  # amélioration JS : recherche en direct
        return render_template("pharmacien/_liste_catalogue.html", liste=liste, q_med=q_med,
                               url_stocks=_url_stocks), status
    return _render_stocks(status, modifier_id=None, valeurs=None, erreurs={}, modal="ajouter",
                          q_med=q_med, liste=liste, selection=selection, existant=existant,
                          form_valeurs=valeurs or {}, form_erreurs=erreurs or {})


@bp.get("/stocks/ajouter")
@role_required("pharmacien")
def ajouter_form():
    pid = current_pharmacie_id()
    selection = existant = None
    mid = int_arg("medicament")
    if mid:
        selection = medicament_repo.get(mid)
        if selection:
            from ..repositories import stock_repo
            existant = stock_repo.get(pid, mid)
    return _modal_ajout(selection=selection, existant=existant)


@bp.post("/stocks/ajouter")
@role_required("pharmacien")
def ajouter():
    _refuser_champs_interdits()
    pid = current_pharmacie_id()
    mid = int_arg("medicament_id", None, request.form)
    valeurs = {"quantite": request.form.get("quantite", ""), "prix": request.form.get("prix", "")}
    selection = medicament_repo.get(mid) if mid else None
    try:
        if not mid:
            raise ValidationError({"medicament": "Sélectionnez un médicament."})
        medicament, now = stock_service.ajouter(pid, mid, valeurs["quantite"], valeurs["prix"])
    except DoublonError as e:
        return _modal_ajout(409, selection=selection, existant=e.existant)
    except ValidationError as e:
        return _modal_ajout(422, selection=selection, valeurs=valeurs, erreurs=e.errors)
    except NotFoundError:
        return _modal_ajout(404, selection=None)
    session["stock_surligne"] = {"medicament_id": medicament.id, "heure": dates.heure_fr(now)}
    flash("Médicament ajouté à votre stock", "success")
    return redirect(_url_stocks())


# ---- Import CSV -----------------------------------------------------------------------
def _modal_import(status=200, apercu=None, erreur_fichier=None):
    return _render_stocks(status, modifier_id=None, valeurs=None, erreurs={}, modal="importer",
                          apercu=apercu, erreur_fichier=erreur_fichier)


@bp.get("/stocks/importer")
@role_required("pharmacien")
def importer_form():
    return _modal_import()


@bp.post("/stocks/importer")
@role_required("pharmacien")
def importer():
    _refuser_champs_interdits()
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        return _modal_import(422, erreur_fichier="Sélectionnez un fichier CSV.")
    if not fichier.filename.lower().endswith(".csv"):
        return _modal_import(422, erreur_fichier="Seuls les fichiers .csv sont acceptés.")
    try:
        apercu = import_service.analyser(current_pharmacie_id(), fichier.read())
    except ValidationError as e:
        return _modal_import(422, erreur_fichier=next(iter(e.errors.values())))
    apercu["nom_fichier"] = fichier.filename[:80]
    return _modal_import(apercu=apercu)


@bp.post("/stocks/importer/confirmer")
@role_required("pharmacien")
def importer_confirmer():
    _refuser_champs_interdits()
    try:
        r = import_service.confirmer(current_pharmacie_id(), request.form.get("token", ""))
    except NotFoundError as e:
        return _modal_import(410, erreur_fichier=e.message)
    flash(f"Import terminé : {r['ajouts']} ajouté(s), {r['maj']} mis à jour", "success")
    return redirect(url_for("pharmacien.stocks"))


@bp.get("/stocks/modele.csv")
@role_required("pharmacien")
def modele_csv():
    return Response(import_service.modele_csv(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="modele-stock.csv"'})


# ---- Gardes (lecture seule) ---------------------------------------------------------
@bp.get("/gardes")
@role_required("pharmacien")
def gardes():
    data = garde_service.pour_pharmacie(current_pharmacie_id())
    return render_template("pharmacien/gardes.html", **data)
