/* IDS JMK dashboard card. No external dependencies or direct API requests. */
const TYPE = "ids-jmk-departures-card";
const DEFAULTS = { limit: 10, layout: "modern", highlight_minutes: 5, show_platform: true, show_accessibility: true };
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
    countdown: row.cancelled ? "Zrušeno" : minutes === null ? "—" : timestamp < now ? "Odjel" : minutes === 0 ? "Nyní" : String(minutes),
    unit: !row.cancelled && minutes > 0 ? "min" : "",
    departed: !row.cancelled && Number.isFinite(timestamp) && timestamp < now,
  };
}

export function isUpcoming(row, threshold, now = Date.now()) {
  const departure = Date.parse(row.departure_time || row.estimated_departure || row.scheduled_departure);
  return threshold > 0 && !row.cancelled && Number.isFinite(departure) &&
    departure >= now && departure - now <= threshold * 60000;
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
  .labels, .row { display:grid; grid-template-columns:44px minmax(0, 1fr) 58px 52px; column-gap:10px; align-items:center; }
  .labels { padding:0 16px 9px; font-size:10px; text-transform:uppercase; letter-spacing:.5px; color:var(--secondary-text-color, #657267); }
  .labels span:nth-child(n+3) { text-align:center; }
  .rows { list-style:none; padding:0; margin:0; }
  .row { grid-template-rows:32px minmax(16px, auto); padding:10px 16px; border-top:1px solid var(--divider-color, #e6eae6); }
  .row.first { background:color-mix(in srgb, var(--primary-color, #447b32) 5%, transparent); }
  .line { grid-column:1; grid-row:1; padding:5px 2px; text-align:center; border-radius:8px; font-weight:800; font-size:16px; line-height:22px; background:color-mix(in srgb, var(--primary-color, #447b32) 13%, transparent); color:var(--primary-text-color, #202c24); overflow:hidden; }
  .destination { grid-column:2; grid-row:1; display:flex; gap:5px; align-items:center; min-width:0; font-size:14px; font-weight:600; line-height:20px; }
  .destination-text { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
  .amenities { display:flex; flex-shrink:0; gap:3px; color:var(--secondary-text-color, #657267); }
  .amenities ha-icon { width:15px; height:15px; --mdc-icon-size:15px; }
  .destination-block { display:contents; }
  .modern .destination-block { display:block; grid-column:2; grid-row:1 / 3; align-self:start; padding-top:6px; min-width:0; }
  .modern .destination { display:flex; align-items:flex-start; }
  .modern .destination-text { white-space:normal; overflow-wrap:anywhere; }
  .modern .amenities { padding-top:2px; }
  .modern .meta { display:block; padding-top:2px; }
  .meta { grid-column:2; grid-row:2; color:var(--secondary-text-color, #657267); font-size:11px; line-height:16px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .scheduled { grid-column:3; grid-row:1; text-align:center; font-size:15px; line-height:20px; font-weight:650; font-variant-numeric:tabular-nums; }
  .delay { grid-column:3; grid-row:2; text-align:center; font-size:11px; line-height:16px; color:var(--warning-color, #986200); white-space:nowrap; }
  .countdown { grid-column:4; grid-row:1; display:grid; place-items:center; height:32px; border-radius:8px; font-size:25px; line-height:1; font-weight:750; font-variant-numeric:tabular-nums; }
  .countdown.word { font-size:11px; }
  .countdown.upcoming { background:#d9f6df; color:#155d2b; }
  .unit { grid-column:4; grid-row:2; text-align:center; font-size:10px; line-height:16px; color:var(--secondary-text-color, #657267); }
  .departed { opacity:.55; }
  .cancelled .destination-text, .cancelled .scheduled { text-decoration:line-through; }
  footer { display:flex; align-items:center; flex-wrap:wrap; gap:6px 12px; justify-content:space-between; padding:12px 20px; border-top:1px solid var(--divider-color, #e6eae6); font-size:10px; color:var(--secondary-text-color, #657267); }
  .status { display:flex; align-items:center; gap:6px; }
  .dot { height:6px; width:6px; border-radius:50%; background:var(--success-color, #4b944d); }
  .warning .dot { background:var(--warning-color, #986200); }
  .message { padding:20px; line-height:1.5; font-size:14px; }
  .compact header { padding:10px 12px; gap:8px; }
  .compact .badge { width:28px; height:28px; border-radius:8px; }
  .compact .badge ha-icon { width:19px; height:19px; --mdc-icon-size:19px; }
  .compact h2 { font-size:16px; }
  .compact .eyebrow { display:none; }
  .compact .labels, .compact .row { grid-template-columns:34px minmax(0,1fr) 54px 46px; column-gap:8px; }
  .compact .labels { padding:0 12px 5px; font-size:9px; }
  .compact .row { grid-template-rows:24px auto; padding:5px 12px; }
  .compact .line { padding:2px; border-radius:5px; font-size:14px; line-height:20px; }
  .compact .destination { font-size:13px; }
  .compact .scheduled { font-size:14px; }
  .compact .countdown { font-size:20px; height:24px; border-radius:5px; }
  .compact .countdown.word { font-size:10px; }
  .compact .unit { display:none; }
  .compact .meta, .compact .delay { font-size:10px; line-height:13px; }
  .compact footer { padding:6px 12px; font-size:9px; }
  @media (max-width:380px) {
    header { padding:16px 12px; } .labels { padding:0 12px 9px; }
    .row { padding:10px 12px; } .labels, .row { grid-template-columns:36px minmax(0,1fr) 54px 46px; column-gap:7px; }
    footer { padding:10px 12px; } h2 { font-size:18px; } .countdown { font-size:23px; }
  }
`;

class IDSJMKDeparturesCard extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: "open" }); }
  setConfig(config) {
    if (!config.entity || typeof config.entity !== "string") throw new Error("Vyberte senzor odjezdové tabule IDS JMK.");
    if (config.limit !== undefined && (!Number.isInteger(config.limit) || config.limit < 1 || config.limit > 50)) {
      throw new Error("Počet odjezdů musí být celé číslo od 1 do 50.");
    }
    if (config.layout !== undefined && !["modern", "compact"].includes(config.layout)) {
      throw new Error("Vyberte vzhled Moderní nebo Kompaktní.");
    }
    if (config.highlight_minutes !== undefined && (!Number.isInteger(config.highlight_minutes) || config.highlight_minutes < 0 || config.highlight_minutes > 60)) {
      throw new Error("Hranice zvýraznění musí být celé číslo od 0 do 60 minut.");
    }
    this.config = { ...DEFAULTS, ...config };
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
  getCardSize() { return 2 + (this.config?.limit ?? 10) * (this.config?.layout === "compact" ? 0.8 : 1.4); }
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
      body = `<div class="labels" aria-hidden="true"><span>Linka</span><span>Směr</span><span>Odjezd</span><span>${this.config.layout === "compact" ? "Za (min)" : "Za"}</span></div><ol class="rows">${rows.map((row, index) => {
        const view = departureView(row);
        const amenities = this.config.show_accessibility ?
          `${row.wheelchair_accessible === true ? icon("wheelchair-accessibility", "Podle jízdního řádu: přístupné vozíčkářům") : ""}${row.bikes_allowed === true ? icon("bicycle", "Podle jízdního řádu: přeprava kol") : ""}` : "";
        const upcoming = !stale && isUpcoming(row, this.config.highlight_minutes);
        return `<li class="row ${index === 0 ? "first" : ""} ${view.departed ? "departed" : ""} ${row.cancelled ? "cancelled" : ""}">
          <span class="line" aria-label="Linka ${escape(row.line)}">${escape(row.line)}</span>
          <div class="destination-block"><div class="destination"><span class="destination-text" title="${escape(row.destination)}">${escape(row.destination)}</span>${amenities ? `<span class="amenities">${amenities}</span>` : ""}</div>${this.config.show_platform && row.platform ? `<span class="meta" title="Stanoviště ${escape(row.platform)}">Stan. ${escape(row.platform)}</span>` : ""}</div>
          <span class="scheduled" title="Odjezd podle jízdního řádu">${escape(view.scheduled)}</span>
          <span class="countdown ${view.unit ? "" : "word"} ${upcoming ? "upcoming" : ""}" title="${row.cancelled ? "Spoj je zrušen" : upcoming ? "Blížící se odjezd včetně dostupného odhadu zpoždění" : "Čas do odjezdu včetně dostupného odhadu zpoždění"}">${escape(view.countdown)}</span>
          ${view.delay && !row.cancelled ? `<span class="delay" title="Odhadované zpoždění">${escape(view.delay)}</span>` : ""}
          ${view.unit ? `<span class="unit">${view.unit}</span>` : ""}
        </li>`;
      }).join("")}</ol>`;
    }
    const markup = `<style>${styles}</style><ha-card class="${this.config.layout}">
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
  setConfig(config) { this.config = { ...DEFAULTS, ...config }; this.render(); }
  set hass(hass) { this._hass = hass; this.render(); }
  connectedCallback() { this.render(); }
  render() {
    if (!this.config || !this._hass) return;
    if (!this.form) {
      this.form = document.createElement("ha-form");
      this.form.schema = [
        { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "ids_jmk" } } },
        { name: "title", selector: { text: {} } },
        { name: "layout", required: true, selector: { select: { mode: "dropdown", options: [{ value: "modern", label: "Moderní" }, { value: "compact", label: "Kompaktní" }] } } },
        { name: "highlight_minutes", required: true, selector: { number: { min: 0, max: 60, mode: "box", unit_of_measurement: "min" } } },
        { name: "limit", required: true, selector: { number: { min: 1, max: 50, mode: "box" } } },
        { name: "show_platform", selector: { boolean: {} } },
        { name: "show_accessibility", selector: { boolean: {} } },
      ];
      const labels = { entity: "Senzor odjezdové tabule", title: "Vlastní nadpis (volitelné)", layout: "Vzhled karty", highlight_minutes: "Zvýraznit odjezd do (0 = vypnuto)", limit: "Počet zobrazených odjezdů", show_platform: "Zobrazit stanoviště", show_accessibility: "Zobrazit ikonky vybavení podle jízdního řádu" };
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
