"""Config flow: log in with the BAPP account through Keycloak (OAuth2 + PKCE)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

from .auth import account_identity
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
    OAUTH_SCOPES,
)

_LOGGER = logging.getLogger(__name__)


class BappAutoConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    DOMAIN = DOMAIN
    VERSION = 2

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        # offline_access keeps the refresh token alive beyond the Keycloak SSO session.
        return {"scope": OAUTH_SCOPES}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BappAutoOptionsFlow()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        unique_id, title = account_identity(data["token"])
        if unique_id:
            await self.async_set_unique_id(unique_id)
        if self.source == SOURCE_REAUTH:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            assert entry is not None
            if entry.unique_id and unique_id and entry.unique_id != unique_id:
                return self.async_abort(reason="wrong_account")
            return self.async_update_reload_and_abort(entry, data=data, title=title, unique_id=unique_id)
        if unique_id:
            self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({}))
        return await self.async_step_user()


class BappAutoOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_MINUTES, max=1440, step=5, mode=NumberSelectorMode.BOX, unit_of_measurement="min"
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
