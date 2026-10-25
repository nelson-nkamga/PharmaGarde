import re

from conftest import Client, PWD, db_rows


def test_connexion_pharmacien_redirige_vers_son_espace(app):
    c = Client(app)
    r = c.login("a@t.cm")
    assert r.status_code == 302 and r.headers["Location"].endswith("/pharmacien/")
    assert "Pharmacie A, Akwa" in c.get("/pharmacien/").get_data(as_text=True)


def test_connexion_admin_redirige_vers_l_administration(app):
    r = Client(app).login("admin@t.cm")
    assert r.headers["Location"].endswith("/admin/")


def test_mauvais_identifiants_meme_message(app):
    c = Client(app)
    r1 = c.login("a@t.cm", "mauvais")
    r2 = c.login("inconnu@t.cm", "mauvais")
    for r in (r1, r2):
        assert r.status_code == 401
        assert "Email ou mot de passe incorrect" in r.get_data(as_text=True)


def test_limitation_des_tentatives(app):
    c = Client(app)
    for _ in range(5):
        assert c.login("a@t.cm", "faux").status_code == 401
    r = c.login("a@t.cm", PWD)                              # même le bon mot de passe est refusé
    assert r.status_code == 429
    assert "Trop de tentatives, réessayez dans 5 minutes" in r.get_data(as_text=True)


def test_champs_vides(app):
    r = Client(app).c.post("/connexion", data={"email": "", "mot_de_passe": "",
                                               "csrf_token": Client(app).csrf()})
    assert r.status_code in (403, 422)


def test_acces_sans_connexion(app, client):
    r = client.get("/pharmacien/stocks")
    assert r.status_code == 302 and "/connexion?next=" in r.headers["Location"]
    assert client.get("/admin/").status_code == 302
    r = client.get("/api/pharmacies/999")
    assert r.status_code == 404 and r.get_json()["error"]["code"] == "RESSOURCE_INTROUVABLE"


def test_roles_etanches(app, pharm_a, admin):
    assert pharm_a.get("/admin/").status_code == 403
    assert pharm_a.get("/admin/pharmacies").status_code == 403
    assert admin.get("/pharmacien/").status_code == 403
    assert admin.get("/pharmacien/stocks").status_code == 403


def test_pas_de_redirection_ouverte(app):
    c = Client(app)
    tok = c.csrf("/connexion?next=https://evil.example")
    r = c.c.post("/connexion", data={"email": "a@t.cm", "mot_de_passe": PWD, "csrf_token": tok,
                                     "next": "https://evil.example/x"})
    assert r.headers["Location"].endswith("/pharmacien/")
    c2 = Client(app)
    tok = c2.csrf()
    r = c2.c.post("/connexion", data={"email": "a@t.cm", "mot_de_passe": PWD, "csrf_token": tok,
                                      "next": "//evil.example"})
    assert r.headers["Location"].endswith("/pharmacien/")
    c3 = Client(app)
    tok = c3.csrf()
    r = c3.c.post("/connexion", data={"email": "a@t.cm", "mot_de_passe": PWD, "csrf_token": tok,
                                      "next": "/pharmacien/gardes"})
    assert r.headers["Location"].endswith("/pharmacien/gardes")


def test_pharmacie_desactivee_ne_peut_plus_se_connecter(app):
    r = Client(app).login("d@t.cm")                           # pharmacie D déjà désactivée
    assert r.status_code == 403
    assert "compte est suspendu" in r.get_data(as_text=True)


def test_desactivation_coupe_la_session_en_cours(app, pharm_a, admin):
    assert pharm_a.get("/pharmacien/").status_code == 200
    admin.post("/admin/pharmacies/1/desactiver", {}, page="/admin/pharmacies")
    assert pharm_a.get("/pharmacien/").status_code == 302     # renvoyé vers la connexion
    admin.post("/admin/pharmacies/1/reactiver", {}, page="/admin/pharmacies")
    assert pharm_a.login("a@t.cm").status_code == 302


def test_mots_de_passe_jamais_en_clair(app):
    rows = db_rows(app, "SELECT mot_de_passe_hash FROM utilisateur")
    assert rows and all(PWD not in r["mot_de_passe_hash"] and ":" in r["mot_de_passe_hash"] for r in rows)


def test_en_tetes_de_securite(client):
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]
    assert "HttpOnly" in client.get("/connexion").headers.get("Set-Cookie", "")
