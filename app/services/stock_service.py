"""Stocks d'une pharmacie. Chaque fonction reçoit pharmacie_id depuis la SESSION (règle R1)."""
import math
import re
from datetime import timedelta

from flask import current_app

from ..core import dates
from ..core.errors import DoublonError, NotFoundError, ValidationError
from ..repositories import medicament_repo, stock_repo

FILTRES = ("tous", "en_stock", "rupture", "a_mettre_a_jour")
MAX_QUANTITE = 1_000_000
MAX_PRIX = 10_000_000


def statut_stock(quantite: int) -> str:
    if quantite <= 0:
        return "rupture"
    if quantite <= current_app.config["SEUIL_STOCK_FAIBLE"]:
        return "faible"
    return "ok"


def seuil_ancien_iso(now=None) -> str:
    """Stock « ancien » = plus de 7 jours révolus (>= 8 jours d'écart)."""
    now = now or dates.now_utc()
    return dates.to_iso(now - timedelta(days=current_app.config["SEUIL_ANCIEN_JOURS"] + 1))


def valider(quantite_brute, prix_brut) -> tuple[int | None, int | None, dict]:
    """Validation côté serveur de la quantité et du prix (messages identiques aux maquettes)."""
    errors, quantite, prix = {}, None, None

    q = str(quantite_brute or "").replace("\u00a0", "").replace(" ", "").strip()
    if not re.fullmatch(r"\d{1,9}", q) or int(q) > MAX_QUANTITE:
        errors["quantite"] = "La quantité doit être un nombre entier positif ou nul"
    else:
        quantite = int(q)

    p = str(prix_brut or "").replace("\u00a0", "").replace(" ", "").strip()
    if not re.fullmatch(r"-?\d+([.,]\d+)?", p):
        errors["prix"] = "Le prix doit être un nombre entier supérieur à 0"
    else:
        val = float(p.replace(",", "."))
        if val <= 0:
            errors["prix"] = "Le prix doit être supérieur à 0"
        elif val != int(val):
            errors["prix"] = "Le prix doit être un nombre entier (en FCFA)"
        elif val > MAX_PRIX:
            errors["prix"] = "Le prix est trop élevé"
        else:
            prix = int(val)
    return quantite, prix, errors


def lister(pharmacie_id: int, q: str = "", filtre: str = "tous", page: int = 1) -> dict:
    filtre = filtre if filtre in FILTRES else "tous"
    q = (q or "").strip()[:60]
    per_page = current_app.config["PER_PAGE"]
    seuil = seuil_ancien_iso()
    totaux = stock_repo.totaux_pharmacie(pharmacie_id, q, filtre, seuil)
    pages = max(1, math.ceil(totaux["total"] / per_page))
    page = min(max(page, 1), pages)
    lignes = stock_repo.lignes_pharmacie(pharmacie_id, q, filtre, seuil, per_page, (page - 1) * per_page)
    debut = (page - 1) * per_page + 1 if lignes else 0
    return {"lignes": lignes, "totaux": totaux, "page": page, "pages": pages, "per_page": per_page,
            "debut": debut, "fin": debut + len(lignes) - 1 if lignes else 0, "q": q, "filtre": filtre}


def modifier(pharmacie_id: int, medicament_id: int, quantite_brute, prix_brut):
    quantite, prix, errors = valider(quantite_brute, prix_brut)
    if errors:
        raise ValidationError(errors)
    now = dates.now_utc()
    # UPDATE ... WHERE pharmacie_id = <session> : impossible de toucher le stock d'une autre pharmacie
    if stock_repo.mettre_a_jour(pharmacie_id, medicament_id, quantite, prix, dates.to_iso(now)) == 0:
        raise NotFoundError("Ce médicament n'est pas dans votre stock.")
    return stock_repo.get(pharmacie_id, medicament_id), now


def ajouter(pharmacie_id: int, medicament_id: int, quantite_brute, prix_brut):
    medicament = medicament_repo.get(medicament_id)
    if medicament is None:
        raise NotFoundError("Médicament introuvable dans le catalogue.")
    existant = stock_repo.get(pharmacie_id, medicament_id)
    if existant:
        err = DoublonError("Ce médicament est déjà dans votre stock")
        err.existant = existant
        raise err
    quantite, prix, errors = valider(quantite_brute, prix_brut)
    if errors:
        raise ValidationError(errors)
    now = dates.now_utc()
    stock_repo.inserer(pharmacie_id, medicament_id, quantite, prix, dates.to_iso(now))
    return medicament, now


def retirer(pharmacie_id: int, medicament_id: int):
    if stock_repo.supprimer(pharmacie_id, medicament_id) == 0:
        raise NotFoundError("Ce médicament n'est pas dans votre stock.")


def catalogue_pour_ajout(pharmacie_id: int, q: str):
    return medicament_repo.rechercher((q or "").strip()[:60], limit=6, pharmacie_id=pharmacie_id)
