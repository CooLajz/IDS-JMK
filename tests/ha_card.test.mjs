import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const elements = new Map();
globalThis.HTMLElement = class {
  attachShadow() { this.shadowRoot = { innerHTML: '' }; }
};
globalThis.customElements = { get: (name) => elements.get(name), define: (name, value) => elements.set(name, value) };
globalThis.window = {};
const source = await readFile(new URL('../custom_components/ids_jmk/www/ids-jmk-departures-card.js', import.meta.url));
const { departureView, isUpcoming } = await import(`data:text/javascript;base64,${source.toString('base64')}`);
const now = Date.parse('2026-10-11T18:00:00+02:00');
const row = { scheduled_departure: '2026-10-11T18:03:00+02:00', departure_time: '2026-10-11T18:05:00+02:00', delay_seconds: 120 };

test('countdown uses effective time without adding delay twice', () => {
  assert.deepEqual(departureView(row, now), { scheduled: '18:03', delay: '+2 min', countdown: '5', unit: 'min', departed: false });
  assert.equal(departureView(row, now + 4 * 60000).countdown, '1');
});
test('zero rounded delay hidden; negative delay and cancellation supported', () => {
  assert.equal(departureView({ ...row, delay_seconds: 29 }, now).delay, '');
  assert.equal(departureView({ ...row, delay_seconds: -120 }, now).delay, '-2 min');
  assert.equal(departureView({ ...row, cancelled: true }, now).countdown, 'Zrušeno');
});
test('departed, midnight rollover and missing timestamps', () => {
  assert.equal(departureView(row, now + 7 * 60000).departed, true);
  assert.equal(departureView({ departure_time: '2026-10-12T00:05:00+02:00' }, Date.parse('2026-10-11T23:55:00+02:00')).countdown, '10');
  assert.equal(departureView({}, now).countdown, '—');
});

const Card = elements.get('ids-jmk-departures-card');
const entity = 'sensor.ids_jmk_test';
function render(state, config = {}) {
  const card = new Card();
  card.setConfig({ entity, ...config });
  card.hass = { states: state ? { [entity]: state } : {} };
  return card.shadowRoot.innerHTML;
}
const attributes = { generated_at: new Date().toISOString(), realtime_stale: false, stop_name: 'Zastávka', departures: [row] };
test('handles missing, unavailable, empty and stale data', () => {
  assert.match(render(null), /Vyberte dostupný senzor/);
  assert.match(render({ state: 'unavailable', attributes }), /Data nejsou dostupná/);
  assert.match(render({ state: 'unknown', attributes: { ...attributes, departures: [] } }), /žádné odjezdy/);
  assert.match(render({ state: '5', attributes: { ...attributes, generated_at: '2000-01-01T00:00:00Z' } }), /Data nejsou aktuální/);
  assert.match(render({ state: '5', attributes: { ...attributes, realtime_stale: true } }), /Realtime není aktuální/);
});
test('escapes data and respects row limit and equipment options', () => {
  const unsafe = '<img src=x onerror=alert(1)>';
  const departure = { ...row, destination: unsafe, platform: unsafe, wheelchair_accessible: true };
  const html = render({ state: '5', attributes: { ...attributes, departures: [departure, departure] } }, { title: unsafe, limit: 1, show_accessibility: false });
  assert.ok(!html.includes(unsafe));
  assert.ok(html.includes('&lt;img'));
  assert.equal((html.match(/<li /g) || []).length, 1);
  assert.ok(!html.includes('mdi:wheelchair-accessibility'));
  assert.throws(() => render(null, { limit: 0 }), /Počet odjezdů/);
});

test('upcoming threshold includes the boundary, respects delay and can be disabled', () => {
  assert.equal(isUpcoming(row, 5, now), true);
  assert.equal(isUpcoming(row, 4, now), false);
  assert.equal(isUpcoming(row, 0, now), false);
  assert.equal(isUpcoming({ ...row, cancelled: true }, 5, now), false);
  assert.equal(isUpcoming(row, 5, now + 6 * 60000), false);
  assert.equal(isUpcoming({}, 5, now), false);
});
test('both layouts are selectable and stale rows are never highlighted', () => {
  const fresh = { ...attributes, generated_at: new Date().toISOString(), departures: [{ ...row, departure_time: new Date(Date.now() + 120000).toISOString() }] };
  const modern = render({ state: '2', attributes: fresh });
  assert.match(modern, /<ha-card class="modern">/);
  assert.match(modern, /class="countdown [^"]*upcoming/);
  const compact = render({ state: '2', attributes: fresh }, { layout: 'compact', highlight_minutes: 0 });
  assert.match(compact, /<ha-card class="compact">/);
  assert.ok(!/class="countdown [^"]*upcoming/.test(compact));
  assert.ok(!/class="countdown [^"]*upcoming/.test(render({ state: '2', attributes: { ...fresh, realtime_stale: true } })));
  assert.throws(() => render(null, { layout: 'invalid' }), /Vyberte vzhled/);
  assert.throws(() => render(null, { highlight_minutes: -1 }), /Hranice zvýraznění/);
});
