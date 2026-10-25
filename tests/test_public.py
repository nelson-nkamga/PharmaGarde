from html import unescape

from conftest import db_rows


def page(resp):
    return unescape(resp.get_data(as_text=True))


def test_accueil_liste_les_pharmacies_de_garde_actives(client):
    html = page(client.get("/"))
    assert "Pharmacie A" in html and "De garde jusqu'à 07h00" in html
    assert "Pharmacie B" not in html           # garde demain
    assert "Pharmacie D" not in html           # désactivée : jamais visible


def test_filtre_par_quartier_et_etat_vide(client):
    assert "Pharmacie A" in page(client.get("/?quartier=1"))
    html = page(client.get("/?quartier=3"))
    assert "Aucune pharmacie de garde dans ce quartier" in html and "Choisir un autre quartier" in html
    assert client.get("/?quartier=99").status_code == 404


def test_recherche_insensible_aux_accents_et_a_la_casse(client):
    for q in ("paracetamol 500", "PARACÉTAMOL 500 mg", "Paracétamol 500 mg"):
        html = page(client.get("/medicaments", query_string={"q": q}))
        assert "Pharmacie A" in html and "Pharmacie B" in html and "2 pharmacies" in html
    html = page(client.get("/medicaments?q=paracetamol+500+mg"))
    assert "De garde" in html                                         # A est de garde


def test_recherche_ne_melange_pas_les_dosages(client):
    html = page(client.get("/medicaments?q=paracetamol+1+g"))
    assert "Pharmacie A" in html and "Pharmacie B" not in html


def test_aucun_resultat(client):
    html = page(client.get("/medicaments?q=paracetamol+1+g&quartier=3&stock=1"))
    assert "Aucun résultat pour ce médicament" in html and "Cela ne signifie pas que le médicament est indisponible" in html
    assert "Réinitialiser les filtres" in html
    assert client.get("/medicaments?q=xyzabc").status_code == 200


def test_filtre_en_stock(client):
    avec = page(client.get("/medicaments?q=amoxicilline"))
    sans = page(client.get("/medicaments?q=amoxicilline&stock=1"))
    assert "Rupture" in avec and "Pharmacie A" in avec
    assert "Aucun résultat" in sans


def test_equivalents_meme_principe_actif(client):
    html = page(client.get("/medicaments?q=paracetamol+1+g&quartier=3"))
    assert "Paracétamol 500 mg" in html and "Doliprane 1000 mg" in html


def test_les_recherches_sont_enregistrees(app, client):
    client.get("/medicaments?q=paracetamol+500+mg")
    client.get("/medicaments?m=4")
    rows = db_rows(app, "SELECT terme, medicament_id, nb_resultats FROM recherche_log ORDER BY id")
    assert rows[0]["nb_resultats"] == 2 and rows[1]["medicament_id"] == 4


def test_stock_masque_pour_une_pharmacie_desactivee(app, client, admin):
    admin.post("/admin/pharmacies/2/desactiver", {}, page="/admin/pharmacies")
    html = page(client.get("/medicaments?q=paracetamol+500"))
    assert "Pharmacie B" not in html and "Pharmacie A" in html
    assert client.get("/api/pharmacies/2").status_code == 404


def test_page_de_suggestions(client):
    html = page(client.get("/medicaments"))
    assert "Médicaments fréquents" in html and "Où cherchez-vous ?" in html


def test_api_json(client):
    assert [q["nom"] for q in client.get("/api/quartiers").get_json()["data"]] == ["Akwa", "Deido", "Makepe"]
    g = client.get("/api/gardes/en-cours").get_json()
    assert g["meta"]["total"] == 1 and g["data"][0]["pharmacie"]["nom"] == "Pharmacie A"
    assert client.get("/api/gardes/en-cours?quartier_id=2").get_json()["data"] == []
    assert client.get("/api/gardes/en-cours?quartier_id=99").status_code == 404
    p = client.get("/api/pharmacies/1").get_json()["data"]
    assert p["de_garde_maintenant"] is True and p["quartier"]["nom"] == "Akwa"
    s = client.get("/api/medicaments/suggestions?q=para").get_json()["data"]
    assert {m["libelle"] for m in s} >= {"Paracétamol 500 mg", "Paracétamol 1 g"}
    assert client.get("/api/medicaments/suggestions?q=p").get_json()["data"] == []


def test_les_pages_privees_ne_sont_pas_indexables(pharm_a, admin):
    assert "noindex" in pharm_a.get("/pharmacien/").get_data(as_text=True)
    assert "noindex" in admin.get("/admin/").get_data(as_text=True)


def test_echappement_html(client):
    html = client.get("/medicaments", query_string={"q": "<script>alert(1)</script>"}).get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html


def test_recherche_avec_caracteres_speciaux_sql(client):
    for q in ("%", "_", "'; DROP TABLE stock; --", "a\\b"):
        assert client.get("/medicaments", query_string={"q": q}).status_code == 200
    assert client.get("/medicaments?q=paracetamol").status_code == 200
