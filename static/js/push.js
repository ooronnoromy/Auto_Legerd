/* Permission is requested only after the user presses Enable notifications. */
(() => {
  const configUrl = document.body.dataset.pushConfig;
  if (!configUrl) return;
  const controls = document.querySelector('[data-push-controls]');
  const enable = controls?.querySelector('[data-enable-push]');
  const disable = controls?.querySelector('[data-disable-push]');
  const status = controls?.querySelector('[data-push-status]');
  let config, registration, current;

  function describe(text, subscribed = false, canEnable = true) {
    if (status) status.textContent = text;
    if (enable) { enable.hidden = subscribed; enable.disabled = !canEnable; }
    if (disable) { disable.hidden = !subscribed; disable.disabled = false; }
  }
  function keyBytes(value) {
    const decoded = atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4));
    return Uint8Array.from(decoded, char => char.charCodeAt(0));
  }
  async function post(url, payload) {
    const response = await fetch(url, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': config.csrfToken},
      body: JSON.stringify(payload), signal: AbortSignal.timeout(10000),
    });
    if (!response.ok || response.redirected) throw new Error('Could not update notification settings. Please try again.');
  }
  async function attach(subscription) {
    await post(document.body.dataset.pushSubscribe, subscription.toJSON());
    current = subscription;
  }
  const ready = (async () => {
    try {
      const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
      if (isIOS && !window.matchMedia('(display-mode: standalone)').matches && !navigator.standalone) {
        describe('On iPhone or iPad, use Share → Add to Home Screen, open AutoLedger from its icon, then enable notifications.', false, false); return;
      }
      if (!window.isSecureContext || !('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
        describe('This browser does not support mobile push. Open the installed app in a supported browser.', false, false); return;
      }
      const response = await fetch(configUrl, {credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
      if (!response.ok || response.redirected) throw new Error('Sign in again to manage notifications.');
      config = await response.json();
      if (!config.available) {
        describe('Mobile notifications are not available yet. Contact your administrator.', false, false); return;
      }
      // Register explicitly too, so the first visit to Profile is supported.
      await navigator.serviceWorker.register('/sw.js');
      registration = await navigator.serviceWorker.ready;
      current = await registration.pushManager.getSubscription();
      if (Notification.permission === 'granted' && current) {
        await attach(current);
        describe('Notifications are enabled on this device for new cars and expenses.', true);
      } else if (Notification.permission === 'denied') {
        describe('Notifications are blocked. Allow them in this app’s browser or phone settings, then reopen AutoLedger.', false, false);
      } else {
        describe('Get a mobile notification when a car or expense is added to your garage.');
      }
    } catch (error) {
      describe(error.message || 'Notification settings could not load. Reload this page to try again.', false, false);
    }
  })();

  enable?.addEventListener('click', async () => {
    if (!registration || !config?.available) return;
    enable.disabled = true;
    try {
      // Keep this call directly within the click gesture for iPhone support.
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        describe(permission === 'denied' ? 'Notifications are blocked. Allow them in your phone or browser settings.' : 'Notifications were not enabled. You can try again whenever you are ready.', false, permission !== 'denied');
        return;
      }
      const subscription = await registration.pushManager.getSubscription() || await registration.pushManager.subscribe({
        userVisibleOnly: true, applicationServerKey: keyBytes(config.publicKey),
      });
      await attach(subscription);
      describe('Notifications are enabled on this device for new cars and expenses.', true);
    } catch (error) {
      describe(error.message || 'Could not enable notifications. Please try again.');
    }
  });
  disable?.addEventListener('click', async () => {
    disable.disabled = true;
    try {
      if (current) {
        await post(document.body.dataset.pushUnsubscribe, {endpoint: current.endpoint});
        await current.unsubscribe(); current = null;
      }
      describe('Notifications are off on this device.');
    } catch (error) {
      describe(error.message || 'Could not disable notifications. Try again.', true);
    }
  });

  // Detach shared phones before signing out; the server also removes the binding.
  document.querySelectorAll('form[action="/logout/"], form[action="/admin/logout/"]').forEach(form => {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      try {
        await Promise.race([ready, new Promise(resolve => setTimeout(resolve, 1500))]);
        if (current) {
          const subscription = current;
          await subscription.unsubscribe();
          current = null;
        }
      } catch {
        // Server-side logout still removes this session's device binding.
      } finally {
        form.submit();
      }
    });
  });
})();
