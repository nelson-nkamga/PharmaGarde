"""PharmaGarde Douala — fabrique d'application Flask (routes -> services -> repositories -> SQLite)."""
import os

import click
from flask import Flask

from config import Config, ProductionConfig

from .core import csrf, db, filters
from .core.errors import register_error_handlers


def create_app(config_object=None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    if config_object is None:
        config_object = ProductionConfig if os.environ.get("FLASK_ENV") == "production" else Config
    app.config.from_object(config_object)
    if config_object is ProductionConfig:
        ProductionConfig.check()
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # derrière Nginx

    db.init_app(app)
    csrf.init_app(app)
    filters.init_app(app)
    register_error_handlers(app)

    from .routes import admin, api, auth, pharmacien, public
    for module in (public, auth, pharmacien, admin, api):
        app.register_blueprint(module.bp)

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "font-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'")
        if resp.mimetype == "text/html":
            resp.headers.setdefault("Cache-Control", "no-store")  # pas de page privée en cache
        return resp

    _register_cli(app)
    return app


def _register_cli(app: Flask):
    @app.cli.command("init-db")
    def init_db_cmd():
        """Crée les tables."""
        db.init_db()
        click.echo("Base initialisée.")

    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Supprime la base existante avant de la remplir.")
    def seed_cmd(reset):
        """Remplit la base de démonstration (25 pharmacies, 100 médicaments, 1 000 lignes de stock...)."""
        from scripts.seed import run
        run(app, reset=reset)
        click.echo("Base de démonstration prête.")
