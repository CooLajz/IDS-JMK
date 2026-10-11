/* IDS JMK dashboard card. No external dependencies or direct API requests. */
const TYPE = "ids-jmk-departures-card";
const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const time = (value) => {
  const date = new Date(value);
  return value && Number.isFinite(date.getTime())
    ? date.toLocaleTimeString("cs-CZ", { timeZone: "Europe/Prague", hour: "2-digit", minute: "2-digit" })
    : "—";
};
const icon = (name, title) => `<ha-icon icon="mdi:${name}" title="${escape(title)}" aria-label="${escape(title)}"></ha-icon>`;

// Effective departure already includes the delay. Never add it a second time.
export function departureView(row, now = Date.now()) {
  const effective = row.departure_time || row.estimated_departure || row.scheduled_departure;
  const timestamp = Date.parse(effective);
  const minutes = Number.isFinite(timestamp) ? Math.ceil((timestamp - now) / 60000) : null;
  const delay = Number.isFinite(row.delay_seconds) ? Math.round(row.delay_seconds / 60) : 0;
  return {
    scheduled: time(row.scheduled_departure),
    delay: delay ? `${delay > 0 ? "+" : ""}${delay} min` : "",
    countdown: row.cancelled ? "Zrušeno" : minutes === null ? "—" : minutes < 0 ? "Odjel" : minutes === 0 ? "Nyní" : String(minutes),
    unit: !row.cancelled && minutes > 0 ? "min" : "",
    departed: !row.cancelled && minutes !== null && minutes < 0,
  };
}

const styles = `
  :host { display:block; color:var(--primary-text-color, #202c24); }
  * { box-sizing:border-box; }
  ha-card { display:block; overflow:hidden; background:var(--ha-card-background, var(--card-background-color, white)); border-radius:var(--ha-card-border-radius, 16px); }
  header { display:flex; align-items:center; gap:12px; padding:20px 20px 16px; }
  .badge { display:grid; place-items:center; width:42px; height:42px; flex-shrink:0; border-radius:13px; color:var(--primary-color, #447b32); background:color-mix(in srgb, var(--primary-color, #447b32) 13%, transparent); }
  ha-icon { display:inline-block; width:18px; height:18px; --mdc-icon-size:18px; vertical-align:middle; }
  .badge ha-icon { width:25px; height:25px; --mdc-icon-size:25px; }
  .heading { min-width:0; }
  h2 { margin:0; font-size:20px; line-height:1.3; font-weight:650; overflow-wrap:anywhere; }
  .eyebrow { font-size:10px; letter-spacing:1.7px; font-weight:700; color:var(--secondary-text-color, #657267); margin-bottom:4px; }
  .labels, .row { display:grid; grid-template-columns:48px minmax(0, 1fr) 64px 49px; gap:10px; align-items:center; }
  .labels { padding:0 20px 9px; font-size:10px; text-transform:uppercase; letter-spacing:.7px; color:var(--secondary-text-color, #657267); }
  .labels span:nth-child(n+3) { text-align:right; }
  .rows { list-style:none; padding:0; margin:0; }
  .row { padding:14px 20px; border-top:1px solid var(--divider-color, #e6eae6); }
  .row.first { background:color-mix(in srgb, var(--primary-color, #447b32) 6%, transparent); }
  .line { padding:7px 3px; text-align:center; border-radius:9px; font-weight:800; font-size:17px; background:color-mix(in srgb, var(--primary-color, #447b32) 13%, transparent); color:var(--primary-text-color, #202c24); overflow-wrap:anywhere; }
  .destination { font-size:14px; font-weight:600; line-height:1.35; overflow-wrap:anywhere; }
  .meta { display:flex; flex-wrap:wrap; align-items:center; gap:7px; margin-top:5px; color:var(--secondary-text-color, #657267); font-size:11px; }
  .scheduled { text-align:right; font-size:15px; font-weight:650; font-variant-numeric:tabular-nums; }
  .delay { display:block; margin-top:4px; font-size:11px; color:var(--warning-color, #986200); white-space:nowrap; }
  .countdown { text-align:right; font-size:25px; line-height:1; font-weight:750; font-variant-numeric:tabular-nums; }
  .countdown.word { font-size:12px; line-height:1.3; overflow-wrap:anywhere; }
  .unit { display:block; font-size:10px; color:var(--secondary-text-color, #657267); margin-top:5px; font-weight:400; }
  .departed { opacity:.55; }
  .cancelled .destination, .cancelled .scheduled > span:first-child { text-decoration:line-through; }
  footer { display:flex; align-items:center; flex-wrap:wrap; gap:6px 12px; justify-content:space-between; padding:12px 20px; border-top:1px solid var(--divider-color, #e6eae6); font-size:10px; color:var(--secondary-text-color, #657267); }
  .status { display:flex; align-items:center; gap:6px; }
  .dot { height:6px; width:6px; border-radius:50%; background:var(--success-color, #4b944d); }
  .warning .dot { background:var(--warning-color, #986200); }
  .message { padding:20px; line-height:1.5; font-size:14px; }
  @media (max-width:380px) {
    header { padding:16px 12px; } .labels { padding:0 12px 9px; }
    .row { padding:13px 12px; } .labels, .row { grid-template-columns:40px minmax(0,1fr) 56px 42px; gap:8px; }
    footer { padding:12px; } h2 { font-size:18px; } .countdown { font-size:23px; }
  }
`;

class IDSJMKDeparturesCard extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: "open" }); }
  setConfig(config) {
    if (!config.entity || typeof config.entity !== "string") throw new Error("Vyberte senzor odjezdové tabule IDS JMK.");
    if (config.limit !== undefined && (!Number.isInteger(config.limit) || config.limit < 1 || config.limit > 50)) {
      throw new Error("Počet odjezdů musí být celé číslo od 1 do 50.");
    }
    this.config = { limit: 10, show_platform: true, show_accessibility: true, ...config };
    this.render();
  }
  set hass(hass) { this.states = hass.states; this.render(); }
  connectedCallback() {
    // New HA frontends use context; the hass setter also supports older versions.
    const request = new CustomEvent("context-request", { bubbles: true, composed: true });
    request.context = "states";
    request.subscribe = true;
    request.callback = (states, unsubscribe) => { this.unsubscribe = unsubscribe; this.states = states; this.render(); };
    this.dispatchEvent(request);
    clearInterval(this.timer);
    this.timer = setInterval(() => this.render(), 15000);
    this.render();
  }
  disconnectedCallback() { clearInterval(this.timer); this.unsubscribe?.(); this.unsubscribe = undefined; }
  getCardSize() { return 2 + Math.min(this.config?.limit ?? 10, 10) * 1.5; }
  getGridOptions() { return { columns: 12, min_columns: 12 }; }
  static getConfigElement() { return document.createElement(`${TYPE}-editor`); }
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find((id) => id.startsWith("sensor.") &&
      Array.isArray(hass.states[id].attributes.departures) && hass.states[id].attributes.stop_id);
    return { entity: entity || "", limit: 10 };
  }
  render() {
    if (!this.config || !this.shadowRoot) return;
    const state = this.states?.[this.config.entity];
    const attributes = state?.attributes ?? {};
    const title = this.config.title || attributes.stop_name || "Odjezdová tabule";
    const rows = Array.isArray(attributes.departures) ? attributes.departures.slice(0, this.config.limit) : [];
    const age = Date.now() - Date.parse(attributes.generated_at);
    const old = !Number.isFinite(age) || age > 120000;
    const unavailable = !state || state.state === "unavailable";
    const invalid = state && !Array.isArray(attributes.departures);
    const stale = old || attributes.realtime_stale !== false;
    let body;
    if (unavailable || invalid) {
      body = `<div class="message" role="status">${!state ? "Vyberte dostupný senzor IDS JMK v nastavení karty." : invalid ? "Vybraný senzor neobsahuje odjezdovou tabuli." : "Data nejsou dostupná. Zkontrolujte připojení integrace k serveru."}</div>`;
    } else if (!rows.length) {
      body = '<div class="message" role="status">Pro zvolené filtry nejsou dostupné žádné odjezdy.</div>';
    } else {
      body = `<div class="labels" aria-hidden="true"><span>Linka</span><span>Směr</span><span>Odjezd</span><span>Za</span></div><ol class="rows">${rows.map((row, index) => {
        const view = departureView(row);
        const amenities = this.config.show_accessibility ?
          `${row.wheelchair_accessible === true ? icon("wheelchair-accessibility", "Podle jízdního řádu: přístupné vozíčkářům") : ""}${row.bikes_allowed === true ? icon("bicycle", "Podle jízdního řádu: přeprava kol") : ""}` : "";
        return `<li class="row ${index === 0 ? "first" : ""} ${view.departed ? "departed" : ""} ${row.cancelled ? "cancelled" : ""}">
          <span class="line" aria-label="Linka ${escape(row.line)}">${escape(row.line)}</span>
          <div><div class="destination">${escape(row.destination)}</div><div class="meta">${this.config.show_platform && row.platform ? `<span>Stan. ${escape(row.platform)}</span>` : ""}${amenities}</div></div>
          <div class="scheduled"><span title="Odjezd podle jízdního řádu">${escape(view.scheduled)}</span>${view.delay && !row.cancelled ? `<span class="delay" title="Odhadované zpoždění">${escape(view.delay)}</span>` : ""}</div>
          <div class="countdown ${view.unit ? "" : "word"}" title="${row.cancelled ? "Spoj je zrušen" : "Čas do odjezdu včetně dostupného odhadu zpoždění"}">${escape(view.countdown)}${view.unit ? `<span class="unit">${view.unit}</span>` : ""}</div>
        </li>`;
      }).join("")}</ol>`;
    }
    const markup = `<style>${styles}</style><ha-card>
      <header><div class="badge">${icon("bus-clock", "Odjezdy IDS JMK")}</div><div class="heading"><div class="eyebrow">IDS JMK · ODJEZDY</div><h2>${escape(title)}</h2></div></header>
      ${body}
      <footer><span class="status ${stale || unavailable ? "warning" : ""}"><span class="dot"></span>${unavailable ? "Bez spojení" : old ? "Data nejsou aktuální" : stale ? "Realtime není aktuální" : "Data aktualizována"}</span><span>Aktualizace ${escape(time(attributes.generated_at))}</span></footer>
    </ha-card>`;
    if (markup !== this._markup) {
      this.shadowRoot.innerHTML = markup;
      this._markup = markup;
    }
  }
}

class IDSJMKDeparturesEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: "open" }); }
  setConfig(config) { this.config = { limit: 10, show_platform: true, show_accessibility: true, ...config }; this.render(); }
  set hass(hass) { this._hass = hass; this.render(); }
  connectedCallback() { this.render(); }
  render() {
    if (!this.config || !this._hass) return;
    if (!this.form) {
      this.form = document.createElement("ha-form");
      this.form.schema = [
        { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "ids_jmk" } } },
        { name: "title", selector: { text: {} } },
        { name: "limit", selector: { number: { min: 1, max: 50, mode: "box" } } },
        { name: "show_platform", selector: { boolean: {} } },
        { name: "show_accessibility", selector: { boolean: {} } },
      ];
      const labels = { entity: "Senzor odjezdové tabule", title: "Vlastní nadpis (volitelné)", limit: "Počet zobrazených odjezdů", show_platform: "Zobrazit stanoviště", show_accessibility: "Zobrazit vybavení podle jízdního řádu" };
      this.form.computeLabel = (schema) => labels[schema.name];
      this.form.addEventListener("value-changed", (event) => {
        event.stopPropagation();
        this.config = { ...this.config, ...event.detail.value };
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this.config }, bubbles: true, composed: true }));
      });
      const help = document.createElement("p");
      help.textContent = "Vyberte senzor vytvořený integrací IDS JMK. Zastávku, linku a směr nastavíte v průvodci integrace. Karta zobrazí nejvýše tolik odjezdů, kolik poskytuje senzor.";
      help.style.cssText = "color:var(--secondary-text-color);font-size:14px;line-height:1.5";
      this.shadowRoot.append(this.form, help);
    }
    this.form.hass = this._hass;
    this.form.data = this.config;
  }
}

if (!customElements.get(TYPE)) customElements.define(TYPE, IDSJMKDeparturesCard);
if (!customElements.get(`${TYPE}-editor`)) customElements.define(`${TYPE}-editor`, IDSJMKDeparturesEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === TYPE)) window.customCards.push({
  type: TYPE,
  name: "IDS JMK — Odjezdová tabule",
  description: "Odjezdy, odpočet, zpoždění a stanoviště ze senzoru IDS JMK.",
  preview: true,
  documentationURL: "https://github.com/CooLajz/IDS-JMK/blob/main/docs/home-assistant.md",
});
