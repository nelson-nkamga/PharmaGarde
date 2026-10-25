from flask import Blueprint, redirect, render_template, request, url_for

from ..core.errors import DomainError, ForbiddenError, TooManyAttempts, ValidationError
from ..core.security import current_user, login_user, logout_user, safe_next
from ..services import auth_service

bp = Blueprint("auth", __name__)


def _accueil_selon_role(user):
    return url_for("admin.tableau_de_bord" if user.role == "admin" else "pharmacien.tableau_de_bord")


@bp.route("/connexion", methods=["GET", "POST"])
def connexion():
    user = current_user()
    if user and request.method == "GET":
        return redirect(_accueil_selon_role(user))
    suivant = safe_next(request.values.get("next"))
    if request.method == "GET":
        return render_template("auth/connexion.html", next=suivant, email="", errors={}, erreur=None)

    email = request.form.get("email", "")
    try:
        user = auth_service.authentifier(email, request.form.get("mot_de_passe", ""), request.remote_addr or "?")
    except ValidationError as e:
        return render_template("auth/connexion.html", next=suivant, email=email, errors=e.errors,
                               erreur=None), 422
    except (DomainError) as e:
        status = e.status if isinstance(e, (TooManyAttempts, ForbiddenError)) else 401
        return render_template("auth/connexion.html", next=suivant, email=email, errors={},
                               erreur=e.message), status
    login_user(user)
    return redirect(suivant or _accueil_selon_role(user))


@bp.post("/deconnexion")
def deconnexion():
    logout_user()
    return redirect(url_for("public.accueil"))
