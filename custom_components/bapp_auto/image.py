"""One image entity per car with its photo, for picture cards and the device page."""

from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from yarl import URL

from .api import BappAutoError
from .coordinator import BappAutoConfigEntry, BappAutoCoordinator
from .entity import BappAutoCarEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: BappAutoConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _sync_entities() -> None:
        new = [CarPhotoImage(hass, coordinator, car_id) for car_id in coordinator.data.cars if car_id not in known]
        known.update(e.car_id for e in new)
        if new:
            async_add_entities(new)

    _sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class CarPhotoImage(BappAutoCarEntity, ImageEntity):
    _attr_translation_key = "photo"
    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, coordinator: BappAutoCoordinator, car_id: int) -> None:
        BappAutoCarEntity.__init__(self, coordinator, car_id, "photo")
        ImageEntity.__init__(self, hass)
        self._photo_path: str | None = None
        self._track_photo()

    def _photo_url(self) -> str | None:
        return self.car.photo_url if self.car else None

    def _track_photo(self) -> None:
        """Bump image_last_updated when the photo changes.

        Signed storage URLs change on every poll, so compare the path only.
        """
        url = self._photo_url()
        path = URL(url).path if url else None
        if path != self._photo_path:
            self._photo_path = path
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow() if path else None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._track_photo()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        return super().available and self._photo_url() is not None

    async def async_image(self) -> bytes | None:
        url = self._photo_url()
        if not url:
            return None
        try:
            data, content_type = await self.coordinator.client.async_fetch_bytes(url)
        except BappAutoError as err:
            _LOGGER.warning("Could not fetch photo for car %s: %s", self.car_id, err)
            return None
        if content_type:
            self._attr_content_type = content_type.split(";")[0].strip()
        return data
