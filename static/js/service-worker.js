const CACHE = 'autoledger-phone-v13';
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll([
    '/static/css/style.css', '/static/css/mobile.css', '/static/css/garage.css', '/static/css/glass.css', '/static/css/liquid.css', '/static/img/liquid-lens.svg', '/static/js/glass.js', '/static/js/push.js', '/static/img/garage-banner.webp', '/static/img/garage-road.svg', '/static/js/app.js', '/static/js/install.js', '/static/js/login.js',
    '/static/icons/icon-glass-192.png?v=pearl-11', '/static/icons/icon-glass-512.png?v=pearl-11', '/static/icons/apple-touch-icon.png?v=pearl-11', '/static/icons/favicon-32.png?v=pearl-11', '/static/icons/favicon.ico?v=pearl-11', '/static/icons/icon-glass.svg?v=pearl-11',
  ])).then(() => self.skipWaiting()));
});

function notificationURL(value) {
  try {
    const url = new URL(value || '/', self.location.origin);
    if (url.origin === self.location.origin && (url.pathname === '/' || url.pathname === '/expenses/' || /^\/vehicles\/\d+\/$/.test(url.pathname))) return url.href;
  } catch { /* Use the garage for malformed or external destinations. */ }
  return self.location.origin + '/';
}

self.addEventListener('push', event => {
  event.waitUntil((async () => {
    let data = {};
    try { data = event.data?.json() || {}; } catch { /* Generic notification below. */ }
    if (!data || typeof data !== 'object') data = {};
    try {
      const response = await fetch('/notifications/config/', {credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(8000)});
      if (!response.ok || response.redirected) return;
      const account = await response.json();
      if (data.recipient && account.userId !== data.recipient) return;
    } catch {
      // If the website is temporarily unreachable, keep lock-screen content generic.
      data = {title:'AutoLedger update',body:'There is a new update in your garage.',url:'/'};
    }
    await self.registration.showNotification(
      typeof data.title === 'string' ? data.title.slice(0,100) : 'AutoLedger update', {
        body:typeof data.body === 'string' ? data.body.slice(0,180) : 'There is a new update in your garage.',
        icon:'/static/icons/icon-glass-192.png?v=pearl-11',
        tag:typeof data.tag === 'string' ? data.tag : undefined,
        data:{url:notificationURL(data.url)},
      });
  })());
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = notificationURL(event.notification.data?.url);
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for (const client of windows) {
      if (new URL(client.url).origin === self.location.origin && 'navigate' in client) {
        const navigated = await client.navigate(url);
        if (navigated) return navigated.focus();
      }
    }
    return self.clients.openWindow(url);
  })());
});

self.addEventListener('pushsubscriptionchange', event => {
  event.waitUntil((async () => {
    try {
      const response = await fetch('/notifications/config/',{credentials:'same-origin',cache:'no-store'});
      if (!response.ok || response.redirected) return;
      const config = await response.json();
      if (!config.available) return;
      const encoded = config.publicKey.replace(/-/g,'+').replace(/_/g,'/');
      const key = Uint8Array.from(atob(encoded+'='.repeat((4-encoded.length%4)%4)),char=>char.charCodeAt(0));
      const sub = event.newSubscription || await self.registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:key});
      await fetch('/notifications/subscribe/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':config.csrfToken},body:JSON.stringify(sub.toJSON())});
    } catch { /* Repaired on the next authenticated app visit. */ }
  })());
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith('autoledger-') && key !== CACHE).map(key => caches.delete(key)),
  )).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || !url.pathname.startsWith('/static/')) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE).then(cache => cache.put(event.request, copy)));
    }
    return response;
  }).catch(() => caches.match(event.request).then(response => response || Response.error())));
});
