import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const elements=new Map();
globalThis.HTMLElement=class {
  attachShadow(){
    const nodes=new Map();
    this.shadowRoot={innerHTML:'',querySelector:s=>{if(s==='#retry')return null;if(!nodes.has(s))nodes.set(s,{});return nodes.get(s);},querySelectorAll:()=>[]};
  }
  dispatchEvent(){}
};
globalThis.customElements={get:n=>elements.get(n),define:(n,v)=>elements.set(n,v)};
globalThis.window={};
const source=await readFile(new URL('../custom_components/ids_jmk/www/ids-jmk-map-card.js',import.meta.url));
await import(`data:text/javascript;base64,${source.toString('base64')}`);
const Editor=elements.get('ids-jmk-map-card-editor');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(){
  const editor=new Editor(),calls=[];
  const hass={connection:{},callWS:async msg=>{
    calls.push(msg);
    if(msg.type==='ids_jmk/map_sources')return[{id:'demo',name:'Demo'}];
    return{routes:[{id:'R',line:'501',name:'Demo',directions:[{id:'0',label:'Tam'}]}]};
  }};
  editor.setConfig({entry_id:'demo',selections:[{route_id:'R',direction:'*'}]});
  editor.hass=hass;
  return{editor,hass,calls};
}
test('HA state updates reuse source/catalogue requests and do not redraw the editor',async()=>{
  const {editor,hass,calls}=fixture();await flush();
  let renders=0;const render=editor.render.bind(editor);editor.render=()=>{renders++;render();};
  for(let i=0;i<100;i++)editor.hass={...hass,states:{tick:i}};
  await flush();
  assert.equal(calls.length,2);
  assert.equal(renders,0);
  editor.setConfig({...editor.config});
  await flush();assert.equal(calls.length,2);
  editor.hass={...hass,connection:{}};
  await flush();assert.equal(calls.length,4);
});
test('changing sources fetches the new catalogue without repeatedly listing sources',async()=>{
  const {editor,calls}=fixture();await flush();
  editor.setConfig({...editor.config,entry_id:'other'});
  await flush();
  assert.equal(calls.filter(m=>m.type==='ids_jmk/map_sources').length,1);
  assert.deepEqual(calls.filter(m=>m.action==='routes').map(m=>m.entry_id),['demo','other']);
});
test('failed catalogue requests do not retry on each HA state update',async()=>{
  const editor=new Editor(),calls=[];
  const hass={connection:{},callWS:async m=>{calls.push(m);throw Error('offline');}};
  editor.setConfig({entry_id:'demo',selections:[]});editor.hass=hass;await flush();
  for(let i=0;i<100;i++)editor.hass={...hass,states:{tick:i}};
  await flush();assert.equal(calls.length,1);assert.ok(editor.error);
  editor.hass={...hass,connection:{}};await flush();assert.equal(calls.length,2);
});

test('map pauses offscreen and in a hidden document, resumes once, and removes listeners', async()=>{
  globalThis.document=new EventTarget();document.hidden=false;
  let observer;
  globalThis.IntersectionObserver=class {
    constructor(callback){this.callback=callback;observer=this;}
    observe(){} disconnect(){this.disconnected=true;}
  };
  const oldSet=globalThis.setInterval,oldClear=globalThis.clearInterval;
  let active=false;
  globalThis.setInterval=()=>{active=true;return 1;};
  globalThis.clearInterval=()=>{active=false;};
  try {
    const Card=elements.get('ids-jmk-map-card'),card=new Card();
    card.isConnected=true;card.config={entry_id:'demo',refresh_interval:30,selections:[{route_id:'R',direction:'*'}]};
    card.init=()=>{};card.map={remove(){}};card.status={};card.detail={};
    card.markers={clearLayers(){}};card.permanentStops={getLayers:()=>[]};
    card.loadStops=()=>{};
    let calls=0;card.call=async()=>{calls++;return{vehicles:[],realtime_enabled:true};};
    card.connectedCallback();assert.equal(active,true);
    observer.callback([{isIntersecting:false}]);assert.equal(active,false);
    await card.refresh();assert.equal(calls,0);
    observer.callback([{isIntersecting:true}]);await flush();assert.equal(active,true);assert.equal(calls,1);
    document.hidden=true;document.dispatchEvent(new Event('visibilitychange'));
    assert.equal(active,false);await card.refresh();assert.equal(calls,1);
    document.hidden=false;document.dispatchEvent(new Event('visibilitychange'));
    await flush();assert.equal(calls,2);
    card.disconnectedCallback();assert.equal(active,false);assert.equal(observer.disconnected,true);
    document.dispatchEvent(new Event('visibilitychange'));assert.equal(active,false);
  } finally {globalThis.setInterval=oldSet;globalThis.clearInterval=oldClear;}
});

test('selected detail follows vehicle updates without refetching geometry, including an in-flight trip', async()=>{
  globalThis.document={hidden:false};
  const Card=elements.get('ids-jmk-map-card'),card=new Card();
  Object.assign(card,{isConnected:true,visible:true,map:{},config:{entry_id:'demo',selections:[{route_id:'R',direction:'*'}]},status:{},detail:{},fitted:true,overview:true});
  card.markers={clearLayers(){}};card.route={clearLayers(){}};
  card.permanentStops={getLayers:()=>[]};card.loadStops=()=>{};card.fit=()=>{};
  card.L={polyline:()=>({addTo(){}}),divIcon:()=>({}),marker:()=>({addTo(){return this;},on(){return this;}})};
  const initial={id:'V',trip_id:'T',service_date:'2026-10-16',line:'1',destination:'C',updated_at:'2026-10-16T12:00:00+02:00',position:{lat:49,lon:16},current_stop:{delay_seconds:60}};
  let current={...initial,current_stop:{delay_seconds:300,delay_source:'vehicle_estimate'},updated_at:'2026-10-16T12:01:00+02:00'};
  let resolveTrip,tripCalls=0;
  card.call=async action=>{
    if(action==='trip'){tripCalls++;return new Promise(resolve=>{resolveTrip=resolve;});}
    return {vehicles:[current],realtime_enabled:true};
  };
  const loading=card.showTrip(initial);
  await card.refresh();
  resolveTrip({stops:[]});await loading;
  assert.match(card.detail.innerHTML,/Odhad zpoždění 5 min/);
  current={...current,current_stop:{delay_seconds:120,delay_source:'trip_update'}};
  await card.refresh();
  assert.match(card.detail.innerHTML,/Zpoždění 2 min/);
  assert.equal(tripCalls,1);
  current={...current,service_date:'2026-10-17'};
  await card.refresh();
  assert.equal(card.selected,null);
});
