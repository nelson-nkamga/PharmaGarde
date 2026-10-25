from ..core.db import get_db
from ..models import Garde

_BASE = """
SELECT g.id, g.pharmacie_id, g.date_debut, g.date_fin,
       p.nom AS pharmacie_nom, p.adresse, p.telephone, p.actif AS pharmacie_actif,
       q.nom AS quartier_nom
  FROM garde g
  JOIN pharmacie p ON p.id = g.pharmacie_id
  JOIN quartier q ON q.id = p.quartier_id
"""


def get(garde_id: int) -> Garde | None:
    r = get_db().execute(_BASE + " WHERE g.id = ?", (garde_id,)).fetchone()
    return Garde.from_row(r) if r else None


def en_cours(now_iso: str, quartier_id: int | None = None) -> list[Garde]:
    sql = _BASE + " WHERE p.actif = 1 AND g.date_debut <= ? AND g.date_fin > ?"
    params = [now_iso, now_iso]
    if quartier_id:
        sql += " AND p.quartier_id = ?"
        params.append(quartier_id)
    rows = get_db().execute(sql + " ORDER BY q.id, p.nom", params).fetchall()
    return [Garde.from_row(r) for r in rows]


def entre(debut_iso: str, fin_iso: str) -> list[Garde]:
    """Gardes qui touchent la période [debut, fin)."""
    rows = get_db().execute(
        _BASE + " WHERE g.date_debut < ? AND g.date_fin > ? ORDER BY g.date_debut, p.nom",
        (fin_iso, debut_iso)).fetchall()
    return [Garde.from_row(r) for r in rows]


def pour_pharmacie(pharmacie_id: int) -> list[Garde]:
    rows = get_db().execute(_BASE + " WHERE g.pharmacie_id = ? ORDER BY g.date_debut",
                            (pharmacie_id,)).fetchall()
    return [Garde.from_row(r) for r in rows]


def prochaine(pharmacie_id: int, now_iso: str) -> Garde | None:
    r = get_db().execute(_BASE + " WHERE g.pharmacie_id = ? AND g.date_fin > ? ORDER BY g.date_debut LIMIT 1",
                         (pharmacie_id, now_iso)).fetchone()
    return Garde.from_row(r) if r else None


def chercher_conflit(pharmacie_id: int, debut_iso: str, fin_iso: str,
                     exclure_id: int | None = None) -> Garde | None:
    """Comparaison stricte : deux gardes qui se touchent (fin = début) ne se chevauchent pas."""
    r = get_db().execute(
        _BASE + """ WHERE g.pharmacie_id = ? AND g.date_debut < ? AND g.date_fin > ?
                      AND (? IS NULL OR g.id != ?) LIMIT 1""",
        (pharmacie_id, fin_iso, debut_iso, exclure_id, exclure_id)).fetchone()
    return Garde.from_row(r) if r else None


def inserer(pharmacie_id: int, debut_iso: str, fin_iso: str) -> int:
    cur = get_db().execute("INSERT INTO garde (pharmacie_id, date_debut, date_fin) VALUES (?, ?, ?)",
                           (pharmacie_id, debut_iso, fin_iso))
    return cur.lastrowid


def modifier(garde_id: int, pharmacie_id: int, debut_iso: str, fin_iso: str):
    get_db().execute("UPDATE garde SET pharmacie_id = ?, date_debut = ?, date_fin = ? WHERE id = ?",
                     (pharmacie_id, debut_iso, fin_iso, garde_id))


def supprimer(garde_id: int) -> int:
    return get_db().execute("DELETE FROM garde WHERE id = ?", (garde_id,)).rowcount


def lire_parametre(cle: str) -> str | None:
    r = get_db().execute("SELECT valeur FROM parametre WHERE cle = ?", (cle,)).fetchone()
    return r["valeur"] if r else None


def ecrire_parametre(cle: str, valeur: str):
    get_db().execute("INSERT INTO parametre (cle, valeur) VALUES (?, ?) "
                     "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur", (cle, valeur))
