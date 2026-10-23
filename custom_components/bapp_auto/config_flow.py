"""Config flow: personal API token, with reauth and a polling-interval option."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import BappAutoAuthError, BappAutoClient, BappAutoConnectionError, BappAutoError
from .const import (
    API_HOST,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
)

TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))})


def _unique_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


async def _validate(flow: ConfigFlow, token: str) -> dict[str, str]:
    """Return a dict of form errors (empty when the token works)."""
    client = BappAutoClient(async_get_clientsession(flow.hass), API_HOST, token)
    try:
        await client.async_validate()
    except BappAutoAuthError:
        return {"base": "invalid_auth"}
    except BappAutoConnectionError:
        return {"base": "cannot_connect"}
    except BappAutoError:
        return {"base": "unknown"}
    return {}


class BappAutoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BappAutoOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            await self.async_set_unique_id(_unique_id(token))
            self._abort_if_unique_id_configured()
            errors = await _validate(self, token)
            if not errors:
                return self.async_create_entry(title="BAPP Auto", data={CONF_TOKEN: token})
        return self.async_show_form(step_id="user", data_schema=TOKEN_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._reauth_entry is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            errors = await _validate(self, token)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, CONF_TOKEN: token},
                    unique_id=_unique_id(token),
                )
        return self.async_show_form(step_id="reauth_confirm", data_schema=TOKEN_SCHEMA, errors=errors)


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
