import os
from pathlib import Path
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# -------------------------------------------------
# Base paths
# -------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_environment() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key and key.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip()
    else:
        load_dotenv(env_path)


_load_environment()

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _get_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

def _split_csv(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]

def _get_timezone(name: str, default: str) -> str:
    env_value = os.getenv(name, "").strip()
    if not env_value:
        return default

    alias_map = {
        "nairobi": "Africa/Nairobi",
        "kampala": "Africa/Kampala",
        "lagos": "Africa/Lagos",
        "accra": "Africa/Accra",
    }
    candidate = alias_map.get(env_value.lower(), env_value)
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return default
    return candidate

# -------------------------------------------------
# Security & environment
# -------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set in environment variables.")

DEBUG = _get_bool("DEBUG", False)

ALLOWED_HOSTS = _split_csv("ALLOWED_HOSTS", "")
if not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS must be set in production.")

CORS_ALLOWED_ORIGINS = _split_csv("CORS_ALLOWED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = _split_csv("CSRF_TRUSTED_ORIGINS", "")

# -------------------------------------------------
# Installed apps
# -------------------------------------------------
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third-party
    'crispy_forms',
    'crispy_bootstrap4',
    'django_filters',
    'django_extensions',
    'corsheaders',
    'rest_framework',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',

    # Project apps
    'main_app.apps.MainAppConfig',
]

CRISPY_TEMPLATE_PACK = os.getenv("CRISPY_TEMPLATE_PACK", "bootstrap4")

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',

    # Custom
    'main_app.middleware.LoginCheckMiddleWare',
    'main_app.suspension_middleware.SuspensionMiddleware',
]

ROOT_URLCONF = 'student_management_system.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",                 # optional project-level
            BASE_DIR / "main_app" / "templates",    # your app templates
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "main_app.context_processors.header_counts",
            ],
        },
    },
]


WSGI_APPLICATION = 'student_management_system.wsgi.application'

# -------------------------------------------------
# Database (Aiven MySQL with TLS, no sslmode leakage)
# -------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment variables.")

u = urlparse(DATABASE_URL)
if u.scheme not in {"mysql", "mysql2", "mysql-connector", "mysqlgis"}:
    raise RuntimeError(f"Unsupported DB scheme '{u.scheme}'. Use a MySQL URL.")

DB_NAME = (u.path or "").lstrip("/") or "defaultdb"
DB_USER = unquote(u.username or "")
DB_PASSWORD = unquote(u.password or "")
DB_HOST = u.hostname or "localhost"
DB_PORT = str(u.port or "3306")

mysql_ca = os.getenv("MYSQL_SSL_CA")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            # Enforce TLS via MySQL's 'ssl' option (NOT sslmode)
            **({"ssl": {"ca": mysql_ca}} if mysql_ca else {"ssl": {}}),
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
# Belt & suspenders: ensure no stray postgres flags exist
for bad in ("sslmode", "ssl-mode"):
    DATABASES["default"]["OPTIONS"].pop(bad, None)

# -------------------------------------------------
# Password validation
# -------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -------------------------------------------------
# Internationalization
# -------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = _get_timezone("TIME_ZONE", "Africa/Kampala")
USE_I18N = True
USE_TZ = True

# -------------------------------------------------
# Static & media
# -------------------------------------------------
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# -------------------------------------------------
# Authentication & Allauth
# -------------------------------------------------
AUTH_USER_MODEL = 'main_app.CustomUser'
AUTHENTICATION_BACKENDS = [
    'main_app.EmailBackend.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
SITE_ID = 1

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# -------------------------------------------------
# DRF
# -------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# -------------------------------------------------
# Email
# -------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_ADDRESS')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_USE_TLS = _get_bool('EMAIL_USE_TLS', True)

# -------------------------------------------------
# Security hardening
# -------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# -------------------------------------------------
# App-specific
# -------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

COSA_SETTINGS = {
    'ALUMNI_VERIFICATION_REQUIRED': True,
    'ALLOW_ALUMNI_REGISTRATION': True,
    'DEFAULT_PRIVACY_LEVEL': 'limited',
    'MENTORSHIP_PROGRAM_ENABLED': True,
    'JOB_BOARD_ENABLED': True,
    'DONATION_SYSTEM_ENABLED': True,
    'EVENT_REGISTRATION_ENABLED': True,
    'MESSAGING_ENABLED': True,
    'GROUPS_ENABLED': True,
}

ALUMNI_PER_PAGE = 24
JOBS_PER_PAGE = 20
EVENTS_PER_PAGE = 12
NEWS_PER_PAGE = 10

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'cosa-alumni-cache',
    }
}
