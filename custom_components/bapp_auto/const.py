"""Constants for the BAPP Auto integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "bapp_auto"

CONF_SCAN_INTERVAL = "scan_interval"

# The bapp cloud the BAPP Auto app talks to; not user-configurable.
API_HOST = "https://panel.bapp.ro"

# Login goes through the same Keycloak as the app, with a public PKCE client
# whose only redirect is Home Assistant's my.home-assistant.io relay.
OAUTH_CLIENT_ID = "bapp-home-assistant"
OAUTH_AUTHORIZE_URL = "https://id.bapp.ro/realms/bapp/protocol/openid-connect/auth"
OAUTH_TOKEN_URL = "https://id.bapp.ro/realms/bapp/protocol/openid-connect/token"
OAUTH_SCOPES = "openid profile email offline_access"
DEFAULT_SCAN_INTERVAL_MINUTES = 30
MIN_SCAN_INTERVAL_MINUTES = 5
DEFAULT_SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)

# The bapp API scopes every request to an application; this is bapp-auto's slug.
APP_SLUG = "auto"
REQUEST_TIMEOUT = 30
MAX_PAGES = 20

CONTENT_TYPE_CAR = "bapp_auto.car"
CONTENT_TYPE_CAR_DOCUMENT = "bapp_auto.cardocument"
CONTENT_TYPE_SERVICE_RECORD = "bapp_auto.carservicerecord"
CONTENT_TYPE_USER_DOCUMENT = "bapp_auto.userdocument"

# Task codes are "<app_label>.<ClassName>"; the server lowercases them on lookup.
TASK_UPDATE_MILEAGE = "bapp_auto.updatemileage"

SERVICE_UPDATE_MILEAGE = "update_mileage"
SERVICE_REFRESH = "refresh"
ATTR_MILEAGE = "mileage"

PLATFORMS = ["sensor", "binary_sensor", "image"]

# Lovelace strategy + car card, served from custom_components/bapp_auto/frontend.
FRONTEND_URL_PATH = f"/{DOMAIN}_static"
FRONTEND_SCRIPT = "bapp-auto-strategy.js"
