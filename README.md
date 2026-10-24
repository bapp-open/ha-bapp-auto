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

1. **Settings → Devices & services → Add integration → BAPP Auto**.
2. Home Assistant sends you to the BAPP login page (the same account as the app). Log in.
3. You are sent back; the integration is created and named after your account.

Every car you own or that was shared with you becomes a device. Nothing to copy or
paste: Home Assistant keeps a refresh token and renews access by itself. If the
login ever stops working, Home Assistant asks you to log in again.

**Options:** the refresh interval (default 30 minutes, minimum 5). Documents change
rarely, so there is no need to poll often.

## Dashboard

The integration ships a Lovelace **strategy** and a **card**, loaded automatically.
Nothing to add under *Resources*.

### Automatic dashboard

**Settings → Dashboards → Add dashboard → New dashboard from scratch**, open it, then
⋮ → **Edit dashboard** → ⋮ → **Raw configuration editor** and paste:

```yaml
strategy:
  type: custom:bapp-auto
```

You get one section per car: the photo with the documents status overlaid, a colored
tile per document (green / amber / red by expiry), the mileage and upcoming service,
plus a section for personal documents. Cars and documents added later appear by
themselves. Options:

```yaml
strategy:
  type: custom:bapp-auto
  title: Mașini            # dashboard and view title
  max_columns: 2           # sections per row (default 3)
  personal_documents: false
```

The same strategy works for a single **view** inside an existing dashboard
(`strategy:` at the view level). *Take control* turns the generated dashboard into
plain built-in cards you can edit.

### One car anywhere

```yaml
type: custom:bapp-auto-car
device: 0123456789abcdef   # the car's device id (pick it in the card editor)
```

`entity: sensor.<any entity of the car>` or `car: <id from the app>` work too;
`name:` overrides the title and `columns:` the tile grid width (default 2).

### Hand-made card

The entities work with any built-in card as well:

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
node --test "tests/frontend/*.test.mjs"       # strategy / card config tests
```

The CI runs the HACS and hassfest validators on every push.

## License

MIT — see [LICENSE](LICENSE).
