(() => {
  let prompt = null;
  const buttons = document.querySelectorAll('[data-install-app]');
  const dialog = document.getElementById('install-help');
  const message = document.getElementById('install-instructions');
  const standalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const update = () => buttons.forEach(button => { button.hidden = standalone(); });
  update();
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    prompt = event;
    update();
  });
  window.addEventListener('appinstalled', () => {
    prompt = null;
    buttons.forEach(button => { button.hidden = true; });
    dialog?.close();
  });
  buttons.forEach(button => button.addEventListener('click', async () => {
    if (prompt) {
      const current = prompt;
      prompt = null;
      try {
        await current.prompt();
        await current.userChoice;
        return;
      } catch { /* The browser menu remains available if the prompt expires. */ }
    }
    if (!dialog || !message) return;
    const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    message.textContent = !window.isSecureContext
      ? 'Open AutoLedger using its HTTPS website address to install it on your phone. Installation is unavailable on a local HTTP address.'
      : ios
        ? 'Open this website in Safari. Tap Share, then Add to Home Screen, and tap Add. AutoLedger will appear as an app on your phone.'
        : 'Open your browser menu and choose Install app or Add to Home screen. On Android, use Chrome or Edge. If you opened this link inside another app, open it in your phone browser first.';
    dialog.showModal();
  }));
  document.querySelector('[data-close-install]')?.addEventListener('click', () => dialog.close());
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
  }
})();
