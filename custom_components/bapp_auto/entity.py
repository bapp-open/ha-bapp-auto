"""Base entities: one Home Assistant device per car, plus one for the account."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BappAutoCoordinator
from .models import Car


def car_device_identifier(car_id: int) -> tuple[str, str]:
    return (DOMAIN, f"car_{car_id}")


def car_device_info(car: Car, host: str) -> DeviceInfo:
    """Device card for a car: the photo and plate make it recognisable with several cars."""
    return DeviceInfo(
        identifiers={car_device_identifier(car.id)},
        name=f"{car.display_name} · {car.license_plate}" if car.license_plate else car.display_name,
        manufacturer=car.make_name or None,
        model=car.model_text or None,
        serial_number=car.vin or None,
        hw_version=str(car.year) if car.year else None,
        configuration_url=host,
    )


def account_device_info(entry_id: str, host: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"account_{entry_id}")},
        name="BAPP Auto",
        manufacturer="BAPP",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=host,
    )


class BappAutoEntity(CoordinatorEntity[BappAutoCoordinator]):
    """Shared defaults."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BappAutoCoordinator, unique_suffix: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_suffix}"


class BappAutoCarEntity(BappAutoEntity):
    """An entity that belongs to one car."""

    def __init__(self, coordinator: BappAutoCoordinator, car_id: int, unique_suffix: str) -> None:
        super().__init__(coordinator, f"car_{car_id}_{unique_suffix}")
        self.car_id = car_id
        self._attr_device_info = car_device_info(coordinator.data.cars[car_id], coordinator.client.host)

    @property
    def car(self) -> Car | None:
        return self.coordinator.data.cars.get(self.car_id)

    @property
    def available(self) -> bool:
        return super().available and self.car is not None


class BappAutoAccountEntity(BappAutoEntity):
    """An entity about the account itself (personal documents)."""

    def __init__(self, coordinator: BappAutoCoordinator, unique_suffix: str) -> None:
        super().__init__(coordinator, f"account_{unique_suffix}")
        self._attr_device_info = account_device_info(coordinator.config_entry.entry_id, coordinator.client.host)
