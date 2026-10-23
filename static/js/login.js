(() => {
  const form = document.querySelector('[data-login-form]');
  if (!form) return;
  let ready = false;
  let pending = false;
  form.addEventListener('submit', async event => {
    if (ready) { ready = false; return; }
    event.preventDefault();
    if (pending) return;
    pending = true;
    const status = document.getElementById('login-status');
    try {
      // Another tab can rotate the CSRF cookie after this form was opened.
      const response = await fetch(form.dataset.csrfUrl, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('Could not refresh session');
      const data = await response.json();
      if (!data.csrfToken) throw new Error('Missing session token');
      form.querySelector('[name="csrfmiddlewaretoken"]').value = data.csrfToken;
      ready = true;
      form.requestSubmit();
    } catch {
      status.hidden = false;
      status.textContent = 'Could not refresh your session. Check your connection and try signing in again.';
    } finally { pending = false; }
  });
})();
