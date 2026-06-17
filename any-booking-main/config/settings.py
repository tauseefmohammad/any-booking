from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])
CSRF_TRUSTED_ORIGINS = [
    f'https://{host}' for host in ALLOWED_HOSTS
    if host not in ('*', 'localhost') and not host.startswith('127.')
]

INSTALLED_APPS = [
    "unfold",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'services',
    'bookings',
    'vendors',
    'payments',
    'terms',
    'reviews',
]

UNFOLD = {
    "SITE_TITLE": "AnyBooking Admin",
    "STYLES": [lambda request: "/static/css/admin_custom.css"],
    "SITE_HEADER": "AnyBooking",
    "SITE_SUBHEADER": "Event Booking Platform",
    "SITE_URL": "/",
    "SITE_ICON": None,
    "COLORS": {
        "primary": {
            "50": "240 249 255",
            "100": "224 242 254",
            "200": "186 230 253",
            "300": "125 211 252",
            "400": "56 189 248",
            "500": "14 165 233",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
            "950": "8 47 73",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Overview",
                "items": [
                    {"title": "Dashboard", "icon": "dashboard", "link": "/admin/dashboard/"},
                ],
            },
            {
                "title": "Bookings",
                "items": [
                    {"title": "Bookings", "icon": "calendar_month", "link": "/admin/bookings/booking/"},
                    {"title": "Blocked Dates", "icon": "event_busy", "link": "/admin/bookings/blockeddate/"},
                    {"title": "Email Logs", "icon": "mail", "link": "/admin/bookings/emaillog/"},
                ],
            },
            {
                "title": "Services",
                "items": [
                    {"title": "Services", "icon": "storefront", "link": "/admin/services/service/"},
                    {"title": "Vendors", "icon": "person", "link": "/admin/services/vendor/"},
                    {"title": "Categories", "icon": "category", "link": "/admin/services/category/"},
                    {"title": "Attributes", "icon": "tune", "link": "/admin/services/attributedefinition/"},
                ],
            },
            {
                "title": "Reviews",
                "items": [
                    {"title": "Reviews", "icon": "star", "link": "/admin/reviews/review/"},
                ],
            },
            {
                "title": "Locations",
                "items": [
                    {"title": "Countries", "icon": "public", "link": "/admin/services/country/"},
                    {"title": "States", "icon": "map", "link": "/admin/services/state/"},
                    {"title": "Districts", "icon": "location_city", "link": "/admin/services/district/"},
                    {"title": "Cities", "icon": "place", "link": "/admin/services/city/"},
                ],
            },
            {
                "title": "Payments",
                "items": [
                    {"title": "Payments", "icon": "payments", "link": "/admin/payments/payment/"},
                    {"title": "Gateway Configs", "icon": "settings", "link": "/admin/payments/paymentgatewayconfig/"},
                ],
            },
            {
                "title": "Configuration",
                "items": [
                    {"title": "Terms of Use", "icon": "gavel", "link": "/admin/terms/termsofuse/"},
                    {"title": "Regional Configs", "icon": "translate", "link": "/admin/services/regionalcategoryconfig/"},
                    {"title": "Staff Profiles", "icon": "badge", "link": "/admin/services/staffprofile/"},
                ],
            },
            {
                "title": "Users",
                "items": [
                    {"title": "Users", "icon": "manage_accounts", "link": "/admin/auth/user/"},
                    {"title": "Groups", "icon": "group", "link": "/admin/auth/group/"},
                ],
            },
        ],
    },
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'services.context_processors.nav_categories',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR}/db.sqlite3')
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

GCS_MEDIA_BUCKET = env('GCS_MEDIA_BUCKET', default='')
if GCS_MEDIA_BUCKET:
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.gcloud.GoogleCloudStorage',
            'OPTIONS': {'bucket_name': GCS_MEDIA_BUCKET},
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

RAZORPAY_KEY_ID = env('RAZORPAY_KEY_ID', default='')
RAZORPAY_KEY_SECRET = env('RAZORPAY_KEY_SECRET', default='')

LOGIN_URL = '/admin/login/'

# ── Email ──────────────────────────────────────────────────────────────────────
# In development: print emails to console.
# In production: set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# and configure EMAIL_HOST / EMAIL_PORT / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD
# via Secret Manager or .env.
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='AnyBooking <noreply@anybooking.in>')

# Super-admin notification email (receives all new booking alerts)
ADMIN_NOTIFY_EMAIL = env('ADMIN_NOTIFY_EMAIL', default='')

# Public site base URL — used to build links in emails
SITE_URL = env('SITE_URL', default='http://127.0.0.1:8000')
