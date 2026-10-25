from datetime import timedelta

from flask import current_app

from ..core import dates
from ..core.errors import AuthError, ForbiddenError, TooManyAttempts, ValidationError
from ..core.security import verify_password
from ..repositories import utilisateur_repo


def authentifier(email: str, mot_de_passe: str, ip: str):
    email = (email or "").strip().lower()
    errors = {}
    if not email:
        errors["email"] = "Saisissez votre adresse e-mail."
    if not mot_de_passe:
        errors["mot_de_passe"] = "Saisissez votre mot de passe."
    if errors:
        raise ValidationError(errors)

    cfg = current_app.config
    now = dates.now_utc()
    cle = f"{email}|{ip}"
    depuis = dates.to_iso(now - timedelta(minutes=cfg["LOGIN_FENETRE_MIN"]))
    if utilisateur_repo.compter_echecs(cle, depuis) >= cfg["LOGIN_MAX_ECHECS"]:
        raise TooManyAttempts()

    user = utilisateur_repo.par_email(email)
    if not verify_password(user.mot_de_passe_hash if user else None, mot_de_passe):
        utilisateur_repo.enregistrer_echec(cle, dates.to_iso(now))
        raise AuthError()  # même message que l'email soit inconnu ou le mot de passe faux
    if not user.peut_se_connecter:
        raise ForbiddenError("Ce compte est suspendu. Contactez l'administrateur du groupement.")
    utilisateur_repo.purger_echecs(cle)
    return user
