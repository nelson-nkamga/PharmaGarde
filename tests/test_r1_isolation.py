"""Règle R1 : un pharmacien ne modifie que les stocks de SA pharmacie (identité = session)."""
from conftest import db_rows


def stock(app, pid, mid):
    return db_rows(app, "SELECT quantite, prix, updated_at FROM stock WHERE pharmacie_id=? AND medicament_id=?",
                   (pid, mid))[0]


def test_le_pharmacien_modifie_son_propre_stock(app, pharm_a):
    r = pharm_a.post("/pharmacien/stocks/1/modifier", {"quantite": "140", "prix": "550"}, page="/pharmacien/stocks")
    assert r.status_code == 302
    assert stock(app, 1, 1)["quantite"] == 140 and stock(app, 1, 1)["prix"] == 550
    assert stock(app, 2, 1)["quantite"] == 20          # la ligne de B (même médicament) n'a pas bougé


def test_impossible_de_modifier_une_ligne_qui_n_est_pas_dans_son_stock(app, pharm_a):
    avant = stock(app, 2, 3)                            # Doliprane : uniquement dans le stock de B
    r = pharm_a.post("/pharmacien/stocks/3/modifier", {"quantite": "1", "prix": "1"}, page="/pharmacien/stocks")
    assert r.status_code == 404
    assert stock(app, 2, 3) == avant


def test_un_champ_pharmacie_id_envoye_par_le_formulaire_est_refuse(app, pharm_a):
    avant = stock(app, 2, 1)
    r = pharm_a.post("/pharmacien/stocks/1/modifier", {"quantite": "1", "prix": "1", "pharmacie_id": "2"},
                     page="/pharmacien/stocks")
    assert r.status_code == 422
    assert stock(app, 2, 1) == avant and stock(app, 1, 1)["quantite"] == 50


def test_la_date_de_mise_a_jour_ne_peut_pas_etre_imposee_par_le_client(app, pharm_a):
    r = pharm_a.post("/pharmacien/stocks/1/modifier",
                     {"quantite": "10", "prix": "500", "updated_at": "2020-01-01T00:00:00Z"}, page="/pharmacien/stocks")
    assert r.status_code == 422
    assert stock(app, 1, 1)["quantite"] == 50


def test_impossible_de_retirer_le_stock_d_une_autre_pharmacie(app, pharm_a):
    r = pharm_a.post("/pharmacien/stocks/3/retirer", {}, page="/pharmacien/stocks")
    assert r.status_code == 404
    assert stock(app, 2, 3)["quantite"] == 10


def test_ajout_va_toujours_dans_la_pharmacie_de_la_session(app, pharm_b):
    r = pharm_b.post("/pharmacien/stocks/ajouter", {"medicament_id": "4", "quantite": "7", "prix": "2600"},
                     page="/pharmacien/stocks")
    assert r.status_code == 302
    assert db_rows(app, "SELECT pharmacie_id FROM stock WHERE medicament_id=4 AND quantite=7") == [{"pharmacie_id": 2}]


def test_la_liste_ne_montre_que_les_stocks_de_la_pharmacie_connectee(app, pharm_a):
    html = pharm_a.get("/pharmacien/stocks").get_data(as_text=True)
    assert "Doliprane" not in html and "Paracétamol" in html


def test_un_lot_d_import_d_une_autre_pharmacie_est_refuse(app, pharm_a, pharm_b):
    csv = "medicament;dosage;forme;quantite;prix_fcfa\r\nParacétamol;500 mg;Comprimé;11;520\r\n".encode()
    import io
    r = pharm_a.c.post("/pharmacien/stocks/importer", data={"fichier": (io.BytesIO(csv), "s.csv"),
                       "csrf_token": pharm_a.csrf("/pharmacien/stocks/importer")}, content_type="multipart/form-data")
    import re
    token = re.search(r'name="token" value="([^"]+)"', r.get_data(as_text=True)).group(1)
    r2 = pharm_b.post("/pharmacien/stocks/importer/confirmer", {"token": token}, page="/pharmacien/stocks")
    assert r2.status_code == 410
    assert stock(app, 2, 1)["quantite"] == 20          # rien d'appliqué chez B
