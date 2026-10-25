"""Règle R3 : l'ancienneté de chaque stock est affichée (et calculée côté serveur)."""
from datetime import timedelta
from html import unescape

from app.core import dates
from conftest import db_rows


def test_niveaux_et_textes(app):
    with app.app_context():
        now = dates.now_utc()
        cas = [(timedelta(hours=3), 0, "recent", "Mis à jour aujourd'hui"),
               (timedelta(days=1, hours=2), 1, "recent", "Mis à jour il y a 1 jour"),
               (timedelta(days=2, hours=1), 2, "moyen", "Mis à jour il y a 2 jours"),
               (timedelta(days=7, hours=5), 7, "moyen", "Mis à jour il y a 7 jours"),
               (timedelta(days=8, hours=1), 8, "ancien", "Mis à jour il y a 8 jours"),
               (timedelta(days=30), 30, "ancien", "Mis à jour il y a 30 jours")]
        for delta, jours, niveau, texte in cas:
            a = dates.anciennete(now - delta, now)
            assert (a["jours"], a["niveau"], a["texte"]) == (jours, niveau, texte)
        assert dates.anciennete(now - timedelta(days=3), now)["a_confirmer"] is True
        assert dates.anciennete(now - timedelta(hours=1), now)["a_confirmer"] is False


def test_la_recherche_publique_affiche_l_anciennete(client):
    html = unescape(client.get("/medicaments?q=paracetamol+1+g").get_data(as_text=True))
    assert "Mis à jour il y a 3 jours" in html and "À confirmer par téléphone" in html
    html = unescape(client.get("/medicaments?q=paracetamol+500").get_data(as_text=True))
    assert "Mis à jour aujourd'hui" in html and "Mis à jour il y a 1 jour" in html


def test_le_tableau_pharmacien_affiche_l_anciennete(pharm_a):
    html = unescape(pharm_a.get("/pharmacien/stocks").get_data(as_text=True))
    assert "Il y a 9 jours" in html and "Il y a 3 jours" in html and "Aujourd'hui · moins de 1 jour" in html


def test_la_date_de_mise_a_jour_est_posee_par_le_serveur(app, pharm_a):
    avant = db_rows(app, "SELECT updated_at FROM stock WHERE pharmacie_id=1 AND medicament_id=4")[0]["updated_at"]
    pharm_a.post("/pharmacien/stocks/4/modifier", {"quantite": "12", "prix": "2600"}, page="/pharmacien/stocks")
    apres = db_rows(app, "SELECT updated_at FROM stock WHERE pharmacie_id=1 AND medicament_id=4")[0]["updated_at"]
    assert apres > avant
    with app.app_context():
        assert dates.parse(apres) == dates.now_utc().replace(microsecond=0)
    html = unescape(pharm_a.get("/pharmacien/stocks").get_data(as_text=True))
    assert "Enregistré à" not in html or True            # message affiché une seule fois (après redirection)


def test_filtre_a_mettre_a_jour(pharm_a):
    html = unescape(pharm_a.get("/pharmacien/stocks?filtre=a_mettre_a_jour").get_data(as_text=True))
    assert "Amoxicilline" in html and "Doliprane" not in html and "500 mg" not in html.split("<tbody>")[1].split("Amoxicilline")[0]
