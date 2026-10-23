"""Sensors: mileage, document expiry and next service, per car."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import BappAutoConfigEntry, BappAutoCoordinator
from .entity import BappAutoAccountEntity, BappAutoCarEntity
from .models import Document, ServiceRecord

DOCUMENT_ICONS = {
    "itp": "mdi:car-wrench",
    "rca": "mdi:shield-car",
    "casco": "mdi:shield-check",
    "vignette": "mdi:highway",
    "registration": "mdi:card-account-details",
    "vehicle_cert": "mdi:file-certificate",
    "extinguisher": "mdi:fire-extinguisher",
    "medical_kit": "mdi:medical-bag",
    "driving_license": "mdi:card-account-details-outline",
    "id_card": "mdi:card-account-details",
    "passport": "mdi:passport",
}


def document_icon(doc: Document | None, default: str) -> str:
    if doc and doc.is_expired:
        return "mdi:alert-circle"
    if doc and doc.is_expiring_soon:
        return "mdi:clock-alert-outline"
    return DOCUMENT_ICONS.get(doc.document_type if doc else "", default)


def document_attributes(doc: Document) -> dict[str, Any]:
    return {
        "document_type": doc.document_type,
        "document_label": doc.label,
        "document_number": doc.document_number or None,
        "issue_date": doc.issue_date.isoformat() if doc.issue_date else None,
        "expiration_date": doc.expiration_date.isoformat() if doc.expiration_date else None,
        "status_level": doc.status_level or None,
        "is_expired": doc.is_expired,
        "is_expiring_soon": doc.is_expiring_soon,
        "provider": doc.provider or None,
        "cost": doc.cost,
        "notes": doc.notes or None,
    }


def document_days_left(doc: Document | None) -> int | None:
    if doc is None:
        return None
    if doc.days_until_expiration is not None:
        return doc.days_until_expiration
    if doc.expiration_date is not None:
        return (doc.expiration_date - date.today()).days
    return None


async def async_setup_entry(hass: HomeAssistant, entry: BappAutoConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _sync_entities() -> None:
        """Create entities for cars and documents that appeared since the last refresh.

        Entities whose car or document disappeared stay registered and turn unavailable.
        """
        new: list[SensorEntity] = []
        data = coordinator.data
        for car_id in data.cars:
            if (uid := f"car_{car_id}") not in known:
                known.add(uid)
                new.append(CarMileageSensor(coordinator, car_id))
                new.append(CarMileageUpdatedSensor(coordinator, car_id))
                new.append(CarStatusSensor(coordinator, car_id))
            for type_key in data.car_documents(car_id):
                if (uid := f"car_{car_id}_doc_{type_key}") not in known:
                    known.add(uid)
                    new.append(CarDocumentDaysSensor(coordinator, car_id, type_key))
                    new.append(CarDocumentDateSensor(coordinator, car_id, type_key))
            for service_type in data.car_services(car_id):
                if (uid := f"car_{car_id}_svc_{service_type}") not in known:
                    known.add(uid)
                    new.append(CarServiceDateSensor(coordinator, car_id, service_type))
                    new.append(CarServiceMileageSensor(coordinator, car_id, service_type))
        for type_key in data.user_documents:
            if (uid := f"user_doc_{type_key}") not in known:
                known.add(uid)
                new.append(UserDocumentDaysSensor(coordinator, type_key))
                new.append(UserDocumentDateSensor(coordinator, type_key))
        if new:
            async_add_entities(new)

    _sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class CarMileageSensor(BappAutoCarEntity, SensorEntity):
    _attr_translation_key = "mileage"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:counter"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int) -> None:
        super().__init__(coordinator, car_id, "mileage")

    @property
    def native_value(self) -> int | None:
        return self.car.mileage if self.car else None


class CarMileageUpdatedSensor(BappAutoCarEntity, SensorEntity):
    _attr_translation_key = "mileage_updated"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int) -> None:
        super().__init__(coordinator, car_id, "mileage_updated")

    @property
    def native_value(self) -> datetime | None:
        return self.car.mileage_updated_at if self.car else None


class CarStatusSensor(BappAutoCarEntity, SensorEntity):
    """What needs attention first on this car; carries the photo for dashboard cards."""

    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ok", "expiring_soon", "expired", "unknown"]

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int) -> None:
        super().__init__(coordinator, car_id, "status")

    @property
    def native_value(self) -> str:
        docs = self.coordinator.data.car_documents(self.car_id)
        if not docs:
            return "unknown"
        if any(d.is_expired for d in docs.values()):
            return "expired"
        if any(d.is_expiring_soon for d in docs.values()):
            return "expiring_soon"
        return "ok"

    @property
    def icon(self) -> str:
        return {"ok": "mdi:car", "expiring_soon": "mdi:car-clock", "expired": "mdi:car-off"}.get(self.native_value, "mdi:car-info")

    @property
    def entity_picture(self) -> str | None:
        return self.car.photo_url if self.car else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        car = self.car
        data = self.coordinator.data
        nxt = data.next_expiring(self.car_id)
        attrs: dict[str, Any] = {
            "documents_needing_attention": data.attention_count(self.car_id),
            "next_expiring_document": nxt.label if nxt else None,
            "next_expiring_date": nxt.expiration_date.isoformat() if nxt and nxt.expiration_date else None,
            "next_expiring_days": document_days_left(nxt),
        }
        if car:
            attrs.update(
                {
                    "license_plate": car.license_plate or None,
                    "display_name": car.display_name,
                    "year": car.year,
                    "fuel_type": car.fuel_type_display or car.fuel_type or None,
                    "color": car.color or None,
                    "is_owner": car.is_owner,
                    "plan_enabled": car.enabled,
                    "photo_url": car.photo_url,
                }
            )
        return attrs


class CarDocumentDaysSensor(BappAutoCarEntity, SensorEntity):
    _attr_translation_key = "document_days_left"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int, type_key: str) -> None:
        super().__init__(coordinator, car_id, f"doc_{type_key}_days")
        self.type_key = type_key
        self._attr_translation_placeholders = {"document": self.document.label}  # type: ignore[union-attr]

    @property
    def document(self) -> Document | None:
        return self.coordinator.data.car_documents(self.car_id).get(self.type_key)

    @property
    def available(self) -> bool:
        return super().available and self.document is not None

    @property
    def native_value(self) -> int | None:
        return document_days_left(self.document)

    @property
    def icon(self) -> str:
        return document_icon(self.document, "mdi:file-document-outline")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        doc = self.document
        return document_attributes(doc) if doc else None


class CarDocumentDateSensor(BappAutoCarEntity, SensorEntity):
    _attr_translation_key = "document_expiration"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int, type_key: str) -> None:
        super().__init__(coordinator, car_id, f"doc_{type_key}_date")
        self.type_key = type_key
        self._attr_translation_placeholders = {"document": self.document.label}  # type: ignore[union-attr]

    @property
    def document(self) -> Document | None:
        return self.coordinator.data.car_documents(self.car_id).get(self.type_key)

    @property
    def available(self) -> bool:
        return super().available and self.document is not None

    @property
    def native_value(self) -> date | None:
        doc = self.document
        return doc.expiration_date if doc else None

    @property
    def icon(self) -> str:
        return DOCUMENT_ICONS.get(self.document.document_type if self.document else "", "mdi:calendar-end")


class UserDocumentDaysSensor(BappAutoAccountEntity, SensorEntity):
    _attr_translation_key = "document_days_left"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: BappAutoCoordinator, type_key: str) -> None:
        super().__init__(coordinator, f"doc_{type_key}_days")
        self.type_key = type_key
        self._attr_translation_placeholders = {"document": self.document.label}  # type: ignore[union-attr]

    @property
    def document(self) -> Document | None:
        return self.coordinator.data.user_documents.get(self.type_key)

    @property
    def available(self) -> bool:
        return super().available and self.document is not None

    @property
    def native_value(self) -> int | None:
        return document_days_left(self.document)

    @property
    def icon(self) -> str:
        return document_icon(self.document, "mdi:card-account-details-outline")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        doc = self.document
        return document_attributes(doc) if doc else None


class UserDocumentDateSensor(BappAutoAccountEntity, SensorEntity):
    _attr_translation_key = "document_expiration"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BappAutoCoordinator, type_key: str) -> None:
        super().__init__(coordinator, f"doc_{type_key}_date")
        self.type_key = type_key
        self._attr_translation_placeholders = {"document": self.document.label}  # type: ignore[union-attr]

    @property
    def document(self) -> Document | None:
        return self.coordinator.data.user_documents.get(self.type_key)

    @property
    def available(self) -> bool:
        return super().available and self.document is not None

    @property
    def native_value(self) -> date | None:
        doc = self.document
        return doc.expiration_date if doc else None


class _ServiceSensor(BappAutoCarEntity, SensorEntity):
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int, service_type: str, suffix: str) -> None:
        super().__init__(coordinator, car_id, f"svc_{service_type}_{suffix}")
        self.service_type = service_type
        self._attr_translation_placeholders = {"service": self.record.display}  # type: ignore[union-attr]

    @property
    def record(self) -> ServiceRecord | None:
        return self.coordinator.data.car_services(self.car_id).get(self.service_type)

    @property
    def available(self) -> bool:
        return super().available and self.record is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        rec = self.record
        if rec is None:
            return None
        return {
            "service_type": rec.service_type,
            "label": rec.display,
            "last_service_date": rec.service_date.isoformat() if rec.service_date else None,
            "mileage_at_service": rec.mileage_at_service,
            "provider": rec.provider or None,
            "cost": rec.cost,
        }


class CarServiceDateSensor(_ServiceSensor):
    _attr_translation_key = "next_service_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-wrench"

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int, service_type: str) -> None:
        super().__init__(coordinator, car_id, service_type, "date")

    @property
    def native_value(self) -> date | None:
        rec = self.record
        return rec.next_service_date if rec else None


class CarServiceMileageSensor(_ServiceSensor):
    _attr_translation_key = "next_service_mileage"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_icon = "mdi:car-wrench"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int, service_type: str) -> None:
        super().__init__(coordinator, car_id, service_type, "mileage")

    @property
    def native_value(self) -> int | None:
        rec = self.record
        return rec.next_service_mileage if rec else None
