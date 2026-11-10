import os

import click
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import IS_PROD, Config, check_production_config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    check_production_config(app.config)
    if IS_PROD:  # derrière le proxy HTTPS de Render : schéma et IP réels des visiteurs
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "warning"

    from .auth import bp as auth_bp
    from .dashboard import bp as dashboard_bp

    app.register_blueprint(auth_bp)
    from .profile import bp as profile_bp
    from .routes import bp as routes_bp
    from .maintenance import bp as maintenance_bp
    from .diagnostic import bp as diagnostic_bp
    from .works import bp as works_bp
    from .reports import bp as reports_bp
    from .map_view import bp as map_bp
    from .users import bp as users_bp
    from .ouvrages import bp as ouvrages_bp
    from .contracts import bp as marches_bp, bp_e as entreprises_bp
    from .access import init_access

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(routes_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(diagnostic_bp)
    app.register_blueprint(works_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(ouvrages_bp)
    app.register_blueprint(marches_bp)
    app.register_blueprint(entreprises_bp)
    init_access(app)

    @app.route("/healthz")
    def healthz():
        """Sonde de santé (Render) : vérifie aussi la connexion à la base."""
        from sqlalchemy import text
        db.session.execute(text("SELECT 1"))
        return {"status": "ok"}

    app.jinja_env.filters["extract"] = lambda key, mapping: mapping.get(key, key)
    register_cli(app)
    return app


def upgrade_schema():
    """Ajoute les colonnes manquantes à toutes les tables existantes (sans outil de migration)."""
    from sqlalchemy import inspect, text

    from . import models  # noqa: F401  (enregistre tous les modèles)

    insp = inspect(db.engine)
    for table in db.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue  # nouvelle table : créée par create_all()
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name not in existing:
                ddl = col.type.compile(db.engine.dialect)
                db.session.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}'))
    db.session.commit()


def register_cli(app):
    from .models import ISLANDS, Route, User

    @app.cli.command("init-db")
    def init_db():
        """Crée les tables."""
        db.create_all()
        upgrade_schema()
        click.echo("Base de données initialisée.")

    @app.cli.command("bootstrap-admin")
    def bootstrap_admin():
        """Crée le premier administrateur depuis ADMIN_USERNAME / ADMIN_PASSWORD / ADMIN_NAME (idempotent)."""
        db.create_all()
        if User.query.filter_by(role="admin").first():
            click.echo("Un administrateur existe déjà : rien à faire.")
            return
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD")
        if not password or len(password) < 8:
            click.echo("ADMIN_PASSWORD absent ou trop court (8 caractères min.) : aucun administrateur créé.")
            return
        user = User(username=username, full_name=os.environ.get("ADMIN_NAME", "Administrateur"),
                    role="admin", must_change_password=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrateur '{username}' créé (changement du mot de passe exigé à la 1re connexion).")

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--full-name", prompt="Nom complet")
    @click.password_option()
    def create_admin(username, full_name, password):
        """Crée un compte administrateur."""
        db.create_all()
        if User.query.filter_by(username=username).first():
            raise click.ClickException("Ce nom d'utilisateur existe déjà.")
        user = User(username=username, full_name=full_name, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrateur '{username}' créé.")

    @app.cli.command("seed-demo")
    @click.option("--offline", is_flag=True, help="Ne pas interroger les services de calcul d'itinéraire.")
    def seed_demo_cmd(offline):
        """Ajoute des données de démonstration (routes, ouvrages, diagnostics, travaux, entretien, marchés)."""
        from .demo import seed_demo

        db.create_all()
        upgrade_schema()
        counts = seed_demo(online=not offline, log=click.echo)
        click.echo("Ajouté : " + ", ".join(f"{v} {k}" for k, v in counts.items() if v) if any(counts.values())
                   else "Rien à ajouter : les données de démonstration existent déjà.")
