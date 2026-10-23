# BAPP Auto for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Validate](https://github.com/bapp-open/ha-bapp-auto/actions/workflows/validate.yml/badge.svg)](https://github.com/bapp-open/ha-bapp-auto/actions/workflows/validate.yml)

Brings the cars you track in the **BAPP Auto** app into Home Assistant: document
expiry dates (ITP, RCA, vignette, CASCO, registration…), mileage, upcoming service
and the car photo, for every car you own or that was shared with you.

## What you get

Each car becomes a **device** named after the car and its licence plate, with its
photo, so several cars stay easy to tell apart. Under each car:

| Entity | Example | Notes |
| --- | --- | --- |
| `sensor.<car>_documents_status` | `expiring_soon` | `ok` / `expiring_soon` / `expired` / `unknown`; carries the photo and the next expiring document as attributes |
| `binary_sensor.<car>_needs_attention` | `on` | On when any document is expired or inside the warning window |
| `sensor.<car>_mileage` | `123456 km` | Odometer as last entered in the app |
| `image.<car>_photo` | | The car photo, for picture cards |
| `sensor.<car>_rca_days_left` | `39 d` | One per document type; negative when expired |
| `binary_sensor.<car>_rca_needs_attention` | `off` | One per document type |
| `sensor.<car>_rca_expiration` | `2026-12-01` | Disabled by default |
| `sensor.<car>_<service>_due_date` / `_due_mileage` | | From the service log, disabled by default |

Personal documents (driving licence, ID…) appear under a separate **BAPP Auto** device.

Entities for a document type appear automatically when you add the first document
of that type in the app. When a renewed document is added, the sensors switch to the
one that is valid the longest.

## Services

- `bapp_auto.update_mileage` — set the odometer of one or more cars (pick the car devices).
- `bapp_auto.refresh` — fetch the latest data now instead of waiting for the next poll.

## Installation

### HACS (recommended)

1. HACS → **Integrations** → ⋮ → **Custom repositories**.
2. Add `https://github.com/bapp-open/ha-bapp-auto` with category **Integration**.
3. Install **BAPP Auto**, restart Home Assistant.

### Manual

Copy `custom_components/bapp_auto` into your `config/custom_components/` folder and
restart Home Assistant.

## Setup

1. In the BAPP Auto app open **Settings → Integrations → Home Assistant** and copy the
   personal API token.
2. In Home Assistant go to **Settings → Devices & services → Add integration → BAPP Auto**
   and paste the token.

The token identifies your account only; it never gives access to a company's bapp data.
Revoking it in the app disconnects Home Assistant, which will then ask for a new one.

**Options:** the refresh interval (default 30 minutes, minimum 5). Documents change
rarely, so there is no need to poll often.

## Dashboard ideas

A picture card per car with the status overlaid:

```yaml
type: picture-entity
entity: sensor.dacia_duster_documents_status
image_entity: image.dacia_duster_photo
name: Dacia Duster · B 123 ABC
```

A reminder automation:

```yaml
alias: Car documents expiring
triggers:
  - trigger: state
    entity_id: binary_sensor.dacia_duster_needs_attention
    to: "on"
actions:
  - action: notify.mobile_app_phone
    data:
      title: "{{ state_attr('sensor.dacia_duster_documents_status', 'display_name') }}"
      message: >
        {{ state_attr('sensor.dacia_duster_documents_status', 'next_expiring_document') }}
        expires in {{ state_attr('sensor.dacia_duster_documents_status', 'next_expiring_days') }} days.
```

## Development

```bash
uv run --with pytest --with yarl pytest       # model tests, no Home Assistant needed
```

The CI runs the HACS and hassfest validators on every push.

## License

MIT — see [LICENSE](LICENSE).
