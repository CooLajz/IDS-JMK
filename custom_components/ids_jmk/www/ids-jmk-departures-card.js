/* IDS JMK dashboard card. No external dependencies or direct API requests. */
const TYPE = "ids-jmk-departures-card";
const DEFAULTS = { show_header: true, show_footer: true, limit: 10, layout: "modern", highlight_minutes: 5, show_platform: true, show_accessibility: true, show_transport_icon: true, show_line_number: true, show_departure_day: true };
const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const time = (value) => {
  const date = new Date(value);
  return value && Number.isFinite(date.getTime())
    ? date.toLocaleTimeString("cs-CZ", { timeZone: "Europe/Prague", hour: "2-digit", minute: "2-digit" })
    : "—";
};
const icon = (name, title) => `<ha-icon icon="mdi:${name}" title="${escape(title)}" aria-label="${escape(title)}"></ha-icon>`;

// Original Material Design Icons by Pictogrammers, rendered by Home Assistant.
const TRANSPORT_ICONS = {
  tram: ["tram", "Šalina"], bus: ["bus", "Autobus"], rail: ["train", "Vlak"],
  trolleybus: ["bus-electric", "Trolejbus"], subway: ["subway-variant", "Metro"],
  ferry: ["ferry", "Lodní doprava"], aerial_lift: ["gondola", "Visutá lanovka"],
  cable_tram: ["tram", "Dráha tažená lanem"], funicular: ["train", "Pozemní lanovka"],
  monorail: ["train", "Jednokolejnicová dráha"],
};
export function transportIcon(mode) {
  return Object.hasOwn(TRANSPORT_ICONS, mode) ? TRANSPORT_ICONS[mode] : null;
}

const calendarDate = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Prague", year: "numeric", month: "numeric", day: "numeric",
});
export function departureDay(value, now = Date.now()) {
  const departure = new Date(value);
  if (!value || !Number.isFinite(departure.getTime()) || !Number.isFinite(new Date(now).getTime())) return "";
  const parts = (date) => Object.fromEntries(calendarDate.formatToParts(date)
    .filter((p) => p.type !== "literal").map((p) => [p.type, Number(p.value)]));
  const day = parts(departure), today = parts(new Date(now));
  // Calendar days, not elapsed 24-hour periods: DST days have 23 or 25 hours.
  const ordinal = (p) => Date.UTC(p.year, p.month - 1, p.day) / 86400000;
  const difference = ordinal(day) - ordinal(today);
  return difference === 0 ? "" : difference === 1 ? "zítra" : `${day.day}.${day.month}.`;
}

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
  :host { display:block; container-type:inline-size; color:var(--primary-text-color, #202c24); }
  * { box-sizing:border-box; }
  ha-card { display:block; overflow:hidden; background:var(--ha-card-background, var(--card-background-color, white)); border-radius:var(--ha-card-border-radius, 16px); }
  header { display:flex; align-items:center; gap:12px; padding:20px 20px 16px; }
  .badge { display:grid; place-items:center; width:42px; height:42px; flex-shrink:0; border-radius:13px; color:var(--primary-color, #447b32); background:color-mix(in srgb, var(--primary-color, #447b32) 13%, transparent); }
  ha-icon { display:inline-block; width:18px; height:18px; --mdc-icon-size:18px; vertical-align:middle; }
  .badge ha-icon { width:25px; height:25px; --mdc-icon-size:25px; }
  .heading { min-width:0; }
  h2 { margin:0; font-size:20px; line-height:1.3; font-weight:650; overflow-wrap:anywhere; }
  .eyebrow { font-size:10px; letter-spacing:1.7px; font-weight:700; color:var(--secondary-text-color, #657267); margin-bottom:4px; }
  .labels, .row { display:grid; grid-template-columns:var(--line-column,) minmax(0, 1fr) var(--day-column,) 46px var(--delay-column,) 48px; column-gap:8px; align-items:center; }
  .labels { padding:0 16px 9px; font-size:9px; text-transform:uppercase; letter-spacing:.2px; color:var(--secondary-text-color, #657267); }
  .labels span { white-space:nowrap; }
  .labels span:nth-child(n+3) { text-align:center; }
  .labels span:last-child { text-align:right; }
  .no-header .labels { padding-top:12px; }
  .compact.no-header .labels { padding-top:6px; }
  .rows { list-style:none; padding:0; margin:0; }
  .row { min-height:68px; padding:12px 16px; border-top:1px solid var(--divider-color, #e6eae6); }
  .row.first { background:color-mix(in srgb, var(--primary-color, #447b32) 5%, transparent); }
  .with-day { --day-column:42px; }
  .with-line { --line-column:var(--line-width, 40px); }
  .compact .with-line { --line-column:var(--line-width, 30px); }
  .icon-only { --line-width:28px; }
  .with-delay { --delay-column:var(--delay-width, 44px); }
  .day { display:none; }
  .with-day .day { display:block; text-align:right; white-space:nowrap; font-size:11px; color:var(--secondary-text-color, #657267); font-variant-numeric:tabular-nums; }
  .with-day.labels .day { font-size:inherit; text-align:right; }
  .with-transport { --line-width:68px; }
  .compact .with-transport { --line-width:60px; }
  .line ha-icon { display:flex; width:20px; height:20px; --mdc-icon-size:20px; flex-shrink:0; }
  .compact .line ha-icon { width:18px; height:18px; --mdc-icon-size:18px; }
  .line { display:flex; align-items:center; justify-content:center; gap:4px; height:32px; padding:0 2px; border-radius:8px; font-weight:800; font-size:16px; line-height:20px; background:color-mix(in srgb, var(--primary-color, #447b32) 13%, transparent); color:var(--primary-text-color, #202c24); overflow:hidden; }
  .destination-block { display:flex; align-items:center; gap:5px; min-width:0; }
  .destination-text { min-width:0; overflow-wrap:anywhere; font-size:14px; font-weight:600; line-height:20px; }
  .amenities { display:inline-flex; align-items:center; flex-shrink:0; gap:3px; height:20px; color:var(--secondary-text-color, #657267); }
  .amenities ha-icon { display:flex; align-items:center; justify-content:center; width:16px; height:16px; line-height:0; --mdc-icon-size:16px; }
  .meta { flex-shrink:0; max-width:40px; padding:1px 3px; border-radius:4px; background:color-mix(in srgb, var(--secondary-text-color, #657267) 10%, transparent); color:var(--secondary-text-color, #657267); font-size:10px; line-height:18px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .modern .destination-block { display:block; line-height:20px; }
  .modern .amenities, .modern .meta { margin-left:5px; vertical-align:middle; }
  .modern .meta { display:inline-block; }
  .scheduled { text-align:center; font-size:15px; line-height:24px; font-weight:650; font-variant-numeric:tabular-nums; white-space:nowrap; }
  .delay { text-align:center; font-size:12px; line-height:24px; color:var(--warning-color, #986200); white-space:nowrap; }
  .countdown { display:grid; align-items:center; justify-items:end; text-align:right; height:34px; font-size:25px; line-height:1; font-weight:750; font-variant-numeric:tabular-nums; }
  .countdown.long-number { font-size:20px; }
  .countdown.word { font-size:10px; }
  .countdown.upcoming { color:var(--success-color, #4b944d); }
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
  .compact .labels, .compact .row { grid-template-columns:var(--line-column,) minmax(0,1fr) var(--day-column,) 42px var(--delay-column,) 42px; --delay-width:38px; column-gap:6px; }
  .compact .labels { padding:0 10px 5px; font-size:8px; }
  .compact .row { height:36px; min-height:36px; padding:5px 10px; grid-template-rows:25px; }
  .compact .line { border-radius:5px; font-size:14px; height:24px; }
  .compact .destination-block { gap:4px; height:24px; overflow:hidden; }
  .compact .destination-text { font-size:13px; line-height:20px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .compact .meta { font-size:9px; padding:0 2px; max-width:32px; }
  .compact .scheduled { font-size:13px; }
  .compact .delay { font-size:11px; }
  .compact .countdown { font-size:20px; height:24px; }
  .compact .countdown.long-number { font-size:16px; }
  .compact .countdown.word { font-size:9px; }
  .compact footer { padding:6px 10px; font-size:9px; }
  @media (max-width:380px) {
    header { padding:16px 10px; } .labels { padding:0 10px 9px; }
    .row { padding:12px 10px; } .labels, .row { grid-template-columns:var(--line-column,) minmax(0,1fr) var(--day-column,) 42px var(--delay-column,) 42px; --delay-width:38px; column-gap:6px; }
    footer { padding:10px; } h2 { font-size:18px; } .countdown { font-size:23px; }
  }
  @container (max-width:420px) {
    .modern .with-line { --line-column:var(--line-width, 30px); }
    .modern .with-transport { --line-width:56px; }
    .modern .with-day { --day-column:36px; }
    .modern .labels, .modern .row { grid-template-columns:var(--line-column,) minmax(0,1fr) var(--day-column,) 40px var(--delay-column,) 38px; --delay-width:38px; column-gap:4px; padding-left:10px; padding-right:10px; }
    .modern .labels { font-size:8px; }
    .modern .line { font-size:14px; gap:3px; }
    .modern .line ha-icon { width:18px; height:18px; --mdc-icon-size:18px; }
    .modern .day { font-size:10px; }
    .modern .scheduled { font-size:13px; }
    .modern .delay { font-size:11px; }
    .modern .countdown { font-size:22px; }
    .modern .countdown.long-number { font-size:17px; }
    .modern .countdown.word { font-size:9px; }
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
  getCardSize() { return (this.config?.show_header === false ? 0 : 1.3) + (this.config?.show_footer === false ? 0 : 0.7) + (this.config?.limit ?? 10) * (this.config?.layout === "compact" ? 0.8 : 1.4); }
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
    const now = Date.now();
    const showLineNumber = this.config.show_line_number;
    const hasTransport = this.config.show_transport_icon && rows.some(row => transportIcon(row.transport_mode));
    const showLine = showLineNumber || hasTransport;
    const lineColumn = showLine ? `with-line ${hasTransport ? (showLineNumber ? "with-transport" : "icon-only") : ""}` : "";
    const views = rows.map((row) => departureView(row, now));
    const days = rows.map((row) => departureDay(row.scheduled_departure, now));
    const dayColumn = this.config.show_departure_day && days.some(Boolean) ? "with-day" : "";
    const age = now - Date.parse(attributes.generated_at);
    const old = !Number.isFinite(age) || age > 120000;
    const unavailable = !state || state.state === "unavailable";
    const invalid = state && !Array.isArray(attributes.departures);
    const realtimeEnabled = attributes.realtime_enabled !== false;
    const showDelay = realtimeEnabled && rows.some((row, index) => !row.cancelled && views[index].delay);
    const delayColumn = showDelay ? "with-delay" : "";
    const stale = old || (realtimeEnabled && attributes.realtime_stale !== false);
    let body;
    if (unavailable || invalid) {
      body = `<div class="message" role="status">${!state ? "Vyberte dostupný senzor IDS JMK v nastavení karty." : invalid ? "Vybraný senzor neobsahuje odjezdovou tabuli." : "Data nejsou dostupná. Zkontrolujte připojení integrace k serveru."}</div>`;
    } else if (!rows.length) {
      body = '<div class="message" role="status">Pro zvolené filtry nejsou dostupné žádné odjezdy.</div>';
    } else {
      body = `<div class="labels ${dayColumn} ${delayColumn} ${lineColumn}" aria-hidden="true">${showLine ? `<span>${showLineNumber ? "Linka" : "Druh"}</span>` : ""}<span>Směr</span><span class="day">Den</span><span>Odjezd</span>${showDelay ? '<span title="Odhadované zpoždění v minutách">Zpož. min</span>' : ""}<span>Za (min)</span></div><ol class="rows">${rows.map((row, index) => {
        const view = views[index];
        const transport = this.config.show_transport_icon ? transportIcon(row.transport_mode) : null;
        const amenities = this.config.show_accessibility ?
          `${row.wheelchair_accessible === true ? icon("wheelchair-accessibility", "Podle jízdního řádu: přístupné vozíčkářům") : ""}${row.bikes_allowed === true ? icon("bicycle", "Podle jízdního řádu: přeprava kol") : ""}` : "";
        const upcoming = !stale && isUpcoming(row, this.config.highlight_minutes, now);
        return `<li class="row ${dayColumn} ${delayColumn} ${lineColumn} ${index === 0 ? "first" : ""} ${view.departed ? "departed" : ""} ${row.cancelled ? "cancelled" : ""}">
          ${showLine ? `<span class="line" ${showLineNumber ? `aria-label="Linka ${escape(row.line)}"` : !transport ? 'aria-hidden="true"' : ""}>${transport ? icon(...transport) : ""}${showLineNumber ? `<span>${escape(row.line)}</span>` : ""}</span>` : ""}
          <div class="destination-block"><span class="destination-text" title="${escape(row.destination)}">${escape(row.destination)}</span>${amenities ? `<span class="amenities">${amenities}</span>` : ""}${this.config.show_platform && row.platform ? `<span class="meta" title="Stanoviště ${escape(row.platform)}" aria-label="Stanoviště ${escape(row.platform)}">${escape(row.platform)}</span>` : ""}</div>
          <span class="day" title="${days[index] ? escape(new Date(row.scheduled_departure).toLocaleDateString("cs-CZ", { timeZone: "Europe/Prague", day: "numeric", month: "numeric", year: "numeric" })) : ""}">${escape(days[index])}</span>
          <span class="scheduled" title="Odjezd podle jízdního řádu">${escape(view.scheduled)}</span>
          ${showDelay ? `<span class="delay" ${view.delay && !row.cancelled ? 'title="Odhadované zpoždění v minutách"' : 'aria-hidden="true"'}>${view.delay && !row.cancelled ? escape(view.delay.replace(" min", "")) : ""}</span>` : ""}
          <span class="countdown ${view.unit ? "" : "word"} ${/^\d{4,}$/.test(view.countdown) ? "long-number" : ""} ${upcoming ? "upcoming" : ""}" title="${row.cancelled ? "Spoj je zrušen" : upcoming ? "Blížící se odjezd včetně dostupného odhadu zpoždění" : "Čas do odjezdu včetně dostupného odhadu zpoždění"}">${escape(view.countdown)}</span>
        </li>`;
      }).join("")}</ol>`;
    }
    const markup = `<style>${styles}</style><ha-card class="${this.config.layout}${this.config.show_header ? "" : " no-header"}">
      ${this.config.show_header ? `<header><div class="badge">${icon("bus-clock", "Odjezdy IDS JMK")}</div><div class="heading"><div class="eyebrow">IDS JMK · ODJEZDY</div><h2>${escape(title)}</h2></div></header>` : ""}
      ${body}
      ${this.config.show_footer ? `<footer><span class="status ${stale || unavailable ? "warning" : ""}"><span class="dot"></span>${unavailable ? "Bez spojení" : old ? "Data nejsou aktuální" : stale ? "Realtime není aktuální" : !realtimeEnabled ? "Jízdní řád · realtime vypnutý" : "Data aktualizována"}</span><span>Aktualizace ${escape(time(attributes.generated_at))}</span></footer>` : ""}
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
        { name: "show_header", selector: { boolean: {} } },
        { name: "show_footer", selector: { boolean: {} } },
        { name: "show_departure_day", selector: { boolean: {} } },
        { name: "show_line_number", selector: { boolean: {} } },
        { name: "show_transport_icon", selector: { boolean: {} } },
        { name: "show_platform", selector: { boolean: {} } },
        { name: "show_accessibility", selector: { boolean: {} } },
      ];
      const labels = { show_header: "Zobrazit záhlaví", show_footer: "Zobrazit zápatí", entity: "Senzor odjezdové tabule", title: "Vlastní nadpis (volitelné)", layout: "Vzhled karty", highlight_minutes: "Zvýraznit odjezd do (0 = vypnuto)", limit: "Počet zobrazených odjezdů", show_departure_day: "Zobrazit den odjezdu", show_line_number: "Zobrazit číslo linky", show_transport_icon: "Zobrazit ikonu druhu dopravy", show_platform: "Zobrazit stanoviště", show_accessibility: "Zobrazit ikonky vybavení podle jízdního řádu" };
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
