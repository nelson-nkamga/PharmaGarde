"""Gestion des pharmacies et de leur compte pharmacien (espace administrateur)."""
import math
import re
import sqlite3

from flask import current_app

from ..core import dates
from ..core.db import transaction
from ..core.errors import NotFoundError, ValidationError
from ..core.security import hash_password
from ..repositories import pharmacie_repo, quartier_repo, utilisateur_repo

STATUTS = ("toutes", "actives", "desactivees")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TEL_RE = re.compile(r"^\+?[0-9][0-9 ]{7,18}$")
MDP_MIN = 12


def lister(q: str = "", statut: str = "toutes", page: int = 1) -> dict:
    statut = statut if statut in STATUTS else "toutes"
    q = (q or "").strip()[:60]
    per_page = current_app.config["PER_PAGE"]
    total = pharmacie_repo.compter(q, statut)
    pages = max(1, math.ceil(total / per_page))
    page = min(max(page, 1), pages)
    items = pharmacie_repo.lister(q, statut, per_page, (page - 1) * per_page)
    debut = (page - 1) * per_page + 1 if items else 0
    return {"items": items, "total": total, "page": page, "pages": pages, "per_page": per_page,
            "debut": debut, "fin": debut + len(items) - 1 if items else 0, "q": q, "statut": statut,
            "total_reseau": pharmacie_repo.compter_total()}


def get(pharmacie_id: int):
    p = pharmacie_repo.get(pharmacie_id)
    if p is None:
        raise NotFoundError("Pharmacie introuvable.")
    return p


def _valider(form, pharmacie_id: int | None) -> dict:
    errors = {}
    nom = " ".join((form.get("nom") or "").split())
    adresse = " ".join((form.get("adresse") or "").split())
    telephone = " ".join((form.get("telephone") or "").split())
    email = (form.get("email") or "").strip().lower()
    mdp = form.get("mot_de_passe") or ""

    if not 2 <= len(nom) <= 80:
        errors["nom"] = "Saisissez le nom de la pharmacie (2 à 80 caractères)."
    if not 3 <= len(adresse) <= 160:
        errors["adresse"] = "Saisissez l'adresse de la pharmacie."
    try:
        quartier_id = int(form.get("quartier_id", ""))
        if quartier_repo.get(quartier_id) is None:
            raise ValueError
    except ValueError:
        quartier_id = None
        errors["quartier_id"] = "Choisissez un quartier de la liste."
    if not TEL_RE.match(telephone):
        errors["telephone"] = "Saisissez un numéro valide, par exemple +237 690 100 101."
    if not EMAIL_RE.match(email) or len(email) > 120:
        errors["email"] = "Saisissez une adresse e-mail valide."
    elif utilisateur_repo.email_pris(email, pharmacie_id):
        errors["email"] = "Cette adresse e-mail est déjà utilisée."
    if pharmacie_id is None and not mdp:
        errors["mot_de_passe"] = "Saisissez un mot de passe temporaire."
    elif mdp and len(mdp) < MDP_MIN:
        errors["mot_de_passe"] = f"Le mot de passe doit contenir au moins {MDP_MIN} caractères."
    if quartier_id and "nom" not in errors and pharmacie_repo.nom_existe(nom, quartier_id, pharmacie_id):
        errors["nom"] = "Une pharmacie portant ce nom existe déjà dans ce quartier."
    if errors:
        raise ValidationError(errors)
    return {"nom": nom, "adresse": adresse, "telephone": telephone, "quartier_id": quartier_id,
            "email": email, "mot_de_passe": mdp}


def creer(form) -> int:
    d = _valider(form, None)
    try:
        with transaction():  # fiche + compte créés ensemble, ou rien
            pid = pharmacie_repo.creer(d["nom"], d["adresse"], d["telephone"], d["quartier_id"])
            utilisateur_repo.creer(d["email"], hash_password(d["mot_de_passe"]), "pharmacien", pid)
    except sqlite3.IntegrityError:
        raise ValidationError({"nom": "Cette pharmacie ou cette adresse e-mail existe déjà."})
    return pid


def modifier(pharmacie_id: int, form):
    get(pharmacie_id)
    d = _valider(form, pharmacie_id)
    try:
        with transaction():
            pharmacie_repo.modifier(pharmacie_id, d["nom"], d["adresse"], d["telephone"], d["quartier_id"])
            utilisateur_repo.maj_email(pharmacie_id, d["email"])
            if d["mot_de_passe"]:
                utilisateur_repo.maj_hash(pharmacie_id, hash_password(d["mot_de_passe"]))
    except sqlite3.IntegrityError:
        raise ValidationError({"nom": "Cette pharmacie ou cette adresse e-mail existe déjà."})


def desactiver(pharmacie_id: int):
    get(pharmacie_id)
    pharmacie_repo.set_actif(pharmacie_id, False)  # fiche, stocks et gardes conservés


def reactiver(pharmacie_id: int):
    get(pharmacie_id)
    pharmacie_repo.set_actif(pharmacie_id, True)
