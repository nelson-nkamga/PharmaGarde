from ..core.db import get_db


def enregistrer(terme: str, medicament_id: int | None, quartier_id: int | None,
                nb_resultats: int, now_iso: str):
    get_db().execute(
        "INSERT INTO recherche_log (terme, medicament_id, quartier_id, nb_resultats, date) VALUES (?, ?, ?, ?, ?)",
        (terme[:120], medicament_id, quartier_id, nb_resultats, now_iso))
