const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');

function fixture({account = 2, offline = false, signedOut = false} = {}) {
  const handlers = {}, notifications = [], opened = [], posts = [];
  const self = {
    location: {origin: 'https://garage.example'},
    addEventListener(type, fn) {handlers[type] = fn;},
    registration: {
      async showNotification(title, options) {notifications.push({title, options});},
      pushManager: {async subscribe() {return {toJSON() {return {endpoint:'https://web.push.apple.com/device',keys:{auth:'auth',p256dh:'key'}};}};}},
    },
    clients: {async matchAll() {return [];}, async openWindow(url) {opened.push(url);}},
  };
  async function fetch(url, options) {
    if (offline) throw new Error('offline');
    if (options?.method === 'POST') {posts.push({url,options}); return {ok:true};}
    return {ok:!signedOut,redirected:signedOut,async json() {return {userId:account,available:true,publicKey:'AQID',csrfToken:'csrf'};}};
  }
  runInNewContext(readFileSync('static/js/service-worker.js','utf8'), {self,fetch,URL,AbortSignal,Uint8Array,atob});
  async function push(data) {
    let promise;
    handlers.push({data:{json:()=>data},waitUntil(p) {promise=p;}});
    await promise;
  }
  return {self,handlers,notifications,opened,posts,push};
}

test('push displays a car or expense notification for the signed-in recipient', async () => {
  const f=fixture();
  await f.push({title:'New expense added',body:'A driver added fuel for Axio.',url:'/expenses/?vehicle=5',recipient:2,tag:'expense-9'});
  assert.equal(f.notifications.length,1);
  assert.equal(f.notifications[0].title,'New expense added');
  assert.equal(f.notifications[0].options.data.url,'https://garage.example/expenses/?vehicle=5');
  assert.equal(f.notifications[0].options.tag,'expense-9');
});

test('signed-out devices and a different signed-in account do not see old notifications', async () => {
  for (const options of [{signedOut:true},{account:3}]) {
    const f=fixture(options);
    await f.push({title:'Private update',recipient:2});
    assert.equal(f.notifications.length,0);
  }
});

test('when the website is unavailable, lock-screen content stays generic', async () => {
  const f=fixture({offline:true});
  await f.push({title:'New expense added',body:'Private car name',recipient:2});
  assert.equal(f.notifications[0].title,'AutoLedger update');
  assert.equal(f.notifications[0].options.body,'There is a new update in your garage.');
});

test('malformed payloads still produce a safe generic notification', async () => {
  const f=fixture();
  await f.push('invalid');
  assert.equal(f.notifications[0].title,'AutoLedger update');
});

test('clicking a notification navigates and focuses an existing app window', async () => {
  const f=fixture();let navigated,focused=false,closed=false,promise;
  f.self.clients.matchAll=async()=>[{url:'https://garage.example/profile/',async navigate(url) {navigated=url;return {async focus() {focused=true;}};}}];
  f.handlers.notificationclick({notification:{data:{url:'/vehicles/5/'},close() {closed=true;}},waitUntil(p) {promise=p;}});
  await promise;
  assert.equal(navigated,'https://garage.example/vehicles/5/');
  assert.equal(focused,true);assert.equal(closed,true);
  assert.equal(f.opened.length,0);
});

test('notification clicks cannot open external or unsupported destinations', async () => {
  const f=fixture();
  for (const url of ['https://evil.example/','javascript:alert(1)','/admin/']) {
    let promise;
    f.handlers.notificationclick({notification:{data:{url},close() {}},waitUntil(p) {promise=p;}});
    await promise;
    assert.equal(f.opened.at(-1),'https://garage.example/');
  }
});

test('expired browser subscription can renew using authenticated CSRF-protected endpoint', async () => {
  const f=fixture();let promise;
  f.handlers.pushsubscriptionchange({waitUntil(p) {promise=p;}});
  await promise;
  assert.equal(f.posts.length,1);
  assert.equal(f.posts[0].url,'/notifications/subscribe/');
  assert.equal(f.posts[0].options.headers['X-CSRFToken'],'csrf');
});
