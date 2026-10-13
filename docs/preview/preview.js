// Only this preview provides sample HA state. Production card sources are unchanged.
import * as mdi from "/web/node_modules/@mdi/js/mdi.js";
import "/custom_components/ids_jmk/www/ids-jmk-departures-card.js";
import "/custom_components/ids_jmk/www/ids-jmk-alerts-card.js";
import "/custom_components/ids_jmk/www/ids-jmk-map-card.js";
class Icon extends HTMLElement {
  connectedCallback() {
    const key =
      "mdi" +
      (this.getAttribute("icon") || "")
        .replace("mdi:", "")
        .split("-")
        .map((s) => s[0]?.toUpperCase() + s.slice(1))
        .join("");
    this.attachShadow({ mode: "open" }).innerHTML =
      `<style>:host{display:inline-flex;width:var(--mdc-icon-size,24px);height:var(--mdc-icon-size,24px)}svg{width:100%;height:100%;fill:currentColor}</style><svg viewBox="0 0 24 24"><path d="${mdi[key] || ""}"/></svg>`;
  }
}
customElements.define("ha-icon", Icon);
const now = Date.now();
const iso = (minutes = 0) => new Date(now + minutes * 60000).toISOString();
const departures = [
  ["8", "Nemocnice Bohunice", 4, 2, "2", "tram", true, true],
  ["12", "Technologický park", 9, 0, "1", "tram", true, false],
  ["67", "Jundrov", 16, 3, "3", "bus", true, false],
  ["S2", "Blansko", 24, 0, "4", "rail", true, true],
].map(
  (
    [
      line,
      destination,
      minutes,
      delay,
      platform,
      transport_mode,
      wheelchair_accessible,
      bikes_allowed,
    ],
    i,
  ) => ({
    trip_id: `demo-${i}`,
    service_date: new Date(now).toISOString().slice(0, 10),
    stop_id: "demo",
    stop_sequence: 1,
    line,
    destination,
    platform,
    transport_mode,
    wheelchair_accessible,
    bikes_allowed,
    scheduled_departure: iso(minutes - delay),
    departure_time: iso(minutes),
    estimated_departure: delay ? iso(minutes) : null,
    delay_seconds: delay * 60,
    minutes_until: minutes,
    departure_time_display: new Date(now + minutes * 60000).toLocaleTimeString(
      "cs-CZ",
      { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Prague" },
    ),
    source: delay ? "vehicle_estimate" : "schedule",
    has_vehicle_position: true,
  }),
);
const attributes = {
  stop_name: "Brno, hlavní nádraží",
  stop_id: "demo",
  generated_at: iso(),
  realtime_enabled: true,
  realtime_stale: false,
  departures,
  alerts_stale: false,
  alerts: [
    {
      id: "demo-alert",
      key: "demo-alert",
      title: "Ukázkové omezení",
      description:
        "Ukázkové omezení na lince 67\nZastávka je dočasně přesunuta. Před cestou ověřte podrobnosti v aktuálních informacích dopravního systému.",
      matched_lines: ["67"],
      scope: "line",
    },
  ],
};
const stops = [
  { name: "Hlavní nádraží", lat: 49.1908, lon: 16.6128 },
  { name: "Nové sady", lat: 49.189, lon: 16.6077 },
  { name: "Šilingrovo náměstí", lat: 49.1915, lon: 16.605 },
  { name: "Česká", lat: 49.198, lon: 16.6055 },
].map((s, i) => ({
  ...s,
  stop_id: `demo-${i}`,
  line: "12",
  route_id: "demo-12",
  direction: "0",
  scheduled_departure: iso(i * 3),
}));
const vehicles = [
  {
    id: "v1",
    trip_id: "demo-1",
    line: "12",
    direction: "0",
    destination: "Technologický park",
    transport_mode: "tram",
    position: { lat: 49.194, lon: 16.6052 },
  },
  {
    id: "v2",
    trip_id: "demo-2",
    line: "8",
    direction: "1",
    destination: "Líšeň, Mifkova",
    transport_mode: "tram",
    position: { lat: 49.1906, lon: 16.616 },
  },
];
vehicles.forEach((v) => {
  v.updated_at = iso();
  v.service_date = "2026-10-13";
});
const hass = {
  states: { "sensor.ids_jmk_demo": { state: "4", attributes } },
  user: { id: "docs" },
  callWS: async (request) =>
    request.action === "vehicles"
      ? { realtime_enabled: true, stale: false, updated_at: iso(), vehicles }
      : request.action === "stops"
        ? { stops }
        : { stops },
};
function add(target, type, config) {
  const card = document.createElement(type);
  card.setConfig(config);
  card.hass = hass;
  document.getElementById(target).append(card);
  return card;
}
add("modern", "ids-jmk-departures-card", {
  entity: "sensor.ids_jmk_demo",
  layout: "modern",
});
add("compact", "ids-jmk-departures-card", {
  entity: "sensor.ids_jmk_demo",
  layout: "compact",
});
add("alerts", "ids-jmk-alerts-card", {
  entities: ["sensor.ids_jmk_demo"],
  title: "Omezení na mých trasách",
});
add("map", "ids-jmk-map-card", {
  entry_id: "demo",
  title: "Mapa vehyklů · centrum Brna",
  selections: [{ route_id: "demo-12", direction: "*", show_stops: true }],
  refresh_interval: 3600,
});
window.docsFixture = { departures, attributes };
if (new URLSearchParams(location.search).has("dark"))
  document.body.classList.add("dark");
