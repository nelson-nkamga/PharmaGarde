"""Stocks. Toute requête côté pharmacien filtre sur pharmacie_id (règle R1)."""
from ..core.db import get_db
from ..core.text import like_pattern
from ..models import LigneStock

_BASE = """
SELECT s.pharmacie_id, s.medicament_id, s.quantite, s.prix, s.updated_at,
       m.nom, m.dosage, m.forme, m.conditionnement
  FROM stock s JOIN medicament m ON m.id = s.medicament_id
"""


def _filtre(pharmacie_id: int, q: str, filtre: str, seuil_ancien_iso: str):
    where, params = ["s.pharmacie_id = ?"], [pharmacie_id]
    if q:
        where.append("norm(m.nom || ' ' || m.dosage || ' ' || m.forme) LIKE ? ESCAPE '\\'")
        params.append(like_pattern(q))
    if filtre == "en_stock":
        where.append("s.quantite > 0")
    elif filtre == "rupture":
        where.append("s.quantite = 0")
    elif filtre == "a_mettre_a_jour":
        where.append("s.updated_at <= ?")
        params.append(seuil_ancien_iso)
    return " WHERE " + " AND ".join(where), params


def lignes_pharmacie(pharmacie_id, q, filtre, seuil_ancien_iso, limit, offset) -> list[LigneStock]:
    where, params = _filtre(pharmacie_id, q, filtre, seuil_ancien_iso)
    rows = get_db().execute(_BASE + where + " ORDER BY m.nom, m.dosage, m.forme LIMIT ? OFFSET ?",
                            params + [limit, offset]).fetchall()
    return [LigneStock.from_row(r) for r in rows]


def totaux_pharmacie(pharmacie_id, q, filtre, seuil_ancien_iso) -> dict:
    where, params = _filtre(pharmacie_id, q, filtre, seuil_ancien_iso)
    r = get_db().execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(s.quantite > 0), 0) AS en_stock, "
        "COALESCE(SUM(s.quantite = 0), 0) AS rupture FROM stock s "
        "JOIN medicament m ON m.id = s.medicament_id" + where, params).fetchone()
    return {"total": r["total"], "en_stock": r["en_stock"], "rupture": r["rupture"]}


def anciennes(pharmacie_id: int, seuil_ancien_iso: str) -> list[LigneStock]:
    rows = get_db().execute(_BASE + " WHERE s.pharmacie_id = ? AND s.updated_at <= ? ORDER BY s.updated_at",
                            (pharmacie_id, seuil_ancien_iso)).fetchall()
    return [LigneStock.from_row(r) for r in rows]


def get(pharmacie_id: int, medicament_id: int) -> LigneStock | None:
    r = get_db().execute(_BASE + " WHERE s.pharmacie_id = ? AND s.medicament_id = ?",
                         (pharmacie_id, medicament_id)).fetchone()
    return LigneStock.from_row(r) if r else None


def inserer(pharmacie_id, medicament_id, quantite, prix, now_iso):
    get_db().execute(
        "INSERT INTO stock (pharmacie_id, medicament_id, quantite, prix, updated_at) VALUES (?, ?, ?, ?, ?)",
        (pharmacie_id, medicament_id, quantite, prix, now_iso))


def mettre_a_jour(pharmacie_id, medicament_id, quantite, prix, now_iso) -> int:
    """Retourne le nombre de lignes modifiées : 0 => la ligne n'appartient pas à CETTE pharmacie."""
    cur = get_db().execute(
        "UPDATE stock SET quantite = ?, prix = ?, updated_at = ? WHERE pharmacie_id = ? AND medicament_id = ?",
        (quantite, prix, now_iso, pharmacie_id, medicament_id))
    return cur.rowcount


def supprimer(pharmacie_id, medicament_id) -> int:
    cur = get_db().execute("DELETE FROM stock WHERE pharmacie_id = ? AND medicament_id = ?",
                           (pharmacie_id, medicament_id))
    return cur.rowcount


def rechercher_public(medicament_ids: list[int], quartier_id: int | None, en_stock: bool,
                      now_iso: str) -> list[LigneStock]:
    if not medicament_ids:
        return []
    marks = ",".join("?" * len(medicament_ids))
    where = [f"s.medicament_id IN ({marks})", "p.actif = 1"]
    params = [now_iso, now_iso] + list(medicament_ids)
    if quartier_id:
        where.append("p.quartier_id = ?")
        params.append(quartier_id)
    if en_stock:
        where.append("s.quantite > 0")
    sql = f"""
    SELECT s.pharmacie_id, s.medicament_id, s.quantite, s.prix, s.updated_at,
           m.nom, m.dosage, m.forme, m.conditionnement,
           p.nom AS pharmacie_nom, p.adresse, p.telephone, q.nom AS quartier_nom,
           EXISTS(SELECT 1 FROM garde g WHERE g.pharmacie_id = p.id
                   AND g.date_debut <= ? AND g.date_fin > ?) AS de_garde
      FROM stock s
      JOIN medicament m ON m.id = s.medicament_id
      JOIN pharmacie p ON p.id = s.pharmacie_id
      JOIN quartier q ON q.id = p.quartier_id
     WHERE {' AND '.join(where)}
     ORDER BY (s.quantite = 0), de_garde DESC, s.updated_at DESC, s.prix ASC, p.nom
     LIMIT 200"""
    return [LigneStock.from_row(r) for r in get_db().execute(sql, params).fetchall()]


# ---- Import CSV --------------------------------------------------------------------
def creer_lot(token: str, pharmacie_id: int, lignes_json: str, now_iso: str):
    get_db().execute("INSERT INTO import_lot (token, pharmacie_id, lignes_json, cree_le) VALUES (?, ?, ?, ?)",
                     (token, pharmacie_id, lignes_json, now_iso))


def get_lot(token: str, pharmacie_id: int):
    """Un lot n'est lisible que par la pharmacie qui l'a créé."""
    return get_db().execute("SELECT * FROM import_lot WHERE token = ? AND pharmacie_id = ?",
                            (token, pharmacie_id)).fetchone()


def supprimer_lot(token: str):
    get_db().execute("DELETE FROM import_lot WHERE token = ?", (token,))


def purger_lots(avant_iso: str):
    get_db().execute("DELETE FROM import_lot WHERE cree_le < ?", (avant_iso,))
