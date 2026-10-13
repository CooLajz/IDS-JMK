import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const elements = new Map();
globalThis.HTMLElement = class {
  attachShadow() { this.shadowRoot = { innerHTML: '' }; }
};
globalThis.customElements = { get: (name) => elements.get(name), define: (name, value) => elements.set(name, value) };
globalThis.window = {};
const helper = await readFile(new URL('../custom_components/ids_jmk/www/board-visibility.js', import.meta.url));
const source = await readFile(new URL('../custom_components/ids_jmk/www/ids-jmk-departures-card.js', import.meta.url));
const { departureView, isUpcoming, transportIcon, departureDay } = await import(`data:text/javascript;base64,${Buffer.from(source.toString().replace('./board-visibility.js', `data:text/javascript;base64,${helper.toString('base64')}`)).toString('base64')}`);
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

test('transport icons use known MDI names and can be hidden independently', () => {
  for (const [mode, name] of [['tram','tram'],['bus','bus'],['rail','train'],['trolleybus','bus-electric']]) {
    assert.equal(transportIcon(mode)[0], name);
    const state = { state: '5', attributes: { ...attributes, departures: [{ ...row, transport_mode: mode, bikes_allowed: true }] } };
    assert.ok(render(state).includes(`icon="mdi:${name}"`));
    const hidden = render(state, { show_transport_icon: false });
    assert.ok(!hidden.includes(`icon="mdi:${name}"`));
    assert.ok(hidden.includes('icon="mdi:bicycle"'));
  }
  for (const mode of [undefined, 'unknown', 'toString', '<script>']) assert.equal(transportIcon(mode), null);
});

test('departure day uses Prague calendar dates across midnight, DST and year boundaries', () => {
  const cases = [
    ['2026-10-11T23:55:00+02:00', '2026-10-11T18:00:00+02:00', ''],
    ['2026-10-12T00:05:00+02:00', '2026-10-11T23:55:00+02:00', 'zítra'],
    ['2026-10-13T04:39:00+02:00', '2026-10-11T23:55:00+02:00', '13.10.'],
    ['2026-12-31T23:05:00Z', '2026-12-31T12:00:00Z', 'zítra'],
    ['2026-11-01T04:39:00+01:00', '2026-10-31T23:55:00+01:00', 'zítra'],
    ['2026-03-30T00:05:00+02:00', '2026-03-28T23:55:00+01:00', '30.3.'],
    ['2026-10-26T23:55:00+01:00', '2026-10-25T00:05:00+02:00', 'zítra'],
    ['2026-10-12T00:05:00+02:00', '2026-10-12T00:00:00+02:00', ''],
    ['2026-10-11T23:55:00+02:00', '2026-10-12T00:00:00+02:00', '11.10.'],
  ];
  for (const [value, current, expected] of cases) assert.equal(departureDay(value, Date.parse(current)), expected);
  for (const value of [undefined, null, '', 'invalid']) assert.equal(departureDay(value, now), '');
});
test('day column follows scheduled time and can be hidden without changing the countdown', () => {
  const today = new Date().toISOString();
  const future = new Date(Date.now() + 3 * 86400000).toISOString();
  const state = (scheduled, effective) => ({state:'5',attributes:{...attributes,departures:[{...row,scheduled_departure:scheduled,departure_time:effective}]}});
  assert.ok(!render(state(today, future)).includes('class="labels with-day'));
  assert.ok(render(state(future, future)).includes('class="labels with-day'));
  assert.ok(!render(state(future, future), {show_departure_day:false}).includes('class="labels with-day'));
  assert.equal(departureView(state(future,future).attributes.departures[0]).scheduled.length, 5);
});

test('delay column follows displayed non-cancelled rows and realtime availability', () => {
  const state = (departures, extra = {}) => ({state:'5',attributes:{...attributes,departures,...extra}});
  const missing = {...row}; delete missing.delay_seconds;
  for (const layout of ['modern','compact']) {
    for (const departures of [[missing], [{...row,delay_seconds:null}], [{...row,delay_seconds:0}], [{...row,delay_seconds:29}], [{...row,cancelled:true}]]) {
      const html=render(state(departures),{layout});
      assert.ok(!html.includes('Zpož. min'));
      assert.ok(!html.includes('<span class="delay"'));
    }
    assert.ok(!render(state([missing,row]),{layout,limit:1}).includes('Zpož. min'));
    assert.ok(!render(state([row],{realtime_enabled:false}),{layout}).includes('Zpož. min'));
    for (const seconds of [120,-120]) {
      const html=render(state([missing,{...row,delay_seconds:seconds}]),{layout});
      assert.ok(html.includes('Zpož. min'));
      assert.equal((html.match(/<span class="delay"/g)||[]).length,2);
      assert.ok(html.includes(seconds>0 ? '>+2</span>' : '>-2</span>'));
    }
  }
  const card=new Card(); card.setConfig({entity});
  for (const [departures,visible] of [[[missing],false],[[row],true],[[missing],false]]) {
    card.hass={states:{[entity]:state(departures)}};
    assert.equal(card.shadowRoot.innerHTML.includes('Zpož. min'),visible);
  }
});

test('line number defaults to visible and is independent of transport icons', () => {
  const state={state:'5',attributes:{...attributes,departures:[{...row,line:'501',transport_mode:'bus'}]}};
  for (const layout of ['modern','compact']) {
    const normal=render(state,{layout});
    assert.ok(normal.includes('<span>501</span>') && normal.includes('icon="mdi:bus"'));
    const iconOnly=render(state,{layout,show_line_number:false});
    assert.ok(!iconOnly.includes('501') && iconOnly.includes('icon="mdi:bus"'));
    assert.ok(iconOnly.includes('icon-only') && iconOnly.includes('<span>Druh</span>'));
    const numberOnly=render(state,{layout,show_transport_icon:false});
    assert.ok(numberOnly.includes('<span>501</span>') && !numberOnly.includes('icon="mdi:bus"'));
    const neither=render(state,{layout,show_line_number:false,show_transport_icon:false});
    assert.ok(!neither.includes('<span class="line"') && !neither.includes('<span>Linka</span>'));
    const unknown=render({...state,attributes:{...state.attributes,departures:[{...row,line:'501',transport_mode:'unknown'}]}},{layout,show_line_number:false});
    assert.ok(!unknown.includes('<span class="line"'));
    assert.ok(neither.includes('Odjezd podle jízdního řádu'));
  }
});
