import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
const source = await readFile(new URL('../custom_components/ids_jmk/www/board-visibility.js', import.meta.url));
const { BoardVisibility } = await import(`data:text/javascript;base64,${source.toString('base64')}`);
globalThis.document = {visibilityState:'visible', addEventListener(){}, removeEventListener(){}};
globalThis.IntersectionObserver = class { constructor(cb){this.cb=cb;} observe(){} disconnect(){} };
const tick = () => new Promise(resolve => setImmediate(resolve));
test('visible cards renew independently, release offscreen and stop on disconnect', async () => {
  const calls=[];
  const hass={connection:{}, callWS:async msg=>calls.push(msg)};
  const a=new BoardVisibility({render(){}},()=>['sensor.a']);
  const b=new BoardVisibility({render(){}},()=>['sensor.a','sensor.b']);
  for(const item of [a,b]) { item.setHass(hass); item.connect(); }
  assert.equal(calls.length,0);
  for(const item of [a,b]) item.observer.cb([{isIntersecting:true}]);
  await tick();
  assert.equal(calls.length,2);assert.notEqual(calls[0].client_id,calls[1].client_id);
  a.setHass({...hass}); await tick(); assert.equal(calls.length,2);
  a.update(true); await tick(); assert.equal(calls.length,3);
  a.observer.cb([{isIntersecting:false}]);await tick(); assert.equal(calls.at(-1).visible,false);
  document.visibilityState='hidden';b.onVisibility();await tick();assert.equal(calls.at(-1).visible,false);
  document.visibilityState='visible';b.onVisibility();await tick();assert.equal(calls.at(-1).visible,true);
  a.disconnect();b.disconnect();await tick(); assert.equal(calls.at(-1).visible,false);
});
test('late subscribe completion is followed by release; failures retry at heartbeat', async()=>{
  let finish;const calls=[];
  const hass={connection:{},callWS:msg=>{calls.push(msg);return msg.visible ? new Promise(resolve=>finish=resolve) : Promise.resolve();}};
  const a=new BoardVisibility({render(){}},()=>['sensor.a']);
  a.setHass(hass);a.connect();a.observer.cb([{isIntersecting:true}]);a.disconnect();
  finish();await tick();assert.deepEqual(calls.map(c=>c.visible),[true,false]);
  const failed={connection:{},callWS:async()=>{throw Error('offline');}};
  a.setHass(failed);a.connect();a.observer.cb([{isIntersecting:true}]);await tick();assert.equal(a.error,true);
  failed.callWS=async msg=>calls.push(msg);a.update(true);await tick();assert.equal(a.error,false);
  a.disconnect();await tick();
});
