"""Binary sensors: one 'needs attention' flag per document and per car."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import BappAutoConfigEntry, BappAutoCoordinator
from .entity import BappAutoAccountEntity, BappAutoCarEntity
from .models import Document


def document_problem_attributes(doc: Document) -> dict[str, Any]:
    return {
        "document_type": doc.document_type,
        "document_label": doc.label,
        "expiration_date": doc.expiration_date.isoformat() if doc.expiration_date else None,
        "days_until_expiration": doc.days_until_expiration,
        "is_expired": doc.is_expired,
        "is_expiring_soon": doc.is_expiring_soon,
        "status_level": doc.status_level or None,
    }


async def async_setup_entry(hass: HomeAssistant, entry: BappAutoConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _sync_entities() -> None:
        new: list[BinarySensorEntity] = []
        data = coordinator.data
        for car_id in data.cars:
            if (uid := f"car_{car_id}") not in known:
                known.add(uid)
                new.append(CarAttentionBinarySensor(coordinator, car_id))
            for type_key in data.car_documents(car_id):
                if (uid := f"car_{car_id}_doc_{type_key}") not in known:
                    known.add(uid)
                    new.append(CarDocumentBinarySensor(coordinator, car_id, type_key))
        for type_key in data.user_documents:
            if (uid := f"user_doc_{type_key}") not in known:
                known.add(uid)
                new.append(UserDocumentBinarySensor(coordinator, type_key))
        if new:
            async_add_entities(new)

    _sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class CarDocumentBinarySensor(BappAutoCarEntity, BinarySensorEntity):
    """On when the car document is expired or inside the warning window."""

    _attr_translation_key = "document_attention"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int, type_key: str) -> None:
        super().__init__(coordinator, car_id, f"doc_{type_key}_attention")
        self.type_key = type_key
        self._attr_translation_placeholders = {"document": self.document.label}  # type: ignore[union-attr]

    @property
    def document(self) -> Document | None:
        return self.coordinator.data.car_documents(self.car_id).get(self.type_key)

    @property
    def available(self) -> bool:
        return super().available and self.document is not None

    @property
    def is_on(self) -> bool | None:
        doc = self.document
        return (doc.is_expired or doc.is_expiring_soon) if doc else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        doc = self.document
        return document_problem_attributes(doc) if doc else None


class UserDocumentBinarySensor(BappAutoAccountEntity, BinarySensorEntity):
    """On when a personal document is expired or inside the warning window."""

    _attr_translation_key = "document_attention"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: BappAutoCoordinator, type_key: str) -> None:
        super().__init__(coordinator, f"doc_{type_key}_attention")
        self.type_key = type_key
        self._attr_translation_placeholders = {"document": self.document.label}  # type: ignore[union-attr]

    @property
    def document(self) -> Document | None:
        return self.coordinator.data.user_documents.get(self.type_key)

    @property
    def available(self) -> bool:
        return super().available and self.document is not None

    @property
    def is_on(self) -> bool | None:
        doc = self.document
        return (doc.is_expired or doc.is_expiring_soon) if doc else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        doc = self.document
        return document_problem_attributes(doc) if doc else None


class CarAttentionBinarySensor(BappAutoCarEntity, BinarySensorEntity):
    """On when any document of the car is expired or expiring soon."""

    _attr_translation_key = "car_attention"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int) -> None:
        super().__init__(coordinator, car_id, "attention")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.attention_count(self.car_id) > 0

    @property
    def entity_picture(self) -> str | None:
        return self.car.photo_url if self.car else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        docs = self.coordinator.data.car_documents(self.car_id).values()
        return {
            "expired": sorted(d.label for d in docs if d.is_expired),
            "expiring_soon": sorted(d.label for d in docs if d.is_expiring_soon and not d.is_expired),
            "documents_needing_attention": self.coordinator.data.attention_count(self.car_id),
        }
