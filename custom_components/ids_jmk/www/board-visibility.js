/* A short-lived subscription shared by our board and alerts cards. */
export class BoardVisibility {
  constructor(host, entities) {
    this.host = host;
    this.entities = entities;
    this.id = globalThis.crypto?.randomUUID?.() || `card-${Date.now()}-${Math.random()}`;
    this.onVisibility = () => this.update();
  }
  setHass(hass) { this.hass = hass; this.update(); }
  connect() {
    if (this.connected) return;
    this.connected = true;
    this.intersecting = false;
    this.observer = new IntersectionObserver(entries => {
      this.intersecting = entries.some(entry => entry.isIntersecting);
      this.update();
    });
    this.observer.observe(this.host);
    document.addEventListener('visibilitychange', this.onVisibility);
    this.timer = setInterval(() => this.update(true), 30000);
    this.update();
  }
  disconnect() {
    this.connected = false;
    this.observer?.disconnect();
    document.removeEventListener('visibilitychange', this.onVisibility);
    clearInterval(this.timer);
    this.update();
  }
  update(force = false) {
    const visible = Boolean(this.connected && this.intersecting && document.visibilityState === 'visible');
    const ids = visible ? [...new Set(this.entities())].filter(Boolean).sort() : [];
    const signature = JSON.stringify(ids);
    if (!force && signature === this.signature && this.hass?.connection === this.connection) return;
    this.signature = signature;
    this.connection = this.hass?.connection;
    this.desired = {hass: this.hass, ids};
    this.flush();
  }
  async flush() {
    if (this.pending) return;
    this.pending = true;
    try {
      while (this.desired) {
        const next = this.desired;
        this.desired = null;
        if (!next.hass?.callWS) continue;
        // Release on the previous connection before claiming on a replacement.
        if (this.claimed && (this.claimed.connection !== next.hass.connection || !next.ids.length)) {
          try { await this.claimed.callWS({type:'ids_jmk/board_visibility', client_id:this.id, visible:false}); } catch { /* TTL handles a closed connection. */ }
          this.claimed = null;
        }
        if (!next.ids.length) continue;
        this.claimed = next.hass;
        try {
          await next.hass.callWS({type:'ids_jmk/board_visibility', client_id:this.id, visible:true, entity_ids:next.ids});
          this.error = false;
        } catch {
          this.error = true;
          // The periodic heartbeat retries without reacting to every state update.
        }
        this.host.render();
      }
    } finally { this.pending = false; }
  }
}
