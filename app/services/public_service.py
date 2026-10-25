"""Espace public : pharmacies de garde et recherche de médicament."""
from datetime import timedelta

from ..core import dates
from ..core.errors import NotFoundError
from ..core.text import pluriel
from ..repositories import garde_repo, medicament_repo, quartier_repo, recherche_repo, stock_repo


def accueil(quartier_id: int | None) -> dict:
    now = dates.now_utc()
    quartiers = quartier_repo.lister()
    quartier = next((q for q in quartiers if q.id == quartier_id), None)
    if quartier_id and quartier is None:
        raise NotFoundError("Quartier introuvable.")
    gardes = garde_repo.en_cours(dates.to_iso(now), quartier_id)
    return {"now": now, "quartiers": quartiers, "quartier": quartier, "gardes": gardes}


def frequents(limit: int = 6):
    depuis = dates.to_iso(dates.now_utc() - timedelta(days=90))
    return medicament_repo.frequents(depuis, limit)


def suggestions(q: str, limit: int = 8):
    q = (q or "").strip()
    if len(q) < 2:
        return []
    return medicament_repo.rechercher(q, limit=limit)


def rechercher(q: str, quartier_id: int | None, en_stock: bool, medicament_id: int | None) -> dict:
    now = dates.now_utc()
    q = (q or "").strip()[:80]
    quartiers = quartier_repo.lister()
    quartier = next((x for x in quartiers if x.id == quartier_id), None)

    if medicament_id:
        m = medicament_repo.get(medicament_id)
        if m is None:
            raise NotFoundError("Médicament introuvable.")
        trouves = [m]
        q = q or m.libelle
    else:
        trouves = medicament_repo.rechercher(q, limit=60)

    lignes = stock_repo.rechercher_public([m.id for m in trouves], quartier_id, en_stock, dates.to_iso(now))

    distincts = {(m.nom, m.dosage) for m in trouves}
    unique = trouves[0] if len(trouves) == 1 else None
    titre = unique.libelle if unique else (q[:1].upper() + q[1:])
    forme_info = ""
    if unique:
        forme_info = " · ".join(x for x in (pluriel(unique.forme), unique.conditionnement) if x)

    pharmacies = {l.pharmacie_id for l in lignes}
    equivalents = []
    if trouves:
        equivalents = medicament_repo.equivalents(trouves[0].principe_actif_id, [m.id for m in trouves])

    recherche_repo.enregistrer(q or titre, unique.id if unique else None, quartier_id,
                               len(lignes), dates.to_iso(now))

    return {"now": now, "q": q, "titre": titre, "lignes": lignes, "nb_pharmacies": len(pharmacies),
            "quartiers": quartiers, "quartier": quartier, "en_stock": en_stock,
            "forme_info": forme_info, "unique": unique, "equivalents": equivalents,
            "medicaments_trouves": trouves, "distincts": distincts,
            "similaires": _similaires(trouves, q) if not lignes else []}


def _similaires(trouves, q):
    """Pistes quand rien n'est affiché : même nom avec un autre dosage ou une autre forme."""
    premier_mot = (q.split() or [""])[0]
    if len(premier_mot) < 3:
        return []
    deja = {m.id for m in trouves}
    return [m for m in medicament_repo.rechercher(premier_mot, limit=8) if m.id not in deja][:4]
