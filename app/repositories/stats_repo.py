from ..core.db import get_db
from ..core.text import like_pattern


def prix_par_medicament(q: str = "", limite: int = 10) -> list[dict]:
    """Prix min / moyen / max (derniers prix déclarés, ruptures comprises) dans le réseau actif."""
    where, params = "", []
    if q:
        where = " WHERE norm(m.nom || ' ' || m.dosage) LIKE ? ESCAPE '\\'"
        params.append(like_pattern(q))
    rows = get_db().execute(
        f"""SELECT m.id, m.nom, m.dosage, m.forme, COUNT(*) AS nb_pharmacies,
                   MIN(s.prix) AS prix_min, CAST(ROUND(AVG(s.prix)) AS INTEGER) AS prix_moyen,
                   MAX(s.prix) AS prix_max
              FROM stock s
              JOIN medicament m ON m.id = s.medicament_id
              JOIN pharmacie p ON p.id = s.pharmacie_id AND p.actif = 1
              {where}
             GROUP BY m.id
             ORDER BY nb_pharmacies DESC, m.nom, m.dosage
             LIMIT ?""", params + [limite]).fetchall()
    return [dict(r) for r in rows]


def compter_medicaments_declares() -> int:
    return get_db().execute("SELECT COUNT(DISTINCT medicament_id) FROM stock").fetchone()[0]


def top_recherches(du_iso: str, au_iso: str, limite: int = 10) -> list[dict]:
    rows = get_db().execute(
        """SELECT COALESCE(MIN(m.nom || ' ' || m.dosage), MIN(r.terme)) AS libelle, COUNT(*) AS nb
             FROM recherche_log r
             LEFT JOIN medicament m ON m.id = r.medicament_id
            WHERE r.date >= ? AND r.date < ?
            GROUP BY CASE WHEN r.medicament_id IS NOT NULL THEN 'm' || r.medicament_id
                          ELSE 't' || norm(r.terme) END
            ORDER BY nb DESC, libelle
            LIMIT ?""", (du_iso, au_iso, limite)).fetchall()
    return [dict(r) for r in rows]


def gardes_par_pharmacie(debut_iso: str, fin_iso: str) -> list[dict]:
    rows = get_db().execute(
        """SELECT p.id, p.nom, COUNT(g.id) AS nb_gardes
             FROM pharmacie p
             LEFT JOIN garde g ON g.pharmacie_id = p.id AND g.date_debut >= ? AND g.date_debut < ?
            WHERE p.actif = 1
            GROUP BY p.id
            ORDER BY nb_gardes DESC, p.nom""", (debut_iso, fin_iso)).fetchall()
    return [dict(r) for r in rows]


_RUPTURE_PARTOUT = """
  FROM medicament m
 WHERE EXISTS (SELECT 1 FROM stock s JOIN pharmacie p ON p.id = s.pharmacie_id AND p.actif = 1
                WHERE s.medicament_id = m.id)
   AND NOT EXISTS (SELECT 1 FROM stock s JOIN pharmacie p ON p.id = s.pharmacie_id AND p.actif = 1
                    WHERE s.medicament_id = m.id AND s.quantite > 0)"""


def ruptures_partout() -> list[dict]:
    rows = get_db().execute("SELECT m.id, m.nom, m.dosage, m.forme" + _RUPTURE_PARTOUT +
                            " ORDER BY m.nom, m.dosage").fetchall()
    return [dict(r) for r in rows]
