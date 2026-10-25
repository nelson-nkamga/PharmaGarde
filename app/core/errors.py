"""Exceptions métier + gestionnaires d'erreurs (HTML ou JSON selon la route)."""
from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException


class DomainError(Exception):
    status = 400
    code = "REQUETE_INVALIDE"
    message = "Requête invalide."

    def __init__(self, message: str | None = None, details=None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details


class ValidationError(DomainError):
    status, code, message = 422, "VALIDATION_ERREUR", "Les données envoyées sont invalides."

    def __init__(self, errors: dict | None = None, message: str | None = None):
        super().__init__(message)
        self.errors = errors or {}
        self.details = [{"champ": k, "message": v} for k, v in self.errors.items()]


class NotFoundError(DomainError):
    status, code, message = 404, "RESSOURCE_INTROUVABLE", "Ressource introuvable."


class NotAuthenticated(DomainError):
    status, code, message = 401, "NON_AUTHENTIFIE", "Connexion requise."


class ForbiddenError(DomainError):
    status, code, message = 403, "ACCES_INTERDIT", "Accès interdit."


class ConflictError(DomainError):
    status, code, message = 409, "CONFLIT", "Conflit avec l'état actuel."


class GardeChevauchement(ConflictError):
    code = "GARDE_CHEVAUCHEMENT"
    message = "Cette pharmacie a déjà une garde qui chevauche cette période."

    def __init__(self, conflit=None):
        super().__init__(self.message)
        self.conflit = conflit  # Garde en conflit (peut être None)


class DoublonError(ConflictError):
    code = "DOUBLON"
    message = "Cet élément existe déjà."


class AuthError(DomainError):
    status, code, message = 401, "IDENTIFIANTS_INVALIDES", "Email ou mot de passe incorrect."


class TooManyAttempts(DomainError):
    status, code = 429, "TROP_DE_TENTATIVES"
    message = "Trop de tentatives, réessayez dans 5 minutes."


class CsrfError(ForbiddenError):
    code, message = "CSRF_INVALIDE", "Votre session a expiré ou le formulaire est invalide. Rechargez la page et réessayez."


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def _respond(status: int, code: str, message: str, details=None):
    if _wants_json():
        body = {"error": {"code": code, "message": message}}
        if details:
            body["error"]["details"] = details
        return jsonify(body), status
    template = {403: "errors/403.html", 404: "errors/404.html"}.get(status, "errors/500.html")
    return render_template(template, status=status, message=message), status


def register_error_handlers(app):
    @app.errorhandler(DomainError)
    def _domain(e: DomainError):
        return _respond(e.status, e.code, e.message, e.details)

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        codes = {400: "REQUETE_INVALIDE", 403: "ACCES_INTERDIT", 404: "RESSOURCE_INTROUVABLE",
                 405: "METHODE_NON_AUTORISEE", 413: "FICHIER_TROP_VOLUMINEUX"}
        messages = {404: "Page introuvable.", 403: "Accès interdit.",
                    405: "Méthode non autorisée.", 413: "Le fichier dépasse la taille maximale (2 Mo)."}
        return _respond(e.code or 500, codes.get(e.code, "ERREUR_HTTP"),
                        messages.get(e.code, e.description or "Erreur."))

    @app.errorhandler(Exception)
    def _unexpected(e: Exception):
        app.logger.exception(e)  # détail dans les journaux, jamais dans la réponse
        return _respond(500, "ERREUR_INTERNE", "Une erreur est survenue. Réessayez dans un instant.")
