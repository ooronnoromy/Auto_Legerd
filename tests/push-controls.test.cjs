const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {runInNewContext}=require('node:vm');

async function fixture({permission='default',available=true,ios=false}={}) {
  const handlers={},posts=[],subscriptions=[];
  let requested=0,current=null,removed=false;
  const enable={disabled:true,hidden:false,addEventListener(name,fn) {handlers.enable=fn;}};
  const disable={hidden:true,disabled:false,addEventListener(name,fn) {handlers.disable=fn;}};
  const status={textContent:''};
  const controls={querySelector(selector) {return selector.includes('data-enable')?enable:selector.includes('data-disable')?disable:status;}};
  const subscription={endpoint:'https://fcm.googleapis.com/fcm/send/device',toJSON(){return {endpoint:this.endpoint,keys:{auth:'auth',p256dh:'key'}};},async unsubscribe(){removed=true;current=null;return true;}};
  const registration={pushManager:{async getSubscription(){return current;},async subscribe(options){subscriptions.push(options);current=subscription;return current;}}};
  const Notification={permission,async requestPermission(){requested++;this.permission='granted';return 'granted';}};
  const window={isSecureContext:true,PushManager:{},Notification,matchMedia(){return {matches:false};}};
  const navigator={userAgent:ios?'iPhone':'Chrome',platform:ios?'iPhone':'Linux',maxTouchPoints:0,
    serviceWorker:{async register(){return registration;},ready:Promise.resolve(registration)}};
  const document={body:{dataset:{pushConfig:'/notifications/config/',pushSubscribe:'/notifications/subscribe/',pushUnsubscribe:'/notifications/unsubscribe/'}},querySelector(){return controls;},querySelectorAll(){return [];}};
  async function fetch(url,options){
    if(options?.method==='POST'){posts.push({url,options});return {ok:true};}
    return {ok:true,async json(){return {available,publicKey:'AQID',csrfToken:'csrf'};}};
  }
  runInNewContext(readFileSync('static/js/push.js','utf8'),{document,window,navigator,Notification,fetch,AbortSignal,Uint8Array,atob,setTimeout});
  await new Promise(setImmediate);
  return {enable,disable,status,handlers,posts,subscriptions,requested:()=>requested,removed:()=>removed};
}

test('loading the app never asks for notification permission automatically',async()=>{
  const f=await fixture();
  assert.equal(f.requested(),0);
  assert.equal(f.enable.disabled,false);
  assert.equal(f.posts.length,0);
});

test('Enable requests permission and binds the subscription with a CSRF token',async()=>{
  const f=await fixture();await f.handlers.enable();
  assert.equal(f.requested(),1);
  assert.equal(f.subscriptions[0].userVisibleOnly,true);
  assert.deepEqual(Array.from(f.subscriptions[0].applicationServerKey),[1,2,3]);
  assert.equal(f.posts[0].options.headers['X-CSRFToken'],'csrf');
  assert.equal(f.enable.hidden,true);assert.equal(f.disable.hidden,false);
});

test('Disable removes only this phone subscription and clears its receiving state',async()=>{
  const f=await fixture();await f.handlers.enable();await f.handlers.disable();
  assert.equal(f.posts.at(-1).url,'/notifications/unsubscribe/');
  assert.equal(f.removed(),true);
  assert.equal(f.enable.hidden,false);assert.equal(f.disable.hidden,true);
});

test('blocked permissions and missing server configuration are explained without prompting',async()=>{
  const blocked=await fixture({permission:'denied'});
  assert.equal(blocked.enable.disabled,true);assert.match(blocked.status.textContent,/blocked/);
  const unavailable=await fixture({available:false});
  assert.equal(unavailable.enable.disabled,true);assert.match(unavailable.status.textContent,/administrator/);
  assert.equal(blocked.requested()+unavailable.requested(),0);
});

test('iPhone browsers show Home Screen instructions before requesting permission',async()=>{
  const f=await fixture({ios:true});
  assert.match(f.status.textContent,/Add to Home Screen/);
  assert.equal(f.enable.disabled,true);assert.equal(f.requested(),0);
});
