"""Planning des gardes. Règle R2 : deux gardes d'une même pharmacie ne se chevauchent jamais."""
import sqlite3
from datetime import timedelta

from flask import current_app

from ..core import dates
from ..core.db import transaction
from ..core.errors import GardeChevauchement, NotFoundError, ValidationError
from ..repositories import garde_repo, pharmacie_repo

DUREE_MAX_H = 48


# ---- Cycle de 8 semaines ----------------------------------------------------------
def cycle_debut():
    valeur = garde_repo.lire_parametre("planning_debut")
    return dates.parse(valeur) if valeur else dates.monday_of(dates.now_utc())


def cycle() -> dict:
    debut = cycle_debut()
    n = current_app.config["PLANNING_SEMAINES"]
    semaines = [(i + 1, debut + timedelta(days=7 * i)) for i in range(n)]
    return {"debut": debut, "fin": debut + timedelta(days=7 * n - 1), "semaines": semaines, "n": n}


def semaine_courante(now) -> int:
    c = cycle()
    idx = (now - c["debut"]).days // 7 + 1
    return min(max(idx, 1), c["n"])


def statut(garde, now) -> str:
    if garde.debut <= now < garde.fin:
        return "en_cours"
    return "a_venir" if now < garde.debut else "terminee"


def planning_semaine(numero: int) -> dict:
    c = cycle()
    numero = min(max(numero, 1), c["n"])
    debut = c["debut"] + timedelta(days=7 * (numero - 1))
    fin = debut + timedelta(days=7)
    now = dates.now_utc()
    gardes = garde_repo.entre(dates.to_iso(debut), dates.to_iso(fin))
    jours = []
    for i in range(7):
        j0 = debut + timedelta(days=i)
        du_jour = [g for g in gardes if dates.jour_local(g.debut) == dates.jour_local(j0)]
        jours.append({"date": j0, "gardes": [{"garde": g, "statut": statut(g, now)} for g in du_jour]})
    return {"numero": numero, "debut": debut, "fin": fin, "jours": jours, "total": len(gardes),
            "cycle": c, "now": now, "nb_en_cours": len(garde_repo.en_cours(dates.to_iso(now)))}


def gardes_semaine_courante() -> dict:
    """Pour le tableau de bord admin : semaine en cours (lundi → dimanche)."""
    now = dates.now_utc()
    debut = dates.monday_of(now)
    gardes = garde_repo.entre(dates.to_iso(debut), dates.to_iso(debut + timedelta(days=7)))
    jours = []
    for i in range(7):
        j0 = debut + timedelta(days=i)
        du_jour = [g for g in gardes if dates.jour_local(g.debut) == dates.jour_local(j0)]
        if du_jour:
            jours.append({"date": j0, "gardes": du_jour})
    return {"debut": debut, "jours": jours, "total": len(gardes)}


# ---- Saisie et règles --------------------------------------------------------------
def lire_formulaire(form) -> dict:
    """Valide le formulaire et renvoie pharmacie_id / debut / fin (UTC). Lève ValidationError."""
    errors = {}
    try:
        pharmacie_id = int(form.get("pharmacie_id", ""))
    except ValueError:
        pharmacie_id = None
        errors["pharmacie_id"] = "Choisissez une pharmacie."
    debut = fin = None
    for cle, libelle in (("debut", "début"), ("fin", "fin")):
        try:
            valeur = dates.from_local(form.get(f"date_{cle}", ""), form.get(f"heure_{cle}", ""))
        except ValueError:
            errors[f"date_{cle}"] = f"Saisissez une date et une heure de {libelle} valides."
            continue
        if cle == "debut":
            debut = valeur
        else:
            fin = valeur
    if debut and fin:
        if fin <= debut:
            errors["date_fin"] = "La fin doit être postérieure au début."
        elif fin - debut > timedelta(hours=DUREE_MAX_H):
            errors["date_fin"] = f"Une garde ne peut pas dépasser {DUREE_MAX_H} heures."
    if errors:
        raise ValidationError(errors)
    pharmacie = pharmacie_repo.get(pharmacie_id)
    if pharmacie is None or not pharmacie.actif:
        raise ValidationError({"pharmacie_id": "Cette pharmacie n'existe pas ou est désactivée."})
    return {"pharmacie_id": pharmacie_id, "debut": debut, "fin": fin}


def verifier_conflit(pharmacie_id, debut, fin, exclure_id=None):
    return garde_repo.chercher_conflit(pharmacie_id, dates.to_iso(debut), dates.to_iso(fin), exclure_id)


def creer(pharmacie_id, debut, fin) -> int:
    try:
        with transaction():  # BEGIN IMMEDIATE : pas de course entre deux administrateurs
            conflit = verifier_conflit(pharmacie_id, debut, fin)
            if conflit:
                raise GardeChevauchement(conflit)
            return garde_repo.inserer(pharmacie_id, dates.to_iso(debut), dates.to_iso(fin))
    except sqlite3.IntegrityError as e:  # filet de sécurité : trigger SQL
        if "GARDE_CHEVAUCHEMENT" in str(e):
            raise GardeChevauchement() from e
        raise


def modifier(garde_id, pharmacie_id, debut, fin):
    if garde_repo.get(garde_id) is None:
        raise NotFoundError("Garde introuvable.")
    try:
        with transaction():
            conflit = verifier_conflit(pharmacie_id, debut, fin, exclure_id=garde_id)  # exclut la garde elle-même
            if conflit:
                raise GardeChevauchement(conflit)
            garde_repo.modifier(garde_id, pharmacie_id, dates.to_iso(debut), dates.to_iso(fin))
    except sqlite3.IntegrityError as e:
        if "GARDE_CHEVAUCHEMENT" in str(e):
            raise GardeChevauchement() from e
        raise


def supprimer(garde_id):
    if garde_repo.supprimer(garde_id) == 0:
        raise NotFoundError("Garde introuvable.")


def message_conflit(conflit) -> str:
    if conflit is None:
        return GardeChevauchement.message
    return (f"Cette pharmacie a déjà une garde qui chevauche cette période "
            f"(du {dates.jj_mm(conflit.debut)} à {dates.heure_courte(conflit.debut)} "
            f"au {dates.jj_mm(conflit.fin)} à {dates.heure_courte(conflit.fin)}).")


# ---- Vue pharmacien (lecture seule) --------------------------------------------------
def pour_pharmacie(pharmacie_id: int) -> dict:
    now = dates.now_utc()
    toutes = garde_repo.pour_pharmacie(pharmacie_id)
    en_cours = next((g for g in toutes if g.debut <= now < g.fin), None)
    a_venir = [g for g in toutes if g.debut > now]
    passees = sorted((g for g in toutes if g.fin <= now), key=lambda g: g.debut, reverse=True)[:12]
    return {"now": now, "en_cours": en_cours, "a_venir": a_venir, "passees": passees,
            "prochaine": a_venir[0] if a_venir else None}
