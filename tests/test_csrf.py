from conftest import Client, db_rows


def test_post_sans_jeton_est_refuse(app):
    c = app.test_client()
    r = c.post("/connexion", data={"email": "a@t.cm", "mot_de_passe": "x"})
    assert r.status_code == 403
    assert "expiré" in r.get_data(as_text=True) or "invalide" in r.get_data(as_text=True)


def test_jeton_invalide_est_refuse(app):
    c = app.test_client()
    c.get("/connexion")
    r = c.post("/connexion", data={"email": "a@t.cm", "mot_de_passe": "x", "csrf_token": "faux"})
    assert r.status_code == 403


def test_modification_de_stock_exige_le_jeton(app, pharm_a):
    r = pharm_a.c.post("/pharmacien/stocks/1/modifier", data={"quantite": "999", "prix": "1"})
    assert r.status_code == 403
    ligne = db_rows(app, "SELECT quantite, prix FROM stock WHERE pharmacie_id=1 AND medicament_id=1")[0]
    assert ligne == {"quantite": 50, "prix": 500}


def test_deconnexion_est_un_post_protege(app, pharm_a):
    assert pharm_a.get("/deconnexion").status_code == 405
    assert pharm_a.c.post("/deconnexion").status_code == 403           # sans jeton
    r = pharm_a.post("/deconnexion", page="/pharmacien/")
    assert r.status_code == 302
    assert pharm_a.get("/pharmacien/").status_code == 302                # session détruite


def test_verification_json_exige_l_en_tete_csrf(app, admin):
    data = {"pharmacie_id": "1", "date_debut": "2026-10-20", "heure_debut": "19:00",
            "date_fin": "2026-10-21", "heure_fin": "07:00"}
    assert admin.c.post("/admin/gardes/verifier", data=data).status_code == 403
    token = admin.csrf("/admin/gardes")
    r = admin.c.post("/admin/gardes/verifier", data=data, headers={"X-CSRF-Token": token})
    assert r.status_code == 200 and r.get_json()["data"]["valide"] is True


def test_le_jeton_est_regenere_a_la_connexion(app):
    c = Client(app)
    avant = c.csrf()
    c.login("a@t.cm")
    apres = c.csrf("/pharmacien/")
    assert avant != apres


def test_tous_les_formulaires_post_contiennent_le_jeton(app, pharm_a, admin):
    import re
    pages = [(pharm_a, "/pharmacien/stocks?modifier=1"), (pharm_a, "/pharmacien/stocks/ajouter?medicament=3"),
             (pharm_a, "/pharmacien/stocks/importer"), (admin, "/admin/pharmacies/nouvelle"),
             (admin, "/admin/gardes/nouvelle"), (admin, "/admin/gardes/1/supprimer"),
             (admin, "/admin/pharmacies/1/desactiver")]
    for client, url in pages:
        html = client.get(url).get_data(as_text=True)
        for form in re.findall(r"<form\b[^>]*>", html):
            if 'method="post"' in form:
                start = html.index(form)
                fin = html.index("</form>", start)
                assert 'name="csrf_token"' in html[start:fin], f"jeton manquant dans {form} ({url})"
