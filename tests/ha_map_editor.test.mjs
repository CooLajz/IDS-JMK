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
