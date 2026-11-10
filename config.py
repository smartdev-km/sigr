import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
IS_PROD = os.environ.get("APP_ENV", "").lower() == "production"


def _database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        return "sqlite:///" + os.path.join(BASE_DIR, "instance", "sigr.db")
    # Render / Heroku fournissent « postgres:// » ou « postgresql:// » : on impose le pilote psycopg 3
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # évite les connexions mortes après une mise en veille de la base
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PROD
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = IS_PROD
    PREFERRED_URL_SCHEME = "https" if IS_PROD else "http"


def check_production_config(cfg):
    """Refuse de démarrer en production avec une clé secrète par défaut."""
    if IS_PROD and cfg.get("SECRET_KEY") in (None, "", "dev-change-me"):
        raise RuntimeError("SECRET_KEY doit être défini (variable d'environnement) en production.")
