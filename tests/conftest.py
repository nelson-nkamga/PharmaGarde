import re
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.core import dates  # noqa: E402
from app.core.db import get_db, init_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from config import TestConfig  # noqa: E402

PWD = "MotDePasse2026!"
DEMO_NOW = "2026-10-15T20:30"          # heure de Douala (19h30 UTC)


def iso(dt):
    return dates.to_iso(dt)


@pytest.fixture
def app(tmp_path):
    cfg = type("Cfg", (TestConfig,), {"DATABASE": str(tmp_path / "test.db"), "DEMO_NOW": DEMO_NOW})
    app = create_app(cfg)
    with app.app_context():
        init_db()
        _seed(get_db())
    return app


def _seed(db):
    now = dates.now_utc()
    for nom in ("Akwa", "Deido", "Makepe"):
        db.execute("INSERT INTO quartier (nom) VALUES (?)", (nom,))
    pharm = [("Pharmacie A", "Rue A", "+237 690 000 001", 1, 1), ("Pharmacie B", "Rue B", "+237 690 000 002", 2, 1),
             ("Pharmacie C", "Rue C", "+237 690 000 003", 3, 1), ("Pharmacie D", "Rue D", "+237 690 000 004", 1, 0)]
    for p in pharm:
        db.execute("INSERT INTO pharmacie (nom, adresse, telephone, quartier_id, actif) VALUES (?,?,?,?,?)", p)
    h = hash_password(PWD)
    for email, role, pid in (("a@t.cm", "pharmacien", 1), ("b@t.cm", "pharmacien", 2), ("c@t.cm", "pharmacien", 3),
                             ("d@t.cm", "pharmacien", 4), ("admin@t.cm", "admin", None)):
        db.execute("INSERT INTO utilisateur (email, mot_de_passe_hash, role, pharmacie_id) VALUES (?,?,?,?)",
                   (email, h, role, pid))
    db.execute("INSERT INTO principe_actif (nom) VALUES ('Paracétamol')")
    db.execute("INSERT INTO principe_actif (nom) VALUES ('Amoxicilline')")
    meds = [("Paracétamol", "500 mg", "Comprimé", "Boîte de 20", 1), ("Paracétamol", "1 g", "Comprimé", "Boîte de 8", 1),
            ("Doliprane", "1000 mg", "Comprimé", "Boîte de 8", 1), ("Amoxicilline", "1 g", "Comprimé dispersible", "Boîte de 12", 2),
            ("Salbutamol", "100 µg/dose", "Aérosol doseur", "Flacon", None)]
    for m in meds:
        db.execute("INSERT INTO medicament (nom, dosage, forme, conditionnement, principe_actif_id) VALUES (?,?,?,?,?)", m)

    def stock(p, m, q, prix, age_days, hours=0):
        db.execute("INSERT INTO stock VALUES (?,?,?,?,?)",
                   (p, m, q, prix, iso(now - timedelta(days=age_days, hours=hours))))
    stock(1, 1, 50, 500, 0, 2)      # A : Paracétamol 500, frais
    stock(1, 2, 5, 900, 3)          # A : Paracétamol 1 g, stock faible, 3 jours
    stock(1, 4, 0, 2500, 9)         # A : Amoxicilline, rupture, 9 jours
    stock(2, 1, 20, 600, 1)         # B : Paracétamol 500
    stock(2, 3, 10, 1500, 2)        # B seule : Doliprane
    stock(1, 5, 0, 1800, 4)         # Salbutamol : rupture partout
    stock(2, 5, 0, 1900, 4)
    # Gardes : A et D de garde maintenant (18h00-06h00 UTC), B demain
    debut = now.replace(hour=18, minute=0, second=0, microsecond=0)
    for pid, d in ((1, debut), (4, debut), (2, debut + timedelta(days=1))):
        db.execute("INSERT INTO garde (pharmacie_id, date_debut, date_fin) VALUES (?,?,?)",
                   (pid, iso(d), iso(d + timedelta(hours=12))))
    db.execute("INSERT INTO parametre (cle, valeur) VALUES ('planning_debut', ?)", (iso(dates.monday_of(now)),))


def token_of(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "jeton CSRF introuvable dans la page"
    return m.group(1)


class Client:
    """Petit client de test qui gère le jeton CSRF comme un navigateur."""

    def __init__(self, app):
        self.c = app.test_client()

    def csrf(self, url="/connexion"):
        return token_of(self.c.get(url).get_data(as_text=True))

    def login(self, email, pwd=PWD):
        return self.c.post("/connexion", data={"email": email, "mot_de_passe": pwd, "csrf_token": self.csrf()})

    def post(self, url, data=None, page="/connexion", **kw):
        data = dict(data or {})
        data["csrf_token"] = self.csrf(page)
        return self.c.post(url, data=data, **kw)

    def get(self, url, **kw):
        return self.c.get(url, **kw)


@pytest.fixture
def client(app):
    return Client(app)


@pytest.fixture
def pharm_a(app):
    c = Client(app)
    assert c.login("a@t.cm").status_code == 302
    return c


@pytest.fixture
def pharm_b(app):
    c = Client(app)
    assert c.login("b@t.cm").status_code == 302
    return c


@pytest.fixture
def admin(app):
    c = Client(app)
    assert c.login("admin@t.cm").status_code == 302
    return c


def db_rows(app, sql, params=()):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql, params).fetchall()]
