/**
 * BAPP Auto for Home Assistant: dashboard strategy, view strategy and car card.
 *
 * Loaded automatically by the integration as a Lovelace module resource.
 *   Dashboard:  strategy: { type: custom:bapp-auto }
 *   View:       strategy: { type: custom:bapp-auto }
 *   Card:       type: custom:bapp-auto-car, device: <device id>  (or entity: / car:)
 *
 * The strategies emit only built-in cards, so "Take control" leaves the user with
 * a plain editable dashboard. The pure functions are exported for unit tests.
 */

export const DOMAIN = "bapp_auto";
export const VERSION = "0.2.0";
const PLACEHOLDER = "/bapp_auto_static/car-placeholder.svg";

const STATUS_COLOR = { ok: "green", expiring_soon: "amber", expired: "red", unknown: "grey" };

const TEXT = {
  en: {
    dashboard: "BAPP Auto",
    personal: "Personal documents",
    empty: "No cars yet. Add a car in the BAPP Auto app and it will show up here.",
    car_not_found: "BAPP Auto car not found. Check the card's `device`, `entity` or `car` option.",
    card_name: "BAPP Auto car",
    card_description: "Photo, document expiry and mileage of one BAPP Auto car.",
  },
  ro: {
    dashboard: "BAPP Auto",
    personal: "Documente personale",
    empty: "Nu există mașini încă. Adaugă o mașină în aplicația BAPP Auto și va apărea aici.",
    car_not_found: "Mașina BAPP Auto nu a fost găsită. Verifică opțiunea `device`, `entity` sau `car` a cardului.",
    card_name: "Mașină BAPP Auto",
    card_description: "Poza, expirarea documentelor și kilometrajul unei mașini din BAPP Auto.",
  },
};

export function t(hass, key) {
  const lang = (hass && hass.language ? hass.language : "en").split("-")[0];
  return (TEXT[lang] || TEXT.en)[key] || TEXT.en[key] || key;
}

function num(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function identifierOf(device, prefix) {
  const found = (device.identifiers || []).find(([dom, id]) => dom === DOMAIN && String(id).startsWith(prefix));
  return found ? String(found[1]) : null;
}

export function deviceName(device) {
  return device.name_by_user || device.name || "Car";
}

/** Car devices of every connected account, sorted by name. */
export function carDevices(hass) {
  return Object.values(hass.devices || {})
    .filter((d) => !d.disabled_by && identifierOf(d, "car_") !== null)
    .sort((a, b) => deviceName(a).localeCompare(deviceName(b)));
}

export function carIdOf(device) {
  const ident = identifierOf(device, "car_");
  return ident ? num(ident.slice(4)) : null;
}

export function accountDevices(hass) {
  return Object.values(hass.devices || {}).filter((d) => !d.disabled_by && identifierOf(d, "account_") !== null);
}

/** Enabled, visible entities of this integration on one device that currently have a state. */
export function deviceEntities(hass, deviceId) {
  return Object.values(hass.entities || {}).filter(
    (e) => e.device_id === deviceId && e.platform === DOMAIN && !e.hidden && hass.states[e.entity_id],
  );
}

const KNOWN_KEYS = new Set([
  "status",
  "mileage",
  "mileage_updated",
  "car_attention",
  "document_days_left",
  "document_attention",
  "document_expiration",
  "next_service_date",
  "next_service_mileage",
]);

/** What an entity is for; uses translation_key and falls back to attributes. */
export function classifyEntity(hass, entry) {
  const domain = entry.entity_id.split(".")[0];
  if (domain === "image") return "photo";
  if (entry.translation_key && KNOWN_KEYS.has(entry.translation_key)) return entry.translation_key;
  const attrs = (hass.states[entry.entity_id] || {}).attributes || {};
  if ("next_expiring_document" in attrs) return "status";
  if (domain === "binary_sensor" && "documents_needing_attention" in attrs) return "car_attention";
  if (domain === "binary_sensor" && "document_type" in attrs) return "document_attention";
  if (domain === "sensor" && "document_type" in attrs) {
    return attrs.unit_of_measurement === "d" ? "document_days_left" : "document_expiration";
  }
  if (domain === "sensor" && "service_type" in attrs) {
    return attrs.device_class === "date" ? "next_service_date" : "next_service_mileage";
  }
  if (domain === "sensor" && attrs.device_class === "distance") return "mileage";
  if (domain === "sensor" && attrs.device_class === "timestamp") return "mileage_updated";
  return null;
}

function daysLeft(hass, entityId) {
  const st = hass.states[entityId];
  return st ? num(st.state) : null;
}

/** Everything the cards need about one car, resolved from the registries. */
export function collectCar(hass, device) {
  const car = {
    device,
    name: deviceName(device),
    carId: carIdOf(device),
    photo: null,
    status: null,
    mileage: null,
    attention: null,
    documents: [],
    services: [],
  };
  for (const entry of deviceEntities(hass, device.id)) {
    switch (classifyEntity(hass, entry)) {
      case "photo":
        car.photo = entry.entity_id;
        break;
      case "status":
        car.status = entry.entity_id;
        break;
      case "mileage":
        car.mileage = entry.entity_id;
        break;
      case "car_attention":
        car.attention = entry.entity_id;
        break;
      case "document_days_left":
        car.documents.push(entry.entity_id);
        break;
      case "next_service_date":
      case "next_service_mileage":
        car.services.push(entry.entity_id);
        break;
      default:
        break;
    }
  }
  // The document that expires first comes first; unknown values go last.
  const order = (id) => {
    const d = daysLeft(hass, id);
    return d === null ? Number.POSITIVE_INFINITY : d;
  };
  car.documents.sort((a, b) => order(a) - order(b));
  car.services.sort((a, b) => a.localeCompare(b));
  return car;
}

export function documentColor(hass, entityId) {
  const st = hass.states[entityId];
  if (!st) return "grey";
  const attrs = st.attributes || {};
  const days = num(st.state);
  if (attrs.is_expired || (days !== null && days < 0)) return "red";
  if (attrs.is_expiring_soon) return "amber";
  if (days === null) return "grey";
  return "green";
}

export function statusColor(hass, entityId) {
  const st = hass.states[entityId];
  return STATUS_COLOR[st ? st.state : "unknown"] || "grey";
}

export function pictureCard(hass, car) {
  const entity = car.status || car.attention || car.mileage;
  if (!entity) return null;
  const card = {
    type: "picture-entity",
    entity,
    name: car.name,
    show_name: true,
    show_state: Boolean(car.status),
    fit_mode: "cover",
    tap_action: { action: "more-info" },
  };
  if (car.photo) card.image_entity = car.photo;
  else card.image = PLACEHOLDER;
  return card;
}

export function documentTile(hass, entityId) {
  const attrs = (hass.states[entityId] || {}).attributes || {};
  const tile = {
    type: "tile",
    entity: entityId,
    color: documentColor(hass, entityId),
    state_content: ["state", "expiration_date"],
  };
  if (attrs.document_label) tile.name = attrs.document_label;
  return tile;
}

/** Built-in cards for one car, in display order; no layout hints. */
export function carCards(hass, car) {
  const cards = [];
  const picture = pictureCard(hass, car);
  if (picture) cards.push(picture);
  for (const id of car.documents) cards.push(documentTile(hass, id));
  if (car.mileage) cards.push({ type: "tile", entity: car.mileage, color: "blue", icon: "mdi:counter" });
  for (const id of car.services) cards.push({ type: "tile", entity: id, color: "purple" });
  return cards;
}

/** A sections-view section for one car: heading with status badge, then the cards. */
export function carSection(hass, car) {
  const heading = { type: "heading", heading: car.name, heading_style: "title", icon: "mdi:car" };
  if (car.status) {
    heading.badges = [{ type: "entity", entity: car.status, show_state: true, color: statusColor(hass, car.status) }];
  }
  const cards = carCards(hass, car).map((card, index) =>
    index === 0 && card.type === "picture-entity" ? { ...card, grid_options: { columns: "full" } } : card,
  );
  return { type: "grid", cards: [heading, ...cards] };
}

export function personalSection(hass) {
  const docs = [];
  for (const device of accountDevices(hass)) {
    for (const entry of deviceEntities(hass, device.id)) {
      if (classifyEntity(hass, entry) === "document_days_left") docs.push(entry.entity_id);
    }
  }
  if (!docs.length) return null;
  const order = (id) => {
    const d = daysLeft(hass, id);
    return d === null ? Number.POSITIVE_INFINITY : d;
  };
  docs.sort((a, b) => order(a) - order(b));
  return {
    type: "grid",
    cards: [
      { type: "heading", heading: t(hass, "personal"), heading_style: "title", icon: "mdi:card-account-details" },
      ...docs.map((id) => documentTile(hass, id)),
    ],
  };
}

export function generateView(config, hass) {
  const cars = carDevices(hass)
    .map((device) => collectCar(hass, device))
    .filter((car) => car.status || car.documents.length || car.mileage);
  const sections = cars.map((car) => carSection(hass, car));
  if (config.personal_documents !== false) {
    const personal = personalSection(hass);
    if (personal) sections.push(personal);
  }
  if (!sections.length) {
    sections.push({ type: "grid", cards: [{ type: "markdown", content: t(hass, "empty") }] });
  }
  return { type: "sections", max_columns: config.max_columns || 3, sections };
}

export function generateDashboard(config, hass) {
  const title = config.title || t(hass, "dashboard");
  const { type: _ignored, ...viewOptions } = config;
  return {
    title,
    views: [
      {
        title,
        path: "bapp-auto",
        icon: "mdi:car-multiple",
        strategy: { ...viewOptions, type: "custom:bapp-auto" },
      },
    ],
  };
}

/** Resolve a card config (device / entity / car) to a car device. */
export function resolveCarDevice(hass, config) {
  if (config.device && hass.devices && hass.devices[config.device]) return hass.devices[config.device];
  if (config.entity && hass.entities && hass.entities[config.entity]) {
    const deviceId = hass.entities[config.entity].device_id;
    if (deviceId && hass.devices[deviceId]) return hass.devices[deviceId];
  }
  if (config.car !== undefined && config.car !== null) {
    const wanted = `car_${config.car}`;
    return carDevices(hass).find((d) => identifierOf(d, "car_") === wanted) || null;
  }
  return null;
}

/** The inner (built-in) card config rendered by custom:bapp-auto-car. */
export function carCardConfig(hass, config) {
  const device = resolveCarDevice(hass, config);
  if (!device || carIdOf(device) === null) {
    return { type: "markdown", content: t(hass, "car_not_found") };
  }
  const car = collectCar(hass, device);
  if (config.name) car.name = config.name;
  const cards = carCards(hass, car);
  const [first, ...rest] = cards;
  const stack = [];
  if (first) stack.push(first);
  if (rest.length) stack.push({ type: "grid", columns: config.columns || 2, square: false, cards: rest });
  return stack.length === 1 ? stack[0] : { type: "vertical-stack", cards: stack };
}

// ---------------------------------------------------------------------------
// Browser registration (skipped under Node so the functions above stay testable)
// ---------------------------------------------------------------------------
if (typeof customElements !== "undefined" && typeof HTMLElement !== "undefined") {
  const define = (tag, cls) => {
    if (!customElements.get(tag)) customElements.define(tag, cls);
  };

  class BappAutoDashboardStrategy extends HTMLElement {
    static async generate(config, hass) {
      return generateDashboard(config, hass);
    }
  }

  class BappAutoViewStrategy extends HTMLElement {
    static async generate(config, hass) {
      return generateView(config, hass);
    }
  }

  class BappAutoCarCard extends HTMLElement {
    static getStubConfig(hass) {
      const first = carDevices(hass)[0];
      return first ? { device: first.id } : {};
    }

    setConfig(config) {
      if (!config || (!config.device && !config.entity && config.car === undefined)) {
        throw new Error('bapp-auto-car: set "device", "entity" or "car"');
      }
      this._config = config;
      this._signature = null;
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    get hass() {
      return this._hass;
    }

    async _render() {
      if (!this._hass || !this._config) return;
      const inner = carCardConfig(this._hass, this._config);
      const signature = JSON.stringify(inner);
      if (signature === this._signature) {
        if (this._card) this._card.hass = this._hass;
        return;
      }
      this._signature = signature;
      const token = (this._token = Symbol("render"));
      const helpers = await window.loadCardHelpers();
      if (token !== this._token) return; // a newer render superseded this one
      const card = helpers.createCardElement(inner);
      card.hass = this._hass;
      this._card = card;
      this.replaceChildren(card);
    }

    getCardSize() {
      return this._card && this._card.getCardSize ? this._card.getCardSize() : 6;
    }

    getGridOptions() {
      return { columns: "full" };
    }
  }

  define("ll-strategy-dashboard-bapp-auto", BappAutoDashboardStrategy);
  define("ll-strategy-view-bapp-auto", BappAutoViewStrategy);
  define("bapp-auto-car", BappAutoCarCard);

  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === "bapp-auto-car")) {
    const lang = (navigator.language || "en").split("-")[0];
    window.customCards.push({
      type: "bapp-auto-car",
      name: t({ language: lang }, "card_name"),
      description: t({ language: lang }, "card_description"),
      preview: true,
      documentationURL: "https://github.com/bapp-open/ha-bapp-auto#dashboard",
    });
  }

  console.info(`%c BAPP Auto %c ${VERSION} `, "background:#0f172a;color:#fff;border-radius:3px 0 0 3px", "background:#2563eb;color:#fff;border-radius:0 3px 3px 0");
}
