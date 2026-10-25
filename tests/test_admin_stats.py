from html import unescape

from app.core import dates
from app.services import stats_service
from conftest import db_rows


def test_creation_d_une_pharmacie_cree_aussi_le_compte(app, admin):
    r = admin.post("/admin/pharmacies", {"nom": "Pharmacie Neuve", "adresse": "Rue Neuve 1", "quartier_id": "2",
                   "telephone": "+237 690 100 130", "email": "neuve@t.cm", "mot_de_passe": "UnMotDePasse12!"},
                   page="/admin/pharmacies/nouvelle")
    assert r.status_code == 302
    assert db_rows(app, "SELECT role, pharmacie_id FROM utilisateur WHERE email='neuve@t.cm'")[0]["role"] == "pharmacien"
    from conftest import Client
    c = Client(app)
    assert c.login("neuve@t.cm", "UnMotDePasse12!").status_code == 302


def test_validation_du_formulaire_pharmacie(app, admin):
    r = admin.post("/admin/pharmacies", {"nom": "", "adresse": "x", "quartier_id": "99", "telephone": "abc",
                   "email": "pas-un-email", "mot_de_passe": "court"}, page="/admin/pharmacies/nouvelle")
    assert r.status_code == 422
    html = unescape(r.get_data(as_text=True))
    for msg in ("Saisissez le nom", "Choisissez un quartier", "numéro valide", "e-mail valide"):
        assert msg in html
    assert "12 caractères" in html
    r = admin.post("/admin/pharmacies", {"nom": "Autre", "adresse": "Rue Y", "quartier_id": "1",
                   "telephone": "+237 690 100 140", "email": "a@t.cm", "mot_de_passe": "UnMotDePasse12!"},
                   page="/admin/pharmacies/nouvelle")
    assert r.status_code == 422 and "déjà utilisée" in unescape(r.get_data(as_text=True))


def test_modification_et_changement_de_mot_de_passe(app, admin):
    r = admin.post("/admin/pharmacies/3/modifier", {"nom": "Pharmacie C bis", "adresse": "Rue C", "quartier_id": "3",
                   "telephone": "+237 690 000 003", "email": "c2@t.cm", "mot_de_passe": "NouveauMdp2026!"},
                   page="/admin/pharmacies")
    assert r.status_code == 302
    from conftest import Client
    assert Client(app).login("c2@t.cm", "NouveauMdp2026!").status_code == 302


def test_pagination_et_recherche_des_pharmacies(admin):
    html = unescape(admin.get("/admin/pharmacies?q=akwa").get_data(as_text=True))
    assert "Pharmacie A" in html and "Pharmacie B" not in html
    assert "Désactivée" in admin.get("/admin/pharmacies?statut=desactivees").get_data(as_text=True)
    assert "Pharmacie D" in admin.get("/admin/pharmacies?statut=desactivees").get_data(as_text=True)


def test_statistiques_prix(app):
    with app.app_context():
        lignes = {f"{l['nom']} {l['dosage']}": l for l in stats_service.prix("", 100)["lignes"]}
    p = lignes["Paracétamol 500 mg"]
    assert (p["prix_min"], p["prix_moyen"], p["prix_max"], p["nb_pharmacies"]) == (500, 550, 600, 2)


def test_statistiques_ruptures_partout(app):
    with app.app_context():
        noms = [r["nom"] for r in stats_service.ruptures()["lignes"]]
    # Amoxicilline (0 chez A, seule pharmacie qui la déclare) et Salbutamol (0 chez A et B) : aucune dispo dans le réseau
    assert noms == ["Amoxicilline", "Salbutamol"]
    with app.app_context():
        from app.core.db import get_db
        get_db().execute("UPDATE stock SET quantite = 4 WHERE pharmacie_id = 2 AND medicament_id = 5")
        assert [r["nom"] for r in stats_service.ruptures()["lignes"]] == ["Amoxicilline"]   # dès qu'une pharmacie en a, il sort de la liste


def test_statistiques_recherches_et_gardes(app, client, admin):
    for _ in range(3):
        client.get("/medicaments?m=1")
    client.get("/medicaments?m=2")
    with app.app_context():
        top = stats_service.recherches("30")["lignes"]
        assert top[0]["libelle"] == "Paracétamol 500 mg" and top[0]["nb"] == 3
        g = stats_service.gardes()
        assert {l["nom"]: l["nb_gardes"] for l in g["lignes"]}["Pharmacie A"] == 1
        assert "Pharmacie D" not in {l["nom"] for l in g["lignes"]}     # désactivée : exclue
    html = admin.get("/admin/statistiques").get_data(as_text=True)
    assert "Prix par médicament" in html and "Médicaments les plus recherchés" in html
    assert "Nombre de gardes par pharmacie" in html and "Médicaments en rupture partout" in html


def test_exports_csv_et_protection_injection(app, admin):
    for nom in ("prix", "recherches", "gardes", "ruptures"):
        r = admin.get(f"/admin/statistiques/{nom}.csv")
        assert r.status_code == 200 and r.mimetype == "text/csv"
    assert stats_service.vers_csv(["a"], [["=1+1"], ["+cmd"], ["@x"], ["ok"]]).count("'=1+1") == 1
    assert "'+cmd" in stats_service.vers_csv(["a"], [["+cmd"]])


def test_tableau_de_bord_admin(admin):
    html = unescape(admin.get("/admin/").get_data(as_text=True))
    assert "Pharmacies" in html and "En rupture partout" in html and "Salbutamol" in html


def test_planning_hors_cycle_et_semaine_invalide(admin):
    assert admin.get("/admin/gardes?semaine=99").status_code == 200
    assert admin.get("/admin/gardes?semaine=abc").status_code == 200
    assert admin.get("/admin/gardes/9999/modifier").status_code == 404
