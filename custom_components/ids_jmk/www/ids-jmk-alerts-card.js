import { BoardVisibility } from "./board-visibility.js";
/* Alerts from board sensor attributes; no independent API requests. */
const TYPE = "ids-jmk-alerts-card";
const escape = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const safeUrl = (value) => { try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : null; } catch { return null; } };

export function alertMarkup(alert) {
  const html = alert.description_html || alert.title_html;
  if (typeof html === "string" && !/[<>]/.test(html.replace(/<\/?(?:p|br|strong|em|u|ul|ol|li)>/g, ""))) return html;
  return escape(alert.description || alert.title);
}

export function collectAlerts(states, entities, now = Date.now()) {
  const merged = new Map(), issues = [];
  for (const id of [...new Set(entities)]) {
    const state = states?.[id], a = state?.attributes ?? {};
    const name = a.stop_name || a.friendly_name || id;
    const age = now - Date.parse(a.generated_at);
    if (a.refresh_pending || a.refresh_active === false) { issues.push(`${name}: čeká se na obnovení při zobrazení`); continue; }
    if (!state || state.state === "unavailable") { issues.push(`${name}: senzor není dostupný`); continue; }
    if (a.realtime_enabled === false) { issues.push(`${name}: realtime je na serveru vypnutý`); continue; }
    if (a.alerts_supported === false || !Array.isArray(a.alerts)) { issues.push(`${name}: aktualizujte API a integraci pro podporu upozornění`); continue; }
    if (a.alerts_stale !== false || !Number.isFinite(age) || age > 120000 || age < -60000) { issues.push(`${name}: upozornění nejsou aktuální`); continue; }
    for (const alert of a.alerts) {
      if (!alert || typeof alert !== "object") continue;
      // Never merge different text under the same provider ID or across server versions.
      const key = JSON.stringify([alert.key || alert.id || "", alert.title, alert.description, alert.title_html, alert.description_html, alert.cause, alert.effect, alert.url]);
      if (!merged.has(key)) merged.set(key, { ...alert, mergeKey: key, matched_lines: new Set(), sources: new Set() });
      const item = merged.get(key);
      for (const line of alert.matched_lines || []) item.matched_lines.add(String(line));
      item.sources.add(name);
    }
  }
  return { alerts: [...merged.values()].map(a => ({...a, matched_lines:[...a.matched_lines].sort(), sources:[...a.sources]})), issues };
}
const styles = `
  :host { display:block; color:var(--primary-text-color); }
  * { box-sizing:border-box; }
  ha-card { display:block; border-radius:var(--ha-card-border-radius,16px); overflow:hidden; background:var(--ha-card-background,var(--card-background-color,white)); }
  header { display:flex; align-items:center; gap:10px; padding:18px 18px 12px; }
  header ha-icon { color:var(--warning-color,#a46600); --mdc-icon-size:24px; width:24px; height:24px; }
  h2 { font-size:18px; line-height:1.3; margin:0; }
  .count { margin-left:auto; font-size:13px; color:var(--secondary-text-color); }
  .items { padding:0 12px 12px; }
  details { border:1px solid color-mix(in srgb,var(--warning-color,#b47a00) 45%,transparent); border-radius:10px; background:color-mix(in srgb,var(--warning-color,#b47a00) 7%,transparent); margin-top:8px; }
  summary { cursor:pointer; padding:12px; line-height:1.45; font-size:14px; font-weight:600; overflow-wrap:anywhere; }
  .lines { display:block; font-size:11px; font-weight:500; color:var(--secondary-text-color); margin:4px 0 0 15px; }
  .body { padding:0 12px 12px; font-size:13px; line-height:1.6; }
  .description { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }
  .description.rich { white-space:normal; }
  .description p { margin:0 0 .65em; }
  .description p:last-child { margin-bottom:0; }
  .description ul, .description ol { margin:.5em 0; padding-left:1.5em; }
  .sources { color:var(--secondary-text-color); font-size:11px; margin:10px 0 0; }
  a { display:inline-block; margin-top:8px; color:var(--primary-color); }
  .message { padding:0 18px 16px; font-size:13px; line-height:1.5; color:var(--secondary-text-color); }
  .issues { margin:0 12px 12px; padding:10px 12px; border-radius:8px; background:color-mix(in srgb,var(--warning-color,#b47a00) 12%,transparent); font-size:12px; line-height:1.5; }
  .issues ul { padding-left:18px; margin:5px 0 0; }
`;
class AlertsCard extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:"open"}); this.visibility = new BoardVisibility(this, () => (this.config?.entities || [])); }
  setConfig(config) {
    if (!Array.isArray(config.entities) || !config.entities.length || config.entities.some(id=>typeof id!=="string" || !id.startsWith("sensor."))) throw new Error("Vyberte alespoň jeden senzor odjezdové tabule IDS JMK.");
    this.config = {...config, entities:[...new Set(config.entities)]}; this.visibility.update(); this.render();
  }
  set hass(hass) { this.states = hass.states; this.visibility.setHass(hass); this.render(); }
  connectedCallback() {
    this.visibility.connect();
    const request = new CustomEvent("context-request", {bubbles:true,composed:true});
    request.context="states"; request.subscribe=true;
    request.callback=(states,unsubscribe)=>{this.unsubscribe=unsubscribe;this.states=states;this.render();};
    this.dispatchEvent(request);
    clearInterval(this.timer); this.timer=setInterval(()=>this.render(),15000); this.render();
  }
  disconnectedCallback() { this.visibility.disconnect(); clearInterval(this.timer); this.unsubscribe?.(); this.unsubscribe=undefined; }
  getCardSize() { return 3; }
  getGridOptions() { return {columns:12,min_columns:6}; }
  static getConfigElement() { return document.createElement(`${TYPE}-editor`); }
  static getStubConfig(hass) { return {entities:Object.keys(hass.states).filter(id=>id.startsWith("sensor.") && hass.states[id].attributes.stop_id && Array.isArray(hass.states[id].attributes.departures)).slice(0,1)}; }
  render() {
    if (!this.config) return;
    const {alerts,issues} = collectAlerts(this.states,this.config.entities);
    if (this.visibility.error) issues.push("Odběr tabulí se nepodařilo obnovit. Zkontrolujte připojení a aktualizaci integrace.");
    const html = `<style>${styles}</style><ha-card><header><ha-icon icon="mdi:alert-outline" aria-hidden="true"></ha-icon><h2>${escape(this.config.title || "Upozornění IDS JMK")}</h2><span class="count">${alerts.length}</span></header>
      ${issues.length ? `<div class="issues" role="status">Některé zdroje nelze ověřit.<ul>${issues.map(s=>`<li>${escape(s)}</li>`).join("")}</ul></div>` : ""}
      ${alerts.length ? `<div class="items">${alerts.map(a=>{
        const heading = a.description?.split("\n").find(s=>s.trim()) || a.title || "Upozornění";
        const url=safeUrl(a.url);
        return `<details data-key="${escape(a.mergeKey)}"><summary>${escape(heading)}<span class="lines">${a.matched_lines.length ? `Linky: ${escape(a.matched_lines.join(", "))}` : escape(a.title)}${a.scope === "line" ? " · Omezení na lince" : ""}</span></summary><div class="body"><div class="description${a.description_html || a.title_html ? " rich" : ""}">${alertMarkup(a)}</div>${url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">Informace dopravního systému ↗</a>` : ""}<p class="sources">Tabule: ${escape(a.sources.join(" · "))}</p></div></details>`;
      }).join("")}</div>` : `<div class="message">${issues.length ? "Z dostupných aktuálních zdrojů nejsou hlášena upozornění." : "Pro vybrané tabule nejsou hlášena žádná upozornění."}</div>`}
      </ha-card>`;
    if (html === this.markup) return;
    const opened = new Set(Array.from(this.shadowRoot.querySelectorAll("details[open]")).map(d=>d.dataset.key));
    this.shadowRoot.innerHTML=html; this.markup=html;
    for (const item of this.shadowRoot.querySelectorAll("details")) item.open=opened.has(item.dataset.key);
  }
}
class AlertsEditor extends HTMLElement {
  constructor() { super();this.attachShadow({mode:"open"}); }
  setConfig(config) { this.config=config;this.render(); }
  set hass(hass) { this._hass=hass;this.render(); }
  render() {
    if (!this.config || !this._hass) return;
    if (!this.form) {
      this.form=document.createElement("ha-form");
      this.form.schema=[{name:"entities",required:true,selector:{entity:{domain:"sensor",integration:"ids_jmk",multiple:true}}},{name:"title",selector:{text:{}}}];
      this.form.computeLabel=s=>({entities:"Senzory odjezdových tabulí",title:"Vlastní nadpis (volitelné)"})[s.name];
      this.form.addEventListener("value-changed",e=>{e.stopPropagation();this.config={...this.config,...e.detail.value};this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this.config},bubbles:true,composed:true}));});
      this.shadowRoot.append(this.form);
    }
    this.form.hass=this._hass;this.form.data=this.config;
  }
}
if (!customElements.get(TYPE)) customElements.define(TYPE,AlertsCard);
if (!customElements.get(`${TYPE}-editor`)) customElements.define(`${TYPE}-editor`,AlertsEditor);
window.customCards=window.customCards||[];
if (!window.customCards.some(c=>c.type===TYPE)) window.customCards.push({type:TYPE,name:"IDS JMK — Upozornění",description:"Výluky a omezení z více odjezdových tabulí bez duplicit.",preview:true,documentationURL:"https://github.com/CooLajz/IDS-JMK/blob/main/docs/home-assistant.md"});
