from ..core.db import get_db
from ..core.text import norm
from ..models import Medicament

_SELECT = """
SELECT m.id, m.nom, m.dosage, m.forme, m.conditionnement, m.principe_actif_id,
       pa.nom AS principe_actif {extra}
  FROM medicament m
  LEFT JOIN principe_actif pa ON pa.id = m.principe_actif_id
"""
_HAYSTACK = "norm(m.nom || ' ' || m.dosage || ' ' || m.forme)"


def get(medicament_id: int) -> Medicament | None:
    r = get_db().execute(_SELECT.format(extra="") + " WHERE m.id = ?", (medicament_id,)).fetchone()
    return Medicament.from_row(r) if r else None


def rechercher(q: str, limit: int = 50, pharmacie_id: int | None = None) -> list[Medicament]:
    """Recherche par mots (début de mot, sans accents) sur nom + dosage + forme."""
    tokens = norm(q).split()[:6]
    where, params = [], []
    for tok in tokens:
        tok = tok.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append(f"(' ' || {_HAYSTACK}) LIKE ? ESCAPE '\\'")
        params.append(f"% {tok}%")
    extra, extra_params = "", []
    if pharmacie_id is not None:
        extra = ", EXISTS(SELECT 1 FROM stock s WHERE s.medicament_id = m.id AND s.pharmacie_id = ?) AS deja_en_stock"
        extra_params = [pharmacie_id]
    sql = _SELECT.format(extra=extra) + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY m.nom, m.dosage LIMIT ?"
    rows = get_db().execute(sql, extra_params + params + [limit]).fetchall()
    return [Medicament.from_row(r) for r in rows]


def frequents(depuis_iso: str, limit: int = 6) -> list[Medicament]:
    """Médicaments les plus recherchés récemment (complétés par le catalogue si besoin)."""
    rows = get_db().execute(
        _SELECT.format(extra="") + """
          JOIN (SELECT medicament_id, COUNT(*) n FROM recherche_log
                 WHERE medicament_id IS NOT NULL AND date >= ?
                 GROUP BY medicament_id) r ON r.medicament_id = m.id
         ORDER BY r.n DESC, m.nom LIMIT ?""", (depuis_iso, limit)).fetchall()
    result = [Medicament.from_row(r) for r in rows]
    if len(result) < limit:
        ids = [m.id for m in result] or [0]
        marks = ",".join("?" * len(ids))
        rows = get_db().execute(
            _SELECT.format(extra="") + f" WHERE m.id NOT IN ({marks}) ORDER BY m.id LIMIT ?",
            ids + [limit - len(result)]).fetchall()
        result += [Medicament.from_row(r) for r in rows]
    return result


def equivalents(principe_actif_id: int | None, exclure_ids: list[int], limit: int = 8) -> list[Medicament]:
    if not principe_actif_id:
        return []
    ids = exclure_ids or [0]
    marks = ",".join("?" * len(ids))
    rows = get_db().execute(
        _SELECT.format(extra="") +
        f" WHERE m.principe_actif_id = ? AND m.id NOT IN ({marks}) ORDER BY m.nom, m.dosage LIMIT ?",
        [principe_actif_id] + ids + [limit]).fetchall()
    return [Medicament.from_row(r) for r in rows]


def trouver(nom: str, dosage: str, forme: str) -> Medicament | None:
    r = get_db().execute(
        _SELECT.format(extra="") +
        " WHERE norm(m.nom) = norm(?) AND norm(m.dosage) = norm(?) AND norm(m.forme) = norm(?)",
        (nom, dosage, forme)).fetchone()
    return Medicament.from_row(r) if r else None


def compter() -> int:
    return get_db().execute("SELECT COUNT(*) FROM medicament").fetchone()[0]
