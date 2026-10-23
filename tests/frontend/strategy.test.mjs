import assert from "node:assert/strict";
import { test } from "node:test";

import {
  carCardConfig,
  carDevices,
  carSection,
  classifyEntity,
  collectCar,
  documentColor,
  generateDashboard,
  generateView,
  personalSection,
  resolveCarDevice,
} from "../../custom_components/bapp_auto/frontend/bapp-auto-strategy.js";

const DOMAIN = "bapp_auto";

function entity(entity_id, device_id, translation_key, state, attributes = {}) {
  return {
    registry: { entity_id, device_id, translation_key, platform: DOMAIN, hidden: false, labels: [] },
    state: { entity_id, state, attributes },
  };
}

function makeHass({ withTranslationKeys = true, language = "ro" } = {}) {
  const devices = {
    dev_duster: { id: "dev_duster", name: "Dacia Duster · B 123 ABC", name_by_user: null, identifiers: [[DOMAIN, "car_7"]], disabled_by: null },
    dev_golf: { id: "dev_golf", name: "VW Golf · CJ 01 XYZ", name_by_user: "Golful", identifiers: [[DOMAIN, "car_9"]], disabled_by: null },
    dev_account: { id: "dev_account", name: "BAPP Auto", identifiers: [[DOMAIN, "account_abc"]], disabled_by: null },
    dev_other: { id: "dev_other", name: "Hue bridge", identifiers: [["hue", "1"]], disabled_by: null },
  };
  const list = [
    entity("sensor.duster_status", "dev_duster", "status", "expiring_soon", { next_expiring_document: "ITP", license_plate: "B 123 ABC" }),
    entity("binary_sensor.duster_attention", "dev_duster", "car_attention", "on", { documents_needing_attention: 1 }),
    entity("sensor.duster_mileage", "dev_duster", "mileage", "123456", { device_class: "distance", unit_of_measurement: "km" }),
    entity("image.duster_photo", "dev_duster", "photo", "2026-10-23T10:00:00+00:00", {}),
    entity("sensor.duster_rca_days", "dev_duster", "document_days_left", "39", { document_type: "rca", document_label: "RCA", unit_of_measurement: "d", is_expired: false, is_expiring_soon: false }),
    entity("sensor.duster_itp_days", "dev_duster", "document_days_left", "5", { document_type: "itp", document_label: "ITP", unit_of_measurement: "d", is_expired: false, is_expiring_soon: true }),
    entity("sensor.duster_vignette_days", "dev_duster", "document_days_left", "-3", { document_type: "vignette", document_label: "Rovinieta", unit_of_measurement: "d", is_expired: true, is_expiring_soon: false }),
    entity("binary_sensor.duster_itp_attention", "dev_duster", "document_attention", "on", { document_type: "itp" }),
    entity("sensor.duster_oil_due", "dev_duster", "next_service_date", "2027-01-05", { service_type: "oil", device_class: "date" }),
    // Golf has no photo, no documents yet
    entity("sensor.golf_status", "dev_golf", "status", "unknown", { next_expiring_document: null }),
    entity("sensor.golf_mileage", "dev_golf", "mileage", "88000", { device_class: "distance", unit_of_measurement: "km" }),
    // personal document
    entity("sensor.permis_days", "dev_account", "document_days_left", "900", { document_type: "driving_license", document_label: "Permis", unit_of_measurement: "d" }),
    // hidden entity must be ignored
    { registry: { entity_id: "sensor.duster_hidden", device_id: "dev_duster", translation_key: "mileage", platform: DOMAIN, hidden: true }, state: { entity_id: "sensor.duster_hidden", state: "1", attributes: {} } },
  ];
  const entities = {};
  const states = {};
  for (const { registry, state } of list) {
    if (!withTranslationKeys) delete registry.translation_key;
    entities[registry.entity_id] = registry;
    states[registry.entity_id] = state;
  }
  return { devices, entities, states, language };
}

test("carDevices returns only bapp_auto car devices, sorted by display name", () => {
  const names = carDevices(makeHass()).map((d) => d.name_by_user || d.name);
  assert.deepEqual(names, ["Dacia Duster · B 123 ABC", "Golful"]);
});

test("collectCar classifies entities and orders documents by urgency", () => {
  const hass = makeHass();
  const car = collectCar(hass, hass.devices.dev_duster);
  assert.equal(car.carId, 7);
  assert.equal(car.photo, "image.duster_photo");
  assert.equal(car.status, "sensor.duster_status");
  assert.equal(car.mileage, "sensor.duster_mileage");
  assert.equal(car.attention, "binary_sensor.duster_attention");
  assert.deepEqual(car.documents, ["sensor.duster_vignette_days", "sensor.duster_itp_days", "sensor.duster_rca_days"]);
  assert.deepEqual(car.services, ["sensor.duster_oil_due"]);
});

test("classification falls back to attributes when translation_key is missing", () => {
  const hass = makeHass({ withTranslationKeys: false });
  const kinds = Object.values(hass.entities).map((e) => [e.entity_id, classifyEntity(hass, e)]);
  const byId = Object.fromEntries(kinds);
  assert.equal(byId["sensor.duster_status"], "status");
  assert.equal(byId["binary_sensor.duster_attention"], "car_attention");
  assert.equal(byId["binary_sensor.duster_itp_attention"], "document_attention");
  assert.equal(byId["sensor.duster_rca_days"], "document_days_left");
  assert.equal(byId["sensor.duster_oil_due"], "next_service_date");
  assert.equal(byId["sensor.duster_mileage"], "mileage");
  assert.equal(byId["image.duster_photo"], "photo");
  const car = collectCar(hass, hass.devices.dev_duster);
  assert.equal(car.documents.length, 3);
});

test("documentColor follows expired / expiring soon / ok", () => {
  const hass = makeHass();
  assert.equal(documentColor(hass, "sensor.duster_vignette_days"), "red");
  assert.equal(documentColor(hass, "sensor.duster_itp_days"), "amber");
  assert.equal(documentColor(hass, "sensor.duster_rca_days"), "green");
  assert.equal(documentColor(hass, "sensor.nope"), "grey");
});

test("carSection uses the photo entity, a status badge and full-width picture", () => {
  const hass = makeHass();
  const section = carSection(hass, collectCar(hass, hass.devices.dev_duster));
  assert.equal(section.type, "grid");
  const [heading, picture, ...tiles] = section.cards;
  assert.equal(heading.type, "heading");
  assert.equal(heading.heading, "Dacia Duster · B 123 ABC");
  assert.equal(heading.badges[0].entity, "sensor.duster_status");
  assert.equal(heading.badges[0].color, "amber");
  assert.equal(picture.type, "picture-entity");
  assert.equal(picture.image_entity, "image.duster_photo");
  assert.equal(picture.image, undefined);
  assert.deepEqual(picture.grid_options, { columns: "full" });
  // 3 documents + mileage + 1 service
  assert.equal(tiles.length, 5);
  assert.equal(tiles[0].name, "Rovinieta");
  assert.equal(tiles[0].color, "red");
  assert.equal(tiles[3].entity, "sensor.duster_mileage");
});

test("a car without a photo gets the placeholder image", () => {
  const hass = makeHass();
  const section = carSection(hass, collectCar(hass, hass.devices.dev_golf));
  const picture = section.cards[1];
  assert.equal(picture.image, "/bapp_auto_static/car-placeholder.svg");
  assert.equal(picture.image_entity, undefined);
});

test("generateView builds one section per car plus personal documents, localized", () => {
  const hass = makeHass();
  const view = generateView({}, hass);
  assert.equal(view.type, "sections");
  assert.equal(view.max_columns, 3);
  assert.equal(view.sections.length, 3);
  assert.equal(view.sections[2].cards[0].heading, "Documente personale");
  assert.equal(view.sections[2].cards[1].entity, "sensor.permis_days");
  const noPersonal = generateView({ personal_documents: false, max_columns: 2 }, hass);
  assert.equal(noPersonal.sections.length, 2);
  assert.equal(noPersonal.max_columns, 2);
});

test("generateView shows an empty-state card when there are no cars", () => {
  const view = generateView({}, { devices: {}, entities: {}, states: {}, language: "en" });
  assert.equal(view.sections.length, 1);
  assert.match(view.sections[0].cards[0].content, /No cars yet/);
});

test("personalSection is null without personal documents", () => {
  const hass = makeHass();
  delete hass.entities["sensor.permis_days"];
  assert.equal(personalSection(hass), null);
});

test("generateDashboard delegates to the view strategy and keeps options", () => {
  const dashboard = generateDashboard({ type: "custom:bapp-auto", max_columns: 4 }, makeHass());
  assert.equal(dashboard.title, "BAPP Auto");
  assert.equal(dashboard.views.length, 1);
  assert.deepEqual(dashboard.views[0].strategy, { max_columns: 4, type: "custom:bapp-auto" });
});

test("resolveCarDevice accepts device, entity or car id", () => {
  const hass = makeHass();
  assert.equal(resolveCarDevice(hass, { device: "dev_golf" }).id, "dev_golf");
  assert.equal(resolveCarDevice(hass, { entity: "sensor.duster_rca_days" }).id, "dev_duster");
  assert.equal(resolveCarDevice(hass, { car: 9 }).id, "dev_golf");
  assert.equal(resolveCarDevice(hass, { car: 404 }), null);
});

test("carCardConfig stacks the picture over a tile grid, or explains when the car is missing", () => {
  const hass = makeHass();
  const config = carCardConfig(hass, { device: "dev_duster", name: "Dusterul" });
  assert.equal(config.type, "vertical-stack");
  assert.equal(config.cards[0].type, "picture-entity");
  assert.equal(config.cards[0].name, "Dusterul");
  assert.equal(config.cards[1].type, "grid");
  assert.equal(config.cards[1].columns, 2);
  assert.equal(config.cards[1].cards.length, 5);
  const missing = carCardConfig(hass, { device: "dev_other" });
  assert.equal(missing.type, "markdown");
  assert.match(missing.content, /nu a fost găsită/);
});
