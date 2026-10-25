import io
import re
from html import unescape

import pytest

from app.services import stock_service
from conftest import db_rows

ENTETE = "medicament;dosage;forme;quantite;prix_fcfa\r\n"


@pytest.mark.parametrize("q,p,champs", [
    ("-2,5", "0", {"quantite", "prix"}), ("abc", "100", {"quantite"}), ("10", "-5", {"prix"}),
    ("1,5", "100", {"quantite"}), ("10", "12,5", {"prix"}), ("", "", {"quantite", "prix"}),
    ("0", "1", set()), ("1 200", "1 500", set()), ("10", "99999999", {"prix"})])
def test_validation_quantite_prix(app, q, p, champs):
    with app.app_context():
        _, _, errors = stock_service.valider(q, p)
        assert set(errors) == champs


def test_messages_des_maquettes(app):
    with app.app_context():
        _, _, e = stock_service.valider("-2,5", "0")
        assert e["quantite"] == "La quantité doit être un nombre entier positif ou nul"
        assert e["prix"] == "Le prix doit être supérieur à 0"


def test_modification_invalide_reaffiche_les_erreurs_sans_rien_enregistrer(app, pharm_a):
    r = pharm_a.post("/pharmacien/stocks/1/modifier", {"quantite": "-2,5", "prix": "0"}, page="/pharmacien/stocks")
    assert r.status_code == 422
    html = unescape(r.get_data(as_text=True))
    assert "La quantité doit être un nombre entier positif ou nul" in html and "Le prix doit être supérieur à 0" in html
    assert 'value="-2,5"' in html
    assert db_rows(app, "SELECT quantite FROM stock WHERE pharmacie_id=1 AND medicament_id=1")[0]["quantite"] == 50


def test_modification_reussie_affiche_le_message(app, pharm_a):
    r = pharm_a.post("/pharmacien/stocks/1/modifier", {"quantite": "140", "prix": "550"}, page="/pharmacien/stocks",
                     follow_redirects=True)
    html = unescape(r.get_data(as_text=True))
    assert "Stock mis à jour" in html and "Enregistré à 20h30" in html


def test_ajout_et_doublon(app, pharm_a):
    r = pharm_a.post("/pharmacien/stocks/ajouter", {"medicament_id": "1", "quantite": "5", "prix": "100"},
                     page="/pharmacien/stocks")
    assert r.status_code == 409
    html = unescape(r.get_data(as_text=True))
    assert "Ce médicament est déjà dans votre stock" in html and "Modifier ce médicament" in html
    assert db_rows(app, "SELECT quantite FROM stock WHERE pharmacie_id=1 AND medicament_id=1")[0]["quantite"] == 50
    r = pharm_a.post("/pharmacien/stocks/ajouter", {"medicament_id": "3", "quantite": "9", "prix": "1400"},
                     page="/pharmacien/stocks")
    assert r.status_code == 302
    assert db_rows(app, "SELECT quantite, prix FROM stock WHERE pharmacie_id=1 AND medicament_id=3") == [{"quantite": 9, "prix": 1400}]


def test_ajout_sans_medicament_ou_valeurs_invalides(app, pharm_a):
    assert pharm_a.post("/pharmacien/stocks/ajouter", {"quantite": "1", "prix": "1"}, page="/pharmacien/stocks").status_code == 422
    assert pharm_a.post("/pharmacien/stocks/ajouter", {"medicament_id": "3", "quantite": "x", "prix": "0"},
                        page="/pharmacien/stocks").status_code == 422
    assert pharm_a.post("/pharmacien/stocks/ajouter", {"medicament_id": "999", "quantite": "1", "prix": "1"},
                        page="/pharmacien/stocks").status_code == 404


def test_catalogue_signale_les_doublons(pharm_a):
    html = unescape(pharm_a.get("/pharmacien/stocks/ajouter?q_med=").get_data(as_text=True))
    assert "Déjà dans votre stock" in html and "Disponible à l'ajout" in html


def _envoyer(client, contenu: bytes, nom="stock.csv"):
    return client.c.post("/pharmacien/stocks/importer", content_type="multipart/form-data",
                         data={"fichier": (io.BytesIO(contenu), nom),
                               "csrf_token": client.csrf("/pharmacien/stocks/importer")})


def test_import_csv_apercu_puis_confirmation(app, pharm_a):
    csv = (ENTETE + "Paracétamol;500 mg;Comprimé;120;500\r\nDoliprane;1000 mg;Comprimé;30;1400\r\n").encode("utf-8-sig")
    r = _envoyer(pharm_a, csv)
    html = unescape(r.get_data(as_text=True))
    assert r.status_code == 200 and "2 lignes valides · 1 à ajouter · 1 à mettre à jour" in html
    assert db_rows(app, "SELECT quantite FROM stock WHERE pharmacie_id=1 AND medicament_id=1")[0]["quantite"] == 50  # rien d'écrit
    token = re.search(r'name="token" value="([^"]+)"', html).group(1)
    r = pharm_a.post("/pharmacien/stocks/importer/confirmer", {"token": token}, page="/pharmacien/stocks")
    assert r.status_code == 302
    assert db_rows(app, "SELECT quantite, prix FROM stock WHERE pharmacie_id=1 AND medicament_id=1") == [{"quantite": 120, "prix": 500}]
    assert db_rows(app, "SELECT quantite FROM stock WHERE pharmacie_id=1 AND medicament_id=3") == [{"quantite": 30}]
    assert pharm_a.post("/pharmacien/stocks/importer/confirmer", {"token": token}, page="/pharmacien/stocks").status_code == 410  # usage unique


def test_import_csv_avec_erreurs_bloque_l_import(app, pharm_a):
    csv = (ENTETE + "Paracétamol;500 mg;Comprimé;-1;500\r\nInconnu;1 g;Comprimé;5;100\r\n"
           "Doliprane;1000 mg;Comprimé;5;100\r\nDoliprane;1000 mg;Comprimé;6;100\r\nxx;yy\r\n").encode()
    html = unescape(_envoyer(pharm_a, csv).get_data(as_text=True))
    assert "4 erreurs" in html and "Médicament inconnu" in html and "Doublon dans le fichier" in html
    assert 'name="token"' not in html and re.search(r'<button[^>]*disabled[^>]*>Importer</button>', html)


def test_import_csv_formats_refuses(app, pharm_a):
    assert "Seuls les fichiers .csv" in unescape(_envoyer(pharm_a, b"x", "a.exe").get_data(as_text=True))
    assert "En-têtes attendus" in unescape(_envoyer(pharm_a, b"a;b\r\n1;2\r\n").get_data(as_text=True))
    assert "UTF-8" in unescape(_envoyer(pharm_a, ENTETE.encode() + "Paracétamol;500 mg;Comprimé;1;1".encode("latin-1")
                                        + b"\xe9").get_data(as_text=True))
    assert "vide" in unescape(_envoyer(pharm_a, b"").get_data(as_text=True))


def test_modele_csv(pharm_a):
    r = pharm_a.get("/pharmacien/stocks/modele.csv")
    assert r.mimetype == "text/csv" and "medicament;dosage;forme;quantite;prix_fcfa" in r.get_data(as_text=True)


def test_retirer_du_stock(app, pharm_a):
    assert pharm_a.post("/pharmacien/stocks/2/retirer", {}, page="/pharmacien/stocks").status_code == 302
    assert db_rows(app, "SELECT 1 FROM stock WHERE pharmacie_id=1 AND medicament_id=2") == []
