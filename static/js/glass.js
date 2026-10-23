/* Native details keeps search usable even before JavaScript loads. */
(() => {
  const search = document.getElementById('glass-search');
  if (!search) return;
  const trigger = search.querySelector('summary');
  const input = search.querySelector('input[type="search"]');
  function closeSearch(restoreFocus = false) {
    search.open = false;
    if (restoreFocus) trigger.focus();
  }
  search.addEventListener('toggle', () => {
    if (search.open) input.focus();
  });
  search.querySelector('[data-close-search]').addEventListener('click', () => closeSearch(true));
  document.addEventListener('click', event => {
    if (search.open && !search.contains(event.target)) closeSearch();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && search.open) {
      event.preventDefault(); closeSearch(true); return;
    }
    const editing = event.target?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable="false"])');
    if (event.key === '/' && !editing && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault(); search.open = true; input.focus();
    }
  });
  // Keep the selected destination visible in the horizontally scrolling phone dock.
  const nav = document.querySelector('.glass-nav');
  const active = nav?.querySelector('[aria-current="page"]');
  if (nav && active) nav.scrollLeft = Math.max(0, active.offsetLeft - nav.clientWidth / 2 + active.offsetWidth / 2);
})();
