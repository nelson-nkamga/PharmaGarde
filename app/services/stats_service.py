"""Statistiques administrateur + tableaux de bord."""
import csv
import io
import math
from datetime import timedelta

from ..core import dates
from ..repositories import (garde_repo, medicament_repo, pharmacie_repo, quartier_repo,
                            stats_repo, stock_repo)
from . import garde_service, stock_service

PERIODES = {"7": ("7 derniers jours", 7), "30": ("30 derniers jours", 30), "90": ("90 derniers jours", 90)}


def _echelle(maximum: int, intervalles: int, nice: bool) -> int:
    maximum = max(maximum, 1)
    if nice:
        mag = 10 ** int(math.floor(math.log10(maximum)))
        for f in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
            if maximum <= f * mag:
                maximum = int(f * mag)
                break
    return int(math.ceil(maximum / intervalles) * intervalles)


def _pct(valeur: int, echelle: int) -> int:
    return min(100, round(valeur / echelle * 100)) if echelle else 0


# ---- Prix ----------------------------------------------------------------------------
def prix(q: str = "", limite: int = 10) -> dict:
    lignes = stats_repo.prix_par_medicament((q or "").strip()[:60], limite)
    return {"lignes": lignes, "q": (q or "").strip(), "catalogue": medicament_repo.compter(),
            "limite": limite}


# ---- Recherches ----------------------------------------------------------------------
def recherches(periode: str = "30") -> dict:
    periode = periode if periode in PERIODES else "30"
    libelle, jours = PERIODES[periode]
    fin = dates.now_utc()
    debut = fin - timedelta(days=jours)
    lignes = stats_repo.top_recherches(dates.to_iso(debut), dates.to_iso(fin + timedelta(seconds=1)), 10)
    echelle = _echelle(max((l["nb"] for l in lignes), default=1), 3, nice=True)
    for l in lignes:
        l["pct"] = _pct(l["nb"], echelle)
    return {"periode": periode, "libelle": libelle, "periodes": PERIODES, "lignes": lignes,
            "echelle": echelle, "ticks": [round(echelle * i / 3) for i in range(4)],
            "debut": debut, "fin": fin}


# ---- Gardes par pharmacie ---------------------------------------------------------------
def gardes() -> dict:
    c = garde_service.cycle()
    fin = c["debut"] + timedelta(days=7 * c["n"])
    lignes = stats_repo.gardes_par_pharmacie(dates.to_iso(c["debut"]), dates.to_iso(fin))
    nombres = [l["nb_gardes"] for l in lignes]
    moyenne = sum(nombres) / len(nombres) if nombres else 0
    echelle = _echelle(max(nombres, default=1), 4, nice=False)
    for l in lignes:
        l["pct"] = _pct(l["nb_gardes"], echelle)
        l["niveau"] = ""
        if moyenne and l["nb_gardes"] > moyenne * 1.5 and l["nb_gardes"] - moyenne >= 3:
            l["niveau"] = "eleve"
        elif moyenne >= 4 and l["nb_gardes"] < moyenne * 0.5:
            l["niveau"] = "faible"
    alerte = None
    if lignes and any(l["niveau"] for l in lignes):
        haut, bas = lignes[0], lignes[-1]
        alerte = (f"Déséquilibre à examiner : {haut['nb_gardes']} gardes à {haut['nom']} contre "
                  f"{bas['nb_gardes']} à {bas['nom']}. Repère indicatif : {math.floor(moyenne * 0.5)} à "
                  f"{math.ceil(moyenne * 1.5)} gardes sur {c['n']} semaines.")
    return {"lignes": lignes, "echelle": echelle, "ticks": [round(echelle * i / 4) for i in range(5)],
            "alerte": alerte, "cycle": c, "fin": fin - timedelta(days=1), "moyenne": moyenne}


def ruptures() -> dict:
    return {"lignes": stats_repo.ruptures_partout(), "now": dates.now_utc()}


# ---- Tableau de bord administrateur -------------------------------------------------------
def tableau_admin() -> dict:
    now = dates.now_utc()
    seuil = stock_service.seuil_ancien_iso(now)
    en_cours = garde_repo.en_cours(dates.to_iso(now))
    stale = pharmacie_repo.sans_mise_a_jour(seuil)
    rupt = stats_repo.ruptures_partout()
    for s in stale:
        derniere = dates.parse(s["derniere"])
        s["derniere_dt"] = derniere
        s["jours"] = (now - derniere).days
    return {"now": now, "nb_pharmacies": pharmacie_repo.compter_actives(),
            "nb_de_garde": len(en_cours), "nb_medicaments": stats_repo.compter_medicaments_declares(),
            "ruptures": rupt, "stale": stale, "semaine": garde_service.gardes_semaine_courante()}


# ---- Tableau de bord pharmacien -------------------------------------------------------------
def tableau_pharmacien(pharmacie_id: int) -> dict:
    now = dates.now_utc()
    seuil = stock_service.seuil_ancien_iso(now)
    totaux = stock_repo.totaux_pharmacie(pharmacie_id, "", "tous", seuil)
    anciennes = stock_repo.anciennes(pharmacie_id, seuil)
    return {"now": now, "totaux": totaux, "anciennes": anciennes,
            "prochaine": garde_repo.prochaine(pharmacie_id, dates.to_iso(now))}


# ---- Exports CSV (protégés contre l'injection de formules) ------------------------------------
def _cellule(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


def vers_csv(entetes: list[str], lignes: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(entetes)
    for l in lignes:
        w.writerow([_cellule(c) for c in l])
    return "\ufeff" + buf.getvalue()
