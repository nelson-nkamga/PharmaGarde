from ..core.db import get_db
from ..models import Utilisateur

_SELECT = """
SELECT u.id, u.email, u.mot_de_passe_hash, u.role, u.pharmacie_id, u.actif,
       p.nom AS pharmacie_nom, p.actif AS pharmacie_actif, q.nom AS quartier_nom
  FROM utilisateur u
  LEFT JOIN pharmacie p ON p.id = u.pharmacie_id
  LEFT JOIN quartier  q ON q.id = p.quartier_id
"""


def get(user_id: int) -> Utilisateur | None:
    r = get_db().execute(_SELECT + " WHERE u.id = ?", (user_id,)).fetchone()
    return Utilisateur.from_row(r) if r else None


def par_email(email: str) -> Utilisateur | None:
    r = get_db().execute(_SELECT + " WHERE u.email = ?", (email,)).fetchone()
    return Utilisateur.from_row(r) if r else None


def creer(email: str, hash_: str, role: str, pharmacie_id: int | None) -> int:
    cur = get_db().execute(
        "INSERT INTO utilisateur (email, mot_de_passe_hash, role, pharmacie_id) VALUES (?, ?, ?, ?)",
        (email, hash_, role, pharmacie_id))
    return cur.lastrowid


def maj_email(pharmacie_id: int, email: str):
    get_db().execute("UPDATE utilisateur SET email = ? WHERE pharmacie_id = ?", (email, pharmacie_id))


def maj_hash(pharmacie_id: int, hash_: str):
    get_db().execute("UPDATE utilisateur SET mot_de_passe_hash = ? WHERE pharmacie_id = ?",
                     (hash_, pharmacie_id))


def email_pris(email: str, sauf_pharmacie_id: int | None = None) -> bool:
    r = get_db().execute(
        "SELECT 1 FROM utilisateur WHERE email = ? AND (? IS NULL OR pharmacie_id IS NOT ?)",
        (email, sauf_pharmacie_id, sauf_pharmacie_id)).fetchone()
    return r is not None


# ---- Limitation des tentatives de connexion -------------------------------------------
def enregistrer_echec(cle: str, date_iso: str):
    get_db().execute("INSERT INTO tentative_connexion (cle, date) VALUES (?, ?)", (cle, date_iso))


def compter_echecs(cle: str, depuis_iso: str) -> int:
    return get_db().execute("SELECT COUNT(*) FROM tentative_connexion WHERE cle = ? AND date >= ?",
                            (cle, depuis_iso)).fetchone()[0]


def purger_echecs(cle: str):
    get_db().execute("DELETE FROM tentative_connexion WHERE cle = ?", (cle,))
