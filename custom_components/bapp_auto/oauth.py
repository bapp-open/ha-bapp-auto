"""Registration of the hardcoded BAPP OAuth client."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH_AUTHORIZE_URL, OAUTH_CLIENT_ID, OAUTH_TOKEN_URL


@callback
def async_register_oauth_implementation(hass: HomeAssistant) -> None:
    """Make the public PKCE client available to the OAuth helpers."""
    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce(hass, DOMAIN, OAUTH_CLIENT_ID, OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL),
    )
