from ..core.db import get_db
from ..core.text import like_pattern
from ..models import Pharmacie

_SELECT = """
SELECT p.id, p.nom, p.adresse, p.telephone, p.quartier_id, q.nom AS quartier_nom, p.actif,
       u.email AS email
  FROM pharmacie p
  JOIN quartier q ON q.id = p.quartier_id
  LEFT JOIN utilisateur u ON u.pharmacie_id = p.id
"""


def _filtre(q: str, statut: str):
    where, params = [], []
    if q:
        where.append("(norm(p.nom) LIKE ? ESCAPE '\\' OR norm(q.nom) LIKE ? ESCAPE '\\' "
                     "OR norm(COALESCE(u.email, '')) LIKE ? ESCAPE '\\')")
        pat = like_pattern(q)
        params += [pat, pat, pat]
    if statut == "actives":
        where.append("p.actif = 1")
    elif statut == "desactivees":
        where.append("p.actif = 0")
    return (" WHERE " + " AND ".join(where)) if where else "", params


def get(pharmacie_id: int) -> Pharmacie | None:
    r = get_db().execute(_SELECT + " WHERE p.id = ?", (pharmacie_id,)).fetchone()
    return Pharmacie.from_row(r) if r else None


def lister(q: str = "", statut: str = "toutes", limit: int = 10, offset: int = 0) -> list[Pharmacie]:
    where, params = _filtre(q, statut)
    rows = get_db().execute(_SELECT + where + " ORDER BY p.id LIMIT ? OFFSET ?",
                            params + [limit, offset]).fetchall()
    return [Pharmacie.from_row(r) for r in rows]


def compter(q: str = "", statut: str = "toutes") -> int:
    where, params = _filtre(q, statut)
    sql = ("SELECT COUNT(*) FROM pharmacie p JOIN quartier q ON q.id = p.quartier_id "
           "LEFT JOIN utilisateur u ON u.pharmacie_id = p.id" + where)
    return get_db().execute(sql, params).fetchone()[0]


def lister_actives() -> list[Pharmacie]:
    rows = get_db().execute(_SELECT + " WHERE p.actif = 1 ORDER BY p.nom").fetchall()
    return [Pharmacie.from_row(r) for r in rows]


def creer(nom, adresse, telephone, quartier_id) -> int:
    cur = get_db().execute(
        "INSERT INTO pharmacie (nom, adresse, telephone, quartier_id) VALUES (?, ?, ?, ?)",
        (nom, adresse, telephone, quartier_id))
    return cur.lastrowid


def modifier(pharmacie_id, nom, adresse, telephone, quartier_id):
    get_db().execute(
        "UPDATE pharmacie SET nom = ?, adresse = ?, telephone = ?, quartier_id = ? WHERE id = ?",
        (nom, adresse, telephone, quartier_id, pharmacie_id))


def set_actif(pharmacie_id: int, actif: bool):
    get_db().execute("UPDATE pharmacie SET actif = ? WHERE id = ?", (1 if actif else 0, pharmacie_id))


def nom_existe(nom: str, quartier_id: int, sauf_id: int | None = None) -> bool:
    r = get_db().execute(
        "SELECT 1 FROM pharmacie WHERE norm(nom) = norm(?) AND quartier_id = ? AND (? IS NULL OR id != ?)",
        (nom, quartier_id, sauf_id, sauf_id)).fetchone()
    return r is not None


def compter_actives() -> int:
    return get_db().execute("SELECT COUNT(*) FROM pharmacie WHERE actif = 1").fetchone()[0]


def compter_total() -> int:
    return get_db().execute("SELECT COUNT(*) FROM pharmacie").fetchone()[0]


def sans_mise_a_jour(avant_iso: str) -> list[dict]:
    """Pharmacies actives dont la dernière déclaration de stock est antérieure (ou absente)."""
    rows = get_db().execute(
        """SELECT p.id, p.nom, q.nom AS quartier_nom, MAX(s.updated_at) AS derniere
             FROM pharmacie p
             JOIN quartier q ON q.id = p.quartier_id
             LEFT JOIN stock s ON s.pharmacie_id = p.id
            WHERE p.actif = 1
            GROUP BY p.id
           HAVING derniere IS NOT NULL AND derniere <= ?
            ORDER BY derniere ASC""", (avant_iso,)).fetchall()
    return [dict(r) for r in rows]
