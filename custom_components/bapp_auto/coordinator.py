"""Polls the bapp API and exposes a BappAutoData snapshot."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BappAutoAuthError, BappAutoClient, BappAutoError
from .const import (
    CONF_SCAN_INTERVAL,
    CONTENT_TYPE_CAR,
    CONTENT_TYPE_CAR_DOCUMENT,
    CONTENT_TYPE_SERVICE_RECORD,
    CONTENT_TYPE_USER_DOCUMENT,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)
from .models import BappAutoData

_LOGGER = logging.getLogger(__name__)

type BappAutoConfigEntry = ConfigEntry[BappAutoCoordinator]


class BappAutoCoordinator(DataUpdateCoordinator[BappAutoData]):
    """Fetches cars, their documents, service records and personal documents."""

    config_entry: BappAutoConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BappAutoConfigEntry, client: BappAutoClient) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(minutes=minutes),
        )
        self.client = client

    async def _async_update_data(self) -> BappAutoData:
        try:
            cars, car_documents, service_records, user_documents = await asyncio.gather(
                self.client.async_list(CONTENT_TYPE_CAR),
                self.client.async_list(CONTENT_TYPE_CAR_DOCUMENT),
                self.client.async_list(CONTENT_TYPE_SERVICE_RECORD),
                self.client.async_list(CONTENT_TYPE_USER_DOCUMENT),
            )
        except BappAutoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BappAutoError as err:
            raise UpdateFailed(str(err)) from err
        return BappAutoData.build(self.client.host, cars, car_documents, service_records, user_documents)
