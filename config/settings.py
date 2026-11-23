"""
Réglages du projet Maélis Orvanne Shop.

Les valeurs personnelles (clé secrète, numéro WhatsApp, base de données…) se trouvent
dans le fichier .env à la racine du projet. Modèle : .env.exemple
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def charger_env(chemin):
    """Lit le fichier .env (lignes CLE=valeur) sans dépendance externe.
    Une variable déjà définie dans le système n'est pas écrasée."""
    if not chemin.exists():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        cle, valeur = cle.strip(), valeur.strip().strip('"').strip("'")
        os.environ.setdefault(cle, valeur)


charger_env(BASE_DIR / ".env")

CLE_DE_DEVELOPPEMENT = "dev-uniquement-a-changer-en-production-3f9a8c1e7b2d"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", CLE_DE_DEVELOPPEMENT)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

if not DEBUG and SECRET_KEY in ("", CLE_DE_DEVELOPPEMENT):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("En production, définissez DJANGO_SECRET_KEY (une longue clé secrète unique).")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Applications du projet
    "boutique",
    "gestion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "boutique.middleware.MaintenanceMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "gestion.context_processors.boutique_infos",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de données : SQLite en développement.
# Pour PostgreSQL en production, remplir les variables POSTGRES_*.
if os.environ.get("POSTGRES_DB", "").strip():
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", ""),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Lome"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Connexion au back-office
LOGIN_URL = "gestion:connexion"
LOGIN_REDIRECT_URL = "gestion:tableau_de_bord"
LOGOUT_REDIRECT_URL = "gestion:connexion"

# Taille maximale d'une image produit (5 Mo)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Informations de la boutique (utilisées dans les pages et les messages WhatsApp)
BOUTIQUE_NOM = "Maélis Orvanne Shop"
BOUTIQUE_DEVISE = "FCFA"
# Numéro WhatsApp qui reçoit les commandes, au format international sans "+" ni espaces.
# Exemple pour le Togo : "22890000000". À remplir plus tard.
BOUTIQUE_WHATSAPP = os.environ.get("BOUTIQUE_WHATSAPP", "")
# Pays où la boutique livre (le premier est proposé par défaut) : TG = Togo, BJ = Bénin, GH = Ghana
BOUTIQUE_PAYS = [c for c in os.environ.get("BOUTIQUE_PAYS", "TG").split(",") if c.strip()]


# ---------------------------------------------------------------- Sécurité
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 12  # une session du back-office dure 12 h

if not DEBUG:
    # En ligne, tout passe en HTTPS
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "2592000"))  # 30 jours
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    if os.environ.get("DJANGO_DERRIERE_PROXY") == "1":
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Limites anti-abus
LIMITE_CONNEXION = (5, 15 * 60)  # 5 essais ratés → 15 minutes de blocage
LIMITE_COMMANDES = (5, 10 * 60)  # 5 commandes max par adresse IP en 10 minutes
