"""Plain data model for what the bapp API returns.

This module is deliberately free of Home Assistant imports so it can be unit
tested on its own. Every ``from_api`` tolerates missing keys: the server adds
fields over time and an older integration must keep working.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

_IMG_SRC = re.compile(r'src="([^"]+)"')


def _parse_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def absolute_url(base_url: str, value: Any) -> str | None:
    """Turn a media path from the API into an absolute URL."""
    if not value or not isinstance(value, str):
        return None
    if value.startswith(("http://", "https://")):
        return value
    return f"{base_url.rstrip('/')}/{value.lstrip('/')}"


@dataclass(slots=True)
class Car:
    """A vehicle the account owns or that was shared with it."""

    id: int
    display_name: str
    license_plate: str
    make_name: str
    model_text: str
    year: int | None
    vin: str
    color: str
    fuel_type: str
    fuel_type_display: str
    mileage: int | None
    mileage_updated_at: datetime | None
    photo_url: str | None
    is_owner: bool
    enabled: bool
    is_active: bool

    @classmethod
    def from_api(cls, raw: dict[str, Any], base_url: str) -> Car:
        photo_url = absolute_url(base_url, raw.get("photo"))
        if photo_url is None and (img := raw.get("photo_img")) and (match := _IMG_SRC.search(str(img))):
            photo_url = absolute_url(base_url, match.group(1))
        make_name = raw.get("make_name") or raw.get("make_text") or ""
        model_text = raw.get("model_text") or ""
        plate = raw.get("license_plate") or ""
        display_name = raw.get("display_name") or " ".join(p for p in (make_name, model_text) if p) or plate
        return cls(
            id=int(raw["id"]),
            display_name=display_name,
            license_plate=plate,
            make_name=make_name,
            model_text=model_text,
            year=_parse_int(raw.get("year")),
            vin=raw.get("vin") or "",
            color=raw.get("color") or "",
            fuel_type=raw.get("fuel_type") or "",
            fuel_type_display=raw.get("fuel_type_display") or "",
            mileage=_parse_int(raw.get("mileage")),
            mileage_updated_at=_parse_datetime(raw.get("mileage_updated_at")),
            photo_url=photo_url,
            is_owner=bool(raw.get("is_owner", True)),
            enabled=bool(raw.get("enabled", True)),
            is_active=bool(raw.get("is_active", True)),
        )


@dataclass(slots=True)
class Document:
    """A car document (ITP, RCA, vignette...) or a personal document (licence)."""

    id: int
    car_id: int | None
    document_type: str
    document_type_display: str
    document_type_other: str
    document_number: str
    issue_date: date | None
    expiration_date: date | None
    days_until_expiration: int | None
    is_expired: bool
    is_expiring_soon: bool
    status_level: str
    provider: str
    cost: float | None
    notes: str

    @property
    def type_key(self) -> str:
        """Stable key for one entity per document type and car.

        Free-form "other" documents cannot share a key, so they stay unique by id.
        """
        if self.document_type == "other":
            return f"other_{self.id}"
        return self.document_type

    @property
    def label(self) -> str:
        if self.document_type == "other" and self.document_type_other:
            return self.document_type_other
        return self.document_type_display or self.document_type

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Document:
        car = raw.get("car")
        if isinstance(car, dict):
            car = car.get("id")
        return cls(
            id=int(raw["id"]),
            car_id=_parse_int(car),
            document_type=raw.get("document_type") or "other",
            document_type_display=raw.get("document_type_display") or "",
            document_type_other=raw.get("document_type_other") or "",
            document_number=raw.get("document_number") or "",
            issue_date=_parse_date(raw.get("issue_date")),
            expiration_date=_parse_date(raw.get("expiration_date")),
            days_until_expiration=_parse_int(raw.get("days_until_expiration")),
            is_expired=bool(raw.get("is_expired", False)),
            is_expiring_soon=bool(raw.get("is_expiring_soon", False)),
            status_level=raw.get("status_level") or "",
            provider=raw.get("provider") or "",
            cost=_parse_float(raw.get("cost")),
            notes=raw.get("notes") or "",
        )


@dataclass(slots=True)
class ServiceRecord:
    """A maintenance entry with the next due date / mileage it implies."""

    id: int
    car_id: int | None
    service_type: str
    service_type_display: str
    label: str
    service_date: date | None
    mileage_at_service: int | None
    next_service_mileage: int | None
    next_service_date: date | None
    provider: str
    cost: float | None

    @property
    def display(self) -> str:
        return self.label or self.service_type_display or self.service_type

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> ServiceRecord:
        car = raw.get("car")
        if isinstance(car, dict):
            car = car.get("id")
        return cls(
            id=int(raw["id"]),
            car_id=_parse_int(car),
            service_type=raw.get("service_type") or "other",
            service_type_display=raw.get("service_type_display") or "",
            label=raw.get("label") or "",
            service_date=_parse_date(raw.get("service_date")),
            mileage_at_service=_parse_int(raw.get("mileage_at_service")),
            next_service_mileage=_parse_int(raw.get("next_service_mileage")),
            next_service_date=_parse_date(raw.get("next_service_date")),
            provider=raw.get("provider") or "",
            cost=_parse_float(raw.get("cost")),
        )


def _newest_document(current: Document | None, candidate: Document) -> Document:
    """Keep the document that is valid the longest: a renewed RCA replaces the old one."""
    if current is None:
        return candidate
    cur = current.expiration_date or date.min
    new = candidate.expiration_date or date.min
    return candidate if new >= cur else current


def _newest_service(current: ServiceRecord | None, candidate: ServiceRecord) -> ServiceRecord:
    if current is None:
        return candidate
    cur = current.service_date or date.min
    new = candidate.service_date or date.min
    return candidate if new >= cur else current


@dataclass(slots=True)
class BappAutoData:
    """One coordinator snapshot."""

    cars: dict[int, Car] = field(default_factory=dict)
    # car_id -> document type key -> the document currently in force
    documents: dict[int, dict[str, Document]] = field(default_factory=dict)
    # car_id -> service type -> the most recent service record
    services: dict[int, dict[str, ServiceRecord]] = field(default_factory=dict)
    # personal documents (driving licence, ID...) keyed by type key
    user_documents: dict[str, Document] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        base_url: str,
        cars: list[dict[str, Any]],
        car_documents: list[dict[str, Any]],
        service_records: list[dict[str, Any]],
        user_documents: list[dict[str, Any]],
    ) -> BappAutoData:
        data = cls()
        for raw in cars:
            car = Car.from_api(raw, base_url)
            if not car.is_active:
                continue
            data.cars[car.id] = car
        for raw in car_documents:
            doc = Document.from_api(raw)
            if doc.car_id is None or doc.car_id not in data.cars:
                continue
            per_car = data.documents.setdefault(doc.car_id, {})
            per_car[doc.type_key] = _newest_document(per_car.get(doc.type_key), doc)
        for raw in service_records:
            rec = ServiceRecord.from_api(raw)
            if rec.car_id is None or rec.car_id not in data.cars:
                continue
            per_car = data.services.setdefault(rec.car_id, {})
            per_car[rec.service_type] = _newest_service(per_car.get(rec.service_type), rec)
        for raw in user_documents:
            doc = Document.from_api(raw)
            data.user_documents[doc.type_key] = _newest_document(data.user_documents.get(doc.type_key), doc)
        return data

    def car_documents(self, car_id: int) -> dict[str, Document]:
        return self.documents.get(car_id, {})

    def car_services(self, car_id: int) -> dict[str, ServiceRecord]:
        return self.services.get(car_id, {})

    def next_expiring(self, car_id: int) -> Document | None:
        """The car document that expires first (or expired longest ago)."""
        docs = [d for d in self.car_documents(car_id).values() if d.expiration_date is not None]
        if not docs:
            return None
        return min(docs, key=lambda d: d.expiration_date or date.max)

    def attention_count(self, car_id: int) -> int:
        return sum(1 for d in self.car_documents(car_id).values() if d.is_expired or d.is_expiring_soon)
