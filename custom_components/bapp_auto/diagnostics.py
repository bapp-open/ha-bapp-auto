"""Diagnostics download with the token redacted."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN
from .coordinator import BappAutoConfigEntry

TO_REDACT = {CONF_TOKEN, "vin", "license_plate", "document_number", "photo_url"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: BappAutoConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    snapshot = {
        "cars": {cid: asdict(car) for cid, car in data.cars.items()},
        "documents": {cid: {k: asdict(d) for k, d in docs.items()} for cid, docs in data.documents.items()},
        "services": {cid: {k: asdict(r) for k, r in recs.items()} for cid, recs in data.services.items()},
        "user_documents": {k: asdict(d) for k, d in data.user_documents.items()},
    }
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "data": async_redact_data(snapshot, TO_REDACT),
    }
