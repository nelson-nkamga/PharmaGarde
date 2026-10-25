"""Import CSV de stock : analyse (aperçu) puis confirmation atomique."""
import csv
import io
import json
import secrets
from datetime import timedelta

from flask import current_app

from ..core import dates
from ..core.db import transaction
from ..core.errors import NotFoundError, ValidationError
from ..core.text import norm
from ..repositories import medicament_repo, stock_repo
from . import stock_service

COLONNES = ["medicament", "dosage", "forme", "quantite", "prix_fcfa"]
MAX_LIGNES = 2000
LOT_VALIDITE_MIN = 30


def modele_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(COLONNES)
    w.writerow(["Paracétamol", "500 mg", "Comprimé", "120", "500"])
    return "\ufeff" + buf.getvalue()


def analyser(pharmacie_id: int, contenu: bytes) -> dict:
    cfg = current_app.config
    if not contenu:
        raise ValidationError({"fichier": "Le fichier est vide."})
    if len(contenu) > cfg["CSV_MAX_BYTES"]:
        raise ValidationError({"fichier": "Le fichier dépasse 2 Mo."})
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationError({"fichier": "Le fichier doit être encodé en UTF-8."})

    lecteur = csv.reader(io.StringIO(texte), delimiter=";")
    try:
        entete = [norm(c) for c in next(lecteur)]
    except StopIteration:
        raise ValidationError({"fichier": "Le fichier est vide."})
    if entete != COLONNES:
        raise ValidationError({"fichier": "En-têtes attendus : " + " ; ".join(COLONNES)
                               + ". Séparateur : point-virgule."})

    lignes, erreurs, vus = [], [], set()
    for numero, cells in enumerate(lecteur, start=2):
        if not any(c.strip() for c in cells):
            continue
        if len(lignes) + len(erreurs) >= MAX_LIGNES:
            erreurs.append({"ligne": numero, "message": f"Maximum {MAX_LIGNES} lignes par import."})
            break
        if len(cells) != len(COLONNES):
            erreurs.append({"ligne": numero, "message": "Nombre de colonnes incorrect (5 attendues)."})
            continue
        nom, dosage, forme, qte_brute, prix_brut = [c.strip() for c in cells]
        quantite, prix, errs = stock_service.valider(qte_brute, prix_brut)
        if errs:
            erreurs.append({"ligne": numero, "message": " ; ".join(errs.values()) + "."})
            continue
        med = medicament_repo.trouver(nom, dosage, forme)
        if med is None:
            erreurs.append({"ligne": numero, "message": f"Médicament inconnu : « {nom} {dosage} {forme} »."})
            continue
        if med.id in vus:
            erreurs.append({"ligne": numero, "message": f"Doublon dans le fichier : {med.libelle} ({med.forme})."})
            continue
        vus.add(med.id)
        existant = stock_repo.get(pharmacie_id, med.id) is not None
        lignes.append({"ligne": numero, "medicament_id": med.id, "libelle": med.libelle,
                       "forme": med.forme, "quantite": quantite, "prix": prix,
                       "action": "maj" if existant else "ajout"})

    if not lignes and not erreurs:
        raise ValidationError({"fichier": "Aucune ligne à importer."})

    token = None
    if lignes and not erreurs:
        token = secrets.token_urlsafe(24)
        now = dates.now_utc()
        stock_repo.purger_lots(dates.to_iso(now - timedelta(minutes=LOT_VALIDITE_MIN)))
        stock_repo.creer_lot(token, pharmacie_id, json.dumps(lignes), dates.to_iso(now))
    return {"lignes": lignes, "erreurs": erreurs, "token": token,
            "nb_ajouts": sum(1 for l in lignes if l["action"] == "ajout"),
            "nb_maj": sum(1 for l in lignes if l["action"] == "maj")}


def confirmer(pharmacie_id: int, token: str) -> dict:
    lot = stock_repo.get_lot(token or "", pharmacie_id)  # un lot n'est visible que de sa pharmacie
    if lot is None:
        raise NotFoundError("Cet import a expiré. Sélectionnez de nouveau votre fichier.")
    now = dates.now_utc()
    if dates.parse(lot["cree_le"]) < now - timedelta(minutes=LOT_VALIDITE_MIN):
        stock_repo.supprimer_lot(token)
        raise NotFoundError("Cet import a expiré. Sélectionnez de nouveau votre fichier.")
    lignes = json.loads(lot["lignes_json"])
    iso = dates.to_iso(now)
    ajouts = maj = 0
    with transaction():  # tout ou rien
        for l in lignes:
            if stock_repo.mettre_a_jour(pharmacie_id, l["medicament_id"], l["quantite"], l["prix"], iso):
                maj += 1
            else:
                stock_repo.inserer(pharmacie_id, l["medicament_id"], l["quantite"], l["prix"], iso)
                ajouts += 1
        stock_repo.supprimer_lot(token)
    return {"ajouts": ajouts, "maj": maj}
