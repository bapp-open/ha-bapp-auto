"""BAPP Auto: vehicle documents, expiry dates and mileage in Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import BappAutoAuthError, BappAutoClient, BappAutoError
from .const import (
    API_HOST,
    ATTR_MILEAGE,
    CONF_TOKEN,
    DOMAIN,
    FRONTEND_SCRIPT,
    FRONTEND_URL_PATH,
    PLATFORMS,
    SERVICE_REFRESH,
    SERVICE_UPDATE_MILEAGE,
    TASK_UPDATE_MILEAGE,
)
from .coordinator import BappAutoConfigEntry, BappAutoCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

UPDATE_MILEAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(ATTR_MILEAGE): vol.All(vol.Coerce(int), vol.Range(min=0, max=5_000_000)),
    },
    extra=vol.ALLOW_EXTRA,
)

REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}, extra=vol.ALLOW_EXTRA)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the Lovelace strategy / car card module and load it on every dashboard."""
    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths([StaticPathConfig(FRONTEND_URL_PATH, str(frontend_dir), cache_headers=True)])
    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{FRONTEND_URL_PATH}/{FRONTEND_SCRIPT}?v={integration.version}")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the frontend module and the domain services once."""
    await _async_register_frontend(hass)

    @callback
    def _resolve_car(device_id: str) -> tuple[BappAutoCoordinator, int]:
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="device_not_found", translation_placeholders={"device_id": device_id}
            )
        car_id = next(
            (int(value.removeprefix("car_")) for domain, value in device.identifiers if domain == DOMAIN and value.startswith("car_")),
            None,
        )
        if car_id is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="not_a_car", translation_placeholders={"device_id": device_id}
            )
        for entry_id in device.config_entries:
            entry: BappAutoConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
            if entry is not None and entry.domain == DOMAIN and hasattr(entry, "runtime_data"):
                return entry.runtime_data, car_id
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_loaded")

    async def _update_mileage(call: ServiceCall) -> None:
        mileage: int = call.data[ATTR_MILEAGE]
        for device_id in call.data[ATTR_DEVICE_ID]:
            coordinator, car_id = _resolve_car(device_id)
            try:
                # `digits` is a string on purpose: the server accepts the full value or the last 3 digits.
                result = await coordinator.client.async_run_task(TASK_UPDATE_MILEAGE, {"car_id": car_id, "digits": str(mileage)})
            except BappAutoAuthError as err:
                coordinator.config_entry.async_start_reauth(hass)
                raise HomeAssistantError(str(err)) from err
            except BappAutoError as err:
                raise HomeAssistantError(str(err)) from err
            if not result.get("success", True):
                raise HomeAssistantError(str(result.get("message") or "Task failed"))
            await coordinator.async_request_refresh()

    async def _refresh(call: ServiceCall) -> None:
        coordinators: set[BappAutoCoordinator] = set()
        if device_ids := call.data.get(ATTR_DEVICE_ID):
            for device_id in device_ids:
                coordinators.add(_resolve_car(device_id)[0])
        else:
            for entry in hass.config_entries.async_loaded_entries(DOMAIN):
                coordinators.add(entry.runtime_data)
        for coordinator in coordinators:
            await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_MILEAGE, _update_mileage, schema=UPDATE_MILEAGE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _refresh, schema=REFRESH_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BappAutoConfigEntry) -> bool:
    client = BappAutoClient(async_get_clientsession(hass), API_HOST, entry.data[CONF_TOKEN])
    try:
        await client.async_validate()
    except BappAutoAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except BappAutoError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = BappAutoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _prune_stale_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


@callback
def _prune_stale_devices(hass: HomeAssistant, entry: ConfigEntry, coordinator: BappAutoCoordinator) -> None:
    """Drop devices for cars that were deleted or un-shared since the last start."""
    registry = dr.async_get(hass)
    live = {f"car_{car_id}" for car_id in coordinator.data.cars} | {f"account_{entry.entry_id}"}
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        ours = {value for domain, value in device.identifiers if domain == DOMAIN}
        if ours and not ours & live:
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BappAutoConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
