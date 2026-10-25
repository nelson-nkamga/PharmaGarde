"""Règle R2 : deux gardes d'une même pharmacie ne se chevauchent pas."""
import sqlite3
from datetime import timedelta

import pytest

from app.core import dates
from app.core.db import get_db
from app.core.errors import GardeChevauchement, ValidationError
from app.services import garde_service
from conftest import db_rows


def utc(day, hour):
    return dates.from_local(f"2026-10-{day:02d}", f"{hour:02d}:00")


def form(pid, d1, h1, d2, h2):
    return {"pharmacie_id": str(pid), "date_debut": f"2026-10-{d1:02d}", "heure_debut": f"{h1:02d}:00",
            "date_fin": f"2026-10-{d2:02d}", "heure_fin": f"{h2:02d}:00"}


def test_chevauchement_exact_partiel_et_inclus_sont_refuses(app):
    with app.app_context():
        garde_service.creer(3, utc(20, 19), utc(21, 7))
        for debut, fin in ((utc(20, 19), utc(21, 7)),       # identique
                           (utc(20, 22), utc(21, 10)),      # partiel (fin après)
                           (utc(20, 15), utc(20, 20)),      # partiel (début avant)
                           (utc(20, 21), utc(21, 1))):      # inclus
            with pytest.raises(GardeChevauchement):
                garde_service.creer(3, debut, fin)
        assert len(db_rows(app, "SELECT id FROM garde WHERE pharmacie_id=3")) == 1


def test_deux_gardes_qui_se_touchent_sont_autorisees(app):
    with app.app_context():
        garde_service.creer(3, utc(20, 19), utc(21, 7))
        garde_service.creer(3, utc(21, 7), utc(21, 19))      # fin = début : pas de chevauchement
        garde_service.creer(3, utc(20, 7), utc(20, 19))
    assert len(db_rows(app, "SELECT id FROM garde WHERE pharmacie_id=3")) == 3


def test_pharmacies_differentes_peuvent_etre_de_garde_en_meme_temps(app):
    with app.app_context():
        garde_service.creer(2, utc(15, 19), utc(16, 7))      # A est déjà de garde sur ce créneau
        garde_service.creer(3, utc(15, 19), utc(16, 7))


def test_modifier_une_garde_ne_la_compare_pas_a_elle_meme(app):
    with app.app_context():
        gid = garde_service.creer(3, utc(20, 19), utc(21, 7))
        garde_service.modifier(gid, 3, utc(20, 19), utc(21, 8))   # prolongée d'une heure
        autre = garde_service.creer(3, utc(22, 19), utc(23, 7))
        with pytest.raises(GardeChevauchement):
            garde_service.modifier(autre, 3, utc(21, 6), utc(22, 20))  # mord sur la première


def test_le_trigger_sql_protege_aussi_les_insertions_directes(app):
    with app.app_context():
        db = get_db()
        with pytest.raises(sqlite3.IntegrityError, match="GARDE_CHEVAUCHEMENT"):
            db.execute("INSERT INTO garde (pharmacie_id, date_debut, date_fin) VALUES (1, ?, ?)",
                       (dates.to_iso(utc(15, 20)), dates.to_iso(utc(15, 22))))


def test_validation_des_dates(app):
    with app.app_context():
        with pytest.raises(ValidationError) as e:
            garde_service.lire_formulaire(form(3, 21, 7, 20, 19))     # fin avant début
        assert "date_fin" in e.value.errors
        with pytest.raises(ValidationError):
            garde_service.lire_formulaire(form(3, 20, 7, 25, 19))     # plus de 48 h
        with pytest.raises(ValidationError) as e:
            garde_service.lire_formulaire(form(4, 20, 19, 21, 7))     # pharmacie D désactivée
        assert "pharmacie_id" in e.value.errors


def test_route_creation_puis_conflit_renvoie_409_avec_message(app, admin):
    r = admin.post("/admin/gardes/nouvelle", form(3, 20, 19, 21, 7), page="/admin/gardes/nouvelle")
    assert r.status_code == 302
    r = admin.post("/admin/gardes/nouvelle", form(3, 20, 22, 21, 9), page="/admin/gardes/nouvelle")
    assert r.status_code == 409
    html = r.get_data(as_text=True)
    assert "a déjà une garde qui chevauche cette période" in html
    assert "(du 20/10 à 19h au 21/10 à 07h)" in html
    assert "Créneau en conflit : du 20/10 à 22h00 au 21/10 à 09h00." in html or "Créneau en conflit" in html
    assert len(db_rows(app, "SELECT id FROM garde WHERE pharmacie_id=3")) == 1


def test_un_pharmacien_ne_peut_pas_gerer_le_planning(app, pharm_a):
    assert pharm_a.get("/admin/gardes").status_code == 403
    r = pharm_a.post("/admin/gardes/nouvelle", form(3, 20, 19, 21, 7), page="/pharmacien/")
    assert r.status_code == 403
    assert db_rows(app, "SELECT id FROM garde WHERE pharmacie_id=3") == []


def test_suppression_d_une_garde(app, admin):
    gid = db_rows(app, "SELECT id FROM garde WHERE pharmacie_id=2")[0]["id"]
    assert admin.get(f"/admin/gardes/{gid}/supprimer").status_code == 200
    assert admin.post(f"/admin/gardes/{gid}/supprimer", {}, page="/admin/gardes").status_code == 302
    assert db_rows(app, "SELECT id FROM garde WHERE pharmacie_id=2") == []
