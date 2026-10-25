from ..core.db import get_db
from ..models import Quartier


def lister() -> list[Quartier]:
    rows = get_db().execute("SELECT id, nom FROM quartier ORDER BY id").fetchall()
    return [Quartier.from_row(r) for r in rows]


def get(quartier_id: int) -> Quartier | None:
    r = get_db().execute("SELECT id, nom FROM quartier WHERE id = ?", (quartier_id,)).fetchone()
    return Quartier.from_row(r) if r else None
