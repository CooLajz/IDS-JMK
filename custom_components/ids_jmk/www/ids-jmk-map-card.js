/* Vehicle data travel through HA WebSocket; no per-vehicle entities. */
const TYPE = "ids-jmk-map-card";
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
// Match the transport symbols used by the departures card.
const TRANSPORT_ICONS = {
  tram: "tram",
  bus: "bus",
  rail: "train",
  trolleybus: "bus-electric",
  subway: "subway-variant",
  ferry: "ferry",
  aerial_lift: "gondola",
  cable_tram: "tram",
  funicular: "train",
  monorail: "train",
};
const directionColor = (direction) =>
  String(direction) === "0"
    ? "#16834a"
    : String(direction) === "1"
      ? "#1769c2"
      : "#586777";
const vehicleIcon = (mode) =>
  Object.hasOwn(TRANSPORT_ICONS, mode) ? TRANSPORT_ICONS[mode] : "map-marker";
let leaflet;
function loadMap() {
  if (window.L) return Promise.resolve(window.L);
  if (!leaflet)
    leaflet = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "/ids_jmk/map-vendor/leaflet.js";
      script.onload = () => resolve(window.L);
      script.onerror = () => {
        leaflet = null;
        script.remove();
        reject(new Error("Mapovou knihovnu nelze načíst."));
      };
      document.head.append(script);
    });
  return leaflet;
}
const css = `:host{display:block}*{box-sizing:border-box}ha-card{display:block;overflow:hidden;background:var(--ha-card-background,var(--card-background-color,#fff));color:var(--primary-text-color,#172b3a);border-radius:16px}header{padding:12px 16px;display:flex;align-items:center;gap:12px}.heading{flex:1;min-width:0}h2{font-size:18px;line-height:1.3;margin:0;overflow-wrap:anywhere}header button{flex-shrink:0}button,select{font:inherit;padding:8px;border:1px solid var(--divider-color,#ccc);border-radius:8px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#172b3a)}button{cursor:pointer}.detail{padding:10px 16px;font-size:13px;line-height:1.5}.status{margin-top:4px;font-size:12px;line-height:1.4;overflow-wrap:anywhere;color:var(--secondary-text-color,#536475)}.map{height:var(--map-height,400px);isolation:isolate;background:#e6ede9}.vehicle{background:none;border:0;text-align:center;white-space:nowrap}.vehicle-badge{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;background:var(--vehicle-color);color:white;border:2px solid white;border-radius:12px;box-shadow:0 2px 6px #0005;font:bold 13px/16px sans-serif}.vehicle ha-icon{display:block;width:26px;height:26px;--mdc-icon-size:26px}.vehicle-number{display:block;max-width:100%;padding:0 2px;overflow:hidden;text-overflow:ellipsis}.leaflet-container{font-family:inherit}.detail:empty{display:none}.detail ol{max-height:150px;overflow:auto;padding-left:22px}@media(max-width:450px){header{padding:12px}h2{font-size:16px}}`;
class MapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.generation = 0;
  }
  setConfig(config) {
    if (
      config.selections &&
      (!Array.isArray(config.selections) ||
        config.selections.length > 20 ||
        config.selections.some(
          (s) =>
            typeof s.route_id !== "string" || typeof s.direction !== "string",
        ))
    )
      throw new Error("Vyberte nejvýše 20 linek a jejich směry.");
    this.config = { ...config, selections: config.selections || [] };
    this.generation++;
    this.selected = null;
    if (this.map) {
      this.markers.clearLayers();
      this.route.clearLayers();
      this.detail.textContent = "";
    }
    this.fitted = false;
    this.init();
    this.refresh();
  }
  set hass(value) {
    this._hass = value;
    this.init();
  }
  static getConfigElement() {
    return document.createElement(`${TYPE}-editor`);
  }
  static getStubConfig() {
    return { title: "Mapa vehyklů", selections: [] };
  }
  getCardSize() {
    return 7;
  }
  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 8 };
  }
  connectedCallback() {
    this.init();
    clearInterval(this.timer);
    this.timer = setInterval(() => this.refresh(), 30000);
  }
  disconnectedCallback() {
    clearInterval(this.timer);
    this.generation++;
    this.observer?.disconnect();
    this.map?.remove();
    this.map = null;
    this.initializing = false;
  }
  async init() {
    if (
      !this.config ||
      !this._hass ||
      !this.isConnected ||
      this.map ||
      this.initializing
    )
      return;
    this.initializing = true;
    this.shadowRoot.innerHTML = `<link rel="stylesheet" href="/ids_jmk/map-vendor/leaflet.css"><style>${css}</style><ha-card><header><div class="heading"><h2>${esc(this.config.title || "Mapa vehyklů")}</h2><div class="status" role="status">Načítání mapy…</div></div><button title="Zobrazit všechna vozidla">Přehled</button></header><div class="map" aria-label="Mapa vozidel IDS JMK"></div><div class="detail"></div></ha-card>`;
    this.status = this.shadowRoot.querySelector(".status");
    this.detail = this.shadowRoot.querySelector(".detail");
    try {
      this.L = await loadMap();
      if (!this.isConnected) return;
      this.map = this.L.map(this.shadowRoot.querySelector(".map")).setView(
        [49.2, 16.6],
        10,
      );
      this.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
          '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(this.map);
      this.markers = this.L.featureGroup().addTo(this.map);
      this.route = this.L.featureGroup().addTo(this.map);
      this.shadowRoot.querySelector("button").onclick = () => this.fit();
      this.observer = new ResizeObserver(() => this.map?.invalidateSize());
      this.observer.observe(this);
      await this.refresh();
    } catch (error) {
      this.status.textContent = error.message || "Mapu nelze načíst.";
    } finally {
      this.initializing = false;
    }
  }
  call(action, extra = {}) {
    return this._hass.callWS({
      type: "ids_jmk/map",
      entry_id: this.config.entry_id,
      action,
      ...extra,
    });
  }
  fit() {
    const bounds = this.markers.getBounds();
    if (bounds.isValid())
      this.map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
  }
  async refresh() {
    if (!this.map || !this.isConnected) return;
    this.shadowRoot.querySelector("h2").textContent =
      this.config.title || "Mapa vehyklů";
    if (!this.config.entry_id || !this.config.selections.length) {
      this.status.textContent =
        "V nastavení karty vyberte zdroj, linky a směry.";
      return;
    }
    const generation = this.generation;
    if (this.pending === generation) return;
    this.pending = generation;
    try {
      const data = await this.call("vehicles", {
        selections: this.config.selections,
      });
      if (generation !== this.generation || !this.isConnected) return;
      this.markers.clearLayers();
      const vehicles = (data.vehicles || []).filter(
        (v) =>
          !v.stale &&
          v.position &&
          Number.isFinite(v.position.lat) &&
          Number.isFinite(v.position.lon),
      );
      this.status.textContent = !data.realtime_enabled
        ? "Realtime data jsou na serveru vypnutá."
        : data.stale
          ? "Polohy nejsou aktuální. Čeká se na nová data."
          : `${vehicles.length} vozidel · ${data.updated_at ? new Date(data.updated_at).toLocaleTimeString("cs-CZ") : "bez aktualizace"}${vehicles.length ? "" : " · Pro výběr nejsou dostupné aktuální polohy."}`;
      for (const v of vehicles) {
        this.L.marker([v.position.lat, v.position.lon], {
          title: `${v.line} → ${v.destination}`,
          icon: this.L.divIcon({
            className: "vehicle",
            html: `<span class="vehicle-badge" style="--vehicle-color:${directionColor(v.direction)}"><ha-icon icon="mdi:${vehicleIcon(v.transport_mode)}" aria-hidden="true"></ha-icon><span class="vehicle-number">${esc(v.line)}</span></span>`,
            iconSize: [44, 52],
            iconAnchor: [22, 26],
          }),
        })
          .addTo(this.markers)
          .on("click", () => this.showTrip(v));
      }
      if (
        this.selected &&
        !vehicles.some(
          (v) =>
            v.id === this.selected.id && v.trip_id === this.selected.trip_id,
        )
      ) {
        this.selected = null;
        this.route.clearLayers();
        this.detail.textContent = "Vybrané vozidlo již nemá aktuální polohu.";
      }
      if (!this.fitted && vehicles.length) {
        this.fit();
        this.fitted = true;
      }
    } catch (error) {
      if (generation !== this.generation || !this.isConnected) return;
      this.markers.clearLayers();
      this.route.clearLayers();
      this.selected = null;
      this.detail.textContent = "";
      this.status.textContent =
        "Mapová data nejsou dostupná. Ověřte připojení a aktualizaci API i integrace.";
    } finally {
      if (this.pending === generation) this.pending = null;
    }
  }
  async showTrip(vehicle) {
    this.selected = vehicle;
    this.route.clearLayers();
    this.detail.textContent = `Linka ${vehicle.line} → ${vehicle.destination} · Načítání zastávek…`;
    const generation = this.generation;
    try {
      const trip = await this.call("trip", {
        trip_id: vehicle.trip_id,
        service_date: vehicle.service_date,
      });
      if (
        this.selected !== vehicle ||
        generation !== this.generation ||
        !this.isConnected
      )
        return;
      const stops = (trip.stops || []).filter(
        (s) => Number.isFinite(s.lat) && Number.isFinite(s.lon),
      );
      this.L.polyline(
        stops.map((s) => [s.lat, s.lon]),
        {
          color: directionColor(vehicle.direction),
          weight: 3,
          dashArray: "6 8",
        },
      ).addTo(this.route);
      for (const stop of stops)
        this.L.circleMarker([stop.lat, stop.lon], {
          radius: 4,
          color: directionColor(vehicle.direction),
          fillOpacity: 1,
          fillColor: "white",
        })
          .bindTooltip(esc(stop.name))
          .addTo(this.route);
      if (this.route.getBounds().isValid())
        this.map.fitBounds(this.route.getBounds(), {
          padding: [24, 24],
          maxZoom: 14,
        });
      const delay = vehicle.current_stop?.delay_seconds;
      this.detail.innerHTML = `<strong>${esc(vehicle.line)} → ${esc(vehicle.destination)}</strong><br>Vozidlo ${esc(vehicle.label || vehicle.id)} · Poloha ${esc(new Date(vehicle.updated_at).toLocaleTimeString("cs-CZ"))}${delay != null ? ` · Zpoždění ${Math.round(delay / 60)} min` : ""}<br>Orientační spojnice zastávek, nikoli přesný průběh trasy.<ol>${stops.map((s) => `<li>${esc(s.name)}</li>`).join("")}</ol>`;
    } catch {
      if (this.selected === vehicle && generation === this.generation)
        this.detail.textContent = "Detail spoje není dostupný.";
    }
  }
}
class MapEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }
  setConfig(config) {
    this.config = { ...config, selections: config.selections || [] };
    this.render();
    this.load();
  }
  set hass(value) {
    this._hass = value;
    this.load();
  }
  async load() {
    if (!this._hass || !this.config || this.loading) return;
    this.loading = true;
    const entry = this.config.entry_id;
    try {
      this.sources = await this._hass.callWS({ type: "ids_jmk/map_sources" });
      if (entry && this.routeEntry !== entry) {
        const data = await this._hass.callWS({
          type: "ids_jmk/map",
          entry_id: entry,
          action: "routes",
        });
        if (this.config.entry_id === entry) {
          this.routes = data.routes;
          this.routeEntry = entry;
        }
      }
      this.error = "";
    } catch {
      this.error = "Seznam nelze načíst. Ověřte připojení a verzi API.";
    } finally {
      this.loading = false;
      this.render();
      if (entry !== this.config.entry_id) this.load();
    }
  }
  change() {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this.config },
        bubbles: true,
        composed: true,
      }),
    );
    this.render();
  }
  render() {
    if (!this.config) return;
    const routes =
      this.routeEntry === this.config.entry_id ? this.routes || [] : [];
    this.shadowRoot.innerHTML = `<style>:host{display:block}*{box-sizing:border-box}label{min-width:0;display:block;margin:12px 0;font-size:14px}select,input{display:block;width:100%;padding:10px;margin-top:6px;font:inherit;background:var(--card-background-color,white);color:var(--primary-text-color);border:1px solid var(--divider-color,#bbb);border-radius:8px}.row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto;gap:8px;align-items:end;margin:10px 0}button{padding:10px;cursor:pointer}p{font-size:13px}</style><label>Zdroj dat<select id="source"><option value="">Vyberte připojení</option>${(this.sources || []).map((s) => `<option value="${esc(s.id)}" ${s.id === this.config.entry_id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select></label><label>Nadpis<input id="title" value="${esc(this.config.title || "Mapa vehyklů")}"></label><p>Vyberte linky a jejich směry. Zkrácené spoje jsou zahrnuty podle směru GTFS.</p>${this.config.selections
      .map((s, i) => {
        const route = routes.find((r) => r.id === s.route_id);
        return `<div class="row"><label>Linka<select data-route="${i}"><option value="">Vyberte linku</option>${routes.map((r) => `<option value="${esc(r.id)}" ${r.id === s.route_id ? "selected" : ""}>${esc(r.line)} · ${esc(r.name)}</option>`).join("")}</select></label><label>Směr<select data-direction="${i}"><option value="*">Oba směry</option>${(route?.directions || []).map((d) => `<option value="${esc(d.id)}" ${s.direction === d.id ? "selected" : ""}>${esc(d.label || "Neuvedený směr")}</option>`).join("")}</select></label><button data-remove="${i}" aria-label="Odebrat linku">×</button></div>`;
      })
      .join(
        "",
      )}<button id="add" ${!routes.length || this.config.selections.length >= 20 ? "disabled" : ""}>Přidat linku</button><p role="status">${esc(this.error || "")}</p>`;
    this.shadowRoot.querySelector("#source").onchange = (e) => {
      this.config = {
        ...this.config,
        entry_id: e.target.value,
        selections: [],
      };
      this.change();
      this.load();
    };
    this.shadowRoot.querySelector("#title").onchange = (e) => {
      this.config = { ...this.config, title: e.target.value };
      this.change();
    };
    this.shadowRoot.querySelector("#add").onclick = () => {
      this.config = {
        ...this.config,
        selections: [
          ...this.config.selections,
          { route_id: routes[0].id, direction: "*" },
        ],
      };
      this.change();
    };
    for (const input of this.shadowRoot.querySelectorAll(
      "[data-route],[data-direction]",
    ))
      input.onchange = (e) => {
        const index = Number(input.dataset.route ?? input.dataset.direction);
        this.config = {
          ...this.config,
          selections: this.config.selections.map((s, i) =>
            i === index
              ? input.dataset.route != null
                ? { route_id: e.target.value, direction: "*" }
                : { ...s, direction: e.target.value }
              : s,
          ),
        };
        this.change();
      };
    for (const button of this.shadowRoot.querySelectorAll("[data-remove]"))
      button.onclick = () => {
        this.config = {
          ...this.config,
          selections: this.config.selections.filter(
            (_, i) => i !== Number(button.dataset.remove),
          ),
        };
        this.change();
      };
  }
}
if (!customElements.get(TYPE)) customElements.define(TYPE, MapCard);
if (!customElements.get(`${TYPE}-editor`))
  customElements.define(`${TYPE}-editor`, MapEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === TYPE))
  window.customCards.push({
    type: TYPE,
    name: "IDS JMK — Mapa vehyklů",
    description: "Vozidla vybraných linek a směrů bez dalších entit.",
    preview: true,
  });
