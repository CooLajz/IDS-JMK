import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const elements=new Map();
globalThis.HTMLElement=class {attachShadow(){this.shadowRoot={innerHTML:'',querySelectorAll:()=>[]};}};
globalThis.customElements={get:n=>elements.get(n),define:(n,v)=>elements.set(n,v)};
globalThis.window={};
const helper = await readFile(new URL('../custom_components/ids_jmk/www/board-visibility.js', import.meta.url));
const source=await readFile(new URL('../custom_components/ids_jmk/www/ids-jmk-alerts-card.js',import.meta.url));
const {collectAlerts}=await import(`data:text/javascript;base64,${Buffer.from(source.toString().replace('./board-visibility.js', `data:text/javascript;base64,${helper.toString('base64')}`)).toString('base64')}`);
const now=Date.now();
const alert={id:'1',key:'same',title:'Výluka',description:'Popis',matched_lines:['25'],scope:'line'};
const state=(alerts,extra={})=>({state:'unknown',attributes:{alerts,alerts_stale:false,generated_at:new Date(now).toISOString(),...extra}});
test('merges duplicate alerts across multiple sensors and retains matching lines and sources',()=>{
  const states={'sensor.a':state([alert],{stop_name:'A'}),'sensor.b':state([{...alert,matched_lines:['26']}],{stop_name:'B'})};
  const result=collectAlerts(states,['sensor.a','sensor.b','sensor.a'],now);
  assert.equal(result.alerts.length,1);assert.deepEqual(result.alerts[0].matched_lines,['25','26']);
  assert.deepEqual(result.alerts[0].sources,['A','B']);assert.deepEqual(result.issues,[]);
  states['sensor.b']=state([{...alert,description:'Jiný popis'}]);
  assert.equal(collectAlerts(states,['sensor.a','sensor.b'],now).alerts.length,2);
});
test('unavailable, old, unsupported and disabled sources cannot report an all clear',()=>{
  const states={'sensor.good':state([alert]),'sensor.old':state([alert],{generated_at:'2000-01-01'}),
    'sensor.off':state([alert],{realtime_enabled:false}),'sensor.legacy':state([], {alerts_supported:false})};
  const r=collectAlerts(states,Object.keys(states).concat('sensor.missing'),now);
  assert.equal(r.alerts.length,1);assert.equal(r.issues.length,4);
  assert.equal(collectAlerts({'sensor.a':state([])},['sensor.a'],now).alerts.length,0);
});
test('card escapes provider text and unsafe links and validates sensor selections',()=>{
  const Card=elements.get('ids-jmk-alerts-card');const c=new Card();
  assert.throws(()=>c.setConfig({entities:[]}),/alespoň/);
  c.setConfig({entities:['sensor.a']});
  c.hass={states:{'sensor.a':state([{...alert,description:'<img src=x onerror=alert(1)>',url:'javascript:alert(1)'}])}};
  assert.ok(!c.shadowRoot.innerHTML.includes('<img'));assert.ok(c.shadowRoot.innerHTML.includes('&lt;img'));
  assert.ok(!c.shadowRoot.innerHTML.includes('href="javascript:'));
});
