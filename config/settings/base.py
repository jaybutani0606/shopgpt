import os
from pathlib import Path
from dotenv import load_dotenv

# Monkeypatch Django's Context copy logic for Python 3.14 compatibility
try:
    import django.template.context
    def _patched_base_context_copy(self):
        obj = self.__class__.__new__(self.__class__)
        obj.__dict__.update(self.__dict__)
        obj.dicts = self.dicts[:]
        return obj
    django.template.context.BaseContext.__copy__ = _patched_base_context_copy
except Exception:
    pass




# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / '.env')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'products',
    'integrations',
    'analytics',
    'ml',
    'endpoints',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.GuestSearchLimitMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / os.environ.get('DB_NAME', 'db.sqlite3'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

# In tests/development, we keep validation simple, but base has defaults.
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging Configuration
LOGS_DIR = BASE_DIR / 'logs'
if not LOGS_DIR.exists():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'shopgpt.log',
            'maxBytes': 1024 * 1024 * 5,  # 5MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'config': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# Guest Search and Login Security settings
GUEST_SEARCH_LIMIT = 2
LOGIN_RATE_LIMIT_ATTEMPTS = 5
LOGIN_RATE_LIMIT_COOLDOWN = 300  # 5 minutes

import os
import socket
import urllib.parse

# Redis cache auto-discovery
REDIS_URL = os.environ.get('REDIS_URL', '')
redis_reachable = False
if REDIS_URL:
    try:
        parsed = urllib.parse.urlparse(REDIS_URL)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 6379
        s = socket.create_connection((host, port), timeout=0.5)
        s.close()
        redis_reachable = True
    except Exception:
        pass

if redis_reachable:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'shopgpt-locmem-cache',
        }
    }

# API configuration
PRODUCT_API_PROVIDER = os.environ.get('PRODUCT_API_PROVIDER', 'null')
PRODUCT_API_KEY = os.environ.get('PRODUCT_API_KEY', '')
PRODUCT_API_TIMEOUT = int(os.environ.get('PRODUCT_API_TIMEOUT', '10'))
PRODUCT_API_MAX_RETRIES = int(os.environ.get('PRODUCT_API_MAX_RETRIES', '3'))
PRODUCT_RESULTS_LIMIT = int(os.environ.get('PRODUCT_RESULTS_LIMIT', '40'))
SERPAPI_API_KEY = PRODUCT_API_KEY

# Celery configurations
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# ML configuration
ML_MIN_TRAINING_ROWS = int(os.environ.get('ML_MIN_TRAINING_ROWS', '10'))
ML_ARTIFACTS_DIR = BASE_DIR / 'ml' / 'artifacts'





